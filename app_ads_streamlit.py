from __future__ import annotations

"""Streamlit app to collect Meta Ads and Google Ads transparency signals for competitor websites.

Design goals:
- Single-file app that can be renamed to app.py and deployed on Streamlit Community Cloud.
- Input websites/domains or brand names.
- Best-effort scraping with graceful fallbacks (public pages can change often).
- Export results to CSV/JSON for GitHub sync.

Dependencies:
    streamlit
    requests
    beautifulsoup4
    pandas

Notes:
- This app uses public transparency pages and may return partial data if a platform blocks requests,
  renders results dynamically, or changes its page structure.
- For reliable production use, add official API credentials where available and comply with each
  platform's terms of service.
"""

from dataclasses import dataclass, asdict
from datetime import datetime
import hashlib
import json
import re
from io import StringIO
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import quote_plus, urlparse

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup


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


# -----------------------------------------------------------------------------
# UI
# -----------------------------------------------------------------------------
st.set_page_config(page_title="Ad Transparency Scraper", page_icon="📣", layout="wide")
st.markdown(
    """
    <style>
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    .small-note { color: #667085; font-size: 0.9rem; }
    .card {
        border: 1px solid #e5e7eb; border-radius: 16px; padding: 1rem 1.1rem; margin-bottom: 0.9rem;
        background: white;
    }
    .metric { font-size: 1.6rem; font-weight: 700; }
    .muted { color: #6b7280; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Meta Ads + Google Ads scraper")
st.caption("Best-effort transparency scraper for competitor websites. Rename this file to app.py for Streamlit Cloud.")

with st.sidebar:
    st.header("Inputs")
    raw_input = st.text_area(
        "Websites / brand names",
        value="https://amplitude.com\nhttps://mixpanel.com\nhttps://posthog.com",
        height=140,
        help="One per line. You can paste a full URL, a domain, or a brand name.",
    )
    country = st.text_input("Meta country code", value="VN", max_chars=2)
    max_results = st.slider("Max results per source", min_value=1, max_value=20, value=5)
    timeout_s = st.slider("Timeout (seconds)", min_value=5, max_value=30, value=15)
    run_button = st.button("Scrape now", type="primary")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _brand_from_input(value: str) -> tuple[str, str]:
    value = (value or "").strip()
    if not value:
        return "", ""
    if "://" in value:
        parsed = urlparse(value)
        host = parsed.netloc or parsed.path
        host = host.replace("www.", "")
        brand = host.split(".")[0].replace("-", " ").title()
        return brand or value, value
    if "." in value and " " not in value:
        host = value.replace("www.", "")
        brand = host.split(".")[0].replace("-", " ").title()
        return brand or value, f"https://{value}"
    return value.title(), value


def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


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


def _hash_record(rec: dict) -> str:
    payload = json.dumps(rec, sort_keys=True, ensure_ascii=False)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _parse_hrefs(html: str, pattern: str) -> list[str]:
    hrefs = re.findall(r'href=["\'](.*?)["\']', html, flags=re.I)
    out = []
    seen = set()
    for href in hrefs:
        if re.search(pattern, href, flags=re.I):
            if href not in seen:
                seen.add(href)
                out.append(href)
    return out


def _guess_landing_from_text(text: str) -> str:
    urls = re.findall(r"https?://[^\s\"'<>]+", text or "", flags=re.I)
    return urls[0] if urls else ""


def _parse_meta_public_page(html: str, brand: str, input_value: str, query_used: str, source_url: str) -> list[AdRecord]:
    # Best-effort parsing from public HTML. This is intentionally conservative.
    records: list[AdRecord] = []
    soup = BeautifulSoup(html, "html.parser")

    # Pull candidate snippets from visible text blocks, keeping only short-ish blocks likely to be ad cards.
    blocks = []
    for tag in soup.find_all(["div", "span", "p", "a"]):
        txt = _clean(tag.get_text(" ", strip=True))
        if 20 <= len(txt) <= 280:
            blocks.append(txt)

    # Heuristically pick blocks that mention ad-related words or the brand.
    candidates = []
    brand_l = brand.lower()
    for b in blocks:
        bl = b.lower()
        if any(k in bl for k in ["ad", "advert", "sponsored", "library", "active", "running"]) or brand_l in bl:
            candidates.append(b)

    # Deduplicate and trim.
    uniq = []
    seen = set()
    for c in candidates[: max(20, max_results * 4)]:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            uniq.append(c)

    hrefs = _parse_hrefs(html, r"ads/library|adstransparency|transparency")
    ad_links = hrefs[:max_results]

    # Create rows from found text.
    for idx, c in enumerate(uniq[:max_results]):
        rec = AdRecord(
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
        records.append(rec)

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
        # Quick signal that the page was fetched successfully.
        page_meta = _extract_title_and_meta(html)
        records = _parse_meta_public_page(html, brand, input_value, q, url)
        if records:
            results.extend(records)
            break
        # Keep at least one diagnostic record if the page loaded but parsing failed.
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

    # Fallback: if nothing at all found, return one diagnostic row.
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


def _parse_google_transparency(html: str, brand: str, input_value: str, query_used: str, source_url: str) -> list[AdRecord]:
    soup = BeautifulSoup(html, "html.parser")
    records: list[AdRecord] = []

    # Many transparency pages include a visible title + snippets. Use a conservative heuristic.
    text_blocks = []
    for tag in soup.find_all(["div", "span", "p", "a", "li"]):
        txt = _clean(tag.get_text(" ", strip=True))
        if 15 <= len(txt) <= 260:
            text_blocks.append(txt)

    # Prefer blocks that look like advertiser / location / ad copy.
    candidates = []
    brand_l = brand.lower()
    for b in text_blocks:
        bl = b.lower()
        if brand_l in bl or any(k in bl for k in ["advertiser", "ads", "transparency", "served", "displayed"]):
            candidates.append(b)

    # Extract likely transparency links.
    hrefs = _parse_hrefs(html, r"adstransparency\.google\.com|google\.com/adstransparency")

    seen = set()
    for idx, c in enumerate(candidates[:max_results]):
        key = c.lower()
        if key in seen:
            continue
        seen.add(key)
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
        records = _parse_google_transparency(html, brand, input_value, q, url)
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
def scrape_all(inputs: tuple[str, ...], country_code: str, timeout_s: int, max_results: int) -> tuple[list[dict], dict]:
    all_rows: list[dict] = []
    summary = {
        "inputs": len(inputs),
        "meta_rows": 0,
        "google_rows": 0,
        "failed_inputs": 0,
    }

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
        if all(x.status in {"not_found"} for x in meta_rows + google_rows):
            summary["failed_inputs"] += 1

    return all_rows, summary


# -----------------------------------------------------------------------------
# Run
# -----------------------------------------------------------------------------
inputs = tuple(line.strip() for line in raw_input.splitlines() if line.strip())

if run_button:
    if not inputs:
        st.warning("Please add at least one website or brand name.")
    else:
        with st.spinner("Scraping transparency pages..."):
            rows, summary = scrape_all(inputs, country.strip() or "VN", timeout_s, max_results)
        st.session_state["rows"] = rows
        st.session_state["summary"] = summary
        st.session_state["ran_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"

rows = st.session_state.get("rows", [])
summary = st.session_state.get("summary", {"inputs": 0, "meta_rows": 0, "google_rows": 0, "failed_inputs": 0})

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
        st.dataframe(
            df[[c for c in [
                "source", "brand", "status", "title", "snippet", "source_url", "landing_url", "collected_at", "notes"
            ] if c in df.columns]],
            use_container_width=True,
            hide_index=True,
        )

    with tab2:
        meta_df = df[df["source"] == "meta"]
        st.dataframe(meta_df, use_container_width=True, hide_index=True)

    with tab3:
        google_df = df[df["source"] == "google"]
        st.dataframe(google_df, use_container_width=True, hide_index=True)

    st.subheader("Export")
    export_df = pd.DataFrame(rows)
    csv_bytes = export_df.to_csv(index=False).encode("utf-8")
    json_bytes = json.dumps(rows, ensure_ascii=False, indent=2).encode("utf-8")

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name=f"ads_scrape_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True,
        )
    with col_b:
        st.download_button(
            "Download JSON",
            data=json_bytes,
            file_name=f"ads_scrape_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True,
        )

    st.subheader("GitHub / Streamlit setup")
    st.code(
        """# 1) Rename this file to app.py\n# 2) Add requirements.txt with:\nstreamlit\nrequests\nbeautifulsoup4\npandas\n# 3) Push to GitHub\n# 4) Deploy on Streamlit Community Cloud\n""",
        language="text",
    )

st.caption(
    "Public transparency pages can change structure over time. If a result is missing, the app returns a diagnostic row instead of crashing."
)
