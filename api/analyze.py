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
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-cookies, x-google-key, x-google-cx')
        self.end_headers()

        if self.command == 'OPTIONS': return

        try:
            query = parse_qs(urlparse(self.path).query)
            url = query.get('url', [None])[0]
            
            # Lấy Google Key từ Header
            google_key = self.headers.get('x-google-key', None)
            google_cx = self.headers.get('x-google-cx', None)

            if not url:
                self.wfile.write(json.dumps({'error': 'Thiếu URL'}).encode('utf-8'))
                return

            print(f"[Analyze] Processing: {url}")
            media_list = []
            seen_urls = set()

            # 1. Trích xuất tên Page ID từ URL
            page_id = ""
            match = re.search(r'facebook\.com\/([^\/\?&]+)', url)
            if match:
                raw_id = match.group(1)
                if raw_id not in ['reel', 'watch', 'videos', 'groups']: 
                    page_id = raw_id
            
            # 2. Sử dụng Google API để tìm danh sách Reels
            if page_id and google_key and google_cx:
                print(f"[Strategy] Google API Searching for: {page_id}")
                
                # Tìm kiếm chính xác các video reel của page này
                search_queries = [
                    f'site:facebook.com/{page_id}/reel',
                    f'site:facebook.com/{page_id}/videos'
                ]

                try:
                    api_url = "https://www.googleapis.com/customsearch/v1"
                    
                    for q in search_queries:
                        if len(media_list) >= 20: break

                        params = {
                            'key': google_key,
                            'cx': google_cx,
                            'q': q,
                            'num': 10 # Google limit
                        }
                        
                        r = requests.get(api_url, params=params)
                        data = r.json()
                        
                        if 'items' in data:
                            for item in data['items']:
                                href = item.get('link')
                                title = item.get('title')
                                
                                # Lấy ảnh thumbnail từ Google
                                thumb = None
                                if 'pagemap' in item and 'cse_image' in item['pagemap']:
                                    thumb = item['pagemap']['cse_image'][0]['src']
                                
                                # Chỉ lấy link Facebook
                                if href and 'facebook.com' in href:
                                    clean_href = href.split('?')[0]
                                    if clean_href not in seen_urls:
                                        seen_urls.add(clean_href)
                                        media_list.append({
                                            'id': f"gg-{len(media_list)}",
                                            'type': 'video',
                                            'url': clean_href, # Link bài viết (RapidAPI sẽ xử lý sau)
                                            'title': title,
                                            'thumbnail': thumb, 
                                            'downloadUrl': clean_href, # Giữ link gốc để gửi cho download.py
                                            'is_search_result': True
                                        })
                except Exception as e:
                    print(f"[Google Error] {e}")

            # Fallback nếu không tìm thấy hoặc không có Key
            if not media_list:
                msg = "Không tìm thấy video."
                if not google_key: msg += " Vui lòng nhập Google API Key & CX trong cấu hình."
                
                media_list = [{
                    'id': 'demo-1',
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': None,
                    'title': f'{msg} (Demo Video)',
                    'is_demo': True
                }]

            self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))