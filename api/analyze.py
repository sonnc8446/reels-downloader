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
            
            # Lấy Google Key từ Header hoặc dùng Key cứng đã cung cấp
            google_key = self.headers.get('x-google-key') or "AIzaSyDfNE8xsUaAUK4RQ-L7Pvafi8txySNUDJ4"
            google_cx = self.headers.get('x-google-cx') or "d35588bebf5864544"

            if not url:
                self.wfile.write(json.dumps({'error': 'Thiếu URL'}).encode('utf-8'))
                return

            print(f"[Analyze] Processing: {url}")
            media_list = []
            seen_urls = set()
            google_error_message = None

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
                
                # Mở rộng từ khóa tìm kiếm: Cả chính xác (site:) và tự nhiên
                search_queries = [
                    f'site:facebook.com/{page_id}/reel',   # Tìm chính xác đường dẫn reel
                    f'{page_id} facebook reels',            # Tìm theo tên page (Rộng hơn)
                    f'site:facebook.com/{page_id}/videos'  # Tìm trong mục videos
                ]

                try:
                    api_url = "https://www.googleapis.com/customsearch/v1"
                    
                    for q in search_queries:
                        if len(media_list) >= 20: break

                        print(f"[Google] Querying: {q}")
                        params = {
                            'key': google_key,
                            'cx': google_cx,
                            'q': q,
                            'num': 10 
                        }
                        
                        r = requests.get(api_url, params=params)
                        data = r.json()
                        
                        # Kiểm tra nếu Google trả về lỗi (VD: Hết quota, Sai key...)
                        if 'error' in data:
                            error_details = data['error'].get('message', 'Unknown Error')
                            print(f"[Google API Error] {error_details}")
                            google_error_message = f"Google Error: {error_details}"
                            continue 

                        if 'items' in data:
                            for item in data['items']:
                                href = item.get('link')
                                title = item.get('title')
                                
                                # Lấy ảnh thumbnail từ Google
                                thumb = None
                                if 'pagemap' in item:
                                    pagemap = item['pagemap']
                                    if 'cse_image' in pagemap:
                                        thumb = pagemap['cse_image'][0]['src']
                                    elif 'metatags' in pagemap:
                                        for tags in pagemap['metatags']:
                                            if 'og:image' in tags:
                                                thumb = tags['og:image']
                                                break
                                
                                # Chỉ lấy link Facebook Reels/Videos
                                if href and 'facebook.com' in href:
                                    # Lọc sơ bộ các link không phải video
                                    if '/reel/' in href or '/videos/' in href or '/watch/' in href:
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
                        else:
                            print(f"[Google] No items found for query: {q}")

                except Exception as e:
                    print(f"[Google Error] {e}")
                    google_error_message = str(e)

            # Fallback nếu không tìm thấy hoặc không có Key
            if not media_list:
                msg = "Không tìm thấy video."
                
                if google_error_message:
                    msg = google_error_message # Hiển thị lỗi Google cụ thể
                elif not google_key: 
                    msg += " Vui lòng nhập Google API Key & CX."
                else:
                    msg += " Google trả về 0 kết quả (Thử kiểm tra lại cấu hình Search Engine 'Toàn bộ web')."
                
                media_list = [{
                    'id': 'demo-1',
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': None,
                    'title': f'{msg}',
                    'is_demo': True
                }]

            self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))