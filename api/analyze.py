from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
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
            
            # --- CÁCH 1: Dùng yt-dlp (Mạnh nhất - Tương đương đoạn cuối script của bạn) ---
            try:
                print(f"Trying yt-dlp for: {url}")
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    # Giả lập Browser như script Selenium
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'referer': 'https://www.facebook.com/',
                    'extract_flat': True, # Chỉ lấy thông tin cơ bản trước cho nhanh (với playlist)
                    'ignoreerrors': True, 
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # extract_flat=True giúp lấy danh sách nhanh hơn mà không cần tải video
                    info = ydl.extract_info(url, download=False)
                    
                    # Xử lý kết quả: Single Video hoặc Playlist
                    if 'entries' in info:
                        entries = info['entries'] # Là danh sách (Profile/Reels tab)
                    else:
                        entries = [info] # Là 1 video lẻ
                    
                    for entry in entries:
                        if not entry: continue
                        
                        # Với extract_flat, url có thể là id hoặc url
                        video_url = entry.get('url')
                        # Nếu là FB reels, url có thể chưa đầy đủ
                        if video_url and 'facebook.com' not in video_url and 'http' not in video_url:
                             video_url = f"https://www.facebook.com{url if '/reel/' in url else ''}"
                        
                        if video_url:
                            media_list.append({
                                'type': 'video',
                                'url': video_url if 'http' in video_url else entry.get('original_url', url),
                                'thumbnail': entry.get('thumbnail') or 'https://placehold.co/600x800/2a1b3d/FFF?text=Reel',
                                'title': entry.get('title', 'Facebook Reel')
                            })
                            
                    # Nếu yt-dlp tìm thấy entries (dạng playlist) nhưng chưa resolve được link direct
                    # Ta sẽ trả về link gốc để Frontend gọi lại API này cho từng video (Lazy loading nếu cần)
                    # Tuy nhiên ở đây ta giả định yt-dlp lấy được.

            except Exception as e:
                print(f"yt-dlp error: {e}")

            # --- CÁCH 2: Fallback Scrape thủ công (Mô phỏng logic Selenium tìm thẻ 'a') ---
            # Nếu yt-dlp thất bại (do FB chặn), ta dùng requests để lấy HTML và regex tìm link
            if not media_list:
                print("Switching to Manual Scrape (Simulation of Selenium logic)...")
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                        'Sec-Fetch-Site': 'none',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-User': '?1',
                        'Sec-Fetch-Dest': 'document',
                    }
                    r = requests.get(url, headers=headers, timeout=15)
                    html = r.text
                    
                    # LOGIC 1: Tìm link /reel/ giống code Selenium của bạn
                    # href.split('/?s=')[0]
                    # Regex tìm các chuỗi khớp với cấu trúc link Reels
                    reel_matches = re.findall(r'href="([^"]*\/reel\/[^"]+)"', html)
                    
                    unique_reels = set()
                    for href in reel_matches:
                        # Làm sạch link như code Python: href.split('/?s=')[0]
                        clean_link = href.split('/?s=')[0].replace('&amp;', '&')
                        if clean_link.startswith('/'):
                            clean_link = f"https://www.facebook.com{clean_link}"
                        
                        if clean_link not in unique_reels:
                            unique_reels.add(clean_link)
                            media_list.append({
                                'type': 'video',
                                'url': clean_link,
                                'thumbnail': 'https://placehold.co/600x800/1a237e/FFF?text=Reel+Found',
                                'title': 'Facebook Reel (Manual)'
                            })

                    # LOGIC 2: Nếu không phải trang danh sách mà là trang video đơn
                    if not media_list:
                        og_video = re.search(r'<meta property="og:video" content="([^"]+)"', html)
                        if og_video:
                            clean_url = og_video.group(1).replace('&amp;', '&')
                            media_list.append({
                                'type': 'video',
                                'url': clean_url, # Link mp4 trực tiếp
                                'thumbnail': 'https://placehold.co/600x800/1a237e/FFF?text=Video+Direct',
                                'title': 'Direct Video'
                            })

                except Exception as ex:
                    print(f"Manual scrape error: {ex}")

            # --- CÁCH 3: Fallback Cuối cùng (Demo Data) ---
            if not media_list:
                print("All failed. Returning Demo Data.")
                media_list = [{
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': 'https://placehold.co/600x800/550000/FFF?text=Demo+Fallback',
                    'title': 'Demo Video (Login Required)',
                    'is_demo': True
                }]

            # Giới hạn kết quả để không quá tải Frontend
            self.wfile.write(json.dumps({'results': media_list[:20]}).encode('utf-8'))

        except Exception as e:
            error_msg = str(e)
            print(f"Critical Server Error: {error_msg}")
            self.wfile.write(json.dumps({'error': f'Lỗi hệ thống: {error_msg}'}).encode('utf-8'))