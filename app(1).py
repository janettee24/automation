from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup

try:
    from scraper_landing import scrape_landing
except Exception:
    scrape_landing = None

try:
    from scraper_g2 import get_reviews_data
except Exception:
    get_reviews_data = None

APP_DIR = Path(__file__).resolve().parent
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}


@dataclass
class AdRecord:
    source: str
    brand: str
    input_value: str
    query_used: str
    title: str = ""
    snippet: str = ""
    advertiser: str = ""
    ad_text: str = ""
    landing_url: str = ""
    source_url: str = ""
    status: str = ""
    start_date: str = ""
    end_date: str = ""
    collected_at: str = ""
    notes: str = ""


# -----------------------------
# Page config / styling
# -----------------------------
st.set_page_config(
    page_title="Competitor Intel + Ads",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background-color: #0f1117; }
section[data-testid="stSidebar"] { background-color: #161b27 !important; border-right: 1px solid #1e2535; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2.5rem 3rem; max-width: 1200px; }
.card { background: #161b27; border: 1px solid #1e2535; border-radius: 12px; padding: 1.1rem 1.25rem; margin-bottom: 1rem; }
.card-accent { background: linear-gradient(135deg,#161b27,#1a2035); border: 1px solid #2a3550; border-radius: 12px; padding: 1.25rem 1.5rem; margin-bottom: 1rem; }
.metric-label { font-size:0.72rem; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#4a5568; margin-bottom:0.3rem; }
.metric-value { font-size:2rem; font-weight:700; color:#e2e8f0; line-height:1; }
.metric-sub   { font-size:0.78rem; color:#4a5568; margin-top:0.25rem; }
.badge-high { background:#2d1b1b; color:#fc8181; border:1px solid #c53030; border-radius:6px; padding:2px 10px; font-size:0.72rem; font-weight:600; }
.badge-low  { background:#1a2535; color:#63b3ed; border:1px solid #2b6cb0; border-radius:6px; padding:2px 10px; font-size:0.72rem; font-weight:600; }
.badge-ok   { background:#1a2d1e; color:#68d391; border:1px solid #2f855a; border-radius:6px; padding:2px 10px; font-size:0.72rem; font-weight:600; }
.badge-gold { background:#2d2500; color:#f6c90e; border:1px solid #b7791f; border-radius:6px; padding:2px 10px; font-size:0.72rem; font-weight:600; }
.section-title { font-size:0.7rem; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#4a5568; margin:2rem 0 1rem; }
.nav-label     { font-size:0.68rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#4a5568; padding:1rem 0 0.5rem; }
.score-bar-bg   { background:#1e2535; border-radius:4px; height:8px; width:100%; margin-top:4px; }
.score-bar-fill { background:linear-gradient(90deg,#4299e1,#63b3ed); border-radius:4px; height:8px; }
.change-before { font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:#fc8181; background:#1a1010; padding:0.4rem 0.7rem; border-radius:6px; margin-bottom:0.3rem; }
.change-after  { font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:#68d391; background:#101a12; padding:0.4rem 0.7rem; }
.variant-card-a { background:linear-gradient(135deg,#0d1f2d,#102030); border:1px solid #2b6cb0; border-radius:12px; padding:1.5rem; }
.variant-card-b { background:linear-gradient(135deg,#1a0d2d,#1e0f35); border:1px solid #6b46c1; border-radius:12px; padding:1.5rem; }
.variant-label  { font-size:0.72rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; margin-bottom:1rem; }
.variant-headline { font-size:1.3rem; font-weight:700; color:#e2e8f0; margin-bottom:0.5rem; line-height:1.3; }
.variant-sub    { font-size:0.88rem; color:#a0aec0; margin-bottom:1rem; }
.variant-cta    { display:inline-block; padding:0.5rem 1.2rem; border-radius:8px; font-size:0.85rem; font-weight:600; }
.variant-cta-a  { background:#2b6cb0; color:#bee3f8; }
.variant-cta-b  { background:#553c9a; color:#e9d8fd; }
.small-note { color:#718096; font-size:0.85rem; }
</style>
""",
    unsafe_allow_html=True,
)


# -----------------------------
# Data helpers
# -----------------------------
@st.cache_data(ttl=300)
def load_data():
    for fname in ["live_data.json", "mock_data.json"]:
        path = APP_DIR / fname
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict) and "snapshots" in raw and isinstance(raw["snapshots"], list):
                return raw, fname
    return None, None


def get_latest_per_competitor(data):
    snaps = data.get("snapshots", [])
    latest = {}
    if snaps and isinstance(snaps[0], dict) and "competitor" in snaps[0]:
        for s in snaps:
            comp = s.get("competitor")
            if not comp:
                continue
            if comp not in latest or s.get("date", "") > latest[comp].get("date", ""):
                latest[comp] = s
    elif snaps and isinstance(snaps[0], dict) and "data" in snaps[0]:
        last_week = snaps[-1]
        for comp, d in last_week.get("data", {}).items():
            latest[comp] = {**d, "competitor": comp, "date": last_week.get("week", "")}
    return latest


def get_all_changes(data):
    snaps = data.get("snapshots", [])
    changes = []
    if snaps and isinstance(snaps[0], dict) and "changes" in snaps[0]:
        for s in snaps:
            for ch in s.get("changes", []):
                changes.append({**ch, "week": s.get("week", ""), "label": s.get("label", "")})
    return changes


# -----------------------------
# Landing + G2 helpers
# -----------------------------
def parse_competitor_lines(text):
    rows = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            continue
        name = parts[0]
        url = parts[1]
        slug = parts[2] if len(parts) >= 3 and parts[2] else name.lower().replace(" ", "-")
        rows.append({"name": name, "url": url, "slug": slug})
    return rows


def run_live_scrape(competitors):
    if scrape_landing is None or get_reviews_data is None:
        raise RuntimeError("Missing scraper modules. Make sure scraper_landing.py and scraper_g2.py are in the same folder as app.py.")

    results = []
    for item in competitors:
        landing = scrape_landing(item["url"])
        reviews = get_reviews_data(item["slug"])
        results.append(
            {
                "company": item["name"],
                "url": item["url"],
                "slug": item["slug"],
                "headline": landing.get("headline", ""),
                "subheadline": landing.get("subheadline", ""),
                "cta": landing.get("cta", ""),
                "avg_rating": reviews.get("avg_rating", 0),
                "review_count": reviews.get("review_count", 0),
                "source": reviews.get("source", ""),
            }
        )
    return pd.DataFrame(results)


# -----------------------------
# Ads helpers
# -----------------------------
def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _brand_from_input(value: str) -> tuple[str, str]:
    value = (value or "").strip()
    if not value:
        return "", ""
    if "://" in value:
        parsed = urlparse(value)
        host = (parsed.netloc or parsed.path).replace("www.", "")
        brand = host.split(".")[0].replace("-", " ").title()
        return brand or value, value
    if "." in value and " " not in value:
        host = value.replace("www.", "")
        brand = host.split(".")[0].replace("-", " ").title()
        return brand or value, f"https://{value}"
    return value.title(), value


def _fetch(url: str, timeout_s: int = 15) -> tuple[int, str]:
    try:
        res = requests.get(url, headers=HEADERS, timeout=timeout_s)
        return res.status_code, res.text
    except Exception as e:
        return 0, f"__ERROR__:{e}"


def _extract_title_and_meta(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = _clean(soup.title.get_text()) if soup.title else ""
    desc = ""
    for sel in ["meta[name='description']", "meta[property='og:description']"]:
        tag = soup.select_one(sel)
        if tag and tag.get("content"):
            desc = _clean(tag.get("content"))
            break
    og_site = ""
    tag = soup.select_one("meta[property='og:site_name']")
    if tag and tag.get("content"):
        og_site = _clean(tag.get("content"))
    return {"title": title, "description": desc, "site_name": og_site}


def _parse_hrefs(html: str, pattern: str) -> list[str]:
    hrefs = re.findall(r'href=["\'](.*?)["\']', html, flags=re.I)
    out = []
    seen = set()
    for href in hrefs:
        if re.search(pattern, href, flags=re.I) and href not in seen:
            seen.add(href)
            out.append(href)
    return out


def _guess_landing_from_text(text: str) -> str:
    urls = re.findall(r"https?://[^\s\"'<>]+", text or "", flags=re.I)
    return urls[0] if urls else ""


def _parse_meta_public_page(html: str, brand: str, input_value: str, query_used: str, source_url: str, max_results: int) -> list[AdRecord]:
    records: list[AdRecord] = []
    soup = BeautifulSoup(html, "html.parser")

    blocks = []
    for tag in soup.find_all(["div", "span", "p", "a"]):
        txt = _clean(tag.get_text(" ", strip=True))
        if 20 <= len(txt) <= 280:
            blocks.append(txt)

    candidates = []
    brand_l = brand.lower()
    for b in blocks:
        bl = b.lower()
        if any(k in bl for k in ["ad", "advert", "sponsored", "library", "active", "running"]) or brand_l in bl:
            candidates.append(b)

    uniq = []
    seen = set()
    for c in candidates[: max(20, max_results * 4)]:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(c)

    hrefs = _parse_hrefs(html, r"ads/library|adstransparency|transparency")
    ad_links = hrefs[:max_results]

    for idx, c in enumerate(uniq[:max_results]):
        records.append(
            AdRecord(
                source="meta",
                brand=brand,
                input_value=input_value,
                query_used=query_used,
                title=c[:120],
                snippet=c[:250],
                advertiser=brand,
                ad_text=c,
                landing_url=_guess_landing_from_text(c),
                source_url=ad_links[idx] if idx < len(ad_links) else source_url,
                status="public_page",
                collected_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
                notes="Parsed from public HTML; verify on Ad Library if needed.",
            )
        )
    return records


def scrape_meta_ads(input_value: str, brand: str, country_code: str, timeout_s: int, max_results: int) -> list[AdRecord]:
    q = quote_plus(brand)
    candidate_urls = [
        f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={country_code.upper()}&q={q}",
        f"https://business.facebook.com/ads/library/?active_status=all&ad_type=all&country={country_code.upper()}&q={q}",
        f"https://business.prod.facebook.com/ads/library/report/?search_type=keyword&q={q}",
    ]

    results: list[AdRecord] = []
    for url in candidate_urls:
        status, html = _fetch(url, timeout_s=timeout_s)
        if status != 200 or html.startswith("__ERROR__"):
            continue
        page_meta = _extract_title_and_meta(html)
        records = _parse_meta_public_page(html, brand, input_value, q, url, max_results)
        if records:
            results.extend(records)
            break
        results.append(
            AdRecord(
                source="meta",
                brand=brand,
                input_value=input_value,
                query_used=q,
                title=page_meta.get("title", "Meta Ad page"),
                snippet=page_meta.get("description", ""),
                advertiser=brand,
                source_url=url,
                status="loaded_no_parse",
                collected_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
                notes="Page loaded but no card-like ad content was extracted.",
            )
        )
        break

    if not results:
        results.append(
            AdRecord(
                source="meta",
                brand=brand,
                input_value=input_value,
                query_used=q,
                title="No result",
                snippet="",
                advertiser=brand,
                source_url=candidate_urls[0],
                status="not_found",
                collected_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
                notes="No public Meta ad result found from the target query.",
            )
        )

    return results[:max_results]


def _parse_google_transparency(html: str, brand: str, input_value: str, query_used: str, source_url: str, max_results: int) -> list[AdRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[AdRecord] = []
    text_blocks = []
    for tag in soup.find_all(["div", "span", "p", "a", "li"]):
        txt = _clean(tag.get_text(" ", strip=True))
        if 15 <= len(txt) <= 260:
            text_blocks.append(txt)

    candidates = []
    brand_l = brand.lower()
    for b in text_blocks:
        bl = b.lower()
        if brand_l in bl or any(k in bl for k in ["advertiser", "ads", "transparency", "served", "displayed"]):
            candidates.append(b)

    hrefs = _parse_hrefs(html, r"adstransparency\.google\.com|google\.com/adstransparency")
    seen = set()
    for idx, c in enumerate(candidates[:max_results]):
        if c.lower() in seen:
            continue
        seen.add(c.lower())
        records.append(
            AdRecord(
                source="google",
                brand=brand,
                input_value=input_value,
                query_used=query_used,
                title=c[:120],
                snippet=c[:250],
                advertiser=brand,
                ad_text=c,
                source_url=hrefs[idx] if idx < len(hrefs) else source_url,
                status="public_page",
                collected_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
                notes="Parsed from Google Ads Transparency page HTML; verify in the UI if needed.",
            )
        )
    return records


def scrape_google_ads(input_value: str, brand: str, timeout_s: int, max_results: int) -> list[AdRecord]:
    q = quote_plus(brand)
    candidate_urls = [
        f"https://adstransparency.google.com/?q={q}&region=anywhere",
        f"https://adstransparency.google.com/?region=anywhere&q={q}",
        f"https://adstransparency.google.com/",
    ]

    results: list[AdRecord] = []
    for url in candidate_urls:
        status, html = _fetch(url, timeout_s=timeout_s)
        if status != 200 or html.startswith("__ERROR__"):
            continue
        records = _parse_google_transparency(html, brand, input_value, q, url, max_results)
        if records:
            results.extend(records)
            break
        page_meta = _extract_title_and_meta(html)
        results.append(
            AdRecord(
                source="google",
                brand=brand,
                input_value=input_value,
                query_used=q,
                title=page_meta.get("title", "Google Ads Transparency Center"),
                snippet=page_meta.get("description", ""),
                advertiser=brand,
                source_url=url,
                status="loaded_no_parse",
                collected_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
                notes="Page loaded but no ad card-like content was extracted.",
            )
        )
        break

    if not results:
        results.append(
            AdRecord(
                source="google",
                brand=brand,
                input_value=input_value,
                query_used=q,
                title="No result",
                snippet="",
                advertiser=brand,
                source_url=candidate_urls[0],
                status="not_found",
                collected_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
                notes="No public Google Ads Transparency result found from the target query.",
            )
        )

    return results[:max_results]


@st.cache_data(ttl=900, show_spinner=False)
def scrape_all_ads(inputs: tuple[str, ...], country_code: str, timeout_s: int, max_results: int) -> tuple[list[dict], dict]:
    all_rows: list[dict] = []
    summary = {"inputs": len(inputs), "meta_rows": 0, "google_rows": 0, "failed_inputs": 0}

    for raw in inputs:
        brand, normalized = _brand_from_input(raw)
        if not brand:
            continue

        meta_rows = scrape_meta_ads(normalized, brand, country_code, timeout_s, max_results)
        google_rows = scrape_google_ads(normalized, brand, timeout_s, max_results)

        for r in meta_rows + google_rows:
            all_rows.append(asdict(r))

        summary["meta_rows"] += sum(1 for r in meta_rows if r.status not in {"not_found", "loaded_no_parse"} or r.title != "No result")
        summary["google_rows"] += sum(1 for r in google_rows if r.status not in {"not_found", "loaded_no_parse"} or r.title != "No result")
        if all(x.status == "not_found" for x in meta_rows + google_rows):
            summary["failed_inputs"] += 1

    return all_rows, summary


# -----------------------------
# Load data
# -----------------------------
data, source_file = load_data()
competitors = []
latest = {}
all_changes = []
ab_variants = {}
last_updated = "N/A"
if data:
    competitors = data.get("competitors", [])
    latest = get_latest_per_competitor(data)
    all_changes = get_all_changes(data)
    ab_variants = data.get("ab_variants", {})
    last_updated = data.get("last_updated", "N/A")


# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.markdown(
        '<div style="padding:1rem 0 0.25rem;"><span style="font-size:1.3rem;">🔍</span> <span style="font-weight:700;color:#e2e8f0;font-size:1rem;">Competitor Intel</span></div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div style="font-size:0.75rem;color:#4a5568;margin-bottom:1.5rem;">Product Analytics · PMM Portfolio</div>', unsafe_allow_html=True)
    st.markdown('<div class="nav-label">Navigation</div>', unsafe_allow_html=True)
    page = st.radio(
        "",
        ["🚀 Live Scraper", "📊 Overview", "🏆 Score Leaderboard", "🔄 Changes Timeline", "🔎 Competitor Detail", "🧪 A/B Generator", "📣 Ads Transparency"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown('<div class="nav-label">Data source</div>', unsafe_allow_html=True)
    if source_file == "live_data.json":
        src_badge = "🟢 Live data"
    elif source_file == "mock_data.json":
        src_badge = "🟡 Mock data"
    else:
        src_badge = "⚪ No dashboard data"
    st.markdown(
        f'<div style="font-size:0.82rem;color:#718096;">{src_badge}<br>Updated: {last_updated}<br>{len(competitors)} competitors tracked</div>',
        unsafe_allow_html=True,
    )
    if source_file == "mock_data.json":
        st.markdown('<div style="font-size:0.75rem;color:#4a5568;margin-top:0.5rem;font-style:italic;">Upload live_data.json từ pipeline để dùng real-time data</div>', unsafe_allow_html=True)


# -----------------------------
# Page 1 — Live Scraper
# -----------------------------
if page == "🚀 Live Scraper":
    st.markdown('<h1 style="font-size:1.6rem;font-weight:700;color:#e2e8f0;margin-bottom:0.25rem;">Live Scraper</h1>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.85rem;color:#718096;margin-bottom:2rem;">Nhập danh sách competitor, app sẽ scrape landing page + rating/review data.</div>', unsafe_allow_html=True)

    sample = """Amplitude,https://amplitude.com,amplitude
Mixpanel,https://mixpanel.com,mixpanel
PostHog,https://posthog.com,posthog"""
    competitors_text = st.text_area("Competitors (name,url,slug)", value=sample, height=160)
    run = st.button("⚡ Run Scraper", type="primary")

    if run:
        items = parse_competitor_lines(competitors_text)
        if not items:
            st.error("Không có competitor hợp lệ. Mỗi dòng cần format: name,url,slug")
        else:
            with st.spinner("Đang scrape..."):
                try:
                    df = run_live_scrape(items)
                    st.success(f"Scraped {len(df)} competitors")
                    st.dataframe(df, use_container_width=True)
                    st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), file_name="competitor_intel.csv", mime="text/csv")
                except Exception as e:
                    st.error(f"Scrape failed: {e}")
    else:
        st.info("Bấm Run Scraper để bắt đầu.")


# -----------------------------
# Page 2 — Overview
# -----------------------------
elif page == "📊 Overview":
    st.markdown('<h1 style="font-size:1.6rem;font-weight:700;color:#e2e8f0;margin-bottom:0.25rem;">Market Overview</h1>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:0.85rem;color:#718096;margin-bottom:2rem;">Product Analytics category · {len(competitors)} competitors · Target: PM/Growth teams</div>', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    high_changes = len([c for c in all_changes if c.get("severity") == "high"])
    with c1:
        st.markdown(f'<div class="card"><div class="metric-label">Competitors</div><div class="metric-value">{len(competitors)}</div><div class="metric-sub">tracked weekly</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="card"><div class="metric-label">Changes detected</div><div class="metric-value">{len(all_changes)}</div><div class="metric-sub">total history</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="card"><div class="metric-label">High severity</div><div class="metric-value" style="color:#fc8181;">{high_changes}</div><div class="metric-sub">need attention</div></div>', unsafe_allow_html=True)
    with c4:
        if latest:
            scores = {k: v.get("score_total", 0) for k, v in latest.items() if v.get("score_total")}
            top = max(scores, key=scores.get) if scores else "-"
        else:
            top = "-"
        st.markdown(f'<div class="card"><div class="metric-label">Top scorer</div><div class="metric-value" style="font-size:1.2rem;padding-top:0.4rem;">{top}</div><div class="metric-sub">best positioning</div></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Current Snapshot</div>', unsafe_allow_html=True)
    if not competitors:
        st.info("Không có dashboard data. Hãy thêm live_data.json hoặc mock_data.json vào cùng thư mục với app.py.")
    for comp in competitors:
        d = latest.get(comp, {})
        if not d:
            continue
        score = d.get("score_total", 0)
        model = d.get("pricing_model", "")
        if model == "PLG":
            model_badge = '<span class="badge-ok">PLG</span>'
        elif model == "Sales-led":
            model_badge = '<span class="badge-low">Sales-led</span>'
        else:
            model_badge = '<span class="badge-low">Hybrid</span>'
        free_badge = '<span class="badge-ok">Free tier</span>' if d.get("has_free_tier") else '<span class="badge-high">No free</span>'
        comp_changes = [c for c in all_changes if c.get("competitor") == comp]
        with st.expander(f"{comp}  ·  Score: {score}/10  ·  {d.get('avg_rating', 0)}⭐  ·  {len(comp_changes)} changes", expanded=False):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f'<div style="font-size:1rem;font-weight:600;color:#e2e8f0;margin-bottom:0.4rem;">{d.get("headline", "—")}</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:0.82rem;color:#718096;margin-bottom:0.8rem;">{str(d.get("subheadline", ""))[:150]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:0.8rem;color:#a0aec0;">CTA: <span style="color:#63b3ed;font-style:italic;">"{d.get("cta", "—")}"</span></div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div style="text-align:right;">{model_badge}<br><br>{free_badge}<br><br><span style="font-size:0.78rem;color:#718096;">{d.get("avg_rating", 0)}⭐ · {d.get("review_count", 0):,} reviews</span></div>', unsafe_allow_html=True)
            plans = d.get("plans", [])
            prices = d.get("prices", [])
            if plans:
                st.markdown(f'<div style="font-size:0.78rem;color:#4a5568;margin-top:0.8rem;">Plans: {" · ".join(plans)}</div>', unsafe_allow_html=True)
            if prices:
                st.markdown(f'<div style="font-size:0.78rem;color:#4a5568;">Prices: {" · ".join(prices)}</div>', unsafe_allow_html=True)
            ad_count = d.get("ad_count", 0)
            if ad_count:
                st.markdown(f'<div style="font-size:0.78rem;color:#4a5568;">Meta Ads: {ad_count} active</div>', unsafe_allow_html=True)


# -----------------------------
# Page 3 — Score Leaderboard
# -----------------------------
elif page == "🏆 Score Leaderboard":
    st.markdown('<h1 style="font-size:1.6rem;font-weight:700;color:#e2e8f0;margin-bottom:0.25rem;">Score Leaderboard</h1>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.85rem;color:#718096;margin-bottom:2rem;">6 tiêu chí · Target audience: Product Manager / Growth</div>', unsafe_allow_html=True)
    scored = [(k, v) for k, v in latest.items() if v.get("score_total") or v.get("score_detail")]
    scored.sort(key=lambda x: x[1].get("score_total", 0), reverse=True)
    if not scored:
        st.info("Chưa có score data. Hãy tạo live_data.json hoặc mock_data.json.")
    else:
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, (comp, d) in enumerate(scored):
            score = d.get("score_total", 0)
            fill = int(score * 10)
            medal = medals[i] if i < len(medals) else f"{i + 1}."
            st.markdown(
                f'''<div class="card" style="margin-bottom:0.75rem;">
                <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.8rem;">
                    <span style="font-size:1.3rem;">{medal}</span>
                    <span style="font-weight:700;color:#e2e8f0;font-size:1.05rem;">{comp}</span>
                    <span style="margin-left:auto;font-size:1.4rem;font-weight:700;color:#63b3ed;">{score}<span style="font-size:0.9rem;color:#4a5568;">/10</span></span>
                </div>
                <div class="score-bar-bg"><div class="score-bar-fill" style="width:{fill}%;"></div></div>
            </div>''',
                unsafe_allow_html=True,
            )

        st.markdown('<div class="section-title">Score Breakdown per Criteria</div>', unsafe_allow_html=True)
        criteria_labels = {"clarity": "Clarity", "value_prop": "Value Prop", "cta_strength": "CTA", "social_proof": "Social Proof", "pricing_transparency": "Pricing", "audience_clarity": "Audience"}
        for comp, d in scored:
            detail = d.get("score_detail", {})
            scores_d = detail.get("scores", {}) if isinstance(detail, dict) else {}
            notes_d = detail.get("notes", {}) if isinstance(detail, dict) else {}
            if not scores_d:
                continue
            with st.expander(f"{comp} — breakdown", expanded=False):
                for key, label in criteria_labels.items():
                    s = scores_d.get(key, 0)
                    note = notes_d.get(key, "")
                    fill = int(s * 10)
                    color = "#68d391" if s >= 7 else "#f6c90e" if s >= 4 else "#fc8181"
                    st.markdown(
                        f'''<div style="margin-bottom:0.8rem;">
                        <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
                            <span style="font-size:0.8rem;color:#a0aec0;">{label}</span>
                            <span style="font-size:0.8rem;font-weight:600;color:{color};">{s}/10</span>
                        </div>
                        <div class="score-bar-bg"><div class="score-bar-fill" style="width:{fill}%;background:{color};"></div></div>
                        <div style="font-size:0.72rem;color:#4a5568;margin-top:3px;">{note}</div>
                    </div>''',
                        unsafe_allow_html=True,
                    )


# -----------------------------
# Page 4 — Changes timeline
# -----------------------------
elif page == "🔄 Changes Timeline":
    st.markdown('<h1 style="font-size:1.6rem;font-weight:700;color:#e2e8f0;margin-bottom:0.25rem;">Changes Timeline</h1>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.85rem;color:#718096;margin-bottom:2rem;">All detected changes — newest first</div>', unsafe_allow_html=True)
    if not competitors:
        st.info("Không có changes vì chưa có dashboard data.")
    else:
        fc1, fc2 = st.columns(2)
        with fc1:
            filter_comp = st.multiselect("Competitor", competitors, default=competitors)
        with fc2:
            filter_sev = st.multiselect("Severity", ["high", "low"], default=["high", "low"])
        filtered = [c for c in reversed(all_changes) if c.get("competitor", "") in filter_comp and c.get("severity", "low") in filter_sev]
        st.markdown(f'<div style="font-size:0.8rem;color:#4a5568;margin-bottom:1.5rem;">{len(filtered)} changes</div>', unsafe_allow_html=True)
        if not filtered:
            st.markdown('<div class="card" style="text-align:center;color:#4a5568;padding:3rem;">Không có changes. Cần chạy pipeline ít nhất 2 lần.</div>', unsafe_allow_html=True)
        else:
            cur_week = None
            for ch in filtered:
                week = ch.get("week") or ch.get("date", "")
                if week != cur_week:
                    cur_week = week
                    label = ch.get("label", week)
                    st.markdown(f'<div class="section-title">{label} · {week}</div>', unsafe_allow_html=True)
                sev = ch.get("severity", "low")
                badge = '<span class="badge-high">HIGH</span>' if sev == "high" else '<span class="badge-low">LOW</span>'
                note = ch.get("note", "")
                st.markdown(
                    f'''<div class="card">
                <div style="display:flex;align-items:center;gap:0.6rem;margin-bottom:0.8rem;">
                    <span style="font-weight:600;color:#e2e8f0;">{ch.get("competitor","")}</span>
                    {badge}
                    <span style="font-size:0.75rem;color:#4a5568;margin-left:auto;">{ch.get("field","").upper()}</span>
                </div>
                <div style="border-left:3px solid {"#c53030" if sev=="high" else "#2b6cb0"};padding-left:1rem;">
                    <div style="font-size:0.72rem;color:#4a5568;text-transform:uppercase;margin-bottom:3px;">Before</div>
                    <div class="change-before">{str(ch.get("before",""))[:120]}</div>
                    <div style="font-size:0.72rem;color:#4a5568;text-transform:uppercase;margin:6px 0 3px;">After</div>
                    <div class="change-after">{str(ch.get("after",""))[:120]}</div>
                    {"<div style='font-size:0.82rem;color:#718096;font-style:italic;margin-top:0.6rem;'>💡 " + note + "</div>" if note else ""}
                </div>
            </div>''',
                    unsafe_allow_html=True,
                )


# -----------------------------
# Page 5 — Competitor detail
# -----------------------------
elif page == "🔎 Competitor Detail":
    st.markdown('<h1 style="font-size:1.6rem;font-weight:700;color:#e2e8f0;margin-bottom:0.25rem;">Competitor Detail</h1>', unsafe_allow_html=True)
    if not competitors:
        st.info("Không có dashboard data.")
    else:
        selected = st.selectbox("Select competitor", competitors)
        d = latest.get(selected, {})
        comp_changes = [c for c in all_changes if c.get("competitor") == selected]
        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.markdown(f'<div class="card"><div class="metric-label">Score</div><div class="metric-value" style="color:#63b3ed;">{d.get("score_total",0)}</div><div class="metric-sub">out of 10</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown(f'<div class="card"><div class="metric-label">G2 Rating</div><div class="metric-value">{d.get("avg_rating",0)}</div><div class="metric-sub">{d.get("review_count",0):,} reviews</div></div>', unsafe_allow_html=True)
        with m3:
            model = d.get("pricing_model", "—")
            color = "#68d391" if model == "PLG" else "#63b3ed"
            st.markdown(f'<div class="card"><div class="metric-label">GTM Model</div><div class="metric-value" style="font-size:1.2rem;color:{color};padding-top:0.4rem;">{model}</div><div class="metric-sub"> </div></div>', unsafe_allow_html=True)
        with m4:
            ad_count = d.get("ad_count", 0)
            st.markdown(f'<div class="card"><div class="metric-label">Meta Ads</div><div class="metric-value">{ad_count}</div><div class="metric-sub">active ads</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Current Positioning</div>', unsafe_allow_html=True)
        st.markdown(f'''<div class="card-accent">
        <div style="font-size:1rem;font-weight:600;color:#e2e8f0;margin-bottom:0.4rem;">{d.get("headline","—")}</div>
        <div style="font-size:0.85rem;color:#718096;margin-bottom:0.8rem;">{d.get("subheadline","")[:200]}</div>
        <div style="font-size:0.82rem;"><span style="color:#4a5568;">CTA: </span><span style="color:#63b3ed;font-style:italic;">"{d.get("cta","—")}"</span></div>
    </div>''', unsafe_allow_html=True)
        detail = d.get("score_detail", {})
        scores_d = detail.get("scores", {}) if isinstance(detail, dict) else {}
        if scores_d:
            st.markdown('<div class="section-title">Score Detail</div>', unsafe_allow_html=True)
            criteria_labels = {"clarity": "Clarity", "value_prop": "Value Prop", "cta_strength": "CTA Strength", "social_proof": "Social Proof", "pricing_transparency": "Pricing", "audience_clarity": "Audience"}
            cols = st.columns(3)
            for i, (key, label) in enumerate(criteria_labels.items()):
                s = scores_d.get(key, 0)
                color = "#68d391" if s >= 7 else "#f6c90e" if s >= 4 else "#fc8181"
                with cols[i % 3]:
                    st.markdown(f'''<div class="card" style="padding:0.8rem 1rem;">
                    <div style="font-size:0.72rem;color:#4a5568;text-transform:uppercase;letter-spacing:0.08em;">{label}</div>
                    <div style="font-size:1.5rem;font-weight:700;color:{color};">{s}<span style="font-size:0.8rem;color:#4a5568;">/10</span></div>
                </div>''', unsafe_allow_html=True)
        if comp_changes:
            st.markdown('<div class="section-title">Changes History</div>', unsafe_allow_html=True)
            for ch in reversed(comp_changes):
                sev = ch.get("severity", "low")
                badge = '<span class="badge-high">HIGH</span>' if sev == "high" else '<span class="badge-low">LOW</span>'
                st.markdown(f'''<div class="card" style="margin-bottom:0.6rem;">
                <div style="display:flex;gap:0.5rem;align-items:center;margin-bottom:0.5rem;">
                    <span style="font-size:0.75rem;color:#718096;">{ch.get("week","")}</span>
                    <span style="font-size:0.75rem;font-weight:600;color:#a0aec0;text-transform:uppercase;">{ch.get("field","")}</span>
                    {badge}
                </div>
                <div class="change-before">{str(ch.get("before", ""))[:100]}</div>
                <div style="color:#4a5568;font-size:0.75rem;text-align:center;margin:3px 0;">↓</div>
                <div class="change-after">{str(ch.get("after", ""))[:100]}</div>
                {"<div style='font-size:0.8rem;color:#718096;font-style:italic;margin-top:0.5rem;'>💡 " + ch.get("note","") + "</div>" if ch.get("note") else ""}
            </div>''', unsafe_allow_html=True)


# -----------------------------
# Page 6 — A/B generator
# -----------------------------
elif page == "🧪 A/B Generator":
    st.markdown('<h1 style="font-size:1.6rem;font-weight:700;color:#e2e8f0;margin-bottom:0.25rem;">A/B Test Generator</h1>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.85rem;color:#718096;margin-bottom:2rem;">2 variants dựa trên competitive analysis · Target: PM/Growth</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Your Product Info</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        product_name = st.text_input("Tên sản phẩm của bạn", value="YourProduct")
    with col2:
        usp = st.text_input("USP / Điểm khác biệt", value="the fastest way to understand why users drop off")
    generate = st.button("⚡ Generate A/B Variants", type="primary")
    if generate or ab_variants:
        scored = [(k, v.get("score_total", 0)) for k, v in latest.items() if v.get("score_total")]
        scored.sort(key=lambda x: x[1], reverse=True)
        if scored:
            st.markdown('<div class="section-title">Competitor Score Context</div>', unsafe_allow_html=True)
            cols = st.columns(len(scored))
            for i, (comp, score) in enumerate(scored):
                medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i] if i < 5 else ""
                with cols[i]:
                    color = "#f6c90e" if i == 0 else "#a0aec0" if i == 1 else "#cd7f32" if i == 2 else "#4a5568"
                    st.markdown(f'<div class="card" style="text-align:center;padding:0.8rem;"><div style="font-size:1.1rem;">{medal}</div><div style="font-size:0.85rem;font-weight:600;color:{color};">{comp}</div><div style="font-size:1.2rem;font-weight:700;color:#e2e8f0;">{score}</div><div style="font-size:0.7rem;color:#4a5568;">/ 10</div></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">Generated Variants</div>', unsafe_allow_html=True)
        if ab_variants and not generate:
            va = ab_variants.get("variant_a", {})
            vb = ab_variants.get("variant_b", {})
            top_comp = ab_variants.get("top_competitor", "")
            overused = ab_variants.get("overused_words", [])
        else:
            top_comp = scored[0][0] if scored else ""
            top_data = latest.get(top_comp, {})
            orig_h = top_data.get("headline", "").lower()
            if "better" in orig_h:
                h_a = f"Build better products with {product_name}"
            elif "understand" in orig_h or "insight" in orig_h:
                h_a = f"Understand your users instantly with {product_name}"
            elif "data" in orig_h:
                h_a = f"Turn product data into decisions with {product_name}"
            else:
                h_a = f"The analytics platform built for product teams — {product_name}"
            va = {"headline": h_a, "sub": f"Join product teams who use {product_name} to {usp}", "cta": top_data.get("cta", "Start for free")}
            all_h = [v.get("headline", "").lower() for v in latest.values()]
            words = {}
            for h in all_h:
                for w in h.split():
                    if len(w) > 4:
                        words[w] = words.get(w, 0) + 1
            overused = [w for w, c in words.items() if c >= 2]
            if "analytics" in overused or "data" in overused:
                h_b = f"Stop analyzing. Start deciding. — {product_name}"
            elif "product" in overused:
                h_b = f"Your users are telling you something. {product_name} translates it."
            else:
                h_b = f"While they show charts, {product_name} shows answers."
            vb = {"headline": h_b, "sub": f"Not another dashboard. {usp.capitalize()} — in 10 minutes.", "cta": "See your first insight now"}
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f'''<div class="variant-card-a">
                <div class="variant-label" style="color:#63b3ed;">🔵 VARIANT A — Follow the Leader</div>
                <div style="font-size:0.75rem;color:#4a5568;margin-bottom:1rem;">Based on {top_comp} (top scorer)</div>
                <div class="variant-headline">{va.get("headline", "")}</div>
                <div class="variant-sub">{va.get("sub", "")}</div>
                <div class="variant-cta variant-cta-a">{va.get("cta", "")}</div>
            </div>''', unsafe_allow_html=True)
        with col_b:
            st.markdown(f'''<div class="variant-card-b">
                <div class="variant-label" style="color:#b794f4;">🟣 VARIANT B — Contrarian</div>
                <div style="font-size:0.75rem;color:#4a5568;margin-bottom:1rem;">Goes against category norms</div>
                <div class="variant-headline">{vb.get("headline", "")}</div>
                <div class="variant-sub">{vb.get("sub", "")}</div>
                <div class="variant-cta variant-cta-b">{vb.get("cta", "")}</div>
            </div>''', unsafe_allow_html=True)


# -----------------------------
# Page 7 — Ads Transparency
# -----------------------------
elif page == "📣 Ads Transparency":
    st.markdown('<h1 style="font-size:1.6rem;font-weight:700;color:#e2e8f0;margin-bottom:0.25rem;">Ads Transparency</h1>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.85rem;color:#718096;margin-bottom:2rem;">Scrape Meta Ads Library + Google Ads Transparency Center cho website/brand đối thủ.</div>', unsafe_allow_html=True)

    with st.sidebar:
        st.markdown('<div class="section-title">Ads inputs</div>', unsafe_allow_html=True)
        raw_input = st.text_area(
            "Websites / brand names",
            value="https://amplitude.com\nhttps://mixpanel.com\nhttps://posthog.com",
            height=140,
            help="One per line. You can paste a full URL, a domain, or a brand name.",
            key="ads_raw_input",
        )
        country = st.text_input("Meta country code", value="VN", max_chars=2, key="ads_country")
        max_results = st.slider("Max results per source", min_value=1, max_value=20, value=5, key="ads_max_results")
        timeout_s = st.slider("Timeout (seconds)", min_value=5, max_value=30, value=15, key="ads_timeout")
        run_button = st.button("Scrape now", type="primary", key="ads_run_button")

    inputs = tuple(line.strip() for line in raw_input.splitlines() if line.strip())
    if run_button:
        if not inputs:
            st.warning("Please add at least one website or brand name.")
        else:
            with st.spinner("Scraping transparency pages..."):
                rows, summary = scrape_all_ads(inputs, country.strip() or "VN", timeout_s, max_results)
            st.session_state["ads_rows"] = rows
            st.session_state["ads_summary"] = summary
            st.session_state["ads_ran_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

    rows = st.session_state.get("ads_rows", [])
    summary = st.session_state.get("ads_summary", {"inputs": 0, "meta_rows": 0, "google_rows": 0, "failed_inputs": 0})

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'<div class="card"><div class="muted">Inputs</div><div class="metric">{summary.get("inputs", 0)}</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="card"><div class="muted">Meta rows</div><div class="metric">{summary.get("meta_rows", 0)}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="card"><div class="muted">Google rows</div><div class="metric">{summary.get("google_rows", 0)}</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="card"><div class="muted">Failed inputs</div><div class="metric">{summary.get("failed_inputs", 0)}</div></div>', unsafe_allow_html=True)

    st.markdown("---")
    if not rows:
        st.info("Paste websites/brand names in the sidebar and click **Scrape now**.")
    else:
        df = pd.DataFrame(rows)
        if "collected_at" in df.columns:
            df["collected_at"] = pd.to_datetime(df["collected_at"], errors="coerce")
        for col in ["source", "brand", "status", "title", "snippet", "source_url", "landing_url", "notes"]:
            if col not in df.columns:
                df[col] = ""

        st.subheader("Results")
        tab1, tab2, tab3 = st.tabs(["All results", "Meta", "Google"])
        with tab1:
            st.dataframe(df[[c for c in ["source", "brand", "status", "title", "snippet", "source_url", "landing_url", "collected_at", "notes"] if c in df.columns]], use_container_width=True, hide_index=True)
        with tab2:
            st.dataframe(df[df["source"] == "meta"], use_container_width=True, hide_index=True)
        with tab3:
            st.dataframe(df[df["source"] == "google"], use_container_width=True, hide_index=True)

        st.subheader("Export")
        export_df = pd.DataFrame(rows)
        csv_bytes = export_df.to_csv(index=False).encode("utf-8")
        json_bytes = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")
        col_a, col_b = st.columns(2)
        with col_a:
            st.download_button("Download CSV", data=csv_bytes, file_name=f"ads_scrape_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv", mime="text/csv", use_container_width=True)
        with col_b:
            st.download_button("Download JSON", data=json_bytes, file_name=f"ads_scrape_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json", mime="application/json", use_container_width=True)

    st.caption("Public transparency pages can change structure over time. If a result is missing, the app returns a diagnostic row instead of crashing.")
