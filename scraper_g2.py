"""
scraper_g2.py
─────────────
Thu thập rating và review count từ G2 / Capterra cho các competitor.

Vì G2 block server requests (403), file này dùng 3-layer fallback:
  Layer 1 → G2 API chính thức       (cần API key, tốt nhất)
  Layer 2 → Capterra scrape          (ít bị block hơn G2)
  Layer 3 → Hardcoded known ratings  (backup, update mỗi quarter)

Cách dùng trong Colab:
    from scraper_g2 import get_reviews_data
    data = get_reviews_data('amplitude')
"""

import requests
from bs4 import BeautifulSoup
import re, json, time

# ── Config ─────────────────────────────────────────────────────────────────────

G2_API_KEY = ''  # ← Điền nếu có G2 Data API key (data.g2.com)

HEADERS = {
    'User-Agent'     : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept'         : 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'DNT'            : '1',
    'Connection'     : 'keep-alive',
}

# Map G2 slug → Capterra search keyword
CAPTERRA_MAP = {
    'amplitude' : 'amplitude analytics',
    'mixpanel'  : 'mixpanel',
    'posthog'   : 'posthog',
    'heap'      : 'heap analytics',
    'pendo'     : 'pendo',
}

# Hardcoded ratings — cập nhật thủ công mỗi quarter
# Nguồn: G2.com public pages, verified Q4 2024
KNOWN_RATINGS = {
    'amplitude' : {'avg_rating': 4.5, 'review_count': 2100},
    'mixpanel'  : {'avg_rating': 4.5, 'review_count': 1100},
    'posthog'   : {'avg_rating': 4.4, 'review_count':  390},
    'heap'      : {'avg_rating': 4.4, 'review_count':  940},
    'pendo'     : {'avg_rating': 4.4, 'review_count': 1500},
}


# ── Main function ──────────────────────────────────────────────────────────────

def get_reviews_data(g2_slug: str) -> dict:
    """
    Lấy avg_rating và review_count cho 1 competitor.

    Args:
        g2_slug: Slug của product trên G2, ví dụ 'amplitude', 'mixpanel'

    Returns:
        dict với các keys:
        - avg_rating    (float): Rating trung bình, ví dụ 4.5
        - review_count  (int)  : Tổng số reviews
        - source        (str)  : Nguồn data ('api', 'capterra', 'hardcoded', 'failed')
    """

    # Layer 1 — G2 API (nếu có key)
    if G2_API_KEY:
        result = _fetch_g2_api(g2_slug)
        if result['avg_rating'] > 0:
            return result

    # Layer 2 — Capterra scrape
    result = _scrape_capterra(g2_slug)
    if result['avg_rating'] > 0:
        return result

    # Layer 3 — Hardcoded fallback
    return _get_hardcoded(g2_slug)


# ── Layer 1: G2 API ────────────────────────────────────────────────────────────

def _fetch_g2_api(slug: str) -> dict:
    """Dùng G2 Data API chính thức — cần API key từ data.g2.com"""
    try:
        url = f'https://data.g2.com/api/v1/products/{slug}/reviews'
        res = requests.get(
            url,
            headers={'Authorization': f'Token {G2_API_KEY}'},
            timeout=10
        )

        if res.status_code == 200:
            data    = res.json()
            reviews = data.get('data', [])
            ratings = [
                r['attributes']['rating']
                for r in reviews
                if 'rating' in r.get('attributes', {})
            ]
            avg = round(sum(ratings) / len(ratings), 1) if ratings else 0
            print(f'  ✓ G2 API: {avg}⭐ ({len(reviews)} reviews)')
            return {'avg_rating': avg, 'review_count': len(reviews), 'source': 'g2_api'}

        elif res.status_code == 401:
            print(f'  ✗ G2 API: Invalid API key')
        elif res.status_code == 403:
            print(f'  ✗ G2 API: Access denied (plan limitation)')
        else:
            print(f'  ✗ G2 API: Status {res.status_code}')

    except Exception as e:
        print(f'  ✗ G2 API error: {e}')

    return {'avg_rating': 0, 'review_count': 0, 'source': 'failed'}


# ── Layer 2: Capterra scrape ───────────────────────────────────────────────────

def _scrape_capterra(slug: str) -> dict:
    """
    Scrape Capterra — ít bị block hơn G2.
    Ưu tiên lấy từ JSON-LD structured data, fallback regex.
    """
    keyword = CAPTERRA_MAP.get(slug, slug)

    # Thử trang product trực tiếp trước
    urls_to_try = [
        f'https://www.capterra.com/p/search-results/?q={keyword}',
        f'https://www.capterra.com/reviews/{slug}/',
    ]

    session = requests.Session()
    session.headers.update(HEADERS)

    for url in urls_to_try:
        try:
            res = session.get(url, timeout=15)
            if res.status_code != 200:
                continue

            soup = BeautifulSoup(res.text, 'html.parser')

            # Thử JSON-LD trước (đáng tin cậy nhất)
            result = _parse_json_ld(soup)
            if result['avg_rating'] > 0:
                print(f'  ✓ Capterra JSON-LD: {result["avg_rating"]}⭐ ({result["review_count"]} reviews)')
                result['source'] = 'capterra'
                return result

            # Fallback regex trong raw HTML
            result = _parse_regex(res.text)
            if result['avg_rating'] > 0:
                print(f'  ✓ Capterra regex: {result["avg_rating"]}⭐ ({result["review_count"]} reviews)')
                result['source'] = 'capterra'
                return result

        except requests.exceptions.Timeout:
            print(f'  ✗ Capterra timeout: {url}')
        except Exception as e:
            print(f'  ✗ Capterra error: {e}')

        time.sleep(1)

    return {'avg_rating': 0, 'review_count': 0, 'source': 'failed'}


# ── Layer 3: Hardcoded ─────────────────────────────────────────────────────────

def _get_hardcoded(slug: str) -> dict:
    """
    Fallback cuối cùng — dùng ratings đã biết từ public sources.
    Cập nhật KNOWN_RATINGS thủ công mỗi quarter (~5 phút).

    Để cập nhật: vào g2.com/products/{slug}/reviews và đọc rating hiển thị.
    """
    if slug in KNOWN_RATINGS:
        data = KNOWN_RATINGS[slug]
        print(f'  ⚠️  Hardcoded: {data["avg_rating"]}⭐ ({data["review_count"]} reviews) — update quarterly')
        return {
            'avg_rating'   : data['avg_rating'],
            'review_count' : data['review_count'],
            'source'       : 'hardcoded_q4_2024'
        }

    print(f'  ✗ No data for slug: {slug}')
    return {'avg_rating': 0, 'review_count': 0, 'source': 'unknown'}


# ── Parse helpers ──────────────────────────────────────────────────────────────

def _parse_json_ld(soup: BeautifulSoup) -> dict:
    """Lấy rating từ JSON-LD structured data"""
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            data  = json.loads(script.string or '')
            items = data if isinstance(data, list) else [data]
            for item in items:
                if item.get('@type') in ('Product', 'SoftwareApplication', 'LocalBusiness'):
                    agg    = item.get('aggregateRating', {})
                    rating = float(agg.get('ratingValue', 0))
                    count  = int(str(agg.get('reviewCount', '0')).replace(',', ''))
                    if 1.0 <= rating <= 5.0 and rating > 0:
                        return {'avg_rating': round(rating, 1), 'review_count': count}
        except Exception:
            continue
    return {'avg_rating': 0, 'review_count': 0}


def _parse_regex(html: str) -> dict:
    """Lấy rating bằng regex từ raw HTML — fallback khi JSON-LD không có"""
    rating, count = 0.0, 0

    rating_patterns = [
        r'"ratingValue":\s*"?([\d.]+)"?',
        r'data-rating="([\d.]+)"',
        r'"averageRating":\s*([\d.]+)',
        r'rating["\s:>]+(\d\.\d)',
    ]
    count_patterns = [
        r'"reviewCount":\s*"?(\d[\d,]*)"?',
        r'"totalReviews":\s*(\d+)',
        r'(\d[\d,]+)\s+reviews?',
    ]

    for pattern in rating_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            try:
                r = float(match.group(1))
                if 1.0 <= r <= 5.0:
                    rating = round(r, 1)
                    break
            except Exception:
                pass

    for pattern in count_patterns:
        match = re.search(pattern, html, re.IGNORECASE)
        if match:
            try:
                count = int(match.group(1).replace(',', ''))
                if count > 0:
                    break
            except Exception:
                pass

    return {'avg_rating': rating, 'review_count': count}


# ── Test trực tiếp ─────────────────────────────────────────────────────────────

if __name__ == '__main__':

    TEST_SLUGS = ['amplitude', 'mixpanel', 'posthog', 'heap', 'pendo']

    print('⭐ G2 / CAPTERRA SCRAPER — TEST')
    print('=' * 55)
    print(f'API key: {"✓ set" if G2_API_KEY else "✗ not set — using Capterra + hardcoded fallback"}')
    print()

    for slug in TEST_SLUGS:
        print(f'[{slug}]')
        result = get_reviews_data(slug)
        print(f'  → {result["avg_rating"]}⭐  |  {result["review_count"]:,} reviews  |  source: {result["source"]}')
        print()
        time.sleep(2)

    print('✅ Done')
