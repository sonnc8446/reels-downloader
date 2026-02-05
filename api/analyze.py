from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
import yt_dlp
import requests
import os
import tempfile

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
            query = parse_qs(urlparse(self.path).query)
            url = query.get('url', [None])[0]
            user_cookies = self.headers.get('x-cookies', None)

            if not url:
                self.wfile.write(json.dumps({'error': 'Thiếu URL'}).encode('utf-8'))
                return

            media_list = []
            
            # 2. Xử lý Cookies (Ghi ra file tạm cho yt-dlp)
            cookie_file_path = None
            if user_cookies:
                try:
                    # Tạo file cookie tạm thời trong /tmp (Nơi duy nhất Vercel cho phép ghi)
                    fd, cookie_file_path = tempfile.mkstemp(suffix='.txt', text=True)
                    with os.fdopen(fd, 'w') as f:
                        f.write(user_cookies)
                except Exception as e:
                    print(f"Cookie write error: {e}")

            # 3. Chạy yt-dlp
            try:
                print(f"Analyzing {url}...")
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'format': 'best',
                    'noplaylist': True,
                    'extract_flat': True,
                    'cache_dir': '/tmp/', # Bắt buộc trên Vercel
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                }
                
                # Nếu có cookie file, nạp vào yt-dlp
                if cookie_file_path:
                    ydl_opts['cookiefile'] = cookie_file_path

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    entries = [info] if 'entries' not in info else info['entries']
                    
                    for entry in entries:
                        if not entry: continue
                        video_url = entry.get('url') or entry.get('original_url')
                        if video_url:
                            media_list.append({
                                'type': 'video',
                                'url': video_url,
                                'thumbnail': entry.get('thumbnail'),
                                'title': entry.get('title', 'Video Content'),
                                'is_demo': False # Video thật
                            })

            except Exception as e:
                print(f"yt-dlp error: {e}")

            # 4. Clean up cookie file
            if cookie_file_path and os.path.exists(cookie_file_path):
                os.remove(cookie_file_path)

            # 5. Trả kết quả
            if not media_list:
                print("All failed. Returning Demo Data.")
                media_list = [{
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': None, # Để Frontend tự sinh gradient
                    'title': 'Demo Video (Login Required / Server Blocked)',
                    'is_demo': True
                }]

            self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))