from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import requests

# --- CẤU HÌNH RAPID API (Thông tin bạn cung cấp) ---
RAPID_API_KEY = "5c807f67a3msha8f5fdfcc6241fbp1aaa13jsn26e9650a4325"
RAPID_API_HOST = "facebook-videos-reels-downloader.p.rapidapi.com"

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. CORS Headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-cookies')
        self.end_headers()

        if self.command == 'OPTIONS': return

        try:
            # 2. Lấy URL từ Frontend
            query = parse_qs(urlparse(self.path).query)
            target_url = query.get('url', [None])[0]

            if not target_url:
                self.wfile.write(json.dumps({'error': 'Thiếu tham số URL'}).encode('utf-8'))
                return

            print(f"[API] Calling RapidAPI for: {target_url}")

            # 3. Cấu hình Request sang RapidAPI (Theo đúng snippet bạn gửi)
            url = f"https://{RAPID_API_HOST}/get-video-info"
            
            querystring = {"url": target_url}

            headers = {
                "x-rapidapi-key": RAPID_API_KEY,
                "x-rapidapi-host": RAPID_API_HOST
            }

            # 4. Gửi yêu cầu
            # timeout=30 để tránh Vercel cắt kết nối sớm nếu API xử lý lâu
            response = requests.get(url, headers=headers, params=querystring, timeout=30)
            
            # Kiểm tra lỗi HTTP từ RapidAPI
            if response.status_code != 200:
                print(f"[RapidAPI Error] Status: {response.status_code}, Body: {response.text}")
                # Fallback Demo nếu API lỗi
                self.return_fallback(f"RapidAPI trả về lỗi {response.status_code}")
                return

            data = response.json()
            print(f"[RapidAPI Data] {str(data)[:200]}...") # Log một phần dữ liệu để debug

            media_list = []

            # 5. Xử lý dữ liệu trả về (Mapping)
            # Lưu ý: API này thường trả về thông tin cho 1 video cụ thể.
            # Nếu input là link profile/reels, API có thể trả về lỗi hoặc list tùy logic của họ.
            
            # Logic mapping dựa trên cấu trúc phổ biến của API này
            if isinstance(data, dict):
                # Trường hợp thành công
                title = data.get('title') or data.get('description') or "Facebook Video"
                thumbnail = data.get('thumbnail') or data.get('picture')
                
                # Tìm link download tốt nhất
                video_url = None
                
                # Check các trường hợp JSON thường gặp
                if 'links' in data:
                    links = data['links']
                    if isinstance(links, dict):
                        video_url = links.get('hd') or links.get('sd') or links.get('Download High Quality')
                    elif isinstance(links, list) and len(links) > 0:
                        video_url = links[0].get('url') # Link đầu tiên thường là tốt nhất
                elif 'download' in data and isinstance(data['download'], list):
                     for item in data['download']:
                         if item.get('type') == 'video': video_url = item.get('url'); break
                elif 'url' in data: # Trả về trực tiếp
                    video_url = data['url']

                if video_url:
                    media_list.append({
                        'id': f"rap-{len(media_list)}",
                        'type': 'video',
                        'url': video_url, # Link trực tiếp (Direct URL)
                        'thumbnail': thumbnail,
                        'title': title,
                        'selected': True,
                        'is_demo': False
                    })
            
            # 6. Trả kết quả
            if not media_list:
                # Nếu API trả về rỗng hoặc lỗi logic -> Trả về Demo
                print("[API] Không tìm thấy video hợp lệ từ phản hồi API.")
                self.return_fallback("API không tìm thấy video (Kiểm tra lại link hoặc key)")
            else:
                self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            print(f"[Critical Error] {str(e)}")
            self.return_fallback(f"Lỗi hệ thống: {str(e)}")

    def return_fallback(self, reason):
        media_list = [{
            'id': 'demo-1',
            'type': 'video',
            'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
            'thumbnail': None,
            'title': f'Demo Video ({reason})',
            'is_demo': True,
            'selected': True
        }]
        self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))