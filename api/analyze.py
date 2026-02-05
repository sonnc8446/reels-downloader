from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
import requests

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-cookies')
        self.end_headers()

        if self.command == 'OPTIONS': return

        try:
            query = parse_qs(urlparse(self.path).query)
            url = query.get('url', [None])[0]
            user_cookies = self.headers.get('x-cookies', None)

            if not url:
                self.wfile.write(json.dumps({'error': 'Thiếu tham số URL'}).encode('utf-8'))
                return

            print(f"[Analyze] Processing: {url}")
            media_list = []

            # Headers giả lập trình duyệt để lấy được HTML đầy đủ nhất
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Sec-Fetch-Site': 'none',
                'Upgrade-Insecure-Requests': '1'
            }
            if user_cookies:
                headers['Cookie'] = user_cookies

            # Request lấy mã nguồn trang
            try:
                r = requests.get(url, headers=headers, timeout=20, allow_redirects=True)
                html = r.text
                
                # --- LOGIC TÌM LINK /VIDEOS/ ---
                # Pattern: https://www.facebook.com/page_name/videos/video_id/
                # Tìm tất cả các chuỗi bắt đầu bằng http, chứa facebook.com và /videos/
                # Regex này bắt cả link đầy đủ trong thẻ a (href) hoặc trong các biến JS
                
                # 1. Tìm các link dạng /videos/ số (thường là link bài viết chuẩn)
                video_matches = re.findall(r'https?:\/\/(?:www\.|m\.|web\.)?facebook\.com\/[^\/]+\/videos\/\d+\/?', html)
                
                # 2. Tìm các link dạng /reel/ (đôi khi FB redirect qua lại)
                reel_matches = re.findall(r'https?:\/\/(?:www\.|m\.|web\.)?facebook\.com\/reel\/\d+\/?', html)

                # Gộp và lọc trùng
                all_links = list(set(video_matches + reel_matches))
                
                print(f"[Analyze] Found {len(all_links)} links matching pattern.")

                for i, link in enumerate(all_links):
                    # Clean link
                    clean_link = link.replace('\\/', '/')
                    
                    media_list.append({
                        'type': 'video',
                        'url': clean_link, # Đây là link bài viết, download.py sẽ lo phần resolve ra mp4
                        'thumbnail': f'https://placehold.co/600x800/1877f2/FFF?text=FB+Video+{i+1}', # Thumbnail tạm
                        'title': f'Facebook Video {i+1}',
                        'is_search_result': True # Đánh dấu để biết đây là link bài viết cần xử lý tiếp
                    })

                # Nếu không tìm thấy bằng regex đơn giản, thử tìm trong JSON blob phức tạp của FB
                if not media_list:
                     # Tìm pattern ID video và dựng lại link
                     ids = re.findall(r'"video_id":"(\d+)"', html)
                     unique_ids = list(set(ids))
                     for vid in unique_ids:
                         media_list.append({
                            'type': 'video',
                            'url': f'https://www.facebook.com/watch/?v={vid}',
                            'thumbnail': f'https://placehold.co/600x800/1877f2/FFF?text=Video+ID+{vid}',
                            'title': f'Video ID {vid}',
                            'is_search_result': True
                         })

            except Exception as e:
                print(f"[Analyze] Error: {e}")

            # Fallback Demo nếu vẫn trắng tay
            if not media_list:
                media_list = [{
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': None,
                    'title': 'Demo (Không tìm thấy link videos)',
                    'is_demo': True
                }]
            
            # Trả về tối đa 20 kết quả
            self.wfile.write(json.dumps({'results': media_list[:20]}).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))