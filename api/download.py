from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        file_url = query.get('url', [None])[0]
        filename = query.get('filename', ['video.mp4'])[0]

        if not file_url:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Missing URL')
            return

        try:
            # Headers giả lập để tránh bị chặn bởi CDN Facebook
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.facebook.com/',
                'Accept': '*/*',
                'Connection': 'keep-alive'
            }

            # stream=True để tải file lớn mà không tràn RAM
            with requests.get(file_url, headers=headers, stream=True, timeout=60) as r:
                r.raise_for_status()

                self.send_response(200)
                
                # Lấy Content-Type từ nguồn hoặc mặc định mp4
                content_type = r.headers.get('Content-Type', 'video/mp4')
                self.send_header('Content-Type', content_type)
                
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Access-Control-Allow-Origin', '*')
                
                if 'Content-Length' in r.headers:
                    self.send_header('Content-Length', r.headers['Content-Length'])
                
                self.end_headers()

                # Gửi dữ liệu theo từng chunk 8KB
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        self.wfile.write(chunk)

        except Exception as e:
            # Chỉ log lỗi, không gửi response mới nếu headers đã gửi
            print(f"Download Error: {e}")