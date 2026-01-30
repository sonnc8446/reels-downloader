from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import json
import re
import yt_dlp
import requests

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
            # 2. Lấy URL
            query = parse_qs(urlparse(self.path).query)
            url = query.get('url', [None])[0]

            if not url:
                self.wfile.write(json.dumps({'error': 'Thiếu tham số URL'}).encode('utf-8'))
                return

            media_list = []
            
            # --- CHIẾN THUẬT 1: Requests + Regex "Quét Cạn" (Deep Scan) ---
            # Facebook Reels thường ẩn link trong HTML hỗn độn, ta sẽ quét mọi khả năng
            print(f"Analyzing URL with Deep Scan: {url}")
            
            try:
                # Giả lập iPhone để nhận HTML mobile (dễ parse hơn)
                headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Upgrade-Insecure-Requests': '1'
                }
                
                session = requests.Session()
                r = session.get(url, headers=headers, timeout=20, allow_redirects=True)
                html = r.text

                # A. Tìm trong thẻ Meta (Cách chuẩn nhất)
                meta_videos = re.findall(r'<meta\s+property="og:video(?::secure_url)?"\s+content="([^"]+)"', html)
                
                # B. Tìm trong JSON (playable_url) - Link thường bị escape (\/)
                json_videos = re.findall(r'"playable_url(?:_quality_hd)?":"([^"]+)"', html)
                
                # C. Tìm "Mù" (Blind Scan) - Tìm chuỗi http...mp4
                # Regex này tìm chuỗi bắt đầu http, kết thúc mp4, có thể chứa tham số token
                blind_videos = re.findall(r'(https:\\/\\/[^"]+\.mp4[^"]*)', html)

                # Gộp tất cả kết quả
                all_candidates = meta_videos + json_videos + blind_videos
                
                for raw_link in all_candidates:
                    # Giải mã link (Facebook mã hóa rất nhiều lớp)
                    # 1. Unescape JSON slash: \/ -> /
                    clean_link = raw_link.replace(r'\/', '/')
                    # 2. Decode Unicode: \u0026 -> &
                    clean_link = clean_link.encode().decode('unicode_escape')
                    # 3. Decode HTML entities: &amp; -> &
                    clean_link = clean_link.replace('&amp;', '&')
                    
                    # Kiểm tra tính hợp lệ
                    if clean_link.startswith('http') and '.mp4' in clean_link:
                        # Lọc trùng lặp
                        if not any(m['url'] == clean_link for m in media_list):
                            media_list.append({
                                'type': 'video',
                                'url': clean_link,
                                'thumbnail': 'https://placehold.co/600x800/1877f2/FFF?text=Facebook+Reel',
                                'title': 'Facebook Video'
                            })
                            # Nếu tìm thấy link HD (thường dài hơn), ưu tiên lấy và dừng
                            if "quality_hd" in raw_link or len(media_list) >= 1: 
                                break
                            
            except Exception as e:
                print(f"Deep Scan Error: {e}")

            # --- CHIẾN THUẬT 2: yt-dlp (Dự phòng mạnh) ---
            # Nếu cách 1 thất bại, dùng yt-dlp (thư viện chuyên dụng)
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
                        # Dùng User Agent Desktop cho yt-dlp vì nó giả lập browser tốt
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    }
                    
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
            # Chỉ dùng khi tất cả đều thất bại để App không bị crash 500
            if not media_list:
                print("All failed. Returning Demo Data.")
                media_list = [{
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': 'https://placehold.co/600x800/550000/FFF?text=Demo+(Protected)',
                    'title': 'Demo Video (Content Protected)',
                    'is_demo': True
                }]

            self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            error_msg = str(e)
            print(f"Critical Server Error: {error_msg}")
            self.wfile.write(json.dumps({'error': f'Lỗi hệ thống: {error_msg}'}).encode('utf-8'))