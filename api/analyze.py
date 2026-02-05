from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote
import json
import re
import requests
import yt_dlp
from duckduckgo_search import DDGS

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

            # --- CHIẾN THUẬT 1: Requests + Regex Deep Scan (Quét mã nguồn trang) ---
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Sec-Fetch-Site': 'none',
                    'Upgrade-Insecure-Requests': '1'
                }
                if user_cookies:
                    headers['Cookie'] = user_cookies

                r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
                html = r.text
                
                # Tìm các link dạng /videos/ hoặc /reel/ hoặc /watch/
                video_matches = re.findall(r'https?:\/\/(?:www\.|m\.|web\.)?facebook\.com\/[^\/]+\/videos\/\d+\/?', html)
                reel_matches = re.findall(r'https?:\/\/(?:www\.|m\.|web\.)?facebook\.com\/reel\/\d+\/?', html)
                watch_matches = re.findall(r'https?:\/\/(?:www\.|m\.|web\.)?facebook\.com\/watch\/\?v=\d+', html)
                
                # Tìm pattern ID video trong JSON
                id_matches = re.findall(r'"video_id":"(\d+)"', html)
                id_links = [f"https://www.facebook.com/watch/?v={vid}" for vid in id_matches]

                # Gộp và lọc trùng
                all_links = list(set(video_matches + reel_matches + watch_matches + id_links))
                
                print(f"[Deep Scan] Found {len(all_links)} potential links.")

                for i, link in enumerate(all_links):
                    clean_link = link.replace('\\/', '/')
                    media_list.append({
                        'type': 'video',
                        'url': clean_link,
                        'thumbnail': f'https://placehold.co/600x800/1877f2/FFF?text=FB+Video+{i+1}',
                        'title': f'Facebook Video {i+1}',
                        'is_search_result': True
                    })
                    if len(media_list) >= 100: break

            except Exception as e:
                print(f"[Deep Scan] Error: {e}")

            # --- CHIẾN THUẬT 2: Search Engine Discovery (DuckDuckGo) ---
            # Nếu chiến thuật 1 không tìm thấy gì (do FB render bằng JS), dùng Search Engine để tìm
            if len(media_list) == 0:
                print("[API] Switching to Search Engine Discovery...")
                try:
                    # Trích xuất tên page từ URL để tạo từ khóa
                    # Ví dụ: facebook.com/powerofpositivity -> site:facebook.com/powerofpositivity/videos
                    match = re.search(r'facebook\.com\/([^\/]+)', url)
                    if match:
                        page_id = match.group(1)
                        if page_id in ['reel', 'watch', 'videos']: page_id = '' # Tránh lấy nhầm keyword hệ thống
                        
                        if page_id:
                            # Tìm kiếm 2 dạng: reels và videos
                            queries = [
                                f"site:facebook.com/{page_id}/reel",
                                f"site:facebook.com/{page_id}/videos"
                            ]
                            
                            with DDGS() as ddgs:
                                for q in queries:
                                    if len(media_list) >= 100: break
                                    print(f"[Search] Querying: {q}")
                                    results = list(ddgs.text(q, max_results=20))
                                    for res in results:
                                        href = res.get('href', '')
                                        if '/reel/' in href or '/videos/' in href:
                                            if not any(m['url'] == href for m in media_list):
                                                media_list.append({
                                                    'type': 'video',
                                                    'url': href,
                                                    'thumbnail': 'https://placehold.co/600x800/e65100/FFF?text=Search+Result',
                                                    'title': res.get('title', 'Facebook Video'),
                                                    'is_search_result': True
                                                })
                except Exception as se:
                    print(f"[Search] Error: {se}")

            # --- CHIẾN THUẬT 3: yt-dlp (Dự phòng cuối cùng) ---
            if len(media_list) == 0:
                try:
                    print("[API] Trying yt-dlp fallback...")
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': True,
                        'noplaylist': True,
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        if 'entries' in info:
                            for entry in info['entries']:
                                media_list.append({
                                    'type': 'video',
                                    'url': entry.get('url'),
                                    'thumbnail': 'https://placehold.co/600x800/333/FFF?text=YTDLP',
                                    'title': entry.get('title', 'Video'),
                                    'is_search_result': True
                                })
                                if len(media_list) >= 100: break
                except:
                    pass

            # Fallback Demo nếu vẫn trắng tay
            if not media_list:
                print("[API] All failed -> Returning Demo.")
                media_list = [{
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': None,
                    'title': 'Demo (Không tìm thấy link videos)',
                    'is_demo': True
                }]
            
            # Trả về tối đa 100 kết quả
            self.wfile.write(json.dumps({'results': media_list[:100]}).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))