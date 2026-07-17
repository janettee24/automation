"""Competitor Intelligence Bot v2

Features:
- Landing page scraping
- Best-effort G2 scraping
- SQLite storage
- Weekly diff and light SEO scoring
- Streamlit dashboard

Run dashboard:
    streamlit run app_v2.py

Or run CLI pipeline:
    python app_v2.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sqlite3
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    import streamlit as st
except Exception:
    st = None

APP_TITLE = "Competitor Intelligence Bot v2"
DB_PATH = os.getenv("INTEL_DB_PATH", "competitor_intel_v2.db")
EXPORT_DIR = Path(os.getenv("INTEL_EXPORT_DIR", "exports_v2"))
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

DEFAULT_TIMEOUT = 25
DEFAULT_SLEEP = 1.0
MAX_VISIBLE_TEXT_CHARS = 15000
MAX_REVIEWS = 50

SAMPLE_COMPETITORS = [
    {
        "name": "Notion",
        "landing_url": "https://www.notion.com/",
        "g2_url": "https://www.g2.com/products/notion/reviews",
    },
    {
        "name": "Mixpanel",
        "landing_url": "https://mixpanel.com/",
        "g2_url": "https://www.g2.com/products/mixpanel/reviews",
    },
    {
        "name": "Amplitude",
        "landing_url": "https://amplitude.com/",
        "g2_url": "https://www.g2.com/products/amplitude-analytics/reviews",
    },
    {
        "name": "PostHog",
        "landing_url": "https://posthog.com/",
        "g2_url": "https://www.g2.com/products/posthog/reviews",
    },
    {
        "name": "Heap",
        "landing_url": "https://heap.io/",
        "g2_url": "https://www.g2.com/products/heap/reviews",
    },
]

STOPWORDS = {
    "the", "and", "for", "with", "from", "that", "this", "your", "you", "are", "our", "has", "have",
    "can", "all", "not", "but", "will", "into", "more", "than", "use", "used", "using", "a", "an",
    "of", "to", "in", "on", "at", "by", "or", "is", "it", "as", "be", "we", "their", "they",
    "team", "product", "platform", "software", "tool", "tools", "solution", "solutions", "new", "best",
    "easy", "simple", "free", "try", "learn", "get", "start", "started"
}

POSITIVE_THEMES = {
    "easy": ["easy", "simple", "intuitive", "quick", "fast", "smooth", "friendly"],
    "support": ["support", "help", "team", "customer success", "responsive", "service"],
    "analytics": ["analytics", "report", "dashboard", "insight", "measurement", "tracking"],
    "integration": ["integrations", "integrate", "api", "connect", "slack", "jira", "hubspot"],
    "automation": ["automation", "automate", "workflow", "no-code", "workflow automation"],
}

NEGATIVE_THEMES = {
    "pricing": ["price", "pricing", "expensive", "cost", "subscription", "billing"],
    "bug": ["bug", "bugs", "issue", "issues", "broken", "glitch", "error"],
    "performance": ["slow", "lag", "performance", "load", "loading", "crash"],
    "ux": ["hard", "confusing", "clunky", "complicated", "difficult", "complex"],
    "support": ["support", "help", "response", "unresponsive", "slow response"],
    "limits": ["limit", "limited", "missing", "lack", "cannot", "can't"],
}


@dataclass
class LandingSnapshot:
    competitor: str
    url: str
    final_url: str = ""
    scraped_at: str = ""
    week: str = ""
    status_code: Optional[int] = None
    title: str = ""
    meta_description: str = ""
    headline: str = ""
    subheadline: str = ""
    primary_cta: str = ""
    secondary_ctas: List[str] = field(default_factory=list)
    h1_count: int = 0
    h2_count: int = 0
    body_word_count: int = 0
    content_hash: str = ""
    hero_hash: str = ""
    top_keywords: List[Tuple[str, int]] = field(default_factory=list)
    visible_text: str = ""
    source_mode: str = "requests"
    error: str = ""


@dataclass
class G2Review:
    competitor: str
    g2_url: str
    scraped_at: str
    title: str = ""
    rating: Optional[float] = None
    review_count: Optional[int] = None
    review_date: str = ""
    reviewer_role: str = ""
    reviewer_company_size: str = ""
    review_text: str = ""
    pros: str = ""
    cons: str = ""
    source_mode: str = "requests"
    error: str = ""


@dataclass
class G2Snapshot:
    competitor: str
    g2_url: str
    scraped_at: str = ""
    week: str = ""
    rating: Optional[float] = None
    review_count: Optional[int] = None
    review_theme_summary: str = ""
    latest_review_count: int = 0
    source_mode: str = "requests"
    error: str = ""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return utc_now().isoformat()


def week_label(dt: Optional[datetime] = None) -> str:
    dt = dt or utc_now()
    return dt.strftime("%Y-W%U")


def safe_str(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, float) and pd.isna(x):
        return ""
    return str(x).strip()


def clean_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def normalize_url(url: str) -> str:
    url = safe_str(url)
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def domain_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host


def md5_text(text: str) -> str:
    return hashlib.md5(safe_str(text).encode("utf-8")).hexdigest()


def dedupe(items: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        item = clean_text(item)
        if item and item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z][a-z0-9-]{1,}", safe_str(text).lower())


def extract_top_keywords(text: str, top_n: int = 12) -> List[Tuple[str, int]]:
    words = [w for w in tokenize(text) if w not in STOPWORDS and not w.isdigit()]
    if not words:
        return []
    counts: Dict[str, int] = {}
    for w in words:
        counts[w] = counts.get(w, 0) + 1
    return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:top_n]


def is_probably_thin_html(html: str) -> bool:
    if not html:
        return True
    soup = BeautifulSoup(html, "html.parser")
    text = clean_text(soup.get_text(" ", strip=True))
    return len(text.split()) < 60


def compare_text(old: str, new: str) -> Dict[str, Any]:
    old = safe_str(old)
    new = safe_str(new)
    if old == new:
        return {"changed": 0, "diff_type": "same", "old": old, "new": new}
    if not old and new:
        return {"changed": 1, "diff_type": "added", "old": old, "new": new}
    if old and not new:
        return {"changed": 1, "diff_type": "removed", "old": old, "new": new}
    return {"changed": 1, "diff_type": "modified", "old": old, "new": new}


def parse_rating(text: str) -> Optional[float]:
    txt = safe_str(text)
    m = re.search(r"(?<!\d)(\d(?:\.\d)?)\s*(?:out of 5|/5|stars?|★)", txt, re.I)
    if m:
        try:
            v = float(m.group(1))
            return v if 0 <= v <= 5 else None
        except Exception:
            return None
    return None


def fetch_html_requests(url: str, timeout: int = DEFAULT_TIMEOUT) -> Tuple[str, int, str]:
    resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return resp.text, resp.status_code, resp.url


def fetch_html_playwright(url: str, timeout_ms: int = 30000) -> Tuple[str, int, str]:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        raise RuntimeError("Install playwright: pip install playwright && playwright install chromium") from exc
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=DEFAULT_HEADERS["User-Agent"], viewport={"width": 1440, "height": 1600})
        page.set_default_timeout(timeout_ms)
        page.goto(url, wait_until="networkidle")
        html = page.content()
        final_url = page.url
        browser.close()
    return html, 200, final_url


def extract_meta_description(soup: BeautifulSoup) -> str:
    for selector in ["meta[name='description']", "meta[property='og:description']"]:
        tag = soup.select_one(selector)
        if tag and tag.get("content"):
            return clean_text(tag.get("content"))
    return ""


def extract_headings(soup: BeautifulSoup) -> Tuple[List[str], List[str]]:
    h1s = [clean_text(x.get_text(" ", strip=True)) for x in soup.find_all("h1")]
    h2s = [clean_text(x.get_text(" ", strip=True)) for x in soup.find_all("h2")]
    return dedupe(h1s), dedupe(h2s)


def extract_ctas(soup: BeautifulSoup) -> List[str]:
    ctas: List[str] = []
    for el in soup.find_all(["button", "a", "input"]):
        text = ""
        if el.name == "input" and (el.get("type") or "").lower() in {"submit", "button"}:
            text = clean_text(el.get("value"))
        else:
            text = clean_text(el.get_text(" ", strip=True))
        if not text or len(text) > 80:
            continue
        if re.search(r"\b(start|get started|sign up|signup|book|request|demo|trial|free|contact|learn more|try|join|watch|see it|talk to sales|get a demo|request a demo)\b", text, re.I):
            ctas.append(text)
        elif len(text.split()) <= 5:
            ctas.append(text)
    return dedupe(ctas)


def extract_visible_text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "noscript", "svg", "path", "canvas"]):
        tag.decompose()
    return clean_text(soup.get_text(" ", strip=True))


def extract_headline_subheadline(soup: BeautifulSoup) -> Tuple[str, str]:
    h1s, h2s = extract_headings(soup)
    headline = h1s[0] if h1s else ""
    subheadline = ""
    if headline:
        h1_tag = soup.find("h1")
        if h1_tag:
            for node in h1_tag.find_all_next(limit=10):
                if node.name in {"p", "div", "span"}:
                    txt = clean_text(node.get_text(" ", strip=True))
                    if 20 <= len(txt) <= 220 and len(txt.split()) <= 40:
                        subheadline = txt
                        break
    if not subheadline and h2s:
        subheadline = h2s[0]
    return headline, subheadline


def scrape_landing_page(url: str, competitor: Optional[str] = None, use_playwright: bool = True) -> LandingSnapshot:
    url = normalize_url(url)
    name = competitor or domain_from_url(url).split(".")[0].title()
    snap = LandingSnapshot(competitor=name, url=url, scraped_at=now_iso(), week=week_label())
    try:
        html, status_code, final_url = fetch_html_requests(url)
        source_mode = "requests"
        if use_playwright and is_probably_thin_html(html):
            try:
                html, status_code, final_url = fetch_html_playwright(url)
                source_mode = "playwright"
            except Exception:
                pass
        soup = BeautifulSoup(html, "html.parser")
        title = clean_text(soup.title.get_text(" ", strip=True)) if soup.title else ""
        meta_description = extract_meta_description(soup)
        h1s, h2s = extract_headings(soup)
        ctas = extract_ctas(soup)
        visible_text = extract_visible_text(soup)
        headline, subheadline = extract_headline_subheadline(soup)
        if not headline:
            headline = meta_description.split(".")[0] if meta_description else title
        content_text = " || ".join([title, meta_description, headline, subheadline, visible_text])
        hero_text = " || ".join([headline, subheadline, ctas[0] if ctas else "", title, meta_description])
        snap.final_url = final_url
        snap.status_code = status_code
        snap.title = title
        snap.meta_description = meta_description
        snap.headline = clean_text(headline)
        snap.subheadline = clean_text(subheadline)
        snap.primary_cta = ctas[0] if ctas else ""
        snap.secondary_ctas = ctas[1:5] if len(ctas) > 1 else []
        snap.h1_count = len(h1s)
        snap.h2_count = len(h2s)
        snap.body_word_count = len(visible_text.split())
        snap.content_hash = md5_text(visible_text)
        snap.hero_hash = md5_text(hero_text)
        snap.top_keywords = extract_top_keywords(content_text, top_n=12)
        snap.visible_text = visible_text[:MAX_VISIBLE_TEXT_CHARS]
        snap.source_mode = source_mode
        return snap
    except Exception as exc:
        snap.error = f"{type(exc).__name__}: {exc}"
        snap.source_mode = "error"
        return snap


def scrape_many_landings(competitors: List[Dict[str, str]], use_playwright: bool = True, sleep_s: float = DEFAULT_SLEEP) -> List[LandingSnapshot]:
    results: List[LandingSnapshot] = []
    for idx, item in enumerate(competitors, start=1):
        name = safe_str(item.get("name") or item.get("company") or item.get("brand") or f"competitor_{idx}")
        url = safe_str(item.get("landing_url") or item.get("url") or item.get("landing"))
        if not url:
            results.append(LandingSnapshot(competitor=name, url="", scraped_at=now_iso(), week=week_label(), source_mode="error", error="Missing landing_url"))
            continue
        print(f"[Landing {idx}/{len(competitors)}] Scraping {name}: {url}")
        results.append(scrape_landing_page(url, competitor=name, use_playwright=use_playwright))
        if sleep_s > 0:
            time.sleep(sleep_s)
    return results


class G2Scraper:
    REVIEW_CARD_SELECTORS = ["[data-testid*='review']", "article", "section", ".review", ".paper-card", ".reviews__item", ".l3__review", ".snippet"]

    def fetch(self, url: str, use_playwright: bool = True) -> Tuple[str, int, str, str]:
        try:
            html, status, final_url = fetch_html_requests(url)
            source_mode = "requests"
            if use_playwright and (status >= 400 or is_probably_thin_html(html)):
                try:
                    html, status, final_url = fetch_html_playwright(url)
                    source_mode = "playwright"
                except Exception:
                    pass
            return html, status, final_url, source_mode
        except Exception:
            if not use_playwright:
                raise
            html, status, final_url = fetch_html_playwright(url)
            return html, status, final_url, "playwright"

    def extract_rating_and_count(self, soup: BeautifulSoup) -> Tuple[Optional[float], Optional[int]]:
        text = clean_text(soup.get_text(" ", strip=True))
        for script in soup.find_all("script", attrs={"type": re.compile(r"ld\+json", re.I)}):
            try:
                data = json.loads(script.get_text(strip=True))
                candidates = data if isinstance(data, list) else [data]
                for obj in candidates:
                    if not isinstance(obj, dict):
                        continue
                    agg = obj.get("aggregateRating") or obj.get("rating")
                    if isinstance(agg, dict):
                        rating = agg.get("ratingValue")
                        count = agg.get("reviewCount") or agg.get("ratingCount")
                        if rating is not None:
                            try:
                                rv = float(rating)
                                if 0 <= rv <= 5:
                                    try:
                                        cv = int(count) if count is not None else None
                                    except Exception:
                                        cv = None
                                    return rv, cv
                            except Exception:
                                pass
            except Exception:
                pass
        rating = None
        m = re.search(r"(?<!\d)(\d(?:\.\d)?)\s*(?:out of 5|/5|stars?|★)", text, re.I)
        if m:
            try:
                rv = float(m.group(1))
                if 0 <= rv <= 5:
                    rating = rv
            except Exception:
                pass
        count = None
        m = re.search(r"([\d,]+)\s+reviews?", text, re.I)
        if m:
            try:
                count = int(m.group(1).replace(",", ""))
            except Exception:
                pass
        return rating, count

    def find_review_cards(self, soup: BeautifulSoup) -> List[Any]:
        cards: List[Any] = []
        seen = set()
        for selector in self.REVIEW_CARD_SELECTORS:
            for el in soup.select(selector):
                txt = clean_text(el.get_text(" ", strip=True))
                if len(txt) < 120:
                    continue
                key = md5_text(txt[:1500])
                if key in seen:
                    continue
                seen.add(key)
                cards.append(el)
                if len(cards) >= MAX_REVIEWS:
                    return cards
        return cards

    def extract_card_review(self, card: Any) -> Dict[str, str]:
        txt = clean_text(card.get_text(" ", strip=True))
        if len(txt) < 120:
            return {}
        title = ""
        review_text = txt
        pros = ""
        cons = ""
        review_date = ""
        reviewer_role = ""
        reviewer_company_size = ""
        m_pros = re.search(r"\bPros\b[:\-]?\s*(.+?)(?=\bCons\b|$)", txt, re.I | re.S)
        m_cons = re.search(r"\bCons\b[:\-]?\s*(.+?)(?=\b|$)", txt, re.I | re.S)
        if m_pros:
            pros = clean_text(m_pros.group(1))
        if m_cons:
            cons = clean_text(m_cons.group(1))
        lines = [clean_text(x) for x in re.split(r"[\n\r]+", txt) if clean_text(x)]
        if lines:
            candidate = lines[0]
            if 5 <= len(candidate.split()) <= 16:
                title = candidate
        m_date = re.search(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},\s+\d{4}\b", txt)
        if m_date:
            review_date = m_date.group(0)
        m_role = re.search(r"\b(?:Verified User|\w.*? at .+?|Director|Manager|Analyst|Founder|VP|Head of .+?)\b", txt)
        if m_role:
            reviewer_role = clean_text(m_role.group(0))
        m_size = re.search(r"\b(?:Small-Business|Mid-Market|Enterprise|1-50 employees|51-200 employees|201-500 employees|500\+ employees)\b", txt, re.I)
        if m_size:
            reviewer_company_size = clean_text(m_size.group(0))
        return {
            "title": title,
            "review_text": review_text,
            "pros": pros,
            "cons": cons,
            "review_date": review_date,
            "reviewer_role": reviewer_role,
            "reviewer_company_size": reviewer_company_size,
        }

    def theme_counts(self, text: str, theme_map: Dict[str, List[str]]) -> List[Tuple[str, int]]:
        hay = safe_str(text).lower()
        counts: List[Tuple[str, int]] = []
        for theme, kws in theme_map.items():
            n = 0
            for kw in kws:
                n += len(re.findall(rf"\b{re.escape(kw.lower())}\b", hay))
            if n > 0:
                counts.append((theme, n))
        return sorted(counts, key=lambda x: x[1], reverse=True)

    def build_theme_summary(self, reviews: List[G2Review]) -> str:
        if not reviews:
            return ""
        positive_text = " ".join([safe_str(r.pros) or safe_str(r.review_text) for r in reviews])
        negative_text = " ".join([safe_str(r.cons) for r in reviews if safe_str(r.cons)])
        all_text = " ".join([safe_str(r.review_text) for r in reviews])
        pos = self.theme_counts(positive_text or all_text, POSITIVE_THEMES)
        neg = self.theme_counts(negative_text or all_text, NEGATIVE_THEMES)
        pos_parts = [f"{k}:{v}" for k, v in pos[:5]]
        neg_parts = [f"{k}:{v}" for k, v in neg[:5]]
        return "POS[" + ", ".join(pos_parts) + "] | NEG[" + ", ".join(neg_parts) + "]"

    def scrape(self, competitor: str, g2_url: str, use_playwright: bool = True) -> Tuple[G2Snapshot, List[G2Review]]:
        g2_url = normalize_url(g2_url)
        snap = G2Snapshot(competitor=competitor, g2_url=g2_url, scraped_at=now_iso(), week=week_label())
        reviews: List[G2Review] = []
        try:
            html, status, final_url, source_mode = self.fetch(g2_url, use_playwright=use_playwright)
            soup = BeautifulSoup(html, "html.parser")
            rating, review_count = self.extract_rating_and_count(soup)
            for card in self.find_review_cards(soup)[:MAX_REVIEWS]:
                parsed = self.extract_card_review(card)
                if not parsed:
                    continue
                reviews.append(
                    G2Review(
                        competitor=competitor,
                        g2_url=g2_url,
                        scraped_at=now_iso(),
                        title=parsed.get("title", ""),
                        rating=rating,
                        review_count=review_count,
                        review_date=parsed.get("review_date", ""),
                        reviewer_role=parsed.get("reviewer_role", ""),
                        reviewer_company_size=parsed.get("reviewer_company_size", ""),
                        review_text=parsed.get("review_text", ""),
                        pros=parsed.get("pros", ""),
                        cons=parsed.get("cons", ""),
                        source_mode=source_mode,
                        error="",
                    )
                )
            snap.rating = rating
            snap.review_count = review_count
            snap.review_theme_summary = self.build_theme_summary(reviews)
            snap.latest_review_count = len(reviews)
            snap.source_mode = source_mode
            return snap, reviews
        except Exception as exc:
            snap.error = f"{type(exc).__name__}: {exc}"
            snap.source_mode = "error"
            return snap, reviews


class SQLiteStore:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS competitors (
                    competitor TEXT PRIMARY KEY,
                    landing_url TEXT NOT NULL,
                    g2_url TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS landing_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competitor TEXT NOT NULL,
                    url TEXT NOT NULL,
                    final_url TEXT,
                    scraped_at TEXT NOT NULL,
                    week TEXT NOT NULL,
                    status_code INTEGER,
                    title TEXT,
                    meta_description TEXT,
                    headline TEXT,
                    subheadline TEXT,
                    primary_cta TEXT,
                    secondary_ctas TEXT,
                    h1_count INTEGER,
                    h2_count INTEGER,
                    body_word_count INTEGER,
                    content_hash TEXT,
                    hero_hash TEXT,
                    top_keywords TEXT,
                    visible_text TEXT,
                    source_mode TEXT,
                    error TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS g2_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competitor TEXT NOT NULL,
                    g2_url TEXT NOT NULL,
                    scraped_at TEXT NOT NULL,
                    week TEXT NOT NULL,
                    rating REAL,
                    review_count INTEGER,
                    review_theme_summary TEXT,
                    latest_review_count INTEGER,
                    source_mode TEXT,
                    error TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS g2_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competitor TEXT NOT NULL,
                    g2_url TEXT NOT NULL,
                    scraped_at TEXT NOT NULL,
                    title TEXT,
                    rating REAL,
                    review_count INTEGER,
                    review_date TEXT,
                    reviewer_role TEXT,
                    reviewer_company_size TEXT,
                    review_text TEXT,
                    pros TEXT,
                    cons TEXT,
                    source_mode TEXT,
                    error TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS landing_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competitor TEXT NOT NULL,
                    week TEXT NOT NULL,
                    prev_week TEXT,
                    headline_changed INTEGER,
                    cta_changed INTEGER,
                    meta_changed INTEGER,
                    content_hash_changed INTEGER,
                    hero_hash_changed INTEGER,
                    created_at TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS g2_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competitor TEXT NOT NULL,
                    week TEXT NOT NULL,
                    prev_week TEXT,
                    rating_changed INTEGER,
                    review_count_changed INTEGER,
                    theme_changed INTEGER,
                    created_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def upsert_competitors(self, competitors: List[Dict[str, str]]) -> None:
        with self.connect() as conn:
            for c in competitors:
                conn.execute(
                    """
                    INSERT INTO competitors (competitor, landing_url, g2_url, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(competitor) DO UPDATE SET landing_url=excluded.landing_url, g2_url=excluded.g2_url
                    """,
                    (
                        safe_str(c.get("name")),
                        normalize_url(safe_str(c.get("landing_url") or c.get("url") or c.get("landing"))),
                        normalize_url(safe_str(c.get("g2_url") or c.get("g2") or "")),
                        now_iso(),
                    ),
                )
            conn.commit()

    def save_landing_snapshots(self, snapshots: List[LandingSnapshot]) -> None:
        with self.connect() as conn:
            for s in snapshots:
                conn.execute(
                    """
                    INSERT INTO landing_snapshots (
                        competitor, url, final_url, scraped_at, week, status_code, title, meta_description,
                        headline, subheadline, primary_cta, secondary_ctas, h1_count, h2_count, body_word_count,
                        content_hash, hero_hash, top_keywords, visible_text, source_mode, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        s.competitor, s.url, s.final_url, s.scraped_at, s.week, s.status_code, s.title,
                        s.meta_description, s.headline, s.subheadline, s.primary_cta, json.dumps(s.secondary_ctas, ensure_ascii=False),
                        s.h1_count, s.h2_count, s.body_word_count, s.content_hash, s.hero_hash,
                        json.dumps(s.top_keywords, ensure_ascii=False), s.visible_text, s.source_mode, s.error,
                    ),
                )
            conn.commit()

    def save_g2_snapshot(self, snapshot: G2Snapshot) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO g2_snapshots (
                    competitor, g2_url, scraped_at, week, rating, review_count, review_theme_summary,
                    latest_review_count, source_mode, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot.competitor, snapshot.g2_url, snapshot.scraped_at, snapshot.week,
                    snapshot.rating, snapshot.review_count, snapshot.review_theme_summary,
                    snapshot.latest_review_count, snapshot.source_mode, snapshot.error,
                ),
            )
            conn.commit()

    def save_g2_reviews(self, reviews: List[G2Review]) -> None:
        if not reviews:
            return
        with self.connect() as conn:
            for r in reviews:
                conn.execute(
                    """
                    INSERT INTO g2_reviews (
                        competitor, g2_url, scraped_at, title, rating, review_count, review_date,
                        reviewer_role, reviewer_company_size, review_text, pros, cons, source_mode, error
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        r.competitor, r.g2_url, r.scraped_at, r.title, r.rating, r.review_count, r.review_date,
                        r.reviewer_role, r.reviewer_company_size, r.review_text, r.pros, r.cons, r.source_mode, r.error,
                    ),
                )
            conn.commit()

    def load_landing_snapshots(self) -> pd.DataFrame:
        with self.connect() as conn:
            df = pd.read_sql_query("SELECT * FROM landing_snapshots ORDER BY scraped_at ASC", conn)
        if not df.empty:
            for col in ["secondary_ctas", "top_keywords"]:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: json.loads(x) if isinstance(x, str) and x else [])
        return df

    def load_g2_snapshots(self) -> pd.DataFrame:
        with self.connect() as conn:
            return pd.read_sql_query("SELECT * FROM g2_snapshots ORDER BY scraped_at ASC", conn)

    def load_g2_reviews(self) -> pd.DataFrame:
        with self.connect() as conn:
            return pd.read_sql_query("SELECT * FROM g2_reviews ORDER BY scraped_at DESC, id DESC", conn)

    def save_landing_changes(self, changes: List[Dict[str, Any]]) -> None:
        if not changes:
            return
        with self.connect() as conn:
            for c in changes:
                conn.execute(
                    """
                    INSERT INTO landing_changes (
                        competitor, week, prev_week, headline_changed, cta_changed, meta_changed,
                        content_hash_changed, hero_hash_changed, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c["competitor"], c["week"], c.get("prev_week", ""), int(c.get("headline_changed", 0)),
                        int(c.get("cta_changed", 0)), int(c.get("meta_changed", 0)), int(c.get("content_hash_changed", 0)),
                        int(c.get("hero_hash_changed", 0)), now_iso(),
                    ),
                )
            conn.commit()

    def save_g2_changes(self, changes: List[Dict[str, Any]]) -> None:
        if not changes:
            return
        with self.connect() as conn:
            for c in changes:
                conn.execute(
                    """
                    INSERT INTO g2_changes (
                        competitor, week, prev_week, rating_changed, review_count_changed, theme_changed, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        c["competitor"], c["week"], c.get("prev_week", ""), int(c.get("rating_changed", 0)),
                        int(c.get("review_count_changed", 0)), int(c.get("theme_changed", 0)), now_iso(),
                    ),
                )
            conn.commit()

    def load_landing_changes(self) -> pd.DataFrame:
        with self.connect() as conn:
            return pd.read_sql_query("SELECT * FROM landing_changes ORDER BY created_at DESC", conn)

    def load_g2_changes(self) -> pd.DataFrame:
        with self.connect() as conn:
            return pd.read_sql_query("SELECT * FROM g2_changes ORDER BY created_at DESC", conn)


class Analyzer:
    def infer_focus_keywords(self, df: pd.DataFrame, max_keywords: int = 8, text_cols: Optional[List[str]] = None) -> Dict[str, List[str]]:
        focus_map: Dict[str, List[str]] = {}
        if df.empty:
            return focus_map
        text_cols = text_cols or ["title", "meta_description", "headline", "subheadline", "visible_text"]
        for comp, g in df.groupby("competitor"):
            chunks = []
            for col in text_cols:
                if col in g.columns:
                    chunks.append(g[col].fillna("").astype(str))
            if not chunks:
                continue
            text = " ".join([" ".join(c.tolist()) for c in chunks])
            focus_map[comp] = [k for k, _ in extract_top_keywords(text, top_n=max_keywords)]
        return focus_map

    def keyword_density(self, text: str, keywords: List[str]) -> Dict[str, float]:
        words = tokenize(text)
        total = max(len(words), 1)
        hay = safe_str(text).lower()
        out: Dict[str, float] = {}
        for kw in keywords:
            kw_l = safe_str(kw).lower().strip()
            if not kw_l:
                continue
            hits = len(re.findall(rf"\b{re.escape(kw_l)}\b", hay))
            out[kw_l] = round(hits / total * 100, 3)
        return out

    def seo_score(self, row: pd.Series, focus_keywords: List[str]) -> Dict[str, Any]:
        title = safe_str(row.get("title", ""))
        meta = safe_str(row.get("meta_description", ""))
        headline = safe_str(row.get("headline", ""))
        subheadline = safe_str(row.get("subheadline", ""))
        primary_cta = safe_str(row.get("primary_cta", ""))
        visible_text = safe_str(row.get("visible_text", ""))
        title_score = 3 if title else 0
        if title and len(title) > 70:
            title_score -= 1
        meta_score = 3 if meta else 0
        if meta and 120 <= len(meta) <= 170:
            meta_score += 0.5
        h1_score = 4 if headline else 0
        cta_score = 2 if primary_cta else 0
        if primary_cta and any(w in primary_cta.lower() for w in ["demo", "trial", "start", "book", "free", "get"]):
            cta_score += 2
        text = " ".join([title, meta, headline, subheadline, visible_text]).lower()
        keyword_score = 0
        for kw in focus_keywords:
            kw_l = safe_str(kw).lower().strip()
            if not kw_l:
                continue
            keyword_score += min(2, sum(int(x in s.lower()) for x, s in [(kw_l, title), (kw_l, meta), (kw_l, headline), (kw_l, subheadline), (kw_l, visible_text)]) * 0.5)
        density = self.keyword_density(text, focus_keywords)
        density_score = 0
        for v in density.values():
            if 0.4 <= v <= 2.5:
                density_score += 1
            elif (0.2 <= v < 0.4) or (2.5 < v <= 4.0):
                density_score += 0.5
            elif v > 4.0:
                density_score -= 0.5
        content_len = len(tokenize(visible_text))
        content_score = 0
        if content_len >= 250:
            content_score += 1
        if content_len >= 500:
            content_score += 1
        if content_len >= 900:
            content_score += 1
        total = (title_score + meta_score + h1_score + cta_score + keyword_score + density_score + content_score) / 2.0
        return {
            "seo_score": round(min(10.0, total), 1),
            "title_score": round(title_score, 1),
            "meta_score": round(meta_score, 1),
            "h1_score": round(h1_score, 1),
            "cta_score": round(cta_score, 1),
            "keyword_score": round(keyword_score, 1),
            "density_score": round(density_score, 1),
            "content_score": round(content_score, 1),
            "content_len": content_len,
        }

    def build_landing_weekly_diff(self, df: pd.DataFrame, focus_map: Dict[str, List[str]]) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if df.empty:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
        df = df.copy()
        df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce", utc=True)
        if "week" not in df.columns or df["week"].isna().all():
            df["week"] = df["scraped_at"].dt.to_period("W").astype(str)
        diff_rows, score_rows, summary_rows = [], [], []
        for comp, g in df.groupby("competitor"):
            g = g.sort_values("scraped_at")
            weeks = sorted(g["week"].dropna().unique().tolist())
            prev_row = None
            focus_keywords = focus_map.get(comp, [])
            for wk in weeks:
                row = g[g["week"] == wk].sort_values("scraped_at").iloc[-1]
                score_pack = self.seo_score(row, focus_keywords)
                top_keywords = extract_top_keywords(" ".join([safe_str(row.get("title", "")), safe_str(row.get("meta_description", "")), safe_str(row.get("headline", "")), safe_str(row.get("subheadline", "")), safe_str(row.get("visible_text", ""))]), top_n=8)
                score_rows.append({"competitor": comp, "week": wk, "url": safe_str(row.get("url", "")), **score_pack, "top_keywords": " | ".join([f"{k}:{v}" for k, v in top_keywords])})
                if prev_row is None:
                    summary_rows.append({"competitor": comp, "week": wk, "prev_week": "", "headline_changed": 0, "cta_changed": 0, "meta_changed": 0, "content_hash_changed": 0, "hero_hash_changed": 0})
                else:
                    d_headline = compare_text(prev_row.get("headline", ""), row.get("headline", ""))
                    d_cta = compare_text(prev_row.get("primary_cta", ""), row.get("primary_cta", ""))
                    d_meta = compare_text(prev_row.get("meta_description", ""), row.get("meta_description", ""))
                    content_hash_changed = int(safe_str(prev_row.get("content_hash", "")) != safe_str(row.get("content_hash", "")))
                    hero_hash_changed = int(safe_str(prev_row.get("hero_hash", "")) != safe_str(row.get("hero_hash", "")))
                    diff_rows.append({
                        "competitor": comp,
                        "week": wk,
                        "prev_week": safe_str(prev_row.get("week", "")),
                        "headline_old": safe_str(prev_row.get("headline", "")),
                        "headline_new": safe_str(row.get("headline", "")),
                        "headline_changed": d_headline["changed"],
                        "subheadline_old": safe_str(prev_row.get("subheadline", "")),
                        "subheadline_new": safe_str(row.get("subheadline", "")),
                        "cta_old": safe_str(prev_row.get("primary_cta", "")),
                        "cta_new": safe_str(row.get("primary_cta", "")),
                        "cta_changed": d_cta["changed"],
                        "meta_old": safe_str(prev_row.get("meta_description", "")),
                        "meta_new": safe_str(row.get("meta_description", "")),
                        "meta_changed": d_meta["changed"],
                        "content_hash_changed": content_hash_changed,
                        "hero_hash_changed": hero_hash_changed,
                        "focus_keywords": " | ".join(focus_keywords),
                    })
                    summary_rows.append({"competitor": comp, "week": wk, "prev_week": safe_str(prev_row.get("week", "")), "headline_changed": d_headline["changed"], "cta_changed": d_cta["changed"], "meta_changed": d_meta["changed"], "content_hash_changed": content_hash_changed, "hero_hash_changed": hero_hash_changed})
                prev_row = row
        return pd.DataFrame(diff_rows), pd.DataFrame(score_rows), pd.DataFrame(summary_rows)

    def build_g2_weekly_diff(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        if df.empty:
            return pd.DataFrame(), pd.DataFrame()
        df = df.copy()
        df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce", utc=True)
        if "week" not in df.columns or df["week"].isna().all():
            df["week"] = df["scraped_at"].dt.to_period("W").astype(str)
        diff_rows, summary_rows = [], []
        for comp, g in df.groupby("competitor"):
            g = g.sort_values("scraped_at")
            weeks = sorted(g["week"].dropna().unique().tolist())
            prev_row = None
            for wk in weeks:
                row = g[g["week"] == wk].sort_values("scraped_at").iloc[-1]
                if prev_row is None:
                    summary_rows.append({"competitor": comp, "week": wk, "prev_week": "", "rating_changed": 0, "review_count_changed": 0, "theme_changed": 0})
                else:
                    rating_changed = int(str(prev_row.get("rating", "")) != str(row.get("rating", "")))
                    review_count_changed = int(str(prev_row.get("review_count", "")) != str(row.get("review_count", "")))
                    theme_changed = int(safe_str(prev_row.get("review_theme_summary", "")) != safe_str(row.get("review_theme_summary", "")))
                    diff_rows.append({"competitor": comp, "week": wk, "prev_week": safe_str(prev_row.get("week", "")), "rating_old": prev_row.get("rating", None), "rating_new": row.get("rating", None), "review_count_old": prev_row.get("review_count", None), "review_count_new": row.get("review_count", None), "rating_changed": rating_changed, "review_count_changed": review_count_changed, "theme_old": safe_str(prev_row.get("review_theme_summary", "")), "theme_new": safe_str(row.get("review_theme_summary", "")), "theme_changed": theme_changed})
                    summary_rows.append({"competitor": comp, "week": wk, "prev_week": safe_str(prev_row.get("week", "")), "rating_changed": rating_changed, "review_count_changed": review_count_changed, "theme_changed": theme_changed})
                prev_row = row
        return pd.DataFrame(diff_rows), pd.DataFrame(summary_rows)

    def theme_summary_from_reviews(self, reviews_df: pd.DataFrame, competitor: str, top_n: int = 5) -> Dict[str, List[Tuple[str, int]]]:
        subset = reviews_df[reviews_df["competitor"] == competitor].copy()
        if subset.empty:
            return {"positive": [], "negative": [], "all": []}
        pos_text = " ".join([safe_str(x) for x in subset["pros"].fillna("").tolist() if safe_str(x)])
        neg_text = " ".join([safe_str(x) for x in subset["cons"].fillna("").tolist() if safe_str(x)])
        all_text = " ".join(subset["review_text"].fillna("").astype(str).tolist())
        return {"positive": extract_top_keywords(pos_text or all_text, top_n=top_n), "negative": extract_top_keywords(neg_text or all_text, top_n=top_n), "all": extract_top_keywords(all_text, top_n=top_n)}


def export_landing_snapshots(snapshots: List[LandingSnapshot], out_json: str = "landing_snapshots_v2.json", out_csv: str = "landing_snapshots_v2.csv") -> Tuple[str, str]:
    rows = [asdict(s) for s in snapshots]
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"snapshots": rows}, f, ensure_ascii=False, indent=2)
    df = pd.DataFrame(rows)
    if not df.empty:
        if "secondary_ctas" in df.columns:
            df["secondary_ctas"] = df["secondary_ctas"].apply(lambda x: " | ".join(x or []))
        if "top_keywords" in df.columns:
            df["top_keywords"] = df["top_keywords"].apply(lambda x: " | ".join([f"{k}:{v}" for k, v in (x or [])]))
    df.to_csv(out_csv, index=False, encoding="utf-8-sig")
    return out_json, out_csv


def export_g2_reviews(reviews: List[G2Review], out_json: str = "g2_reviews_v2.json", out_csv: str = "g2_reviews_v2.csv") -> Tuple[str, str]:
    rows = [asdict(r) for r in reviews]
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"reviews": rows}, f, ensure_ascii=False, indent=2)
    pd.DataFrame(rows).to_csv(out_csv, index=False, encoding="utf-8-sig")
    return out_json, out_csv


def normalize_competitor_records(records: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    for r in records:
        if not isinstance(r, dict):
            continue
        out.append({"name": safe_str(r.get("name") or r.get("competitor") or r.get("brand") or ""), "landing_url": safe_str(r.get("landing_url") or r.get("url") or r.get("landing")), "g2_url": safe_str(r.get("g2_url") or r.get("g2") or "")})
    return out


def load_competitors_from_json(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict) and "competitors" in data:
        data = data["competitors"]
    if not isinstance(data, list):
        raise ValueError("JSON must be a list or contain a 'competitors' list")
    return normalize_competitor_records(data)


def load_competitors_from_csv(path: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({"name": safe_str(row.get("name") or row.get("competitor") or row.get("brand") or ""), "landing_url": safe_str(row.get("landing_url") or row.get("url") or row.get("landing") or ""), "g2_url": safe_str(row.get("g2_url") or row.get("g2") or "")})
    return rows


def load_competitors(path: Optional[str] = None) -> List[Dict[str, str]]:
    if not path:
        return SAMPLE_COMPETITORS
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        return load_competitors_from_json(path)
    if suffix == ".csv":
        return load_competitors_from_csv(path)
    raise ValueError("Input file must be .json or .csv")


def load_competitors_from_text(text: str) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3:
            items.append({"name": parts[0], "landing_url": parts[1], "g2_url": parts[2]})
        elif len(parts) == 2:
            items.append({"name": parts[0], "landing_url": parts[1], "g2_url": ""})
        else:
            items.append({"name": domain_from_url(parts[0]).split(".")[0].title(), "landing_url": parts[0], "g2_url": ""})
    return normalize_competitor_records(items)


def run_pipeline(competitors: List[Dict[str, str]], use_playwright: bool = True, sleep_s: float = DEFAULT_SLEEP) -> Dict[str, Any]:
    store = SQLiteStore(DB_PATH)
    analyzer = Analyzer()
    g2scraper = G2Scraper()
    store.upsert_competitors(competitors)
    landing_snaps = scrape_many_landings(competitors, use_playwright=use_playwright, sleep_s=sleep_s)
    store.save_landing_snapshots(landing_snaps)
    g2_snapshots: List[G2Snapshot] = []
    g2_reviews: List[G2Review] = []
    for idx, item in enumerate(competitors, start=1):
        name = safe_str(item.get("name") or item.get("competitor") or f"competitor_{idx}")
        g2_url = safe_str(item.get("g2_url") or item.get("g2"))
        if not g2_url:
            g2_snapshots.append(G2Snapshot(competitor=name, g2_url="", scraped_at=now_iso(), week=week_label(), source_mode="error", error="Missing g2_url"))
            continue
        print(f"[G2 {idx}/{len(competitors)}] Scraping {name}: {g2_url}")
        snap, reviews = g2scraper.scrape(name, g2_url, use_playwright=use_playwright)
        g2_snapshots.append(snap)
        g2_reviews.extend(reviews)
        time.sleep(sleep_s)
    for snap in g2_snapshots:
        store.save_g2_snapshot(snap)
    store.save_g2_reviews(g2_reviews)
    landing_df = store.load_landing_snapshots()
    g2_df = store.load_g2_snapshots()
    reviews_df = store.load_g2_reviews()
    focus_map = analyzer.infer_focus_keywords(landing_df)
    landing_diff_df, landing_score_df, landing_summary_df = analyzer.build_landing_weekly_diff(landing_df, focus_map)
    g2_diff_df, g2_summary_df = analyzer.build_g2_weekly_diff(g2_df)
    store.save_landing_changes(landing_summary_df.to_dict(orient="records"))
    store.save_g2_changes(g2_summary_df.to_dict(orient="records"))
    export_landing_snapshots(landing_snaps)
    export_g2_reviews(g2_reviews)
    return {
        "landing_df": landing_df,
        "g2_df": g2_df,
        "reviews_df": reviews_df,
        "landing_diff_df": landing_diff_df,
        "landing_score_df": landing_score_df,
        "landing_summary_df": landing_summary_df,
        "g2_diff_df": g2_diff_df,
        "g2_summary_df": g2_summary_df,
    }


def _display_review_row(row: pd.Series) -> str:
    header = safe_str(row.get("title", "")) or "Review"
    body = safe_str(row.get("pros", "")) or safe_str(row.get("review_text", ""))
    cons = safe_str(row.get("cons", ""))
    return f"**{header}**\n\n{body[:500]}{'...' if len(body) > 500 else ''}\n\nCons: {cons[:300]}{'...' if len(cons) > 300 else ''}"


def render_dashboard():
    assert st is not None
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)
    st.caption("Version 2: Landing pages + G2 review intelligence + weekly diff + Streamlit dashboard")
    store = SQLiteStore(DB_PATH)
    analyzer = Analyzer()
    with st.sidebar:
        st.header("Data input")
        mode = st.radio("Source", ["Sample list", "Paste URLs", "Upload JSON/CSV"], index=0)
        use_playwright = st.checkbox("Use Playwright fallback", value=True)
        sleep_s = st.slider("Sleep between requests (sec)", 0.0, 5.0, DEFAULT_SLEEP, 0.5)
        run_scrape = st.button("Run scrape", type="primary")
        competitors: List[Dict[str, str]] = []
        if mode == "Sample list":
            competitors = SAMPLE_COMPETITORS
        elif mode == "Paste URLs":
            pasted_text = st.text_area("Paste one row per line: Name,landing_url,g2_url", value=(
                "Notion,https://www.notion.com/,https://www.g2.com/products/notion/reviews\n"
                "Mixpanel,https://mixpanel.com/,https://www.g2.com/products/mixpanel/reviews\n"
                "Amplitude,https://amplitude.com/,https://www.g2.com/products/amplitude-analytics/reviews"
            ), height=180)
            competitors = load_competitors_from_text(pasted_text)
        else:
            uploaded = st.file_uploader("Upload competitor file", type=["json", "csv"])
            if uploaded is not None:
                suffix = uploaded.name.lower().split(".")[-1]
                raw = uploaded.getvalue().decode("utf-8-sig")
                if suffix == "json":
                    data = json.loads(raw)
                    if isinstance(data, dict) and "competitors" in data:
                        data = data["competitors"]
                    competitors = normalize_competitor_records(data if isinstance(data, list) else [])
                else:
                    tmp = Path("_uploaded_competitors.csv")
                    tmp.write_text(raw, encoding="utf-8")
                    competitors = load_competitors_from_csv(str(tmp))
        st.divider()
        st.write(f"DB: `{DB_PATH}`")
        if st.button("Refresh from DB"):
            st.rerun()
    if run_scrape:
        if not competitors:
            st.error("No competitors found.")
        else:
            with st.spinner("Scraping landing pages and G2..."):
                result = run_pipeline(competitors, use_playwright=use_playwright, sleep_s=sleep_s)
                st.success(f"Saved {len(result['landing_df'])} landing snapshots and {len(result['g2_df'])} G2 snapshots.")
    landing_df = store.load_landing_snapshots()
    g2_df = store.load_g2_snapshots()
    reviews_df = store.load_g2_reviews()
    if landing_df.empty and g2_df.empty:
        st.info("No data yet. Run a scrape from the sidebar.")
        return
    landing_focus = analyzer.infer_focus_keywords(landing_df) if not landing_df.empty else {}
    landing_diff_df, landing_score_df, landing_summary_df = analyzer.build_landing_weekly_diff(landing_df, landing_focus) if not landing_df.empty else (pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    g2_diff_df, g2_summary_df = analyzer.build_g2_weekly_diff(g2_df) if not g2_df.empty else (pd.DataFrame(), pd.DataFrame())
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Competitors", max(landing_df["competitor"].nunique() if not landing_df.empty else 0, g2_df["competitor"].nunique() if not g2_df.empty else 0))
    c2.metric("Landing snapshots", len(landing_df))
    c3.metric("G2 snapshots", len(g2_df))
    c4.metric("Reviews stored", len(reviews_df))
    tabs = st.tabs(["Overview", "Landing", "G2 Reviews", "Changes Timeline"])
    with tabs[0]:
        st.subheader("Latest snapshots")
        cols = st.columns(2)
        with cols[0]:
            if not landing_df.empty:
                latest_landing = landing_df.sort_values("scraped_at").groupby("competitor", as_index=False).tail(1).sort_values("competitor")
                st.dataframe(latest_landing[["competitor", "week", "headline", "primary_cta", "h1_count", "h2_count", "body_word_count", "source_mode", "error"]], use_container_width=True, hide_index=True)
            else:
                st.info("No landing data.")
        with cols[1]:
            if not g2_df.empty:
                latest_g2 = g2_df.sort_values("scraped_at").groupby("competitor", as_index=False).tail(1).sort_values("competitor")
                st.dataframe(latest_g2[["competitor", "week", "rating", "review_count", "review_theme_summary", "latest_review_count", "source_mode", "error"]], use_container_width=True, hide_index=True)
            else:
                st.info("No G2 data.")
    with tabs[1]:
        st.subheader("Landing intelligence")
        if landing_df.empty:
            st.info("No landing data yet.")
        else:
            latest = landing_df.sort_values("scraped_at").groupby("competitor", as_index=False).tail(1)
            left, right = st.columns([1, 2])
            with left:
                if not landing_score_df.empty:
                    latest_score = landing_score_df.sort_values(["competitor", "week"]).groupby("competitor", as_index=False).tail(1).sort_values("seo_score", ascending=False)
                    st.dataframe(latest_score[["competitor", "week", "seo_score", "title_score", "meta_score", "h1_score", "cta_score", "keyword_score", "density_score", "content_score"]], use_container_width=True, hide_index=True)
            with right:
                st.dataframe(latest[["competitor", "week", "title", "headline", "subheadline", "primary_cta", "top_keywords"]], use_container_width=True, hide_index=True)
            if not landing_summary_df.empty:
                tmp = landing_summary_df.copy()
                tmp["change_count"] = tmp[["headline_changed", "cta_changed", "meta_changed", "content_hash_changed", "hero_hash_changed"]].fillna(0).sum(axis=1)
                st.dataframe(tmp.sort_values(["competitor", "week"]), use_container_width=True, hide_index=True)
            if not landing_diff_df.empty:
                st.dataframe(landing_diff_df, use_container_width=True, hide_index=True)
    with tabs[2]:
        st.subheader("G2 review intelligence")
        if g2_df.empty:
            st.info("No G2 data yet.")
        else:
            latest_g2 = g2_df.sort_values("scraped_at").groupby("competitor", as_index=False).tail(1).sort_values("competitor")
            st.dataframe(latest_g2[["competitor", "week", "rating", "review_count", "review_theme_summary", "latest_review_count", "source_mode", "error"]], use_container_width=True, hide_index=True)
            comp_list = sorted(g2_df["competitor"].dropna().unique().tolist())
            selected = st.selectbox("Select competitor", comp_list)
            comp_reviews = reviews_df[reviews_df["competitor"] == selected].copy() if not reviews_df.empty else pd.DataFrame()
            comp_snap = g2_df[g2_df["competitor"] == selected].sort_values("scraped_at") if not g2_df.empty else pd.DataFrame()
            if not comp_snap.empty:
                st.line_chart(comp_snap.set_index("week")["rating"])
                st.line_chart(comp_snap.set_index("week")["review_count"])
            if not comp_reviews.empty:
                themes = analyzer.theme_summary_from_reviews(comp_reviews, selected, top_n=6)
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write("Positive themes")
                    st.write(themes["positive"])
                with c2:
                    st.write("Negative themes")
                    st.write(themes["negative"])
                with c3:
                    st.write("All themes")
                    st.write(themes["all"])
                for _, row in comp_reviews.head(10).iterrows():
                    with st.expander(safe_str(row.get("title", "Review")) or "Review"):
                        st.markdown(_display_review_row(row))
            else:
                st.info("No review text stored yet for this competitor.")
    with tabs[3]:
        st.subheader("Weekly change timeline")
        left, right = st.columns(2)
        with left:
            if landing_summary_df.empty:
                st.info("No landing change history.")
            else:
                tmp = landing_summary_df.copy()
                tmp["change_count"] = tmp[["headline_changed", "cta_changed", "meta_changed", "content_hash_changed", "hero_hash_changed"]].fillna(0).sum(axis=1)
                st.dataframe(tmp.sort_values(["competitor", "week"]), use_container_width=True, hide_index=True)
        with right:
            if g2_summary_df.empty:
                st.info("No G2 change history.")
            else:
                tmp = g2_summary_df.copy()
                tmp["change_count"] = tmp[["rating_changed", "review_count_changed", "theme_changed"]].fillna(0).sum(axis=1)
                st.dataframe(tmp.sort_values(["competitor", "week"]), use_container_width=True, hide_index=True)
    st.caption("Next version can add Meta Ads, Google Ads, LLM scoring, and A/B generator.")


def run_pipeline_from_cli() -> None:
    result = run_pipeline(SAMPLE_COMPETITORS, use_playwright=True, sleep_s=DEFAULT_SLEEP)
    print(f"Saved landing snapshots: {len(result['landing_df'])}")
    print(f"Saved G2 snapshots: {len(result['g2_df'])}")


if __name__ == "__main__":
    if st is not None and hasattr(st, "runtime"):
        render_dashboard()
    else:
        run_pipeline_from_cli()
