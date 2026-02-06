from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
import requests
import time
import yt_dlp

# Thử import thư viện tìm kiếm dự phòng
try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. CORS Headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        # Cho phép các headers tùy chỉnh từ Frontend
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-cookies, x-google-key, x-google-cx')
        self.end_headers()

        if self.command == 'OPTIONS': return

        try:
            # 2. Lấy Input và Keys
            query = parse_qs(urlparse(self.path).query)
            url = query.get('url', [None])[0]
            
            # Lấy thông tin xác thực từ Header
            user_cookies = self.headers.get('x-cookies', None)
            google_key = self.headers.get('x-google-key', None)
            google_cx = self.headers.get('x-google-cx', None)

            if not url:
                self.wfile.write(json.dumps({'error': 'Thiếu tham số URL'}).encode('utf-8'))
                return

            print(f"[Analyze] Processing: {url}")
            media_list = []
            seen_urls = set()

            # Trích xuất tên Page (Username)
            page_id = ""
            match = re.search(r'facebook\.com\/([^\/\?&]+)', url)
            if match:
                raw_id = match.group(1)
                # Lọc bỏ các từ khóa hệ thống
                if raw_id not in ['reel', 'watch', 'videos', 'groups', 'people', 'story', 'pages']:
                    page_id = raw_id
            
            print(f"[Analyze] Target Page ID: {page_id}")

            # ==================================================================
            # CHIẾN THUẬT 1: GOOGLE CUSTOM SEARCH API (VIP - Ổn định nhất)
            # ==================================================================
            if page_id and google_key and google_cx:
                print("[Strategy 1] Using Google Official API...")
                try:
                    # Tìm kiếm Reels của page cụ thể
                    search_query = f'site:facebook.com/{page_id}/reel'
                    api_url = "https://www.googleapis.com/customsearch/v1"
                    
                    # Google Custom Search Free Tier giới hạn 10 kết quả/request
                    # Ta có thể gọi loop start=1, start=11 nếu muốn lấy nhiều hơn (cần cẩn thận quota)
                    params = {
                        'key': google_key,
                        'cx': google_cx,
                        'q': search_query,
                        'num': 10 
                    }
                    
                    r = requests.get(api_url, params=params)
                    data = r.json()
                    
                    if 'items' in data:
                        for item in data['items']:
                            href = item.get('link')
                            title = item.get('title')
                            
                            # Lấy ảnh thumbnail từ dữ liệu cấu trúc (pagemap) của Google
                            thumb = None
                            if 'pagemap' in item and 'cse_image' in item['pagemap']:
                                thumb = item['pagemap']['cse_image'][0]['src']
                            elif 'pagemap' in item and 'metatags' in item['pagemap']:
                                # Thử lấy og:image từ metatags mà Google đã cache
                                for tags in item['pagemap']['metatags']:
                                    if 'og:image' in tags:
                                        thumb = tags['og:image']
                                        break
                            
                            if href and 'facebook.com' in href and '/reel/' in href:
                                if href not in seen_urls:
                                    seen_urls.add(href)
                                    media_list.append({
                                        'id': f"gg-{len(media_list)}",
                                        'type': 'video',
                                        'url': href,
                                        'title': title,
                                        'thumbnail': thumb, 
                                        'is_search_result': True
                                    })
                    else:
                        print(f"[Google API] No items found or Error: {data.get('error', {}).get('message', 'Unknown')}")

                except Exception as e:
                    print(f"[Google API Error] {e}")

            # ==================================================================
            # CHIẾN THUẬT 2: DUCKDUCKGO (Backup nếu không có Google Key)
            # ==================================================================
            if len(media_list) < 5 and DDGS and page_id:
                print("[Strategy 2] DuckDuckGo Search Discovery...")
                try:
                    queries = [
                        f'site:facebook.com/{page_id}/reel',
                        f'site:facebook.com/{page_id}/videos',
                        f'"{page_id}" facebook reels'
                    ]

                    with DDGS() as ddgs:
                        for q in queries:
                            if len(media_list) >= 50: break
                            
                            try:
                                results = list(ddgs.text(q, max_results=20))
                                for res in results:
                                    href = res.get('href', '')
                                    title = res.get('title', 'Facebook Video')
                                    
                                    if 'facebook.com' in href and ('/reel/' in href or '/videos/' in href):
                                        clean_href = href.split('?')[0]
                                        if clean_href not in seen_urls:
                                            seen_urls.add(clean_href)
                                            media_list.append({
                                                'id': f"ddg-{len(media_list)}",
                                                'type': 'video',
                                                'url': clean_href,
                                                'thumbnail': None,
                                                'title': title,
                                                'is_search_result': True
                                            })
                            except Exception as q_e:
                                print(f"[DDG Error] {q_e}")
                                time.sleep(1)

                except Exception as e:
                    print(f"[Search Error] {e}")

            # ==================================================================
            # CHIẾN THUẬT 3: MBASIC SCRAPING (Cần Cookie)
            # ==================================================================
            if len(media_list) < 5:
                print("[Strategy 3] Trying mbasic with Cookie...")
                try:
                    mbasic_url = url.replace("www.facebook.com", "mbasic.facebook.com") \
                                    .replace("web.facebook.com", "mbasic.facebook.com")
                    if "mbasic.facebook.com" not in mbasic_url:
                        mbasic_url = mbasic_url.replace("facebook.com", "mbasic.facebook.com")

                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                    }
                    if user_cookies: headers['Cookie'] = user_cookies

                    r = requests.get(mbasic_url, headers=headers, timeout=15, allow_redirects=True)
                    
                    if "login" not in r.url:
                        html = r.text
                        internal_links = re.findall(r'href="([^"]*\/reel\/[^"]+)"', html)
                        internal_links += re.findall(r'href="([^"]*\/videos\/[^"]+)"', html)
                        
                        for link in internal_links:
                            full_link = link if link.startswith('http') else f"https://www.facebook.com{link}"
                            clean_link = full_link.split('?')[0].replace('&amp;', '&')
                            
                            if clean_link not in seen_urls:
                                seen_urls.add(clean_link)
                                media_list.append({
                                    'id': f"mb-{len(media_list)}",
                                    'type': 'video',
                                    'url': clean_link,
                                    'thumbnail': None,
                                    'title': 'Facebook Reel (mbasic)',
                                    'is_search_result': True
                                })
                except Exception as e:
                    print(f"[mbasic Error] {e}")

            # ==================================================================
            # CHIẾN THUẬT 4: YT-DLP (Dự phòng cuối cùng cho video lẻ)
            # ==================================================================
            if len(media_list) == 0:
                try:
                    print("[Strategy 4] yt-dlp fallback...")
                    ydl_opts = {
                        'quiet': True, 'no_warnings': True, 'extract_flat': 'in_playlist',
                        'noplaylist': False, 'ignoreerrors': True, 'cache_dir': '/tmp/',
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        entries = info.get('entries', [info]) if 'entries' in info or 'url' in info else []
                        for entry in entries:
                            if not entry: continue
                            u = entry.get('url')
                            if u and u not in seen_urls:
                                seen_urls.add(u)
                                media_list.append({
                                    'id': f"yt-{len(media_list)}",
                                    'type': 'video', 'url': u, 'title': entry.get('title', 'Video'),
                                    'thumbnail': entry.get('thumbnail'),
                                    'is_search_result': True
                                })
                                if len(media_list) >= 20: break
                except: pass

            # --- FALLBACK DEMO ---
            if not media_list:
                print("[API] All methods failed -> Demo.")
                status_msg = "Không tìm thấy video. Hãy nhập Google API Key để tìm tốt hơn."
                if google_key: status_msg = "Google API không tìm thấy kết quả hoặc quota hết hạn."
                
                media_list = [{
                    'id': 'demo-1',
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': None,
                    'title': f'{status_msg} (Video Mẫu)',
                    'is_demo': True
                }]

            self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            print(f"Critical Error: {str(e)}")
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))