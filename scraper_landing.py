"""
scraper_landing.py
──────────────────
Thu thập headline, subheadline, CTA từ landing page của competitors.
Dùng requests + BeautifulSoup. Không cần API key.

Cách dùng trong Colab:
    from scraper_landing import scrape_landing
    data = scrape_landing('https://amplitude.com')
"""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent'     : 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept'         : 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT'            : '1',
    'Connection'     : 'keep-alive',
}

# ── Selectors ──────────────────────────────────────────────────────────────────

HEADLINE_SELECTORS = [
    'h1',
    '[class*=hero] h1',
    '[class*=headline] h1',
    '[class*=banner] h1',
    'main h1',
    'section h1',
    '[class*=hero__title]',
    '[class*=heading--1]',
]

SUBHEADLINE_SELECTORS = [
    '[class*=hero] p',
    '[class*=subtitle]',
    '[class*=subhead]',
    '[class*=hero__subtitle]',
    '[class*=description]',
    'header p',
    'main > section p',
]

CTA_SELECTORS = [
    '[class*=cta]',
    '[class*=btn-primary]',
    '[class*=button-primary]',
    '[class*=btn--primary]',
    'header a[class*=btn]',
    'nav a[class*=btn]',
    'a[class*=primary]',
    'button[class*=primary]',
    '[class*=hero] a',
    '[class*=hero] button',
]


# ── Main function ──────────────────────────────────────────────────────────────

def scrape_landing(url: str) -> dict:
    """
    Scrape headline, subheadline, CTA từ landing page.

    Args:
        url: URL của landing page, ví dụ 'https://amplitude.com'

    Returns:
        dict với 3 keys:
        - headline     (str): H1 chính của trang
        - subheadline  (str): Đoạn mô tả bên dưới headline, tối đa 250 ký tự
        - cta          (str): Text của nút CTA chính
    """
    try:
        res  = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, 'html.parser')

        headline    = _extract_headline(soup)
        subheadline = _extract_subheadline(soup)
        cta         = _extract_cta(soup)

        return {
            'headline'    : headline,
            'subheadline' : subheadline,
            'cta'         : cta,
        }

    except requests.exceptions.Timeout:
        print(f'  ✗ Landing timeout: {url}')
    except requests.exceptions.HTTPError as e:
        print(f'  ✗ Landing HTTP error {e.response.status_code}: {url}')
    except Exception as e:
        print(f'  ✗ Landing error: {e}')

    return {'headline': '', 'subheadline': '', 'cta': ''}


# ── Private helpers ────────────────────────────────────────────────────────────

def _extract_headline(soup: BeautifulSoup) -> str:
    for sel in HEADLINE_SELECTORS:
        tag = soup.select_one(sel)
        if tag:
            text = tag.get_text(separator=' ', strip=True)
            if text and len(text) > 3:
                return text
    return ''


def _extract_subheadline(soup: BeautifulSoup) -> str:
    for sel in SUBHEADLINE_SELECTORS:
        tag = soup.select_one(sel)
        if tag:
            text = tag.get_text(separator=' ', strip=True)
            # Bỏ qua đoạn text quá ngắn hoặc là nav item
            if text and len(text) > 20:
                return text[:250]
    return ''


def _extract_cta(soup: BeautifulSoup) -> str:
    for sel in CTA_SELECTORS:
        tag = soup.select_one(sel)
        if tag:
            text = tag.get_text(separator=' ', strip=True)
            # CTA thường ngắn, bỏ qua nếu quá dài
            if text and 2 < len(text) < 60:
                return text
    return ''


# ── Test trực tiếp ─────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import time

    TEST_URLS = [
        ('Amplitude'     , 'https://amplitude.com'),
        ('Mixpanel'      , 'https://mixpanel.com'),
        ('PostHog'       , 'https://posthog.com'),
        ('Heap'          , 'https://heap.io'),
        ('Pendo'         , 'https://www.pendo.io'),
    ]

    print('🌐 LANDING PAGE SCRAPER — TEST')
    print('=' * 55)

    for name, url in TEST_URLS:
        print(f'\n[{name}]')
        result = scrape_landing(url)
        print(f'  Headline    : {result["headline"][:70] or "—"}')
        print(f'  Subheadline : {result["subheadline"][:70] or "—"}')
        print(f'  CTA         : {result["cta"] or "—"}')
        time.sleep(2)

    print('\n✅ Done')
