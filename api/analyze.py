from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import requests

# --- CẤU HÌNH RAPID API ---
# BẠN PHẢI DÁN KEY CỦA BẠN VÀO DÒNG DƯỚI
RAPID_API_KEY = "5c807f67a3msha8f5fdfcc6241fbp1aaa13jsn26e9650a4325"
RAPID_API_HOST = "facebook-videos-reels-downloader.p.rapidapi.com"

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()

        if self.command == 'OPTIONS': return

        try:
            query = parse_qs(urlparse(self.path).query)
            target_url = query.get('url', [None])[0]

            if not target_url:
                self.wfile.write(json.dumps({'error': 'Thiếu URL'}).encode('utf-8'))
                return

            print(f"[API] Calling RapidAPI for: {target_url}")

            # Endpoint chuẩn của API trong ảnh bạn gửi
            url = f"https://{RAPID_API_HOST}/get"
            
            querystring = {"url": target_url}

            headers = {
                "x-rapidapi-key": RAPID_API_KEY,
                "x-rapidapi-host": RAPID_API_HOST
            }

            # Gọi API
            response = requests.get(url, headers=headers, params=querystring)
            data = response.json()
            
            # Log để debug trên Vercel
            print(f"[RapidAPI Response] {json.dumps(data)}")

            media_list = []

            # Xử lý kết quả trả về từ RapidAPI (Mapping dữ liệu)
            # Cấu trúc trả về thường có dạng: { success: true, links: { ... }, title: ... }
            
            if isinstance(data, dict):
                # 1. Lấy Title
                title = data.get('title', 'Facebook Video')
                
                # 2. Lấy Thumbnail
                thumbnail = data.get('picture') or data.get('thumbnail')
                
                # 3. Lấy Link Video (Ưu tiên HD)
                video_url = None
                if 'links' in data:
                    # Một số API trả về links['hd'] hoặc links[0]['url']
                    if isinstance(data['links'], list) and len(data['links']) > 0:
                         video_url = data['links'][0].get('url') # Lấy link đầu tiên
                    elif isinstance(data['links'], dict):
                         video_url = data['links'].get('hd') or data['links'].get('sd') or data['links'].get('Download Low Quality')
                
                # Nếu cấu trúc khác (ví dụ mảng 'download')
                if not video_url and 'download' in data:
                     for item in data['download']:
                         if item.get('type') == 'video':
                             video_url = item.get('url')
                             break

                # Nếu tìm thấy link
                if video_url:
                    media_list.append({
                        'id': 'rapid-1',
                        'type': 'video',
                        'url': video_url, # Link trực tiếp
                        'thumbnail': thumbnail,
                        'title': title,
                        'selected': True
                    })

            # Nếu không tìm thấy (Do Key sai hoặc API lỗi) -> Trả về Demo
            if not media_list:
                print("[API] Không tìm thấy video. Trả về Demo.")
                status = "Lỗi Key RapidAPI" if "message" in data and "Forbidden" in data["message"] else "Không tìm thấy video"
                
                media_list = [{
                    'id': 'demo-1',
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': None,
                    'title': f'Demo: {status} (Vui lòng kiểm tra Key)',
                    'is_demo': True
                }]

            self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            print(f"[Error] {str(e)}")
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))