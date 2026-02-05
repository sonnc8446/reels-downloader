from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
import requests
import yt_dlp
from duckduckgo_search import DDGS

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. Setup CORS
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-cookies')
        self.end_headers()

        if self.command == 'OPTIONS': return

        try:
            # 2. Parse URL & Cookie
            query = parse_qs(urlparse(self.path).query)
            target_url = query.get('url', [None])[0]
            user_cookies = self.headers.get('x-cookies', None)

            if not target_url:
                self.wfile.write(json.dumps({'error': 'Thiếu tham số URL'}).encode('utf-8'))
                return

            print(f"[Analyze] Processing: {target_url}")
            media_list = []
            seen_urls = set()

            # --- CHIẾN THUẬT 1: yt-dlp (Flat Extraction) - Ưu tiên số 1 ---
            # extract_flat='in_playlist' giúp lấy danh sách video cực nhanh mà không cần tải info chi tiết
            try:
                print("[Analyze] Trying yt-dlp (Flat Mode)...")
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': 'in_playlist', 
                    'noplaylist': False,
                    'ignoreerrors': True,
                    # Giả lập Browser Windows mới nhất
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(target_url, download=False)
                    
                    entries = []
                    if 'entries' in info:
                        entries = info['entries'] # Là danh sách (Profile/Reels tab)
                    elif 'url' in info:
                        entries = [info] # Là 1 video lẻ

                    for entry in entries:
                        if not entry: continue
                        url = entry.get('url')
                        title = entry.get('title', 'Facebook Video')
                        
                        # Chỉ lấy nếu là link http (bỏ qua các ID nội bộ)
                        if url and url.startswith('http') and url not in seen_urls:
                            seen_urls.add(url)
                            media_list.append({
                                'id': f"yt-{len(media_list)}",
                                'type': 'video',
                                'url': url,
                                'title': title,
                                'thumbnail': None, # Frontend sẽ tự sinh gradient
                                'is_search_result': True # Để frontend xử lý download
                            })
                            if len(media_list) >= 50: break
            except Exception as e:
                print(f"[yt-dlp] Error: {e}")

            # --- CHIẾN THUẬT 2: Requests + Regex (Manual Scrape) - Backup ---
            if len(media_list) == 0:
                print("[Analyze] yt-dlp failed. Switching to Manual Regex...")
                try:
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                        'Sec-Fetch-Site': 'none'
                    }
                    if user_cookies: headers['Cookie'] = user_cookies
                    
                    # Request HTML
                    r = requests.get(target_url, headers=headers, timeout=15)
                    html = r.text
                    
                    # Tìm các link dạng /reel/123... hoặc /videos/123... trong thẻ a (href)
                    # Regex này tìm chuỗi bắt đầu bằng href=", chứa facebook.com hoặc /reel/, /videos/
                    links = re.findall(r'href="([^"]*\/reel\/[^"]+)"', html)
                    links += re.findall(r'href="([^"]*\/videos\/[^"]+)"', html)
                    
                    for link in links:
                        # Chuẩn hóa link (thêm domain nếu thiếu)
                        if link.startswith('/'):
                            full_link = f"https://www.facebook.com{link}"
                        else:
                            full_link = link
                        
                        # Bỏ tham số rác sau dấu ?
                        full_link = full_link.split('?')[0].split('&')[0]
                        
                        if full_link not in seen_urls:
                            seen_urls.add(full_link)
                            media_list.append({
                                'id': f"man-{len(media_list)}",
                                'type': 'video',
                                'url': full_link,
                                'title': 'Detected Reel (Manual)',
                                'thumbnail': None,
                                'is_search_result': True
                            })
                            if len(media_list) >= 50: break
                except Exception as e:
                    print(f"[Manual] Error: {e}")

            # --- CHIẾN THUẬT 3: DuckDuckGo Search (OSINT) - Cuối cùng ---
            if len(media_list) == 0:
                print("[Analyze] Manual failed. Switching to Search Engine...")
                try:
                    # Trích xuất username
                    username = ""
                    match = re.search(r'facebook\.com\/([^\/\?&]+)', target_url)
                    if match:
                        username = match.group(1)
                        if username in ['reel', 'watch', 'videos', 'groups', 'people', 'story']: username = ""
                    
                    if username:
                        queries = [f'site:facebook.com/{username}/reel', f'site:facebook.com/{username}/videos']
                        with DDGS() as ddgs:
                            for q in queries:
                                if len(media_list) >= 50: break
                                try:
                                    results = list(ddgs.text(q, max_results=30))
                                    for res in results:
                                        href = res.get('href', '')
                                        if 'facebook.com' in href and ('/reel/' in href or '/videos/' in href):
                                            if href not in seen_urls:
                                                seen_urls.add(href)
                                                media_list.append({
                                                    'id': f"ddg-{len(media_list)}",
                                                    'type': 'video',
                                                    'url': href,
                                                    'title': res.get('title', 'Facebook Video'),
                                                    'thumbnail': None,
                                                    'is_search_result': True
                                                })
                                except Exception: pass
                except Exception as e:
                    print(f"[Search] Error: {e}")

            # --- FALLBACK DEMO ---
            if not media_list:
                print("[API] All methods failed -> Returning Demo.")
                media_list = [{
                    'id': 'demo-1',
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'title': 'Không tìm thấy video nào (Demo)',
                    'thumbnail': None,
                    'is_demo': True
                }]

            # Trả về kết quả JSON
            self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            print(f"Critical Error: {str(e)}")
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))