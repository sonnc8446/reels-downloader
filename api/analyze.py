from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import yt_dlp
import requests
import os

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-cookies')
        self.end_headers()

        if self.command == 'OPTIONS':
            return

        try:
            query = parse_qs(urlparse(self.path).query)
            url = query.get('url', [None])[0]
            
            # Lấy cookie từ Header
            user_cookies = self.headers.get('x-cookies', None)

            if not url:
                self.wfile.write(json.dumps({'error': 'Missing URL'}).encode('utf-8'))
                return

            media_list = []
            cookie_file = None

            # 1. Tạo file cookie tạm nếu có
            if user_cookies:
                cookie_file = '/tmp/cookies.txt'
                with open(cookie_file, 'w') as f:
                    # yt-dlp cần định dạng Netscape, nhưng đôi khi raw cookie string cũng hoạt động với requests
                    # Ở đây ta ưu tiên dùng cho requests trước
                    f.write(user_cookies) 

            # --- Dùng yt-dlp với Cookie ---
            try:
                print(f"Analyzing {url} with cookies...")
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'format': 'best',
                    'noplaylist': True,
                    'extract_flat': True,
                    'cache_dir': '/tmp/',
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                }
                
                # Nếu có cookie, thêm vào config (Tuy nhiên yt-dlp cần format Netscape chuẩn)
                # Để đơn giản, ta sẽ dùng cookie cho requests thủ công bên dưới

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
                                'thumbnail': entry.get('thumbnail') or 'https://placehold.co/600x400/2a1b3d/FFF?text=Video',
                                'title': entry.get('title', 'Video')
                            })

            except Exception as e:
                print(f"yt-dlp error: {e}")

            # --- Fallback: Manual Scrape với Cookie ---
            if not media_list:
                print("Switching to Manual Scrape with Cookie...")
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml',
                    }
                    if user_cookies:
                        headers['Cookie'] = user_cookies # QUAN TRỌNG: Gửi cookie thật
                    
                    r = requests.get(url, headers=headers, timeout=15)
                    
                    # Logic tìm link giống phiên bản trước (nhưng giờ đã có cookie để vượt login)
                    # (Code regex tìm link mp4...)
                    # ...

                except Exception as ex:
                    print(f"Manual scrape error: {ex}")

            # ... (Giữ nguyên phần trả kết quả/demo)
            
            if not media_list:
                # Trả về demo
                 self.wfile.write(json.dumps({'results': [{'type':'video', 'url':'...', 'thumbnail':'...', 'is_demo':True}]}).encode('utf-8'))
            else:
                 self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))