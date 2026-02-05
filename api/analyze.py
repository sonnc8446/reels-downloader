from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
from duckduckgo_search import DDGS

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Setup CORS
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-cookies')
        self.end_headers()

        if self.command == 'OPTIONS': return

        try:
            # 2. Parse URL
            query = parse_qs(urlparse(self.path).query)
            target_url = query.get('url', [None])[0]

            if not target_url:
                self.wfile.write(json.dumps({'error': 'Thiếu tham số URL'}).encode('utf-8'))
                return

            print(f"[Analyze] Processing: {target_url}")
            media_list = []
            seen_urls = set()

            # 3. Trích xuất tên Page (Username) từ URL
            # VD: https://www.facebook.com/powerofpositivity/reels -> powerofpositivity
            username = ""
            match = re.search(r'facebook\.com\/([^\/\?&]+)', target_url)
            if match:
                username = match.group(1)
                # Loại bỏ các từ khóa hệ thống nếu lỡ bắt nhầm
                if username in ['reel', 'watch', 'videos', 'groups', 'people', 'story']:
                    username = ""
            
            # Nếu không lấy được username, thử lấy ID
            if not username:
                match_id = re.search(r'id=(\d+)', target_url)
                if match_id: username = match_id.group(1)

            print(f"[Analyze] Detected Username/ID: {username}")

            if username:
                # 4. Sử dụng DuckDuckGo để tìm kiếm Link Video đã được Index
                # Chiến thuật này không truy cập Facebook trực tiếp nên không bị chặn IP
                search_queries = [
                    f'site:facebook.com/{username}/videos',
                    f'site:facebook.com/{username}/reel',
                    f'"{username}" facebook reels'
                ]

                # Dùng DDGS để tìm kiếm
                try:
                    with DDGS() as ddgs:
                        for q in search_queries:
                            if len(media_list) >= 50: break # Giới hạn 50 video
                            
                            print(f"[Search] Querying: {q}")
                            # max_results=30 cho mỗi query
                            results = list(ddgs.text(q, max_results=30))
                            
                            for res in results:
                                href = res.get('href', '')
                                title = res.get('title', 'Facebook Video')
                                body = res.get('body', '')

                                # Chỉ lấy các link là Video hoặc Reel
                                if 'facebook.com' in href and ('/videos/' in href or '/reel/' in href):
                                    # Làm sạch link (bỏ tham số tracking)
                                    clean_href = href.split('?')[0]
                                    
                                    if clean_href not in seen_urls:
                                        seen_urls.add(clean_href)
                                        
                                        # Tạo thumbnail giả lập dựa trên index (Vì search engine không trả thumbnail ảnh)
                                        # Frontend sẽ tự hiển thị Gradient đẹp
                                        media_list.append({
                                            'id': f"fb-{len(media_list)}",
                                            'type': 'video',
                                            'url': clean_href, # Link bài viết (download.py sẽ xử lý sau)
                                            'title': title,
                                            'description': body,
                                            'thumbnail': None, 
                                            'is_search_result': True
                                        })
                except Exception as e:
                    print(f"[Search Error] {str(e)}")
            
            # 5. Nếu vẫn không có kết quả (Page quá mới hoặc không index), trả về Demo để không crash app
            if not media_list:
                print("[Analyze] No results found. Returning Demo.")
                media_list = [{
                    'id': 'demo-1',
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'title': 'Không tìm thấy kết quả công khai (Demo Video)',
                    'thumbnail': None,
                    'is_demo': True
                }]

            # 6. Trả về JSON
            self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            print(f"Critical Error: {str(e)}")
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))