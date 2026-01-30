from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import yt_dlp
import requests
import re

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

            media_list = []

            # --- CÁCH 1: Thử dùng yt-dlp (Mạnh nhất nhưng dễ bị chặn IP Server) ---
            try:
                # Cấu hình yt-dlp tối ưu cho Serverless (Vercel)
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'format': 'best',
                    'noplaylist': True,
                    'extract_flat': True, # Chỉ lấy metadata
                    'cache_dir': '/tmp/', # Chỉ cho phép ghi vào /tmp trên Vercel
                    # Giả lập User-Agent của trình duyệt thật
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                }
                
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
                                'title': entry.get('title', 'Video Content')
                            })
            except Exception as e:
                print(f"YTDLP Error (Expected on Vercel): {str(e)}")
                # Không crash, tiếp tục thử cách 2

            # --- CÁCH 2: Fallback Scrape thủ công (Dùng requests + Regex) ---
            # Nếu yt-dlp thất bại, ta tự request HTML và tìm thẻ meta og:video
            if not media_list:
                print("Switching to Manual Scrape...")
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                        'Accept-Language': 'en-US,en;q=0.5'
                    }
                    # Timeout ngắn để tránh treo serverless function
                    r = requests.get(url, headers=headers, timeout=10)
                    html = r.text

                    # Tìm thẻ og:video (Facebook/Instagram thường dùng)
                    og_video = re.search(r'<meta\s+(?:property|name)="og:video"\s+content="([^"]+)"', html)
                    if og_video:
                        clean_url = og_video.group(1).replace('&amp;', '&')
                        media_list.append({
                            'type': 'video',
                            'url': clean_url,
                            'thumbnail': 'https://placehold.co/600x400/1a237e/FFF?text=Video+Found',
                            'title': 'Video (Manual Scrape)'
                        })
                    
                    # Tìm thẻ og:image (Nếu không có video thì lấy ảnh)
                    if not media_list:
                        og_image = re.search(r'<meta\s+(?:property|name)="og:image"\s+content="([^"]+)"', html)
                        if og_image:
                            clean_url = og_image.group(1).replace('&amp;', '&')
                            media_list.append({
                                'type': 'image',
                                'url': clean_url,
                                'thumbnail': clean_url,
                                'title': 'Image (Manual Scrape)'
                            })

                except Exception as ex:
                    print(f"Manual scrape error: {str(ex)}")

            # 4. Trả kết quả
            if not media_list:
                # Vẫn giữ Demo fallback để App không bị lỗi trắng trang khi demo
                print("All methods failed. Returning Demo Data.")
                response = {
                    'results': [{
                        'type': 'video',
                        'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                        'thumbnail': 'https://placehold.co/600x400/550000/FFF?text=Demo+(Server+Blocked)',
                        'title': 'Demo Video (Server Blocked)',
                        'is_demo': True
                    }]
                }
            else:
                response = {'results': media_list}
            
            self.wfile.write(json.dumps(response).encode('utf-8'))

        except Exception as e:
            print(f"Critical Error: {str(e)}")
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))