from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import json
import re
import yt_dlp
import requests
import os
from duckduckgo_search import DDGS

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-cookies')
        self.end_headers()

        if self.command == 'OPTIONS':
            return

        try:
            query = parse_qs(urlparse(self.path).query)
            url = query.get('url', [None])[0]
            user_cookies = self.headers.get('x-cookies', None)

            if not url:
                self.wfile.write(json.dumps({'error': 'Thiếu tham số URL'}).encode('utf-8'))
                return

            media_list = []
            print(f"[API] Analyzing: {url}")

            # --- CHIẾN THUẬT 1: Requests + Regex Deep Scan (Ưu tiên số 1) ---
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
                    'Accept': 'text/html,application/xhtml+xml',
                    'Sec-Fetch-Site': 'none'
                }
                if user_cookies: headers['Cookie'] = user_cookies
                
                # Timeout ngắn để chuyển nhanh sang cách khác nếu lag
                r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
                html = r.text
                
                # Tìm link mp4 trong source code
                mp4_matches = re.findall(r'"playable_url(?:_quality_hd)?":"([^"]+)"', html)
                if not mp4_matches:
                    mp4_matches = re.findall(r'(https:\\/\\/[^"]+\.mp4[^"]*)', html)

                for raw_link in mp4_matches:
                    clean_link = raw_link.replace(r'\/', '/').encode().decode('unicode_escape').replace('&amp;', '&')
                    if clean_link.startswith('http') and '.mp4' in clean_link:
                        if not any(m['url'] == clean_link for m in media_list):
                            media_list.append({
                                'type': 'video',
                                'url': clean_link,
                                'thumbnail': 'https://placehold.co/600x800/1877f2/FFF?text=Direct+Video',
                                'title': 'Facebook Reel'
                            })
                            if len(media_list) >= 5: break # Lấy tối đa 5 video từ source
            except Exception as e:
                print(f"[Deep Scan] Error: {e}")

            # --- CHIẾN THUẬT 2: Search Engine Discovery (Tương tự Google Search API) ---
            # Nếu không tìm thấy video trực tiếp, ta sẽ hỏi Search Engine
            if len(media_list) == 0:
                print("[API] Switching to Search Engine Discovery...")
                try:
                    # Tạo từ khóa tìm kiếm: site:facebook.com/page_name/reels
                    # Ví dụ: site:facebook.com/powerofpositivity/reels
                    
                    # 1. Trích xuất tên page từ URL
                    page_name_match = re.search(r'facebook\.com\/([^\/]+)', url)
                    page_name = page_name_match.group(1) if page_name_match else "facebook reels"
                    
                    search_query = f"site:facebook.com/{page_name}/reel"
                    print(f"[Search] Query: {search_query}")

                    # 2. Sử dụng DuckDuckGo (Thay thế Google để tránh bị chặn IP server)
                    # DDG trả về kết quả tương tự Google nhưng open hơn
                    with DDGS() as ddgs:
                        # Tìm kiếm 10 kết quả
                        results = list(ddgs.text(search_query, max_results=10))
                        
                        for res in results:
                            href = res.get('href', '')
                            # Lọc các link là Reel cụ thể
                            if '/reel/' in href:
                                # Dùng yt-dlp để lấy link stream của từng Reel tìm được
                                # (Làm nhanh, chỉ lấy thông tin flat)
                                media_list.append({
                                    'type': 'video',
                                    'url': href, # Link bài viết Reel (Frontend sẽ gọi download để resolve sau)
                                    'thumbnail': 'https://placehold.co/600x800/e65100/FFF?text=Search+Result',
                                    'title': res.get('title', 'Reel from Search'),
                                    'is_search_result': True # Đánh dấu để Frontend biết đây là link bài viết, cần resolve khi download
                                })

                except Exception as search_err:
                    print(f"[Search] Error: {search_err}")

            # --- CHIẾN THUẬT 3: yt-dlp (Dự phòng cuối) ---
            if not media_list:
                try:
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': True,
                        'noplaylist': True,
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        if 'entries' in info:
                            for entry in info['entries']:
                                media_list.append({
                                    'type': 'video',
                                    'url': entry.get('url'),
                                    'thumbnail': 'https://placehold.co/600x800/333/FFF?text=YTDLP',
                                    'title': entry.get('title', 'Video')
                                })
                        elif info.get('url'):
                             media_list.append({
                                'type': 'video',
                                'url': info.get('url'),
                                'thumbnail': 'https://placehold.co/600x800/333/FFF?text=YTDLP',
                                'title': info.get('title', 'Video')
                            })
                except:
                    pass

            # --- Fallback Demo ---
            if not media_list:
                print("[API] All failed -> Returning Demo.")
                media_list = [{
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': 'https://placehold.co/600x800/550000/FFF?text=Demo+(No+Results)',
                    'title': 'Demo Video (No results found)',
                    'is_demo': True
                }]

            self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            error_msg = str(e)
            print(f"Critical Error: {error_msg}")
            self.wfile.write(json.dumps({'error': f'Lỗi hệ thống: {error_msg}'}).encode('utf-8'))