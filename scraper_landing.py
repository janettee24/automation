"""
scraper_landing.py
──────────────────
Scrape headline, subheadline, and CTA from competitor landing pages.
Built for Streamlit + notebook use.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "DNT": "1",
    "Connection": "keep-alive",
}

HEADLINE_SELECTORS = [
    "h1",
    "[class*=hero] h1",
    "[class*=headline] h1",
    "[class*=banner] h1",
    "main h1",
    "section h1",
    "[class*=hero__title]",
    "[class*=heading--1]",
    "[data-testid*=hero] h1",
]

SUBHEADLINE_SELECTORS = [
    "[class*=hero] p",
    "[class*=subtitle]",
    "[class*=subhead]",
    "[class*=hero__subtitle]",
    "[class*=description]",
    "header p",
    "main > section p",
    "meta[name='description']",
    "meta[property='og:description']",
]

CTA_SELECTORS = [
    "[class*=cta]",
    "[class*=btn-primary]",
    "[class*=button-primary]",
    "[class*=btn--primary]",
    "header a[class*=btn]",
    "nav a[class*=btn]",
    "a[class*=primary]",
    "button[class*=primary]",
    "[class*=hero] a",
    "[class*=hero] button",
    "a[href*='signup']",
    "a[href*='trial']",
    "a[href*='demo']",
    "a[href*='contact']",
]

CTA_WORDS = (
    "start",
    "sign up",
    "signup",
    "try",
    "book",
    "get started",
    "request",
    "demo",
    "contact",
    "talk to sales",
    "see",
    "watch",
    "join",
    "free trial",
)


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text


def _extract_text_from_meta(soup: BeautifulSoup, selector: str) -> str:
    tag = soup.select_one(selector)
    if not tag:
        return ""
    content = tag.get("content", "")
    return _clean(content)


def _pick_best_text(candidates):
    for text in candidates:
        text = _clean(text)
        if text:
            return text
    return ""


def _extract_headline(soup: BeautifulSoup) -> tuple[str, str]:
    # Prefer visible headings.
    for sel in HEADLINE_SELECTORS:
        tag = soup.select_one(sel)
        if tag:
            text = _clean(tag.get_text(separator=" ", strip=True))
            if text and len(text) > 3:
                return text, f"selector:{sel}"

    # Fallback to title / OG title.
    title = _pick_best_text([
        soup.title.get_text(strip=True) if soup.title else "",
        _extract_text_from_meta(soup, "meta[property='og:title']"),
        _extract_text_from_meta(soup, "meta[name='twitter:title']"),
    ])
    if title:
        return title, "meta:title"

    return "", ""


def _extract_subheadline(soup: BeautifulSoup) -> tuple[str, str]:
    for sel in SUBHEADLINE_SELECTORS:
        tag = soup.select_one(sel)
        if not tag:
            continue
        if tag.name == "meta":
            text = _clean(tag.get("content", ""))
            if len(text) > 20:
                return text[:250], f"meta:{sel}"
        else:
            text = _clean(tag.get_text(separator=" ", strip=True))
            if len(text) > 20:
                return text[:250], f"selector:{sel}"

    # Fallback to first reasonably long paragraph.
    for p in soup.find_all("p")[:20]:
        text = _clean(p.get_text(separator=" ", strip=True))
        if len(text) > 20:
            return text[:250], "fallback:p"

    return "", ""


def _extract_cta(soup: BeautifulSoup) -> tuple[str, str]:
    def score(text: str) -> int:
        t = text.lower()
        s = 0
        for kw in CTA_WORDS:
            if kw in t:
                s += 3 if len(kw) >= 5 else 2
        if 2 < len(t) < 60:
            s += 1
        return s

    candidates = []
    for sel in CTA_SELECTORS:
        for tag in soup.select(sel)[:10]:
            text = _clean(tag.get_text(separator=" ", strip=True))
            if text:
                candidates.append((score(text), text, f"selector:{sel}"))

    # Include all buttons/links as fallback candidates.
    for tag in soup.find_all(["a", "button"])[:120]:
        text = _clean(tag.get_text(separator=" ", strip=True))
        href = _clean(tag.get("href", ""))
        blob = f"{text} {href}".strip().lower()
        if any(kw in blob for kw in CTA_WORDS):
            candidates.append((score(text), text or href, "fallback:cta-words"))

    if not candidates:
        return "", ""

    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0]
    if best[1] and len(best[1]) < 60:
        return best[1], best[2]
    return "", ""


def scrape_landing(url: str) -> Dict[str, Any]:
    """Scrape headline, subheadline, and CTA from a landing page."""
    result: Dict[str, Any] = {
        "headline": "",
        "subheadline": "",
        "cta": "",
        "headline_source": "",
        "subheadline_source": "",
        "cta_source": "",
        "status_code": None,
        "final_url": url,
        "title": "",
        "error": "",
    }

    try:
        session = requests.Session()
        res = session.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        result["status_code"] = res.status_code
        result["final_url"] = res.url
        result["title"] = ""

        # Some sites return anti-bot pages with 200 but empty useful content.
        if not res.text or len(res.text) < 200:
            result["error"] = f"empty_response(len={len(res.text or '')})"
            return result

        soup = BeautifulSoup(res.text, "html.parser")
        result["title"] = _clean(soup.title.get_text(strip=True)) if soup.title else ""

        headline, headline_source = _extract_headline(soup)
        subheadline, subheadline_source = _extract_subheadline(soup)
        cta, cta_source = _extract_cta(soup)

        # Extra fallback: if no subheadline, use meta description.
        if not subheadline:
            meta_desc = _pick_best_text([
                _extract_text_from_meta(soup, "meta[name='description']"),
                _extract_text_from_meta(soup, "meta[property='og:description']"),
                _extract_text_from_meta(soup, "meta[name='twitter:description']"),
            ])
            if meta_desc:
                subheadline = meta_desc[:250]
                subheadline_source = "meta:description"

        result.update(
            {
                "headline": headline,
                "subheadline": subheadline,
                "cta": cta,
                "headline_source": headline_source,
                "subheadline_source": subheadline_source,
                "cta_source": cta_source,
            }
        )

        if not any([headline, subheadline, cta]):
            result["error"] = "no_fields_extracted"

        return result

    except requests.exceptions.Timeout:
        result["error"] = "timeout"
        return result
    except requests.exceptions.HTTPError as e:
        result["error"] = f"http_error:{getattr(e.response, 'status_code', 'unknown')}"
        return result
    except Exception as e:
        result["error"] = f"exception:{type(e).__name__}:{e}"
        return result


if __name__ == "__main__":
    TEST_URLS = [
        ("Amplitude", "https://amplitude.com"),
        ("Mixpanel", "https://mixpanel.com"),
        ("PostHog", "https://posthog.com"),
        ("Heap", "https://heap.io"),
        ("Pendo", "https://www.pendo.io"),
    ]

    for name, url in TEST_URLS:
        print(f"\n[{name}]")
        print(scrape_landing(url))
