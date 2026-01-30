from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Parse Query
        query = parse_qs(urlparse(self.path).query)
        file_url = query.get('url', [None])[0]
        filename = query.get('filename', ['video.mp4'])[0]

        # 2. Validate Input
        if not file_url:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Missing URL')
            return

        try:
            # 3. Enhanced Headers (Đồng bộ với analyze.py)
            # CDN của Facebook/Insta rất nhạy cảm với User-Agent và Referer
            domain_referer = 'https://www.instagram.com/' if 'instagram' in file_url else 'https://www.facebook.com/'
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': '*/*',
                'Accept-Encoding': 'identity;q=1, *;q=0',
                'Accept-Language': 'en-US,en;q=0.9',
                'Sec-Fetch-Site': 'cross-site',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Dest': 'video',
                'Referer': domain_referer,
                'Range': 'bytes=0-' # Yêu cầu tải từ đầu file
            }

            # 4. Stream Request
            # stream=True: Bắt buộc để không tải toàn bộ file vào RAM server (Vercel giới hạn RAM)
            # timeout=20: Tránh treo server quá lâu nếu CDN không phản hồi
            with requests.get(file_url, headers=headers, stream=True, timeout=20) as r:
                r.raise_for_status()

                # 5. Forward Headers về Client
                self.send_response(200)
                
                # Content-Type
                content_type = r.headers.get('Content-Type', 'application/octet-stream')
                self.send_header('Content-Type', content_type)
                
                # Force Download
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                
                # CORS (Cho phép Frontend gọi)
                self.send_header('Access-Control-Allow-Origin', '*')
                
                # Content-Length (Quan trọng để hiển thị thanh tiến trình download trên trình duyệt)
                if 'Content-Length' in r.headers:
                    self.send_header('Content-Length', r.headers['Content-Length'])
                
                self.end_headers()

                # 6. Pipe Data (Chuyển tiếp dữ liệu)
                # Chunk size 8192 (8KB) là kích thước chuẩn tối ưu cho network I/O
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        self.wfile.write(chunk)

        except Exception as e:
            print(f"Download Proxy Error: {e}")
            # Chỉ gửi lỗi về client nếu headers chưa được gửi đi
            try:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Lỗi tải xuống: {str(e)}".encode())
            except:
                pass