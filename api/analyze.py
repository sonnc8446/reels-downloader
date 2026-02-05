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
            seen_urls = set()

            # --- CHIẾN THUẬT 1: Quét ID và Tái tạo Link (Hiệu quả cho trang danh sách/Reels) ---
            try:
                # Dùng User-Agent mobile để nhận HTML nhẹ hơn
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Sec-Fetch-Site': 'none'
                }
                if user_cookies: headers['Cookie'] = user_cookies

                r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
                html = r.text
                
                # Regex tìm Video ID (Dãy số dài từ 10-20 ký tự thường đi kèm các từ khóa video)
                # Tìm trong pattern: /reel/12345/ hoặc "video_id":"12345"
                id_patterns = [
                    r'\/reel\/(\d+)',
                    r'\/videos\/(\d+)',
                    r'"video_id":"(\d+)"',
                    r'"videoId":"(\d+)"'
                ]
                
                found_ids = []
                for pattern in id_patterns:
                    found_ids.extend(re.findall(pattern, html))
                
                # Lọc trùng và tạo link
                unique_ids = list(set(found_ids))
                print(f"[Deep Scan] Found {len(unique_ids)} potential video IDs.")

                for vid in unique_ids:
                    # Bỏ qua các ID quá ngắn (thường là rác)
                    if len(vid) < 10: continue
                    
                    # Tái tạo thành link chuẩn Facebook Reel
                    # Frontend sẽ gửi link này cho api/download.py để xử lý tải sau
                    reel_link = f"https://www.facebook.com/reel/{vid}"
                    
                    if reel_link not in seen_urls:
                        seen_urls.add(reel_link)
                        media_list.append({
                            'type': 'video',
                            'url': reel_link, 
                            'thumbnail': f'https://placehold.co/600x800/1877f2/FFF?text=Reel+{vid[-4:]}', # Thumbnail tạm
                            'title': f'Facebook Reel #{vid}',
                            'is_search_result': True # Đánh dấu để biết đây là link bài viết
                        })
                        if len(media_list) >= 50: break

            except Exception as e:
                print(f"[Deep Scan] Error: {e}")

            # --- CHIẾN THUẬT 2: Search Engine Discovery (Nếu cách 1 tìm được ít) ---
            if len(media_list) < 10 and DDGS:
                print("[API] Expanding results with Search Engine...")
                try:
                    # Trích xuất tên page từ URL
                    match = re.search(r'facebook\.com\/([^\/]+)', url)
                    if match:
                        page_id = match.group(1)
                        if page_id not in ['reel', 'watch', 'videos', 'groups']:
                            queries = [
                                f'site:facebook.com/{page_id}/reel',
                                f'site:facebook.com/{page_id}/videos'
                            ]
                            
                            with DDGS() as ddgs:
                                for q in queries:
                                    if len(media_list) >= 50: break
                                    print(f"[Search] Querying: {q}")
                                    try:
                                        # Tìm kiếm text trả về kết quả tốt hơn cho dạng list
                                        results = list(ddgs.text(q, max_results=30))
                                        for res in results:
                                            href = res.get('href', '')
                                            title = res.get('title', 'Facebook Video')
                                            
                                            if 'facebook.com' in href and ('/reel/' in href or '/videos/' in href):
                                                clean_href = href.split('?')[0]
                                                if clean_href not in seen_urls:
                                                    seen_urls.add(clean_href)
                                                    media_list.append({
                                                        'type': 'video',
                                                        'url': clean_href,
                                                        'thumbnail': 'https://placehold.co/600x800/e65100/FFF?text=Web+Result',
                                                        'title': title,
                                                        'is_search_result': True
                                                    })
                                    except Exception as q_err:
                                        print(f"Query error: {q_err}")
                except Exception as se:
                    print(f"[Search] Error: {se}")

            # --- CHIẾN THUẬT 3: yt-dlp (Quét Playlist) ---
            if len(media_list) == 0:
                try:
                    print("[API] Trying yt-dlp playlist scan...")
                    ydl_opts = {
                        'quiet': True,
                        'no_warnings': True,
                        'extract_flat': 'in_playlist', # Chỉ lấy danh sách, không resolve link
                        'noplaylist': False,
                        'ignoreerrors': True,
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
                            if video_url and video_url not in seen_urls:
                                seen_urls.add(video_url)
                                media_list.append({
                                    'type': 'video',
                                    'url': video_url,
                                    'thumbnail': 'https://placehold.co/600x800/333/FFF?text=YTDLP',
                                    'title': entry.get('title', 'Video'),
                                    'is_search_result': True
                                })
                except Exception as e:
                    print(f"yt-dlp error: {e}")

            # Fallback Demo
            if not media_list:
                print("[API] All failed -> Returning Demo.")
                media_list = [{
                    'type': 'video',
                    'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                    'thumbnail': None,
                    'title': 'Demo (Không tìm thấy video nào)',
                    'is_demo': True
                }]
            
            self.wfile.write(json.dumps({'results': media_list[:100]}).encode('utf-8'))

        except Exception as e:
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))