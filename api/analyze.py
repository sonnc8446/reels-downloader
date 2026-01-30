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
            
            # --- CHIẾN THUẬT 1: Facebook HTML Regex (Mạnh nhất cho FB Reels) ---
            # Phương pháp này giả lập trình duyệt mobile để lấy HTML nhẹ hơn và parse chuỗi JSON
            if 'facebook.com' in url:
                print("Detected Facebook URL, trying HTML Regex...")
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                        'Sec-Fetch-Site': 'none',
                        'Upgrade-Insecure-Requests': '1'
                    }
                    
                    # Thử request mobile trước
                    session = requests.Session()
                    r = session.get(url, headers=headers, timeout=15, allow_redirects=True)
                    html = r.text

                    # Tìm link HD
                    hd_urls = re.findall(r'"playable_url_quality_hd":"([^"]+)"', html)
                    # Tìm link SD
                    sd_urls = re.findall(r'"playable_url":"([^"]+)"', html)
                    
                    found_urls = hd_urls + sd_urls
                    
                    for raw_link in found_urls:
                        # Link trong JSON bị escape dấu /, cần replace
                        clean_link = raw_link.replace('\\/', '/')
                        if clean_link.startswith('http') and not any(m['url'] == clean_link for m in media_list):
                            media_list.append({
                                'type': 'video',
                                'url': clean_link,
                                'thumbnail': 'https://placehold.co/600x800/1877f2/FFF?text=Facebook+Video',
                                'title': 'Facebook Reel'
                            })
                            # Chỉ lấy 1 link tốt nhất để tránh trùng lặp
                            break 
                            
                except Exception as e:
                    print(f"Facebook Regex Error: {e}")

            # --- CHIẾN THUẬT 2: yt-dlp (Dự phòng cho Instagram/TikTok/FB) ---
            if not media_list:
                try:
                    print(f"Trying yt-dlp fallback...")
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'format': 'best',
                        'noplaylist': True,
                        'extract_flat': True, 
                        'cache_dir': '/tmp/',
                        # Dùng User Agent Desktop cho yt-dlp
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