from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
import requests
import yt_dlp
import os
import tempfile

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
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-cookies, x-google-key, x-google-cx')
        self.end_headers()

        if self.command == 'OPTIONS': return

        try:
            query = parse_qs(urlparse(self.path).query)
            url = query.get('url', [None])[0]
            
            # Lấy headers
            user_cookies = self.headers.get('x-cookies', None)
            google_key = self.headers.get('x-google-key', None)
            google_cx = self.headers.get('x-google-cx', None)

            if not url:
                self.wfile.write(json.dumps({'error': 'Thiếu URL'}).encode('utf-8'))
                return

            print(f"[Analyze] Processing: {url}")
            media_list = []
            seen_urls = set()

            # Trích xuất tên Page ID
            page_id = ""
            match = re.search(r'facebook\.com\/([^\/\?&]+)', url)
            if match:
                raw_id = match.group(1)
                if raw_id not in ['reel', 'watch', 'videos', 'groups', 'people', 'story', 'pages']:
                    page_id = raw_id
            
            # ==================================================================
            # CHIẾN THUẬT 1: GOOGLE CUSTOM SEARCH API (Chế độ Site-Restricted)
            # ==================================================================
            if page_id and google_key and google_cx:
                print(f"[Strategy 1] Google API Searching (Site Restricted): {page_id}")
                try:
                    # Vì Engine đã giới hạn site là facebook.com, ta không cần 'site:' nữa
                    # Ta chỉ cần tìm Tên Page + từ khóa
                    queries = [
                        f'{page_id} reels',
                        f'{page_id} videos',
                        f'{page_id}'
                    ]
                    
                    api_url = "https://www.googleapis.com/customsearch/v1"
                    
                    for q in queries:
                        if len(media_list) >= 20: break

                        params = {
                            'key': google_key,
                            'cx': google_cx,
                            'q': q,
                            'num': 10
                        }
                        
                        r = requests.get(api_url, params=params)
                        data = r.json()
                        
                        if 'items' in data:
                            for item in data['items']:
                                href = item.get('link')
                                title = item.get('title')
                                
                                # Lấy thumbnail
                                thumb = None
                                if 'pagemap' in item:
                                    if 'cse_image' in item['pagemap']:
                                        thumb = item['pagemap']['cse_image'][0]['src']
                                    elif 'metatags' in item['pagemap']:
                                        for tags in item['pagemap']['metatags']:
                                            if 'og:image' in tags:
                                                thumb = tags['og:image']
                                                break
                                
                                # Lọc kết quả: Phải là link video/reel
                                if href and ('/reel/' in href or '/videos/' in href):
                                    clean_href = href.split('?')[0]
                                    if clean_href not in seen_urls:
                                        seen_urls.add(clean_href)
                                        media_list.append({
                                            'id': f"gg-{len(media_list)}",
                                            'type': 'video',
                                            'url': clean_href,
                                            'title': title,
                                            'thumbnail': thumb, 
                                            'is_search_result': True
                                        })
                except Exception as e:
                    print(f"[Google API Error] {e}")

            # ==================================================================
            # CHIẾN THUẬT 2: DuckDuckGo (Vẫn giữ 'site:' vì DDG tìm toàn web)
            # ==================================================================
            if len(media_list) < 5 and DDGS and page_id:
                print("[Strategy 2] DuckDuckGo Search...")
                try:
                    # Với DDG ta vẫn phải dùng site: vì nó tìm toàn bộ web
                    queries = [
                        f'site:facebook.com/{page_id}/reel',
                        f'site:facebook.com/{page_id}/videos'
                    ]
                    with DDGS() as ddgs:
                        for q in queries:
                            if len(media_list) >= 50: break
                            try:
                                results = list(ddgs.text(q, max_results=30))
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
                                                'title': title,
                                                'thumbnail': None,
                                                'is_search_result': True
                                            })
                            except: pass
                except Exception as e:
                    print(f"[DDG Error] {e}")

            # ==================================================================
            # CHIẾN THUẬT 3: Cookie + mbasic (Nếu có cookie)
            # ==================================================================
            if len(media_list) < 5 and user_cookies:
                print("[Strategy 3] Trying mbasic with Cookie...")
                try:
                    mbasic_url = url.replace("www.facebook.com", "mbasic.facebook.com") \
                                    .replace("web.facebook.com", "mbasic.facebook.com")
                    if "mbasic.facebook.com" not in mbasic_url:
                        mbasic_url = mbasic_url.replace("facebook.com", "mbasic.facebook.com")

                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                        'Cookie': user_cookies
                    }

                    r = requests.get(mbasic_url, headers=headers, timeout=15, allow_redirects=True)
                    if "login" not in r.url:
                        html = r.text
                        links = re.findall(r'href="([^"]*\/reel\/[^"]+)"', html)
                        links += re.findall(r'href="([^"]*\/videos\/[^"]+)"', html)
                        
                        for link in links:
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

            # --- FALLBACK ---
            if not media_list:
                print("[API] All failed -> Demo.")
                status_msg = "Không tìm thấy video. Vui lòng kiểm tra lại cấu hình Search Engine (phải có *.facebook.com/*)."
                
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