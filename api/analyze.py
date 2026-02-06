from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import re
import requests
import time

# Thử import thư viện tìm kiếm
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
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, x-cookies')
        self.end_headers()

        if self.command == 'OPTIONS': return

        try:
            # 2. Lấy Input
            query = parse_qs(urlparse(self.path).query)
            url = query.get('url', [None])[0]
            user_cookies = self.headers.get('x-cookies', None)

            if not url:
                self.wfile.write(json.dumps({'error': 'Thiếu tham số URL'}).encode('utf-8'))
                return

            print(f"[Analyze] Processing: {url}")
            media_list = []
            seen_urls = set()

            # Trích xuất thông tin Page (VD: powerofpositivity)
            page_id = ""
            match = re.search(r'facebook\.com\/([^\/\?&]+)', url)
            if match:
                raw_id = match.group(1)
                # Lọc bỏ các từ khóa hệ thống
                if raw_id not in ['reel', 'watch', 'videos', 'groups', 'people', 'story', 'pages']:
                    page_id = raw_id
            
            print(f"[Analyze] Target Page ID: {page_id}")

            # ==================================================================
            # CHIẾN THUẬT 1: SEARCH ENGINE DISCOVERY (Mạnh nhất, không cần Login)
            # ==================================================================
            if DDGS and page_id:
                print("[Strategy 1] Searching via DuckDuckGo (OSINT)...")
                try:
                    # Tạo các truy vấn tìm kiếm mô phỏng Google
                    queries = [
                        f'site:facebook.com/{page_id}/reel',    # Tìm link reel cụ thể của page
                        f'site:facebook.com/{page_id}/videos',  # Tìm link video cụ thể
                        f'"{page_id}" facebook reels',           # Tìm theo tên
                        f'"{page_id}" facebook video'
                    ]

                    with DDGS() as ddgs:
                        for q in queries:
                            if len(media_list) >= 50: break
                            
                            # Tìm kiếm (Thử lại nếu lỗi rate limit)
                            try:
                                results = list(ddgs.text(q, max_results=20))
                                for res in results:
                                    href = res.get('href', '')
                                    title = res.get('title', 'Facebook Reel')
                                    
                                    # Chỉ lấy link Video/Reel thực sự
                                    if 'facebook.com' in href and ('/reel/' in href or '/videos/' in href):
                                        clean_href = href.split('?')[0] # Bỏ tham số tracking
                                        
                                        if clean_href not in seen_urls:
                                            seen_urls.add(clean_href)
                                            media_list.append({
                                                'id': f"ddg-{len(media_list)}",
                                                'type': 'video',
                                                'url': clean_href,
                                                'thumbnail': None, # Frontend sẽ tự sinh gradient
                                                'title': title,
                                                'is_search_result': True
                                            })
                            except Exception as q_e:
                                print(f"[Search Query Error] {q}: {q_e}")
                                time.sleep(1) # Nghỉ xíu để tránh spam

                except Exception as e:
                    print(f"[Search Error] {e}")

            # ==================================================================
            # CHIẾN THUẬT 2: MBASIC SCRAPING (Cần Cookie)
            # ==================================================================
            if len(media_list) < 10:
                print("[Strategy 2] Trying mbasic.facebook.com with Cookie...")
                try:
                    # Chuyển link sang mbasic (giao diện nhẹ, dễ cào)
                    mbasic_url = url.replace("www.facebook.com", "mbasic.facebook.com") \
                                    .replace("web.facebook.com", "mbasic.facebook.com")
                    if "mbasic.facebook.com" not in mbasic_url:
                        mbasic_url = mbasic_url.replace("facebook.com", "mbasic.facebook.com")

                    headers = {
                        'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Sec-Fetch-Site': 'none',
                        'Upgrade-Insecure-Requests': '1'
                    }
                    # QUAN TRỌNG: Gắn cookie vào request
                    if user_cookies:
                        headers['Cookie'] = user_cookies
                    else:
                        print("[Warning] No cookie provided for Strategy 2")

                    r = requests.get(mbasic_url, headers=headers, timeout=15, allow_redirects=True)
                    
                    # Kiểm tra xem có bị chuyển hướng về trang login không
                    if "login" in r.url or "Đăng nhập" in r.text:
                        print("[mbasic] Cookie hết hạn hoặc chưa đăng nhập.")
                    else:
                        # Tìm link video trong mbasic
                        # Link thường nằm trong thẻ a href="/reel/..." hoặc /video.php?v=...
                        html = r.text
                        
                        # Regex tìm link nội bộ FB
                        # href="/page_name/videos/12345/"
                        # href="/reel/12345/"
                        internal_links = re.findall(r'href="([^"]*\/reel\/[^"]+)"', html)
                        internal_links += re.findall(r'href="([^"]*\/videos\/[^"]+)"', html)
                        
                        for link in internal_links:
                            # Xử lý link tương đối -> tuyệt đối
                            full_link = link if link.startswith('http') else f"https://www.facebook.com{link}"
                            # Làm sạch
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
            # KẾT QUẢ & FALLBACK
            # ==================================================================
            
            # Nếu tìm thấy kết quả -> Trả về
            if media_list:
                print(f"[API] Success! Found {len(media_list)} videos.")
                self.wfile.write(json.dumps({'results': media_list[:100]}).encode('utf-8'))
                return

            # Nếu KHÔNG tìm thấy gì -> Trả về DEMO + Thông báo lỗi
            print("[API] Failed to find videos.")
            
            error_reason = "Không tìm thấy video."
            if not user_cookies:
                error_reason += " (Bạn chưa nhập Cookie)"
            elif len(media_list) == 0:
                error_reason += " (Cookie có thể đã hết hạn hoặc IP Server bị chặn. Đang hiển thị kết quả mẫu)"

            media_list = [{
                'id': 'demo-1',
                'type': 'video',
                'url': 'https://www.w3schools.com/html/mov_bbb.mp4',
                'thumbnail': None,
                'title': f'VIDEO MẪU: {error_reason}',
                'is_demo': True
            }]
            
            self.wfile.write(json.dumps({'results': media_list}).encode('utf-8'))

        except Exception as e:
            print(f"Critical Error: {str(e)}")
            self.wfile.write(json.dumps({'error': str(e)}).encode('utf-8'))