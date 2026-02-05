from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import json
import re
import requests
import yt_dlp

# Xử lý lỗi nếu chưa cài đặt thư viện duckduckgo_search
try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None
    print("Warning: duckduckgo_search not installed.")

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
                self.wfile.write(json.dumps({'error': 'Thiếu tham số URL'}).encode('utf-8'))
                return

            print(f"[Analyze] Processing: {url}")
            media_list = []

            # --- CHIẾN THUẬT 1: Requests + Regex Deep Scan (Cào trực tiếp) ---
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Sec-Fetch-Site': 'none',
                    'Upgrade-Insecure-Requests': '1'
                }
                if user_cookies: headers['Cookie'] = user_cookies

                r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
                html = r.text
                
                # Regex tìm link video
                video_matches = re.findall(r'https?:\/\/(?:www\.|m\.|web\.)?facebook\.com\/[^\/]+\/videos\/\d+\/?', html)
                reel_matches = re.findall(r'https?:\/\/(?:www\.|m\.|web\.)?facebook\.com\/reel\/\d+\/?', html)
                
                all_links = list(set(video_matches + reel_matches))
                for link in all_links:
                    clean_link = link.replace('\\/', '/')
                    if not any(m['url'] == clean_link for m in media_list):
                        media_list.append({
                            'type': 'video',
                            'url': clean_link,
                            'thumbnail': 'https://placehold.co/600x800/1877f2/FFF?text=Direct+Hit',
                            'title': 'Recent Reel (Direct)',
                            'is_search_result': True
                        })
            except Exception as e:
                print(f"[Deep Scan] Error: {e}")

            # --- CHIẾN THUẬT 2: Search Engine Discovery (DuckDuckGo - Nâng cấp) ---
            if len(media_list) < 50 and DDGS:
                print("[API] Expanding results with Search Engine...")
                try:
                    # Lấy ID/Tên Page
                    match = re.search(r'facebook\.com\/([^\/]+)', url)
                    if match:
                        page_id = match.group(1)
                        # Loại bỏ các từ khóa hệ thống nếu lỡ bắt nhầm
                        if page_id in ['reel', 'watch', 'videos', 'groups', 'profile', 'people']: 
                            page_id = '' 
                        
                        if page_id:
                            search_queries = [
                                f'site:facebook.com/{page_id}/reel',
                                f'"{page_id}" facebook reels', # Tìm rộng hơn
                                f'site:facebook.com/{page_id}/videos'
                            ]
                            
                            with DDGS() as ddgs:
                                for q in search_queries:
                                    if len(media_list) >= 100: break
                                    print(f"[Search] Querying: {q}")
                                    try:
                                        # max_results=50 để lấy nhiều hơn
                                        results = list(ddgs.text(q, max_results=50))
                                        
                                        for res in results:
                                            href = res.get('href', '')
                                            title = res.get('title', 'Facebook Video')
                                            
                                            if 'facebook.com' in href and ('/reel/' in href or '/videos/' in href):
                                                clean_href = href.split('?')[0]
                                                if not any(m['url'] == clean_href for m in media_list):
                                                    media_list.append({
                                                        'type': 'video',
                                                        'url': clean_href,
                                                        'thumbnail': 'https://placehold.co/600x800/e65100/FFF?text=Web+Search',
                                                        'title': title,
                                                        'is_search_result': True
                                                    })
                                    except Exception as q_err:
                                        print(f"Query '{q}' failed: {q_err}")
                except Exception as se:
                    print(f"[Search] Error: {se}")

            # --- CHIẾN THUẬT 3: yt-dlp (Dự phòng cuối cùng - Đã tối ưu) ---
            # Nếu danh sách vẫn ít, dùng yt-dlp quét chính URL đó (yt-dlp xử lý playlist/profile rất tốt)
            if len(media_list) < 5:
                try:
                    print("[API] Trying yt-dlp fallback for playlist...")
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': 'in_playlist', # Chỉ lấy metadata danh sách, không tải sâu
                        'noplaylist': False, # Cho phép xử lý playlist
                        'ignoreerrors': True, # Bỏ qua video lỗi, tiếp tục lấy video khác
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        
                        entries = []
                        if 'entries' in info:
                            entries = info['entries']
                        elif 'url' in info:
                            entries = [info]

                        for entry in entries:
                            if not entry: continue
                            video_url = entry.get('url')
                            if video_url:
                                # yt-dlp có thể trả về link fb gốc hoặc link direct
                                title = entry.get('title', 'Video')
                                if not any(m['url'] == video_url for m in media_list):
                                    media_list.append({
                                        'type': 'video',
                                        'url': video_url,
                                        'thumbnail': 'https://placehold.co/600x800/333/FFF?text=YTDLP',
                                        'title': title,
                                        'is_search_result': True
                                    })
                            if len(media_list) >= 100: break
                except Exception as e:
                    print(f"yt-dlp error: {e}")

            # Fallback Demo nếu vẫn trắng tay
            if not media_list:
                print("[API] All failed -> Returning Demo.")
                media_list = [{
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': None,
                    'title': 'Demo (Không tìm thấy video nào)',
                    'is_demo': True
                }]
            
            print(f"[API] Returning {len(media_list)} videos.")
            self.wfile.write(json.dumps({'results': media_list[:100]}).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))