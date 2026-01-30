from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import yt_dlp

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. CORS Headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.end_headers()

        if self.command == 'OPTIONS':
            return

        try:
            query = parse_qs(urlparse(self.path).query)
            url = query.get('url', [None])[0]

            if not url:
                self.wfile.write(json.dumps({'error': 'Thiếu URL'}).encode('utf-8'))
                return

            # 2. Cấu hình yt-dlp tối ưu cho Serverless (Vercel)
            # QUAN TRỌNG: cache_dir phải trỏ về /tmp hoặc tắt đi, nếu không sẽ lỗi 500
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': 'best',
                'noplaylist': True,
                'extract_flat': True, # Chỉ lấy metadata, không tải video
                'cache_dir': '/tmp/', # Chỉ cho phép ghi vào /tmp trên Vercel
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            }

            media_list = []

            # 3. Chạy yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    info = ydl.extract_info(url, download=False)
                    
                    entries = [info] if 'entries' not in info else info['entries']
                    
                    for entry in entries:
                        if not entry: continue
                        
                        video_url = entry.get('url')
                        # Fallback nếu yt-dlp trả về null
                        if not video_url: 
                            video_url = entry.get('original_url')

                        if video_url:
                            media_list.append({
                                'type': 'video',
                                'url': video_url,
                                'thumbnail': entry.get('thumbnail') or 'https://placehold.co/600x400/2a1b3d/FFF?text=Video',
                                'title': entry.get('title', 'Video Content')
                            })
                except Exception as e:
                    print(f"YTDLP Error: {str(e)}")
                    # Không crash, để code chạy tiếp xuống phần fallback (nếu có)

            # 4. Trả kết quả
            if not media_list:
                # Trả về video demo thay vì lỗi 500 để người dùng không hoang mang
                response = {
                    'results': [{
                        'type': 'video',
                        'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                        'thumbnail': 'https://placehold.co/600x400/550000/FFF?text=Demo+(Backend+Fail)',
                        'title': 'Demo Video (Backend Failed)',
                        'is_demo': True
                    }]
                }
            else:
                response = {'results': media_list}
            
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            print(f"Critical Error: {str(e)}")
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))