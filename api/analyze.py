from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
import yt_dlp
import requests
import tempfile
import os

# Thử import DDGS
try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
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

            print(f"[Analyze] Processing: {url}")
            media_list = []
            seen_urls = set()

            # --- KIỂM TRA LOẠI URL ---
            # Nếu là link danh sách (Reels tab / Profile), ưu tiên dùng Search Engine
            is_list_url = '/reels' in url or '/videos' in url or 'profile.php' in url
            
            # --- CHIẾN THUẬT 1: SEARCH ENGINE (DuckDuckGo) ---
            # Đây là cách hiệu quả nhất để lấy danh sách video mà không bị FB chặn
            if is_list_url and DDGS:
                print("[Strategy 1] DuckDuckGo Search Discovery...")
                try:
                    # Trích xuất tên Page
                    page_name = ""
                    match = re.search(r'facebook\.com\/([^\/\?&]+)', url)
                    if match:
                        page_name = match.group(1)
                        if page_name in ['reel', 'watch', 'videos', 'groups', 'people']: page_name = ""
                    
                    if page_name:
                        # Tạo các truy vấn tìm kiếm thông minh
                        queries = [
                            f'site:facebook.com/{page_name}/reel',
                            f'site:facebook.com/{page_name}/videos',
                            f'{page_name} facebook reels video'
                        ]

                        with DDGS() as ddgs:
                            for q in queries:
                                if len(media_list) >= 50: break
                                print(f"[Search] Querying: {q}")
                                # Tìm kiếm text trả về kết quả link
                                results = list(ddgs.text(q, max_results=30))
                                
                                for res in results:
                                    href = res.get('href', '')
                                    title = res.get('title', 'Facebook Video')
                                    
                                    # Lọc lấy link video
                                    if 'facebook.com' in href and ('/reel/' in href or '/videos/' in href):
                                        clean_href = href.split('?')[0]
                                        if clean_href not in seen_urls:
                                            seen_urls.add(clean_href)
                                            media_list.append({
                                                'id': f"ddg-{len(media_list)}",
                                                'type': 'video',
                                                'url': clean_href,
                                                'thumbnail': None, # Frontend tự sinh gradient
                                                'title': title,
                                                'is_search_result': True
                                            })
                except Exception as e:
                    print(f"[Search Error] {str(e)}")

            # --- CHIẾN THUẬT 2: YT-DLP VỚI COOKIE (Cho video lẻ hoặc nếu Search thất bại) ---
            if len(media_list) == 0:
                print("[Strategy 2] Trying yt-dlp with Cookie...")
                cookie_file_path = None
                
                try:
                    # Tạo file cookie tạm thời
                    if user_cookies:
                        fd, cookie_file_path = tempfile.mkstemp(suffix='.txt', text=True)
                        # yt-dlp cần format Netscape, nhưng ta thử ghi header cookie xem có ăn may không
                        # Hoặc tốt nhất là người dùng paste nội dung file Netscape vào
                        with os.fdopen(fd, 'w') as f:
                            f.write(user_cookies)
                    
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': 'in_playlist', # Quét nhanh playlist
                        'noplaylist': False,
                        'ignoreerrors': True,
                        'cache_dir': '/tmp/',
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    }
                    
                    if cookie_file_path:
                        ydl_opts['cookiefile'] = cookie_file_path

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        
                        entries = []
                        if 'entries' in info: entries = info['entries']
                        elif 'url' in info: entries = [info]

                        for entry in entries:
                            if not entry: continue
                            video_url = entry.get('url')
                            if video_url:
                                if video_url not in seen_urls:
                                    seen_urls.add(video_url)
                                    media_list.append({
                                        'id': f"yt-{len(media_list)}",
                                        'type': 'video',
                                        'url': video_url,
                                        'thumbnail': entry.get('thumbnail'),
                                        'title': entry.get('title', 'Facebook Video'),
                                        'is_search_result': True
                                    })
                            if len(media_list) >= 50: break

                except Exception as e:
                    print(f"[yt-dlp Error] {str(e)}")
                finally:
                    # Dọn dẹp file cookie
                    if cookie_file_path and os.path.exists(cookie_file_path):
                        os.remove(cookie_file_path)

            # --- FALLBACK DEMO (Chỉ hiện khi thất bại hoàn toàn) ---
            if not media_list:
                print("[API] All methods failed -> Demo.")
                status_msg = "Không tìm thấy video. Vui lòng kiểm tra Cookie." if user_cookies else "Không tìm thấy (Cần nhập Cookie Facebook)"
                media_list = [{
                    'id': 'demo-1',
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': None,
                    'title': status_msg,
                    'is_demo': True
                }]

            self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))