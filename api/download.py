from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
import yt_dlp

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        target_url = query.get('url', [None])[0]
        filename = query.get('filename', ['video.mp4'])[0]

        if not target_url:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Missing URL')
            return

        direct_url = target_url

        try:
            # KIỂM TRA: Nếu URL là trang web (facebook.com/...) chứ không phải file (.mp4)
            # Chúng ta dùng yt-dlp để lấy link thực (direct link) ngay lúc download
            if 'facebook.com' in target_url and '.mp4' not in target_url:
                print(f"[Download] Resolving direct link for: {target_url}")
                ydl_opts = {
                    'format': 'best',
                    'quiet': True,
                    'noplaylist': True,
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...'
                }
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(target_url, download=False)
                    direct_url = info.get('url', target_url)
                    print(f"[Download] Resolved to: {direct_url[:50]}...")

            # STREAMING
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.facebook.com/'
            }

            with requests.get(direct_url, headers=headers, stream=True, timeout=30) as r:
                r.raise_for_status()

                self.send_response(200)
                self.send_header('Content-Type', r.headers.get('Content-Type', 'application/octet-stream'))
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Access-Control-Allow-Origin', '*')
                
                if 'Content-Length' in r.headers:
                    self.send_header('Content-Length', r.headers['Content-Length'])
                
                self.end_headers()

                for chunk in r.iter_content(chunk_size=8192):
                    self.wfile.write(chunk)

        except Exception as e:
            print(f"[Download] Error: {e}")
            try:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(f"Download Error: {str(e)}".encode())
            except:
                pass