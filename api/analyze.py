from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
import requests
import yt_dlp

# Thử import DDGS, nếu lỗi thì bỏ qua
try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # 1. CORS Setup
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

            media_list = []
            seen_ids = set()

            print(f"[Analyze] Processing: {url}")

            # ==================================================================
            # CHIẾN THUẬT 1: MBASIC.FACEBOOK.COM (Hiệu quả nhất cho Server)
            # ==================================================================
            try:
                # Chuyển đổi sang link mbasic
                mbasic_url = url.replace("www.facebook.com", "mbasic.facebook.com") \
                                .replace("web.facebook.com", "mbasic.facebook.com")
                if "mbasic.facebook.com" not in mbasic_url:
                    mbasic_url = mbasic_url.replace("facebook.com", "mbasic.facebook.com")
                
                print(f"[Strategy 1] Trying mbasic: {mbasic_url}")

                headers = {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 4.4.2; Nexus 4 Build/KOT49H) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/34.0.1847.114 Mobile Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                }
                if user_cookies: headers['Cookie'] = user_cookies

                r = requests.get(mbasic_url, headers=headers, timeout=10)
                html = r.text

                # Tìm các link video trong mbasic (thường nằm trong thẻ a href)
                # Pattern: /reel/12345/ hoặc /video.php?v=12345
                hrefs = re.findall(r'href="([^"]+)"', html)
                
                for href in hrefs:
                    vid_id = None
                    # Parse ID từ các dạng link khác nhau
                    if '/reel/' in href:
                        match = re.search(r'\/reel\/(\d+)', href)
                        if match: vid_id = match.group(1)
                    elif 'video.php' in href:
                        match = re.search(r'v=(\d+)', href)
                        if match: vid_id = match.group(1)
                    elif '/videos/' in href:
                         match = re.search(r'\/videos\/(\d+)', href)
                         if match: vid_id = match.group(1)

                    if vid_id and vid_id not in seen_ids:
                        seen_ids.add(vid_id)
                        # Tái tạo link chuẩn để frontend hiển thị và backend download xử lý sau
                        clean_url = f"https://www.facebook.com/reel/{vid_id}"
                        media_list.append({
                            'id': f"mb-{vid_id}",
                            'type': 'video',
                            'url': clean_url,
                            'thumbnail': f'https://placehold.co/600x800/1877f2/FFF?text=Reel+{vid_id[-4:]}',
                            'title': f'Facebook Reel #{vid_id}',
                            'is_search_result': True
                        })
                        if len(media_list) >= 50: break

            except Exception as e:
                print(f"[mbasic] Error: {e}")

            # ==================================================================
            # CHIẾN THUẬT 2: Quét ID trong HTML gốc (Desktop)
            # ==================================================================
            if len(media_list) < 5:
                try:
                    print("[Strategy 2] Scanning original HTML for IDs...")
                    headers_desktop = {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    }
                    if user_cookies: headers_desktop['Cookie'] = user_cookies
                    
                    r = requests.get(url, headers=headers_desktop, timeout=15)
                    html_desktop = r.text

                    # Tìm mọi chuỗi số dài (ID video thường có 15-16 số) nằm cạnh từ khóa video
                    # Ví dụ: "video_id":"123456789012345"
                    potential_ids = re.findall(r'"video_id":"(\d+)"', html_desktop)
                    potential_ids += re.findall(r'"videoId":"(\d+)"', html_desktop)
                    potential_ids += re.findall(r'\/videos\/(\d+)\/', html_desktop)

                    for vid in potential_ids:
                        if vid not in seen_ids and len(vid) > 10:
                            seen_ids.add(vid)
                            clean_url = f"https://www.facebook.com/reel/{vid}"
                            media_list.append({
                                'id': f"ds-{vid}",
                                'type': 'video',
                                'url': clean_url,
                                'thumbnail': f'https://placehold.co/600x800/2e7d32/FFF?text=Video+{vid[-4:]}',
                                'title': f'Detected Video #{vid}',
                                'is_search_result': True
                            })
                            if len(media_list) >= 50: break
                except Exception as e:
                    print(f"[Desktop Scan] Error: {e}")

            # ==================================================================
            # CHIẾN THUẬT 3: Search Engine (DuckDuckGo)
            # ==================================================================
            if len(media_list) < 5 and DDGS:
                try:
                    print("[Strategy 3] DuckDuckGo Search...")
                    match = re.search(r'facebook\.com\/([^\/\?&]+)', url)
                    if match:
                        page_id = match.group(1)
                        if page_id not in ['reel', 'watch', 'videos', 'groups']:
                            queries = [f'site:facebook.com/{page_id}/reel']
                            
                            with DDGS() as ddgs:
                                for q in queries:
                                    if len(media_list) >= 50: break
                                    results = list(ddgs.text(q, max_results=30))
                                    for res in results:
                                        href = res.get('href', '')
                                        if '/reel/' in href or '/videos/' in href:
                                            clean_href = href.split('?')[0]
                                            # Trích xuất ID từ link tìm được để tránh trùng
                                            vid_match = re.search(r'\/(\d+)', clean_href)
                                            vid_id = vid_match.group(1) if vid_match else clean_href
                                            
                                            if vid_id not in seen_ids:
                                                seen_ids.add(vid_id)
                                                media_list.append({
                                                    'id': f"ddg-{len(media_list)}",
                                                    'type': 'video',
                                                    'url': clean_href,
                                                    'thumbnail': 'https://placehold.co/600x800/e65100/FFF?text=Web+Result',
                                                    'title': res.get('title', 'Facebook Video'),
                                                    'is_search_result': True
                                                })
                except Exception as e:
                    print(f"[Search] Error: {e}")

            # ==================================================================
            # CHIẾN THUẬT 4: yt-dlp (Flat Playlist) - Cuối cùng
            # ==================================================================
            if len(media_list) == 0:
                try:
                    print("[Strategy 4] yt-dlp fallback...")
                    ydl_opts = {
                        'quiet': True, 'no_warnings': True, 'extract_flat': 'in_playlist',
                        'noplaylist': False, 'ignoreerrors': True,
                        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...'
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)
                        entries = info.get('entries', [info]) if 'entries' in info or 'url' in info else []
                        
                        for entry in entries:
                            if not entry: continue
                            u = entry.get('url')
                            if u and u not in seen_ids: # url của yt-dlp flat thường là link gốc hoặc ID
                                media_list.append({
                                    'id': f"yt-{len(media_list)}",
                                    'type': 'video', 
                                    'url': u, 
                                    'title': entry.get('title', 'Video'),
                                    'thumbnail': None,
                                    'is_search_result': True
                                })
                except: pass

            # Fallback Demo
            if not media_list:
                print("[API] All failed -> Demo.")
                media_list = [{
                    'id': 'demo-1',
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': None,
                    'title': 'Không tìm thấy video (Demo)',
                    'is_demo': True
                }]

            self.wfile.write(json.dumps({'results': media_list[:100]}).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))