import streamlit as st
import json, os, time
from datetime import datetime

# ── Page config ────────────────────────────────────────────────
st.set_page_config(
    page_title="Competitor Intel",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Styling ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.stApp { background-color: #0f1117; }
section[data-testid="stSidebar"] { background-color: #161b27 !important; border-right: 1px solid #1e2535; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2.5rem 3rem; max-width: 1200px; }
.card { background: #161b27; border: 1px solid #1e2535; border-radius: 12px; padding: 1.25rem 1.5rem; margin-bottom: 1rem; }
.card-accent { background: linear-gradient(135deg,#161b27,#1a2035); border: 1px solid #2a3550; border-radius: 12px; padding: 1.25rem 1.5rem; margin-bottom: 1rem; }
.metric-label { font-size:0.72rem; font-weight:600; letter-spacing:0.08em; text-transform:uppercase; color:#4a5568; margin-bottom:0.3rem; }
.metric-value { font-size:2rem; font-weight:700; color:#e2e8f0; line-height:1; }
.metric-sub   { font-size:0.78rem; color:#4a5568; margin-top:0.25rem; }
.badge-high { background:#2d1b1b; color:#fc8181; border:1px solid #c53030; border-radius:6px; padding:2px 10px; font-size:0.72rem; font-weight:600; }
.badge-low  { background:#1a2535; color:#63b3ed; border:1px solid #2b6cb0; border-radius:6px; padding:2px 10px; font-size:0.72rem; font-weight:600; }
.badge-ok   { background:#1a2d1e; color:#68d391; border:1px solid #2f855a; border-radius:6px; padding:2px 10px; font-size:0.72rem; font-weight:600; }
.section-title { font-size:0.7rem; font-weight:700; letter-spacing:0.12em; text-transform:uppercase; color:#4a5568; margin:2rem 0 1rem; }
.nav-label { font-size:0.68rem; font-weight:700; letter-spacing:0.1em; text-transform:uppercase; color:#4a5568; padding:1rem 0 0.5rem; }
.score-bar-bg   { background:#1e2535; border-radius:4px; height:8px; width:100%; margin-top:4px; }
.score-bar-fill { background:linear-gradient(90deg,#4299e1,#63b3ed); border-radius:4px; height:8px; }
.change-before { font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:#fc8181; background:#1a1010; padding:0.4rem 0.7rem; border-radius:6px; margin-bottom:0.3rem; }
.change-after  { font-family:'JetBrains Mono',monospace; font-size:0.8rem; color:#68d391; background:#101a12; padding:0.4rem 0.7rem; border-radius:6px; }
.variant-card-a { background:linear-gradient(135deg,#0d1f2d,#102030); border:1px solid #2b6cb0; border-radius:12px; padding:1.5rem; }
.variant-card-b { background:linear-gradient(135deg,#1a0d2d,#1e0f35); border:1px solid #6b46c1; border-radius:12px; padding:1.5rem; }
.variant-headline { font-size:1.3rem; font-weight:700; color:#e2e8f0; margin-bottom:0.5rem; line-height:1.3; }
.variant-sub { font-size:0.88rem; color:#a0aec0; margin-bottom:1rem; }
.variant-cta-a { display:inline-block; background:#2b6cb0; color:#bee3f8; padding:0.5rem 1.2rem; border-radius:8px; font-size:0.85rem; font-weight:600; }
.variant-cta-b { display:inline-block; background:#553c9a; color:#e9d8fd; padding:0.5rem 1.2rem; border-radius:8px; font-size:0.85rem; font-weight:600; }
</style>
""", unsafe_allow_html=True)


# ── Competitors config ─────────────────────────────────────────
COMPETITORS = [
    {'name': 'Amplitude',  'landing_url': 'https://amplitude.com',       'g2_slug': 'amplitude'},
    {'name': 'Mixpanel',   'landing_url': 'https://mixpanel.com',        'g2_slug': 'mixpanel'},
    {'name': 'PostHog',    'landing_url': 'https://posthog.com',         'g2_slug': 'posthog'},
    {'name': 'Heap',       'landing_url': 'https://heap.io',             'g2_slug': 'heap'},
    {'name': 'Pendo',      'landing_url': 'https://www.pendo.io',        'g2_slug': 'pendo'},
]


# ── Import scrapers ────────────────────────────────────────────
try:
    from scraper_landing import scrape_landing
    from scraper_g2 import get_reviews_data
    SCRAPERS_AVAILABLE = True
except ImportError:
    SCRAPERS_AVAILABLE = False


# ── Scrape all competitors ─────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def run_scrape() -> dict:
    """
    Scrape tất cả competitors real-time.
    Cache 1 giờ — bấm Refresh để scrape lại.
    """
    results = {}
    for c in COMPETITORS:
        name    = c['name']
        landing = scrape_landing(c['landing_url']) if SCRAPERS_AVAILABLE else {}
        time.sleep(1)
        reviews = get_reviews_data(c['g2_slug']) if SCRAPERS_AVAILABLE else {}
        results[name] = {**landing, **reviews, 'competitor': name}
    return {
        'data'        : results,
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'source'      : 'live_scrape'
    }


# ── Session state — giữ data giữa các lần bấm ─────────────────
if 'scraped_data' not in st.session_state:
    st.session_state.scraped_data = None
if 'is_loading' not in st.session_state:
    st.session_state.is_loading = False


# ── Sidebar ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="padding:1rem 0 0.25rem;"><span style="font-size:1.3rem;">🔍</span> <span style="font-weight:700;color:#e2e8f0;font-size:1rem;">Competitor Intel</span></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.75rem;color:#4a5568;margin-bottom:1.5rem;">Product Analytics · PMM Portfolio</div>', unsafe_allow_html=True)

    st.markdown('<div class="nav-label">Navigation</div>', unsafe_allow_html=True)
    page = st.radio("", [
        "📊 Overview",
        "🏆 Score Leaderboard",
        "🔎 Competitor Detail",
        "🧪 A/B Generator"
    ], label_visibility="collapsed")

    st.markdown("---")
    st.markdown('<div class="nav-label">Data</div>', unsafe_allow_html=True)

    scraper_badge = '🟢 Scrapers ready' if SCRAPERS_AVAILABLE else '🔴 Scrapers not found'
    st.markdown(f'<div style="font-size:0.8rem;color:#718096;margin-bottom:0.8rem;">{scraper_badge}</div>', unsafe_allow_html=True)

    # Refresh button
    if st.button("🔄 Refresh data", use_container_width=True):
        run_scrape.clear()
        st.session_state.scraped_data = None
        st.rerun()

    # Last updated
    if st.session_state.scraped_data:
        lu = st.session_state.scraped_data.get('last_updated', '')
        st.markdown(f'<div style="font-size:0.72rem;color:#4a5568;margin-top:0.5rem;">Last scraped:<br>{lu}</div>', unsafe_allow_html=True)


# ── Load / scrape data ─────────────────────────────────────────
if st.session_state.scraped_data is None:
    if not SCRAPERS_AVAILABLE:
        st.error("⚠️ Không tìm thấy `scraper_landing.py` hoặc `scraper_g2.py`. Đảm bảo 2 files này có trong cùng thư mục với `app.py`.")
        st.stop()

    with st.spinner("⏳ Đang scrape data real-time từ 5 competitors..."):
        st.session_state.scraped_data = run_scrape()

scraped   = st.session_state.scraped_data
latest    = scraped.get('data', {})
comp_names = [c['name'] for c in COMPETITORS]


# ══════════════════════════════════════════════════════════════════
# PAGE 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════════
if page == "📊 Overview":
    st.markdown('<h1 style="font-size:1.6rem;font-weight:700;color:#e2e8f0;margin-bottom:0.25rem;">Market Overview</h1>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:0.85rem;color:#718096;margin-bottom:2rem;">Product Analytics · {len(comp_names)} competitors · Real-time scrape · Target: PM/Growth</div>', unsafe_allow_html=True)

    # Top metrics
    c1, c2, c3, c4 = st.columns(4)
    has_data   = sum(1 for d in latest.values() if d.get('headline'))
    avg_rating = round(sum(d.get('avg_rating', 0) for d in latest.values()) / max(len(latest), 1), 1)
    top_rated  = max(latest.items(), key=lambda x: x[1].get('avg_rating', 0))[0] if latest else '—'

    with c1:
        st.markdown(f'<div class="card"><div class="metric-label">Competitors</div><div class="metric-value">{len(comp_names)}</div><div class="metric-sub">tracked</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="card"><div class="metric-label">Scraped OK</div><div class="metric-value" style="color:#68d391;">{has_data}</div><div class="metric-sub">of {len(comp_names)}</div></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="card"><div class="metric-label">Avg G2 Rating</div><div class="metric-value">{avg_rating}</div><div class="metric-sub">across category</div></div>', unsafe_allow_html=True)
    with c4:
        st.markdown(f'<div class="card"><div class="metric-label">Top Rated</div><div class="metric-value" style="font-size:1.2rem;padding-top:0.4rem;">{top_rated}</div><div class="metric-sub">by G2</div></div>', unsafe_allow_html=True)

    # Competitor cards
    st.markdown('<div class="section-title">Current Snapshot — Real-time</div>', unsafe_allow_html=True)

    for comp in comp_names:
        d = latest.get(comp, {})
        headline = d.get('headline', '')
        rating   = d.get('avg_rating', 0)
        count    = d.get('review_count', 0)
        source   = d.get('source', '')
        cta      = d.get('cta', '')

        status_icon = '🟢' if headline else '🔴'
        src_label   = {'g2_api': 'G2 API', 'capterra': 'Capterra',
                       'hardcoded_q4_2024': 'Hardcoded', 'failed': 'Failed'}.get(source, source)

        with st.expander(f"{status_icon}  {comp}  ·  {rating}⭐  ·  {count:,} reviews", expanded=False):
            if headline:
                st.markdown(f'<div style="font-size:1rem;font-weight:600;color:#e2e8f0;margin-bottom:0.4rem;">{headline}</div>', unsafe_allow_html=True)
                sub = d.get('subheadline', '')
                if sub:
                    st.markdown(f'<div style="font-size:0.82rem;color:#718096;margin-bottom:0.6rem;">{sub[:150]}</div>', unsafe_allow_html=True)
                if cta:
                    st.markdown(f'<div style="font-size:0.8rem;color:#a0aec0;">CTA: <span style="color:#63b3ed;font-style:italic;">"{cta}"</span></div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:#fc8181;font-size:0.85rem;">⚠️ Không lấy được headline — trang có thể dùng JS rendering</div>', unsafe_allow_html=True)

            st.markdown(f'<div style="font-size:0.72rem;color:#4a5568;margin-top:0.8rem;">Rating source: {src_label}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# PAGE 2 — SCORE LEADERBOARD
# ══════════════════════════════════════════════════════════════════
elif page == "🏆 Score Leaderboard":
    st.markdown('<h1 style="font-size:1.6rem;font-weight:700;color:#e2e8f0;margin-bottom:0.25rem;">Score Leaderboard</h1>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.85rem;color:#718096;margin-bottom:2rem;">Dựa trên G2 rating + review count từ real-time scrape</div>', unsafe_allow_html=True)

    # Score đơn giản dựa trên G2 rating + review count (không cần full scoring engine)
    def simple_score(d):
        rating = d.get('avg_rating', 0)
        count  = d.get('review_count', 0)
        r_score = (rating / 5.0) * 6          # max 6 điểm từ rating
        c_score = min(4, count / 3000)         # max 4 điểm từ review count
        return round(r_score + c_score, 1)

    scored = [(name, latest.get(name, {})) for name in comp_names]
    scored.sort(key=lambda x: simple_score(x[1]), reverse=True)

    medals = ['🥇','🥈','🥉','4️⃣','5️⃣']
    for i, (comp, d) in enumerate(scored):
        score = simple_score(d)
        fill  = int(score * 10)
        medal = medals[i] if i < len(medals) else f'{i+1}.'
        rating = d.get('avg_rating', 0)
        count  = d.get('review_count', 0)

        st.markdown(f'''<div class="card" style="margin-bottom:0.75rem;">
            <div style="display:flex;align-items:center;gap:0.75rem;margin-bottom:0.6rem;">
                <span style="font-size:1.3rem;">{medal}</span>
                <span style="font-weight:700;color:#e2e8f0;font-size:1.05rem;">{comp}</span>
                <span style="margin-left:auto;font-size:0.82rem;color:#718096;">{rating}⭐ · {count:,} reviews</span>
                <span style="font-size:1.4rem;font-weight:700;color:#63b3ed;">{score}<span style="font-size:0.85rem;color:#4a5568;">/10</span></span>
            </div>
            <div class="score-bar-bg"><div class="score-bar-fill" style="width:{fill}%;"></div></div>
        </div>''', unsafe_allow_html=True)

    st.markdown('<div style="font-size:0.75rem;color:#4a5568;margin-top:1rem;">Score = G2 rating (60%) + review volume (40%). Chạy Colab notebook để có full 6-criteria scoring.</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# PAGE 3 — COMPETITOR DETAIL
# ══════════════════════════════════════════════════════════════════
elif page == "🔎 Competitor Detail":
    st.markdown('<h1 style="font-size:1.6rem;font-weight:700;color:#e2e8f0;margin-bottom:0.25rem;">Competitor Detail</h1>', unsafe_allow_html=True)

    selected = st.selectbox("Select competitor", comp_names)
    d        = latest.get(selected, {})

    m1, m2, m3 = st.columns(3)
    with m1:
        st.markdown(f'<div class="card"><div class="metric-label">G2 Rating</div><div class="metric-value">{d.get("avg_rating",0)}</div><div class="metric-sub">{d.get("review_count",0):,} reviews</div></div>', unsafe_allow_html=True)
    with m2:
        src = d.get('source','—')
        src_label = {'g2_api':'G2 API','capterra':'Capterra','hardcoded_q4_2024':'Hardcoded','failed':'Failed'}.get(src, src)
        st.markdown(f'<div class="card"><div class="metric-label">Data source</div><div class="metric-value" style="font-size:1rem;padding-top:0.5rem;">{src_label}</div><div class="metric-sub"> </div></div>', unsafe_allow_html=True)
    with m3:
        headline_ok = '✅ OK' if d.get('headline') else '❌ Empty'
        color = '#68d391' if d.get('headline') else '#fc8181'
        st.markdown(f'<div class="card"><div class="metric-label">Headline</div><div class="metric-value" style="font-size:1rem;color:{color};padding-top:0.5rem;">{headline_ok}</div><div class="metric-sub"> </div></div>', unsafe_allow_html=True)

    # Positioning
    st.markdown('<div class="section-title">Current Positioning</div>', unsafe_allow_html=True)
    if d.get('headline'):
        st.markdown(f'''<div class="card-accent">
            <div style="font-size:1rem;font-weight:600;color:#e2e8f0;margin-bottom:0.4rem;">{d.get("headline","—")}</div>
            <div style="font-size:0.85rem;color:#718096;margin-bottom:0.8rem;">{d.get("subheadline","")[:200]}</div>
            <div style="font-size:0.82rem;"><span style="color:#4a5568;">CTA: </span><span style="color:#63b3ed;font-style:italic;">"{d.get("cta","—")}"</span></div>
        </div>''', unsafe_allow_html=True)
    else:
        st.warning(f"Không lấy được data từ {selected}. Trang có thể dùng JavaScript rendering — cần Playwright để scrape.")

    # Raw data
    with st.expander("Raw data", expanded=False):
        st.json(d)


# ══════════════════════════════════════════════════════════════════
# PAGE 4 — A/B GENERATOR
# ══════════════════════════════════════════════════════════════════
elif page == "🧪 A/B Generator":
    st.markdown('<h1 style="font-size:1.6rem;font-weight:700;color:#e2e8f0;margin-bottom:0.25rem;">A/B Test Generator</h1>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.85rem;color:#718096;margin-bottom:2rem;">2 variants từ competitive analysis · Target: PM/Growth</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        product_name = st.text_input("Tên sản phẩm của bạn", value="YourProduct")
    with col2:
        usp = st.text_input("USP / Điểm khác biệt", value="the fastest way to understand why users drop off")

    if st.button("⚡ Generate A/B Variants", type="primary"):

        # Tìm top competitor có headline
        ranked = sorted(
            [(n, d) for n, d in latest.items() if d.get('headline')],
            key=lambda x: x[1].get('avg_rating', 0),
            reverse=True
        )
        top_comp = ranked[0][0] if ranked else ''
        top_data = latest.get(top_comp, {})
        orig_h   = top_data.get('headline', '').lower()

        # Variant A
        if 'better' in orig_h:
            h_a = f'Build better products with {product_name}'
        elif 'understand' in orig_h or 'insight' in orig_h:
            h_a = f'Understand your users instantly with {product_name}'
        elif 'data' in orig_h or 'analytic' in orig_h:
            h_a = f'Turn product data into decisions with {product_name}'
        else:
            h_a = f'The analytics platform built for product teams — {product_name}'

        va = {
            'headline': h_a,
            'sub'     : f'Join product teams who use {product_name} to {usp}',
            'cta'     : top_data.get('cta', 'Start for free')
        }

        # Variant B — Contrarian
        all_headlines = [d.get('headline','').lower() for d in latest.values() if d.get('headline')]
        words = {}
        for h in all_headlines:
            for w in h.split():
                if len(w) > 4:
                    words[w] = words.get(w, 0) + 1
        overused = [w for w, c in words.items() if c >= 2]

        if 'analytic' in ' '.join(overused) or 'data' in overused:
            h_b = f'Stop analyzing. Start deciding. — {product_name}'
        elif 'product' in overused:
            h_b = f'Your users are telling you something. {product_name} translates it.'
        else:
            h_b = f'While others show charts, {product_name} shows answers.'

        vb = {
            'headline': h_b,
            'sub'     : f'Not another dashboard. {usp.capitalize()} — in 10 minutes.',
            'cta'     : 'See your first insight now'
        }

        # Display
        st.markdown('<div class="section-title">Based on real-time scrape</div>', unsafe_allow_html=True)
        if top_comp:
            st.markdown(f'<div style="font-size:0.8rem;color:#718096;margin-bottom:1.5rem;">Top competitor: <span style="color:#e2e8f0;font-weight:600;">{top_comp}</span> ({latest.get(top_comp,{}).get("avg_rating",0)}⭐) · Overused words: <span style="color:#b794f4;">{", ".join(overused[:5]) or "none"}</span></div>', unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown(f'''<div class="variant-card-a">
                <div style="font-size:0.72rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#63b3ed;margin-bottom:0.5rem;">🔵 VARIANT A — Follow the Leader</div>
                <div style="font-size:0.72rem;color:#4a5568;margin-bottom:1rem;">Based on {top_comp}</div>
                <div class="variant-headline">{va["headline"]}</div>
                <div class="variant-sub">{va["sub"]}</div>
                <div class="variant-cta-a">{va["cta"]}</div>
                <div style="margin-top:1rem;padding-top:1rem;border-top:1px solid #2b6cb0;font-size:0.8rem;color:#718096;">
                    Copy structure của top rated competitor — proven với PM/Growth audience
                </div>
            </div>''', unsafe_allow_html=True)

        with col_b:
            st.markdown(f'''<div class="variant-card-b">
                <div style="font-size:0.72rem;font-weight:700;letter-spacing:0.1em;text-transform:uppercase;color:#b794f4;margin-bottom:0.5rem;">🟣 VARIANT B — Contrarian</div>
                <div style="font-size:0.72rem;color:#4a5568;margin-bottom:1rem;">Against category norms</div>
                <div class="variant-headline">{vb["headline"]}</div>
                <div class="variant-sub">{vb["sub"]}</div>
                <div class="variant-cta-b">{vb["cta"]}</div>
                <div style="margin-top:1rem;padding-top:1rem;border-top:1px solid #6b46c1;font-size:0.8rem;color:#718096;">
                    Overused: <span style="color:#b794f4;">{", ".join(overused[:4]) or "N/A"}</span> → ZAG sang outcomes
                </div>
            </div>''', unsafe_allow_html=True)
