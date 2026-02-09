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
            # Headers giả lập trình duyệt để CDN cho phép tải
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.facebook.com/',
                'Origin': 'https://www.facebook.com'
            }

            # stream=True cực kỳ quan trọng trên Vercel để tránh tràn RAM
            with requests.get(file_url, headers=headers, stream=True, timeout=60) as r:
                if r.status_code >= 400:
                    # Nếu link gốc lỗi (ví dụ hết hạn), báo lỗi về client
                    self.send_response(r.status_code)
                    self.end_headers()
                    self.wfile.write(f"Source URL Error: {r.status_code}".encode())
                    return

                self.send_response(200)
                
                # Forward Content-Type chuẩn (thường là video/mp4)
                content_type = r.headers.get('Content-Type', 'video/mp4')
                self.send_header('Content-Type', content_type)
                
                # Set tên file tải về
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Access-Control-Allow-Origin', '*')
                
                # Forward Content-Length nếu có (để hiện thanh tiến trình)
                if 'Content-Length' in r.headers:
                    self.send_header('Content-Length', r.headers['Content-Length'])
                
                self.end_headers()

                # Stream dữ liệu
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        self.wfile.write(chunk)

        except Exception as e:
            print(f"Download Proxy Error: {e}")
            try:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
            except:
                pass