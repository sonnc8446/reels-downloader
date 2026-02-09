from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import requests

# CẤU HÌNH RAPID API (Bạn cần thay Key của mình vào đây hoặc dùng biến môi trường)
RAPID_API_KEY = "YOUR_RAPID_API_KEY_HERE" 
RAPID_API_HOST = "facebook-reel-and-video-downloader.p.rapidapi.com" # Ví dụ host

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        try:
            query = parse_qs(urlparse(self.path).query)
            url = query.get('url', [None])[0]

            if not url:
                self.wfile.write(json.dumps({'error': 'Missing URL'}).encode('utf-8'))
                return

            # Gọi sang RapidAPI (Ví dụ endpoint, tùy API bạn chọn mà chỉnh sửa)
            api_url = "https://facebook-reel-and-video-downloader.p.rapidapi.com/app/main.php"
            querystring = {"url": url}
            
            headers = {
                "X-RapidAPI-Key": RAPID_API_KEY,
                "X-RapidAPI-Host": RAPID_API_HOST
            }

            # Gửi request
            response = requests.get(api_url, headers=headers, params=querystring)
            data = response.json()

            media_list = []
            
            # Xử lý dữ liệu trả về từ RapidAPI (Cần điều chỉnh theo cấu trúc JSON thực tế của API đó)
            # Ví dụ giả định:
            if 'links' in data:
                # Lấy link HD nếu có
                hd_link = data['links'].get('hd') or data['links'].get('sd')
                if hd_link:
                    media_list.append({
                        'type': 'video',
                        'url': hd_link,
                        'thumbnail': data.get('thumbnail', ''),
                        'title': data.get('title', 'Facebook Reel')
                    })

            if not media_list:
                self.wfile.write(json.dumps({'results': [], 'error': 'API không tìm thấy video'}).encode('utf-8'))
            else:
                self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))