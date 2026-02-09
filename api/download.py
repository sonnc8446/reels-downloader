from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests
import json

# --- CẤU HÌNH RAPID API ---
RAPID_API_KEY = "5c807f67a3msha8f5fdfcc6241fbp1aaa13jsn26e9650a4325"
RAPID_API_HOST = "facebook-videos-reels-downloader.p.rapidapi.com"

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        fb_url = query.get('url', [None])[0] # Đây là link bài viết FB
        filename = query.get('filename', ['video.mp4'])[0]

        if not fb_url:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Missing URL')
            return

        # 1. RESOLVE LINK QUA RAPID API
        direct_download_url = fb_url # Mặc định nếu là link mp4 rồi
        
        # Nếu chưa phải mp4 (tức là link fb), gọi Rapid để lấy link mp4
        if 'facebook.com' in fb_url and '.mp4' not in fb_url:
            print(f"[Download] Resolving via RapidAPI: {fb_url}")
            try:
                api_url = f"https://{RAPID_API_HOST}/get-video-info"
                querystring = {"url": fb_url}
                headers = {
                    "x-rapidapi-key": RAPID_API_KEY,
                    "x-rapidapi-host": RAPID_API_HOST
                }
                
                api_res = requests.get(api_url, headers=headers, params=querystring)
                data = api_res.json()
                
                # Tìm link HD hoặc SD
                found_link = None
                if 'links' in data and isinstance(data['links'], dict):
                     found_link = data['links'].get('hd') or data['links'].get('sd')
                elif 'download' in data and isinstance(data['download'], list):
                     for item in data['download']:
                         if item.get('url'): 
                             found_link = item.get('url')
                             break
                
                if found_link:
                    direct_download_url = found_link
                    print("[Download] Link resolved successfully.")
                else:
                    print("[Download] RapidAPI did not return a valid video link.")
                    # Nếu lỗi, thử tiếp tục với url gốc (biết đâu may mắn)
            
            except Exception as e:
                print(f"[Download] RapidAPI Error: {e}")

        # 2. STREAM FILE VỀ CLIENT
        try:
            # Fake headers để tải từ CDN FB
            stream_headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Referer': 'https://www.facebook.com/'
            }

            with requests.get(direct_download_url, headers=stream_headers, stream=True, timeout=60) as r:
                if r.status_code >= 400:
                    self.send_response(r.status_code)
                    self.end_headers()
                    self.wfile.write(f"Source Error: {r.status_code}".encode())
                    return

                self.send_response(200)
                self.send_header('Content-Type', r.headers.get('Content-Type', 'video/mp4'))
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Access-Control-Allow-Origin', '*')
                
                if 'Content-Length' in r.headers:
                    self.send_header('Content-Length', r.headers['Content-Length'])
                
                self.end_headers()

                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: self.wfile.write(chunk)

        except Exception as e:
            print(f"Stream Error: {e}")
            try:
                self.send_response(500)
                self.end_headers()
            except: pass