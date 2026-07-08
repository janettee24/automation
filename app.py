import streamlit as st
import json
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

/* Background */
.stApp { background-color: #0f1117; }
section[data-testid="stSidebar"] { background-color: #161b27 !important; border-right: 1px solid #1e2535; }

/* Hide default streamlit elements */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 2rem 2.5rem 3rem; max-width: 1200px; }

/* Cards */
.card {
    background: #161b27;
    border: 1px solid #1e2535;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}
.card-highlight {
    background: linear-gradient(135deg, #161b27 0%, #1a2035 100%);
    border: 1px solid #2a3550;
    border-radius: 12px;
    padding: 1.25rem 1.5rem;
    margin-bottom: 1rem;
}

/* Metrics */
.metric-label { font-size: 0.72rem; font-weight: 600; letter-spacing: 0.08em; text-transform: uppercase; color: #4a5568; margin-bottom: 0.3rem; }
.metric-value { font-size: 2rem; font-weight: 700; color: #e2e8f0; line-height: 1; }
.metric-sub   { font-size: 0.78rem; color: #4a5568; margin-top: 0.25rem; }

/* Badges */
.badge-high { background: #2d1b1b; color: #fc8181; border: 1px solid #c53030; border-radius: 6px; padding: 2px 10px; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em; }
.badge-low  { background: #1a2535; color: #63b3ed; border: 1px solid #2b6cb0; border-radius: 6px; padding: 2px 10px; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em; }
.badge-ok   { background: #1a2d1e; color: #68d391; border: 1px solid #2f855a; border-radius: 6px; padding: 2px 10px; font-size: 0.72rem; font-weight: 600; letter-spacing: 0.04em; }

/* Section header */
.section-title { font-size: 0.7rem; font-weight: 700; letter-spacing: 0.12em; text-transform: uppercase; color: #4a5568; margin: 2rem 0 1rem; }

/* Change row */
.change-row { border-left: 3px solid #c53030; padding-left: 1rem; margin-bottom: 1.5rem; }
.change-row-low { border-left: 3px solid #2b6cb0; padding-left: 1rem; margin-bottom: 1.5rem; }
.change-field { font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase; color: #a0aec0; margin-bottom: 0.4rem; }
.change-before { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #fc8181; background: #1a1010; padding: 0.4rem 0.7rem; border-radius: 6px; margin-bottom: 0.3rem; }
.change-after  { font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #68d391; background: #101a12; padding: 0.4rem 0.7rem; border-radius: 6px; margin-bottom: 0.4rem; }
.change-note { font-size: 0.82rem; color: #718096; font-style: italic; }

/* Competitor pill */
.comp-pill { display: inline-block; background: #1e2535; color: #a0aec0; border-radius: 20px; padding: 3px 12px; font-size: 0.78rem; font-weight: 500; margin-right: 6px; }

/* Stars */
.stars { color: #f6c90e; font-size: 0.9rem; }

/* Nav label */
.nav-label { font-size: 0.68rem; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #4a5568; padding: 1rem 0 0.5rem; }
</style>
""", unsafe_allow_html=True)


# ── Load data ───────────────────────────────────────────────────
@st.cache_data
def load_data():
    with open("mock_data.json", "r", encoding="utf-8") as f:
        return json.load(f)

data = load_data()
snapshots  = data["snapshots"]
competitors = data["competitors"]
summary    = data["summary"]

all_changes = []
for snap in snapshots:
    for ch in snap["changes"]:
        all_changes.append({**ch, "week": snap["week"], "label": snap["label"]})


# ── Sidebar ─────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div style="padding: 1rem 0 0.5rem;"><span style="font-size:1.3rem;">🔍</span> <span style="font-weight:700; color:#e2e8f0; font-size:1rem;">Competitor Intel</span></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.75rem; color:#4a5568; margin-bottom:1.5rem;">Positioning tracker · PMM portfolio</div>', unsafe_allow_html=True)

    st.markdown('<div class="nav-label">Navigation</div>', unsafe_allow_html=True)
    page = st.radio("", ["Overview", "Changes Timeline", "Competitor Detail"], label_visibility="collapsed")

    st.markdown("---")
    st.markdown('<div class="nav-label">Tracking</div>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:0.82rem; color:#718096;">{len(competitors)} competitors<br>{len(snapshots)} weeks of data<br>{len(all_changes)} changes detected</div>', unsafe_allow_html=True)

    st.markdown("---")
    latest = snapshots[-1]
    st.markdown(f'<div style="font-size:0.72rem; color:#4a5568;">Last updated<br><span style="color:#718096;">{latest["week"]}</span></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# PAGE 1 — OVERVIEW
# ══════════════════════════════════════════════════════════════
if page == "Overview":
    st.markdown('<h1 style="font-size:1.6rem; font-weight:700; color:#e2e8f0; margin-bottom:0.25rem;">Market Overview</h1>', unsafe_allow_html=True)
    st.markdown(f'<div style="font-size:0.85rem; color:#718096; margin-bottom:2rem;">Tracking {len(competitors)} competitors · {len(snapshots)} weeks · {summary["total_changes"]} changes detected</div>', unsafe_allow_html=True)

    # Top metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f'''<div class="card">
            <div class="metric-label">Competitors</div>
            <div class="metric-value">{len(competitors)}</div>
            <div class="metric-sub">tracked weekly</div>
        </div>''', unsafe_allow_html=True)
    with c2:
        st.markdown(f'''<div class="card">
            <div class="metric-label">Total Changes</div>
            <div class="metric-value">{summary["total_changes"]}</div>
            <div class="metric-sub">last {len(snapshots)} weeks</div>
        </div>''', unsafe_allow_html=True)
    with c3:
        st.markdown(f'''<div class="card">
            <div class="metric-label">High Severity</div>
            <div class="metric-value" style="color:#fc8181;">{summary["high_severity"]}</div>
            <div class="metric-sub">need attention</div>
        </div>''', unsafe_allow_html=True)
    with c4:
        st.markdown(f'''<div class="card">
            <div class="metric-label">Most Active</div>
            <div class="metric-value" style="font-size:1.2rem; padding-top:0.4rem;">{summary["most_active_competitor"]}</div>
            <div class="metric-sub">most changes</div>
        </div>''', unsafe_allow_html=True)

    # Competitor snapshot cards
    st.markdown('<div class="section-title">Current Snapshot</div>', unsafe_allow_html=True)

    latest_data = snapshots[-1]["data"]
    for comp in competitors:
        d = latest_data[comp]
        comp_changes = [c for c in all_changes if c["competitor"] == comp]
        high_count   = len([c for c in comp_changes if c["severity"] == "high"])

        with st.expander(f"  {comp}  —  {d['avg_rating']}⭐  ·  {len(comp_changes)} changes detected", expanded=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f'<div style="font-size:0.95rem; font-weight:600; color:#e2e8f0; margin-bottom:0.4rem;">{d["headline"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:0.82rem; color:#718096; margin-bottom:0.8rem;">{d["subheadline"][:120]}...</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:0.78rem; color:#a0aec0;">CTA: <span style="color:#63b3ed; font-style:italic;">"{d["cta"]}"</span></div>', unsafe_allow_html=True)
            with col2:
                free_badge = '<span class="badge-ok">Free tier</span>' if d["has_free_tier"] else '<span class="badge-high">No free tier</span>'
                high_badge = f'<span class="badge-high">{high_count} high severity</span>' if high_count > 0 else '<span class="badge-ok">No high alerts</span>'
                st.markdown(f'''
                    <div style="text-align:right;">
                        <div style="margin-bottom:0.5rem;">{free_badge}</div>
                        <div style="margin-bottom:0.5rem;">{high_badge}</div>
                        <div style="font-size:0.78rem; color:#718096;">{d["avg_rating"]}⭐ · {d["review_count"]:,} reviews</div>
                    </div>''', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:0.78rem; color:#4a5568; margin-top:0.8rem;">Plans: {" · ".join(d["plans"])}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:0.78rem; color:#4a5568;">Prices: {" · ".join(d["prices"])}</div>', unsafe_allow_html=True)

    # Key trends
    st.markdown('<div class="section-title">Key Trends</div>', unsafe_allow_html=True)
    for trend in summary["key_trends"]:
        st.markdown(f'<div class="card" style="padding:0.9rem 1.2rem; margin-bottom:0.6rem;"><span style="color:#f6c90e; margin-right:0.5rem;">→</span><span style="font-size:0.88rem; color:#cbd5e0;">{trend}</span></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# PAGE 2 — CHANGES TIMELINE
# ══════════════════════════════════════════════════════════════
elif page == "Changes Timeline":
    st.markdown('<h1 style="font-size:1.6rem; font-weight:700; color:#e2e8f0; margin-bottom:0.25rem;">Changes Timeline</h1>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.85rem; color:#718096; margin-bottom:2rem;">All detected changes, newest first</div>', unsafe_allow_html=True)

    # Filters
    fc1, fc2 = st.columns([2, 2])
    with fc1:
        filter_comp = st.multiselect("Competitor", competitors, default=competitors)
    with fc2:
        filter_sev = st.multiselect("Severity", ["high", "low"], default=["high", "low"])

    filtered = [c for c in reversed(all_changes)
                if c["competitor"] in filter_comp and c["severity"] in filter_sev]

    st.markdown(f'<div style="font-size:0.8rem; color:#4a5568; margin-bottom:1.5rem;">{len(filtered)} changes shown</div>', unsafe_allow_html=True)

    current_week = None
    for ch in filtered:
        if ch["week"] != current_week:
            current_week = ch["week"]
            st.markdown(f'<div class="section-title">{ch["label"]} · {ch["week"]}</div>', unsafe_allow_html=True)

        row_class = "change-row" if ch["severity"] == "high" else "change-row-low"
        badge = f'<span class="badge-high">HIGH</span>' if ch["severity"] == "high" else f'<span class="badge-low">LOW</span>'

        st.markdown(f'''<div class="card">
            <div style="display:flex; align-items:center; gap:0.6rem; margin-bottom:0.8rem;">
                <span style="font-weight:600; color:#e2e8f0;">{ch["competitor"]}</span>
                {badge}
                <span style="font-size:0.75rem; color:#4a5568; margin-left:auto;">{ch["field"].upper()}</span>
            </div>
            <div class="{row_class}">
                <div class="change-field">Before</div>
                <div class="change-before">{ch["before"][:120]}</div>
                <div class="change-field" style="margin-top:0.5rem;">After</div>
                <div class="change-after">{ch["after"][:120]}</div>
                <div class="change-note" style="margin-top:0.6rem;">💡 {ch["note"]}</div>
            </div>
        </div>''', unsafe_allow_html=True)

    if not filtered:
        st.markdown('<div class="card" style="text-align:center; color:#4a5568; padding:3rem;">No changes match the selected filters.</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# PAGE 3 — COMPETITOR DETAIL
# ══════════════════════════════════════════════════════════════
elif page == "Competitor Detail":
    st.markdown('<h1 style="font-size:1.6rem; font-weight:700; color:#e2e8f0; margin-bottom:0.25rem;">Competitor Detail</h1>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.85rem; color:#718096; margin-bottom:2rem;">Track every field change week by week</div>', unsafe_allow_html=True)

    selected = st.selectbox("Select competitor", competitors)
    comp_changes = [c for c in all_changes if c["competitor"] == selected]

    # Header stats
    latest_d = snapshots[-1]["data"][selected]
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'''<div class="card"><div class="metric-label">G2 Rating</div>
            <div class="metric-value">{latest_d["avg_rating"]}</div>
            <div class="metric-sub">{latest_d["review_count"]:,} reviews</div></div>''', unsafe_allow_html=True)
    with m2:
        st.markdown(f'''<div class="card"><div class="metric-label">Changes</div>
            <div class="metric-value">{len(comp_changes)}</div>
            <div class="metric-sub">last {len(snapshots)} weeks</div></div>''', unsafe_allow_html=True)
    with m3:
        free_label = "Yes" if latest_d["has_free_tier"] else "No"
        free_color = "#68d391" if latest_d["has_free_tier"] else "#fc8181"
        st.markdown(f'''<div class="card"><div class="metric-label">Free Tier</div>
            <div class="metric-value" style="color:{free_color};">{free_label}</div>
            <div class="metric-sub"> </div></div>''', unsafe_allow_html=True)
    with m4:
        high_count = len([c for c in comp_changes if c["severity"] == "high"])
        st.markdown(f'''<div class="card"><div class="metric-label">High Alerts</div>
            <div class="metric-value" style="color:{"#fc8181" if high_count > 0 else "#68d391"};">{high_count}</div>
            <div class="metric-sub">need attention</div></div>''', unsafe_allow_html=True)

    # Week-by-week breakdown
    st.markdown('<div class="section-title">Week by Week</div>', unsafe_allow_html=True)

    TRACKED_FIELDS = ["headline", "subheadline", "cta", "plans", "prices"]
    FIELD_LABELS   = {"headline": "Headline", "subheadline": "Subheadline",
                      "cta": "CTA", "plans": "Plans", "prices": "Pricing"}

    for snap in reversed(snapshots):
        snap_changes = [c for c in snap["changes"] if c["competitor"] == selected]
        d = snap["data"][selected]
        status_badge = f'<span class="badge-high">{len(snap_changes)} change{"s" if len(snap_changes)>1 else ""}</span>' if snap_changes else '<span class="badge-ok">No changes</span>'

        with st.expander(f'{snap["label"]}  ·  {snap["week"]}', expanded=(snap == snapshots[-1])):
            st.markdown(f'<div style="margin-bottom:0.8rem;">{status_badge}</div>', unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f'<div style="font-size:0.72rem; color:#4a5568; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.4rem;">Headline</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:0.88rem; color:#e2e8f0; margin-bottom:1rem;">{d["headline"]}</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:0.72rem; color:#4a5568; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.4rem;">CTA</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="font-size:0.88rem; color:#63b3ed; font-style:italic;">"{d["cta"]}"</div>', unsafe_allow_html=True)
            with col2:
                st.markdown(f'<div style="font-size:0.72rem; color:#4a5568; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.4rem;">Plans & Pricing</div>', unsafe_allow_html=True)
                for plan, price in zip(d["plans"], d["prices"]):
                    st.markdown(f'<div style="font-size:0.82rem; color:#a0aec0; margin-bottom:0.2rem;">{plan} — <span style="color:#e2e8f0;">{price}</span></div>', unsafe_allow_html=True)

            if snap_changes:
                st.markdown('<hr style="border-color:#1e2535; margin: 1rem 0;">', unsafe_allow_html=True)
                st.markdown('<div style="font-size:0.72rem; color:#fc8181; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:0.8rem;">Changes detected</div>', unsafe_allow_html=True)
                for ch in snap_changes:
                    badge = '<span class="badge-high">HIGH</span>' if ch["severity"] == "high" else '<span class="badge-low">LOW</span>'
                    st.markdown(f'''<div style="margin-bottom:1rem;">
                        <div style="display:flex; align-items:center; gap:0.5rem; margin-bottom:0.5rem;">
                            <span style="font-size:0.72rem; font-weight:700; color:#a0aec0; text-transform:uppercase;">{ch["field"]}</span>
                            {badge}
                        </div>
                        <div class="change-before">{ch["before"][:120]}</div>
                        <div style="color:#4a5568; font-size:0.75rem; text-align:center; margin: 2px 0;">↓</div>
                        <div class="change-after">{ch["after"][:120]}</div>
                        <div class="change-note" style="margin-top:0.5rem;">💡 {ch["note"]}</div>
                    </div>''', unsafe_allow_html=True)
