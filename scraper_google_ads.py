"""
scraper_google_ads.py
─────────────────────
Thu thập Google Ads data từ Google Ads Transparency Center.
Dùng package GoogleAds (reverse-engineered RPC) — không cần API key.

Install:
    pip install Google-Ads-Transparency-Scraper

Cách dùng trong Colab:
    from scraper_google_ads import get_google_ads_data
    data = get_google_ads_data('Amplitude', 'amplitude.com')
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

# ── Try import package ─────────────────────────────────────────────────────────
try:
    from GoogleAds import GoogleAds as _GoogleAds
    PACKAGE_AVAILABLE = True
except ImportError:
    PACKAGE_AVAILABLE = False
    print("⚠️  Package chưa được cài. Chạy: pip install Google-Ads-Transparency-Scraper")


# ── Competitor domains map ─────────────────────────────────────────────────────
# keyword dùng để search trên Transparency Center
COMPETITOR_KEYWORDS = {
    'amplitude' : 'Amplitude',
    'mixpanel'  : 'Mixpanel',
    'posthog'   : 'PostHog',
    'heap'      : 'Heap',
    'pendo'     : 'Pendo',
}

# Domain map để tìm advertiser ID chính xác hơn
COMPETITOR_DOMAINS = {
    'amplitude' : 'amplitude.com',
    'mixpanel'  : 'mixpanel.com',
    'posthog'   : 'posthog.com',
    'heap'      : 'heap.io',
    'pendo'     : 'pendo.io',
}


# ── Main function ──────────────────────────────────────────────────────────────

def get_google_ads_data(slug: str, max_ads: int = 20) -> Dict[str, Any]:
    """
    Lấy Google Ads data cho 1 competitor từ Google Ads Transparency Center.

    Args:
        slug        : Slug của competitor, ví dụ 'amplitude', 'mixpanel'
        max_ads     : Số ads tối đa cần lấy chi tiết (default 20)

    Returns:
        dict với các keys:
        - advertiser_name  (str)  : Tên advertiser trên Google
        - advertiser_id    (str)  : Google Advertiser ID (AR...)
        - ad_count         (int)  : Tổng số ads đang/đã chạy
        - ads              (list) : Chi tiết từng ad (format, title, body, last_shown)
        - ad_formats       (dict) : Phân loại theo format {Text: n, Image: n, Video: n}
        - top_messages     (list) : Ad titles/bodies nổi bật nhất
        - source           (str)  : Nguồn data
    """
    if not PACKAGE_AVAILABLE:
        return _empty_result(slug, error='package_not_installed')

    keyword = COMPETITOR_KEYWORDS.get(slug, slug.capitalize())
    domain  = COMPETITOR_DOMAINS.get(slug, f'{slug}.com')

    try:
        # Layer 1 — Search by keyword
        result = _fetch_by_keyword(keyword, domain, max_ads)
        if result['ad_count'] > 0:
            return result

        # Layer 2 — Search by domain trực tiếp
        result = _fetch_by_domain(domain, max_ads)
        if result['ad_count'] > 0:
            return result

        print(f'  ⚠️  No ads found for {slug} — may not be running Google Ads')
        return _empty_result(slug, error='no_ads_found')

    except Exception as e:
        print(f'  ✗ Google Ads error for {slug}: {type(e).__name__}: {e}')
        return _empty_result(slug, error=str(e))


# ── Layer 1: Search by keyword ─────────────────────────────────────────────────

def _fetch_by_keyword(keyword: str, domain: str, max_ads: int) -> Dict[str, Any]:
    """Tìm advertiser bằng keyword, sau đó lấy ads"""
    try:
        client   = _GoogleAds()
        creatives = client.get_creative_Ids(keyword, count=max_ads)

        advertiser_name = creatives.get('Advertisor', '')
        advertiser_id   = creatives.get('Advertisor Id', '')
        ad_count        = creatives.get('Ad Count', 0)
        creative_ids    = creatives.get('Creative_Ids', [])

        if not ad_count:
            return _empty_result(keyword, error='no_ads')

        print(f'  ✓ Found: {advertiser_name} ({advertiser_id}) — {ad_count} ads')

        # Lấy chi tiết ads
        ads = _fetch_ad_details(client, advertiser_id, creative_ids[:max_ads])

        return _build_result(
            advertiser_name=advertiser_name,
            advertiser_id=advertiser_id,
            ad_count=ad_count,
            ads=ads,
            source='google_transparency_keyword'
        )

    except Exception as e:
        print(f'  ✗ Keyword search failed: {e}')
        return _empty_result(keyword, error=str(e))


# ── Layer 2: Search by domain ──────────────────────────────────────────────────

def _fetch_by_domain(domain: str, max_ads: int) -> Dict[str, Any]:
    """Tìm advertiser trực tiếp bằng domain"""
    try:
        client   = _GoogleAds()
        result   = client.get_advistisor_by_domain(domain)

        if not result:
            return _empty_result(domain, error='domain_not_found')

        advertiser_id   = result.get('Advertisor Id', '')
        advertiser_name = result.get('Name', domain)

        print(f'  ✓ Domain lookup: {advertiser_name} ({advertiser_id})')

        # Lấy creative IDs
        creative_ids = client.creative_search_by_advertiser_id(
            advertiser_id, count=max_ads
        )
        ad_count = len(creative_ids)

        if not ad_count:
            return _empty_result(domain, error='no_creatives')

        ads = _fetch_ad_details(client, advertiser_id, creative_ids)

        return _build_result(
            advertiser_name=advertiser_name,
            advertiser_id=advertiser_id,
            ad_count=ad_count,
            ads=ads,
            source='google_transparency_domain'
        )

    except Exception as e:
        print(f'  ✗ Domain search failed: {e}')
        return _empty_result(domain, error=str(e))


# ── Fetch ad details ───────────────────────────────────────────────────────────

def _fetch_ad_details(
    client: Any,
    advertiser_id: str,
    creative_ids: List[str],
    delay: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Lấy chi tiết từng ad: format, title, body, last_shown.
    Dùng get_detailed_ad() — trả về cả Ad Title và Ad Body cho Text ads.
    """
    ads = []
    for creative_id in creative_ids:
        try:
            detail = client.get_detailed_ad(advertiser_id, creative_id)
            ads.append({
                'creative_id' : creative_id,
                'format'      : detail.get('Ad Format', ''),
                'title'       : detail.get('Ad Title', ''),
                'body'        : detail.get('Ad Body', ''),
                'last_shown'  : detail.get('Last Shown', ''),
                'ad_link'     : detail.get('Ad Link', ''),
            })
            time.sleep(delay)
        except Exception as e:
            # Không dừng vì 1 ad lỗi
            continue

    return ads


# ── Build result ───────────────────────────────────────────────────────────────

def _build_result(
    advertiser_name : str,
    advertiser_id   : str,
    ad_count        : int,
    ads             : List[Dict],
    source          : str
) -> Dict[str, Any]:
    """Tổng hợp kết quả + phân tích nhanh"""

    # Đếm theo format
    ad_formats: Dict[str, int] = {'Text': 0, 'Image': 0, 'Video': 0}
    for ad in ads:
        fmt = ad.get('format', '')
        if fmt in ad_formats:
            ad_formats[fmt] += 1

    # Lấy top messages từ Text ads
    top_messages = [
        f'{ad["title"]} — {ad["body"]}'.strip(' —')
        for ad in ads
        if ad.get('format') == 'Text' and (ad.get('title') or ad.get('body'))
    ][:5]

    # Tìm common keywords trong titles/bodies
    all_text = ' '.join(
        f'{ad.get("title","")} {ad.get("body","")}'.lower()
        for ad in ads
    )
    keywords = _extract_keywords(all_text)

    return {
        'advertiser_name' : advertiser_name,
        'advertiser_id'   : advertiser_id,
        'ad_count'        : ad_count,
        'ads_fetched'     : len(ads),
        'ads'             : ads,
        'ad_formats'      : ad_formats,
        'top_messages'    : top_messages,
        'top_keywords'    : keywords,
        'source'          : source,
        'error'           : '',
    }


def _extract_keywords(text: str, top_n: int = 8) -> List[str]:
    """Tìm keywords phổ biến nhất trong ad copy"""
    import re
    STOPWORDS = {
        'the','a','an','and','or','but','in','on','at','to','for','of',
        'with','by','from','is','are','was','were','be','been','being',
        'have','has','had','do','does','did','will','would','could','should',
        'may','might','can','get','your','you','our','we','it','its',
        'this','that','these','those','not','no','so','more','all','any',
        'their','they','them','my','me','us','as','if','up','out','how',
        'what','when','who','which',
    }
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    freq: Dict[str, int] = {}
    for w in words:
        if w not in STOPWORDS:
            freq[w] = freq.get(w, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: x[1], reverse=True)[:top_n]]


def _empty_result(name: str, error: str = '') -> Dict[str, Any]:
    return {
        'advertiser_name' : name,
        'advertiser_id'   : '',
        'ad_count'        : 0,
        'ads_fetched'     : 0,
        'ads'             : [],
        'ad_formats'      : {'Text': 0, 'Image': 0, 'Video': 0},
        'top_messages'    : [],
        'top_keywords'    : [],
        'source'          : 'failed',
        'error'           : error,
    }


# ── Batch function — scrape tất cả competitors ────────────────────────────────

def scrape_all_google_ads(slugs: List[str], max_ads: int = 20, delay: float = 3.0) -> Dict[str, Any]:
    """
    Scrape Google Ads cho toàn bộ danh sách competitors.

    Args:
        slugs   : List slugs, ví dụ ['amplitude', 'mixpanel', 'posthog']
        max_ads : Số ads tối đa mỗi competitor
        delay   : Giây chờ giữa các competitor

    Returns:
        dict {slug: result_dict}
    """
    results = {}
    for i, slug in enumerate(slugs, 1):
        print(f'\n[{i}/{len(slugs)}] {slug.capitalize()}')
        results[slug] = get_google_ads_data(slug, max_ads=max_ads)
        if i < len(slugs):
            time.sleep(delay)
    return results


# ── Test trực tiếp ─────────────────────────────────────────────────────────────

if __name__ == '__main__':

    SLUGS = ['amplitude', 'mixpanel', 'posthog', 'heap', 'pendo']

    print('📣 GOOGLE ADS TRANSPARENCY SCRAPER — TEST')
    print('=' * 55)
    print(f'Package available: {"✅" if PACKAGE_AVAILABLE else "❌ Run: pip install Google-Ads-Transparency-Scraper"}')
    print()

    if not PACKAGE_AVAILABLE:
        exit(1)

    results = scrape_all_google_ads(SLUGS, max_ads=10)

    print('\n' + '=' * 55)
    print('📊 SUMMARY')
    print('=' * 55)

    for slug, r in results.items():
        status = '✅' if r['ad_count'] > 0 else '❌'
        print(f'\n{status} {r["advertiser_name"]}')
        print(f'   Ad count    : {r["ad_count"]}')
        print(f'   Fetched     : {r["ads_fetched"]}')
        print(f'   Formats     : {r["ad_formats"]}')
        print(f'   Top keywords: {r["top_keywords"][:5]}')
        if r['top_messages']:
            print(f'   Sample ad   : {r["top_messages"][0][:80]}')
        if r['error']:
            print(f'   Error       : {r["error"]}')

    print('\n✅ Done')
