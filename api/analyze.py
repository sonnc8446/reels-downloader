from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import json
import re
import yt_dlp
import requests
import os

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. CORS Headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-cookies') # Cho phép header cookies
        self.end_headers()

        if self.command == 'OPTIONS':
            return

        try:
            # 2. Lấy URL và Cookies
            query = parse_qs(urlparse(self.path).query)
            url = query.get('url', [None])[0]
            
            # Lấy cookies từ Header (được gửi từ Frontend)
            user_cookies = self.headers.get('x-cookies', None)

            if not url:
                self.wfile.write(json.dumps({'error': 'Thiếu tham số URL'}).encode('utf-8'))
                return

            media_list = []
            
            # Tạo file cookie tạm thời cho yt-dlp (nếu có cookie)
            cookie_file_path = None
            if user_cookies:
                # yt-dlp cần file Netscape format, nhưng đôi khi header cookie thô cũng giúp requests hoạt động
                # Ở đây ta ưu tiên dùng requests với cookie thô cho Manual Scrape trước
                print("Đã nhận được User Cookies từ request.")

            # --- CHIẾN THUẬT 1: Requests + Regex "Quét Cạn" (Có Cookie) ---
            print(f"Analyzing URL with Deep Scan: {url}")
            
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Upgrade-Insecure-Requests': '1'
                }

                # Thêm Cookie vào header nếu có
                if user_cookies:
                    headers['Cookie'] = user_cookies
                
                session = requests.Session()
                # allow_redirects=True quan trọng để follow link rút gọn
                r = session.get(url, headers=headers, timeout=20, allow_redirects=True)
                html = r.text

                # A. Tìm trong thẻ Meta (Cách chuẩn nhất)
                meta_videos = re.findall(r'<meta\s+property="og:video(?::secure_url)?"\s+content="([^"]+)"', html)
                
                # B. Tìm trong JSON (playable_url)
                json_videos = re.findall(r'"playable_url(?:_quality_hd)?":"([^"]+)"', html)
                
                # C. Tìm "Mù" (Blind Scan)
                blind_videos = re.findall(r'(https:\\/\\/[^"]+\.mp4[^"]*)', html)

                # Gộp tất cả kết quả
                all_candidates = meta_videos + json_videos + blind_videos
                
                for raw_link in all_candidates:
                    # Giải mã link
                    clean_link = raw_link.replace(r'\/', '/')
                    clean_link = clean_link.encode().decode('unicode_escape')
                    clean_link = clean_link.replace('&amp;', '&')
                    
                    if clean_link.startswith('http') and '.mp4' in clean_link:
                        if not any(m['url'] == clean_link for m in media_list):
                            media_list.append({
                                'type': 'video',
                                'url': clean_link,
                                'thumbnail': 'https://placehold.co/600x800/1877f2/FFF?text=Facebook+Reel',
                                'title': 'Facebook Video'
                            })
                            if "quality_hd" in raw_link or len(media_list) >= 1: 
                                break
                            
            except Exception as e:
                print(f"Deep Scan Error: {e}")

            # --- CHIẾN THUẬT 2: yt-dlp (Dự phòng) ---
            if not media_list:
                try:
                    print(f"Deep Scan failed, trying yt-dlp...")
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'format': 'best',
                        'noplaylist': True,
                        'extract_flat': True, 
                        'cache_dir': '/tmp/',
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    }
                    
                    # Lưu ý: Truyền cookie dạng string cho yt-dlp phức tạp hơn (cần cookiejar),
                    # nên ở đây ta vẫn dùng yt-dlp mode ẩn danh làm fallback.
                    # Nếu muốn yt-dlp dùng cookie, cần ghi user_cookies ra file /tmp/cookies.txt và thêm 'cookiefile' vào ydl_opts.

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        entries = [info] if 'entries' not in info else info['entries']
                        
                        for entry in entries:
                            if not entry: continue
                            video_url = entry.get('url') or entry.get('original_url')
                            if video_url and 'http' in video_url:
                                media_list.append({
                                    'type': 'video',
                                    'url': video_url,
                                    'thumbnail': entry.get('thumbnail') or 'https://placehold.co/600x800/e1306c/FFF?text=Reel',
                                    'title': entry.get('title', 'Video')
                                })
                except Exception as e:
                    print(f"yt-dlp error: {e}")

            # --- CHIẾN THUẬT 3: Fallback Cuối (Demo Data) ---
            if not media_list:
                print("All failed. Returning Demo Data.")
                # Nếu có cookie mà vẫn lỗi, có thể do cookie hết hạn hoặc FB chặn quá gắt
                status_text = "Demo (Protected)" if not user_cookies else "Demo (Cookie Invalid/Blocked)"
                media_list = [{
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': f'https://placehold.co/600x800/550000/FFF?text={status_text}',
                    'title': 'Demo Video (Content Protected)',
                    'is_demo': True
                }]

            self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            error_msg = str(e)
            print(f"Critical Server Error: {error_msg}")
            self.wfile.write(json.dumps({'error': f'Lỗi hệ thống: {error_msg}'}).encode('utf-8'))