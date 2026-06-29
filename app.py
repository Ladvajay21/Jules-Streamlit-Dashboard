import streamlit as st
import requests
import plotly.graph_objects as go
import pandas as pd
import re
import os
import json
from datetime import datetime, date, timedelta
from dotenv import load_dotenv

load_dotenv()

# ─── CONFIG ───────────────────────────────────────────────
def get_secret(key, default=""):
    try:
        val = st.secrets[key]
        return val
    except Exception:
        return os.getenv(key, default)

JIRA_EMAIL    = get_secret("JIRA_EMAIL")
JIRA_TOKEN    = get_secret("JIRA_API_TOKEN", "").replace("\n","").replace("\r","").replace(" ","").strip()
JIRA_BASE     = get_secret("JIRA_BASE_URL", "https://minehub.atlassian.net")
SLACK_WEBHOOK = get_secret("SLACK_WEBHOOK_URL")
DASHBOARD_PIN = get_secret("DASHBOARD_PIN")

CLOUD_ID      = "7a6832b7-8317-4cb3-b886-1a6da3749a41"
PROJECT       = "JENG"

DONE_STATUSES    = {"Done", "PO/QA VALID", "Demo", "In Production", "CS Reviewed"}
BLOCKED_STATUSES = {"Blocked"}
ACTIVE_STATUSES  = {"In Progress", "AIM OF THE DAY", "Tech review", "PO review",
                     "PO/QA Test run", "Aim Of The week", "PO not valid", "TECH GROOMED"}
EXCLUDE_FROM_CARDS = {"Unassigned", "Jay Ladva"}

DEV_COLORS = {
    "Nikita Vaidya": "#818cf8",
    "Satadru Roy":   "#f472b6",
    "Rizky Ario":    "#fb923c",
    "Jay Pitroda":   "#34d399",
    "Unassigned":    "#64748b",
}

# Auto-assign palette for any new devs not in DEV_COLORS
_AUTO_COLORS = ["#38bdf8", "#facc15", "#a78bfa", "#f87171", "#2dd4bf", "#e879f9", "#84cc16"]
_auto_color_idx = 0

def get_dev_color(name):
    global _auto_color_idx
    if name in DEV_COLORS:
        return DEV_COLORS[name]
    # Auto-assign a color for new devs
    color = _AUTO_COLORS[_auto_color_idx % len(_AUTO_COLORS)]
    DEV_COLORS[name] = color
    _auto_color_idx += 1
    return color

STATUS_COLORS = {
    "Done": "#10b981", "PO/QA VALID": "#34d399", "PO/QA Test run": "#6ee7b7",
    "Demo": "#a7f3d0", "In Production": "#059669", "CS Reviewed": "#065f46",
    "PO review": "#818cf8", "Tech review": "#a78bfa", "In Progress": "#38bdf8",
    "AIM OF THE DAY": "#7dd3fc", "Aim Of The week": "#bae6fd",
    "TECH GROOMED": "#c084fc",
    "To Do": "#64748b", "Blocked": "#f87171", "PO not valid": "#f97316",
}

STATUS_ORDER = [
    "Done", "PO/QA VALID", "Demo", "In Production", "CS Reviewed",
    "PO/QA Test run", "Tech review", "PO review",
    "AIM OF THE DAY", "In Progress", "Aim Of The week", "TECH GROOMED",
    "To Do", "Blocked", "PO not valid",
]

SPRINT_TIPS = [
    "A blocker today is a fire tomorrow. Escalate early! 🔥",
    "Small PRs get reviewed faster. Ship in slices. ⚡",
    "Done = merged + deployed + verified. All three. 🚀",
    "The best code is the code you don't write. ✂️",
    "Sprint health = team health. Look out for each other. 🤝",
    "Every blocker resolved = smoother sprint review. 📊",
    "Write the test first, thank yourself later. 🧪",
    "If it's unclear, clarify it now — not on the last day. 💬",
]

GREETINGS = [
    "Let's make today count! 💪",
    "Another day, another ticket shipped! 🚀",
    "Stay focused, stay unblocked! 🎯",
    "Great work so far — keep the momentum! ⚡",
    "Sprint strong, team Jules! 🏃",
]


# ─── PAGE CONFIG ──────────────────────────────────────────
st.set_page_config(page_title="Jules Sprint Dashboard", page_icon="🚀", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;600;700;900&family=Space+Mono:wght@400;700&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif !important; background-color: #080c1a !important; color: #e2e8f0 !important; }
.stApp { background: radial-gradient(ellipse at 20% 10%, #0d1b3e 0%, #080c1a 55%, #050710 100%) !important; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.5rem !important; max-width: 1200px !important; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: rgba(13,27,62,0.5); border-radius: 12px; padding: 4px; border: 1px solid rgba(0,212,255,0.08); }
.stTabs [data-baseweb="tab"] { border-radius: 8px; padding: 8px 16px; font-size: 13px; font-weight: 600; color: #64748b; }
.stTabs [aria-selected="true"] { background: rgba(0,212,255,0.1) !important; color: #00d4ff !important; }
div[data-testid="stMetric"] { background: rgba(13,27,62,0.5); border: 1px solid rgba(0,212,255,0.08); border-radius: 12px; padding: 12px 16px; }
div[data-testid="stMetric"] label { color: #64748b !important; font-size: 11px !important; }
div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #e2e8f0 !important; font-size: 22px !important; font-weight: 700 !important; }
.dash-card { background: rgba(13,27,62,0.4); border: 1px solid rgba(0,212,255,0.08); border-radius: 14px; padding: 16px 18px; margin-bottom: 12px; transition: all 0.25s ease; }
.dash-card:hover { border-color: rgba(0,212,255,0.2); box-shadow: 0 8px 32px rgba(0,0,0,0.3); }
.live-dot { width: 7px; height: 7px; border-radius: 50%; background: #10b981; display: inline-block; animation: livePulse 1.5s ease-in-out infinite; }

/* ── ANIMATIONS ── */
@keyframes livePulse { 0%,100% { opacity:.5; box-shadow:0 0 0 0 rgba(16,185,129,0.4); } 50% { opacity:1; box-shadow:0 0 0 6px rgba(16,185,129,0); } }
@keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-16px)} }
@keyframes shimmer { 0%{background-position:-300% center} 100%{background-position:300% center} }
@keyframes shimmerBar { 0%{background-position:-400% 0} 100%{background-position:400% 0} }
@keyframes pulse3 { 0%,100%{opacity:.3;transform:scale(1)} 50%{opacity:.7;transform:scale(1.08)} }
@keyframes fadeUp { from{opacity:0;transform:translateY(28px)} to{opacity:1;transform:translateY(0)} }
@keyframes fadeInLeft { from{opacity:0;transform:translateX(-20px)} to{opacity:1;transform:translateX(0)} }
@keyframes bounceIn { 0%{opacity:0;transform:scale(0.3)} 50%{opacity:1;transform:scale(1.05)} 70%{transform:scale(0.95)} 100%{transform:scale(1)} }
@keyframes borderGlow { 0%,100%{border-color:rgba(248,113,113,0.3);box-shadow:0 0 8px rgba(248,113,113,0.1)} 50%{border-color:rgba(248,113,113,0.7);box-shadow:0 0 20px rgba(248,113,113,0.25)} }
@keyframes confetti { 0%{transform:translateY(-10px) rotate(0deg);opacity:1} 100%{transform:translateY(110vh) rotate(720deg);opacity:0} }
@keyframes float-particle { 0%{transform:translateY(100vh) translateX(0) rotate(0deg);opacity:0} 10%{opacity:0.4} 90%{opacity:0.2} 100%{transform:translateY(-10vh) translateX(50px) rotate(360deg);opacity:0} }

/* ── SHIMMER BAR ── */
.shimmer-bar { background:linear-gradient(90deg,#1e2d47 25%,rgba(0,212,255,0.06) 50%,#1e2d47 75%); background-size:400% 100%; animation:shimmerBar 1.5s infinite; border-radius:8px; }

/* ── SECTION HEADERS ── */
.section-header { font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#475569;margin-bottom:14px;display:flex;align-items:center;gap:8px; }
.section-header::after { content:'';flex:1;height:1px;background:linear-gradient(90deg,rgba(0,212,255,0.2),transparent); }

/* ── BLOCKED PULSE ── */
.blocked-alert { animation: borderGlow 2s ease-in-out infinite; }

/* ── DEV CARD HOVER ── */
.dev-card { transition: all 0.25s ease !important; }
.dev-card:hover { transform: translateY(-3px) !important; box-shadow: 0 12px 32px rgba(0,0,0,0.3) !important; }

/* ── KPI CARD ── */
.kpi-card { animation: bounceIn 0.6s cubic-bezier(0.16,1,0.3,1) both; transition: all 0.25s ease; }
.kpi-card:hover { transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,0,0,0.3); }

/* ── FLOATING PARTICLES ── */
.particle { position:fixed; border-radius:50%; pointer-events:none; animation:float-particle linear infinite; z-index:0; }

/* ── TICKET ROW ── */
.ticket-key { font-family: 'Space Mono', monospace; font-size: 11px; color: #00d4ff; text-decoration: none; margin-right: 6px; }
.ticket-key:hover { color: #c4b5fd; }
.ticket-row { display:flex; align-items:center; padding:5px 0; border-bottom:1px solid rgba(0,212,255,0.04); font-size:12px; gap:6px; transition:all 0.2s ease; }
.ticket-row:last-child { border-bottom:none; }
.ticket-row:hover { padding-left:3px; background:rgba(0,212,255,0.02); }

/* ── BUTTON SHIMMER ── */
.stButton > button { transition: all 0.3s ease !important; }
.stButton > button:hover { box-shadow: 0 4px 16px rgba(0,212,255,0.2) !important; }

/* ── SCROLLBAR ── */
::-webkit-scrollbar { width:6px; }
::-webkit-scrollbar-track { background:#080c1a; }
::-webkit-scrollbar-thumb { background:#1e2d47; border-radius:3px; }
::-webkit-scrollbar-thumb:hover { background:#2d4a6f; }
</style>
""", unsafe_allow_html=True)


# ─── PIN PROTECTION ───────────────────────────────────────
def check_pin():
    if not DASHBOARD_PIN:
        return True
    if st.session_state.get("pin_ok"):
        return True

    # Animated login page
    st.html("""
    <style>
    .login-wrap { position:fixed;top:0;left:0;width:100%;height:100%;
        background:linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%); overflow:hidden; z-index:-2; }
    .orb-a { position:fixed;top:-120px;right:-80px;width:420px;height:420px;border-radius:50%;
        background:radial-gradient(circle, rgba(0,212,255,0.12) 0%, transparent 70%);
        animation:pulse3 5s ease-in-out infinite; }
    .orb-b { position:fixed;bottom:-180px;left:-120px;width:520px;height:520px;border-radius:50%;
        background:radial-gradient(circle, rgba(16,185,129,0.09) 0%, transparent 70%);
        animation:pulse3 7s ease-in-out infinite reverse; }
    .orb-c { position:fixed;top:45%;left:5%;width:180px;height:180px;border-radius:50%;
        background:radial-gradient(circle, rgba(56,189,248,0.07) 0%, transparent 70%);
        animation:pulse3 9s ease-in-out infinite; }
    .grid-lines { position:fixed;top:0;left:0;width:100%;height:100%;
        background-image: linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
                          linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px);
        background-size: 60px 60px; z-index:-1; }
    .login-card { animation: fadeUp 0.7s cubic-bezier(0.16,1,0.3,1) both; }
    .rocket { font-size:68px; animation:float 3s ease-in-out infinite; display:block;
        filter:drop-shadow(0 0 18px rgba(0,212,255,0.9)) drop-shadow(0 0 40px rgba(16,185,129,0.5)); }
    .login-title { font-size:40px !important; font-weight:900 !important;
        background: linear-gradient(90deg, #00d4ff, #10b981, #38bdf8, #00d4ff) !important;
        background-size: 300% auto !important;
        -webkit-background-clip: text !important; -webkit-text-fill-color: transparent !important;
        animation: shimmer 4s linear infinite !important; letter-spacing: -1px !important; }
    .divider-line { width:50px;height:3px;margin:16px auto;
        background:linear-gradient(90deg,#00d4ff,#10b981); border-radius:99px; }
    @keyframes pulse3 { 0%,100%{opacity:.3;transform:scale(1)} 50%{opacity:.7;transform:scale(1.08)} }
    @keyframes float { 0%,100%{transform:translateY(0)} 50%{transform:translateY(-16px)} }
    @keyframes shimmer { 0%{background-position:-300% center} 100%{background-position:300% center} }
    @keyframes fadeUp { from{opacity:0;transform:translateY(28px)} to{opacity:1;transform:translateY(0)} }
    </style>
    <div class="login-wrap"></div>
    <div class="orb-a"></div><div class="orb-b"></div><div class="orb-c"></div>
    <div class="grid-lines"></div>
    <div class="login-card" style="max-width:400px;margin:50px auto 0;text-align:center;">
        <span class="rocket">🚀</span>
        <h1 class="login-title">Jules Dashboard</h1>
        <div class="divider-line"></div>
        <p style="color:#64748b;font-size:13px;margin-top:12px;">Enter PIN to access sprint data</p>
    </div>
    """)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        pin = st.text_input("PIN", type="password", label_visibility="collapsed", placeholder="· · · ·")
        if st.button("🔓 Enter Dashboard", use_container_width=True):
            if pin == DASHBOARD_PIN:
                st.session_state.pin_ok = True
                st.rerun()
            else:
                st.error("Wrong PIN")
    return False


# ─── HELPERS ──────────────────────────────────────────────
def clean_title(s):
    s = re.sub(r'^(AAWU,?\s*|AAD,?\s*)', '', s, flags=re.IGNORECASE)
    return s.lstrip(',').strip()


def jira_auth():
    return (JIRA_EMAIL, JIRA_TOKEN)


def jira_headers():
    return {"Accept": "application/json", "Content-Type": "application/json"}


# ─── FETCH SPRINT INFO ───────────────────────────────────
@st.cache_data(ttl=600)
def fetch_available_sprints():
    """Fetch all sprints from Jira Agile API to get start/end dates."""
    # First get the board ID
    url = f"{JIRA_BASE}/rest/agile/1.0/board"
    params = {"projectKeyOrId": PROJECT, "maxResults": 10}
    try:
        resp = requests.get(url, auth=jira_auth(), headers=jira_headers(), params=params, timeout=15)
        resp.raise_for_status()
        boards = resp.json().get("values", [])
        if not boards:
            return []
        board_id = boards[0]["id"]

        # Now get sprints for this board
        url2 = f"{JIRA_BASE}/rest/agile/1.0/board/{board_id}/sprint"
        params2 = {"state": "active,closed", "maxResults": 20}
        resp2 = requests.get(url2, auth=jira_auth(), headers=jira_headers(), params=params2, timeout=15)
        resp2.raise_for_status()
        sprints = []
        for s in resp2.json().get("values", []):
            sprints.append({
                "id": s["id"],
                "name": s.get("name", "Unknown"),
                "state": s.get("state", "unknown"),
                "startDate": s.get("startDate", ""),
                "endDate": s.get("endDate", ""),
            })
        return sprints
    except Exception as e:
        st.warning(f"Could not fetch sprints: {e}")
        return []


def get_active_sprint_dates(sprints):
    """Get start/end dates of the active sprint."""
    for s in sprints:
        if s["state"] == "active":
            try:
                start = datetime.fromisoformat(s["startDate"].replace("Z", "+00:00")).date()
                end = datetime.fromisoformat(s["endDate"].replace("Z", "+00:00")).date()
                name = s["name"]
                return start, end, name
            except Exception:
                pass
    # Fallback: if no active sprint found, use sensible dynamic defaults
    today = date.today()
    return today - timedelta(days=7), today + timedelta(days=7), "Sprint (fallback)"


# ─── SHARED SPRINT-NAME PARSER ───────────────────────────
def _parse_sprint_names(sprints_raw):
    """
    Robustly extract sprint names from customfield_10020 regardless of format.
    Handles both Jira Cloud v3 dict objects and legacy string format.
    Also handles displayName fallback for tickets with many historical sprints.
    """
    names = []
    if not sprints_raw:
        return names
    if not isinstance(sprints_raw, list):
        sprints_raw = [sprints_raw]
    for sp in sprints_raw:
        if isinstance(sp, dict):
            n = sp.get("name") or sp.get("displayName") or ""
            if n:
                names.append(n.strip())
        elif isinstance(sp, str):
            hit = re.search(r'name=([^,\]]+)', sp)
            if hit:
                names.append(hit.group(1).strip())
    return names


# ─── FETCH TICKETS ────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch_jira_tickets():
    """Fetch all open sprint tickets from Jira REST API."""
    url = f"{JIRA_BASE}/rest/api/3/search/jql"
    all_tickets = []
    start_at = 0

    while True:
        params = {
            "jql": f"project = {PROJECT} AND sprint in openSprints() ORDER BY created DESC",
            "maxResults": 100,
            "startAt": start_at,
            "fields": "summary,status,assignee,customfield_10024,issuetype,fixVersions,customfield_10020,resolutiondate",
        }
        resp = requests.get(url, headers=jira_headers(), auth=jira_auth(), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        issues = data.get("issues", [])

        for issue in issues:
            f = issue.get("fields", {})
            sprint_names = _parse_sprint_names(f.get("customfield_10020"))
            fix_versions = [fv.get("name", "") for fv in (f.get("fixVersions") or [])]

            all_tickets.append({
                "key": issue["key"],
                "summary": clean_title(f.get("summary", "")),
                "status": f.get("status", {}).get("name", "Unknown"),
                "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
                "sp": int(f["customfield_10024"]) if f.get("customfield_10024") else None,
                "type": f.get("issuetype", {}).get("name", "Task"),
                "sprints": sprint_names,
                "fix_versions": fix_versions,
                "carried_over": len(sprint_names) > 1,
                "resolution_date": f.get("resolutiondate", ""),
            })

        if start_at + len(issues) >= data.get("total", 0):
            break
        start_at += len(issues)

    # ── Catch-all verification: fetches ALL sprint tickets regardless of status ──
    verify_url = f"{JIRA_BASE}/rest/api/3/search/jql"
    existing_keys = {t["key"]: t for t in all_tickets}
    v_start = 0
    while True:
        try:
            vparams = {
                "jql": f'project = {PROJECT} AND sprint in openSprints() ORDER BY key ASC',
                "maxResults": 200,
                "startAt": v_start,
                "fields": "summary,status,assignee,customfield_10024,issuetype,fixVersions,customfield_10020,resolutiondate",
            }
            vresp = requests.get(verify_url, headers=jira_headers(), auth=jira_auth(), params=vparams, timeout=30)
            vresp.raise_for_status()
            vdata = vresp.json()
            v_issues = vdata.get("issues", [])
            for issue in v_issues:
                f = issue.get("fields", {})
                key = issue["key"]
                new_status = f.get("status", {}).get("name", "Unknown")
                if key in existing_keys:
                    existing_keys[key]["status"] = new_status
                else:
                    sprint_names = _parse_sprint_names(f.get("customfield_10020"))
                    fix_versions = [fv.get("name", "") for fv in (f.get("fixVersions") or [])]
                    new_ticket = {
                        "key": key,
                        "summary": clean_title(f.get("summary", "")),
                        "status": new_status,
                        "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
                        "sp": int(f["customfield_10024"]) if f.get("customfield_10024") else None,
                        "type": f.get("issuetype", {}).get("name", "Task"),
                        "sprints": sprint_names,
                        "fix_versions": fix_versions,
                        "carried_over": len(sprint_names) > 1,
                        "resolution_date": f.get("resolutiondate", ""),
                    }
                    all_tickets.append(new_ticket)
                    existing_keys[key] = new_ticket
            if v_start + len(v_issues) >= vdata.get("total", 0):
                break
            v_start += len(v_issues)
        except Exception:
            break

    return all_tickets


# ─── FETCH GO-LIVE BLOCKER TICKETS ────────────────────────
@st.cache_data(ttl=300)
def fetch_go_live_blocker_tickets():
    """Fetch tickets labelled 'go-live-blocker' from the current open sprint."""
    url = f"{JIRA_BASE}/rest/api/3/search/jql"
    all_tickets = []
    start_at = 0
    while True:
        params = {
            "jql": f'project = {PROJECT} AND sprint in openSprints() AND labels = "GoLiveBlocker" ORDER BY created DESC',
            "maxResults": 100,
            "startAt": start_at,
            "fields": "summary,status,assignee,customfield_10024,priority",
        }
        try:
            resp = requests.get(url, headers=jira_headers(), auth=jira_auth(), params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            issues = data.get("issues", [])
            for issue in issues:
                f = issue.get("fields", {})
                all_tickets.append({
                    "key": issue["key"],
                    "summary": clean_title(f.get("summary", "")),
                    "status": f.get("status", {}).get("name", "Unknown"),
                    "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
                    "sp": int(f["customfield_10024"]) if f.get("customfield_10024") else None,
                    "priority": (f.get("priority") or {}).get("name", ""),
                })
            if start_at + len(issues) >= data.get("total", 0):
                break
            start_at += len(issues)
        except Exception:
            break
    return all_tickets


# ─── FETCH ALL SPRINTS HISTORY (NEW) ──────────────────────
@st.cache_data(ttl=600)
def fetch_all_sprints_tickets():
    """
    Fetch ALL tickets across ALL sprints (active + closed) for the history tab.
    Also pulls reporter / company (organisation) custom field where available.
    Returns (tickets_list, sprints_list).
    """
    # ── 1. Get board & all sprints ──
    board_id = None
    all_sprint_meta = []
    try:
        url = f"{JIRA_BASE}/rest/agile/1.0/board"
        resp = requests.get(url, auth=jira_auth(), headers=jira_headers(),
                            params={"projectKeyOrId": PROJECT, "maxResults": 10}, timeout=15)
        resp.raise_for_status()
        boards = resp.json().get("values", [])
        if boards:
            board_id = boards[0]["id"]

        if board_id:
            s_url = f"{JIRA_BASE}/rest/agile/1.0/board/{board_id}/sprint"
            s_start = 0
            while True:
                sr = requests.get(s_url, auth=jira_auth(), headers=jira_headers(),
                                  params={"state": "active,closed,future", "maxResults": 50,
                                          "startAt": s_start}, timeout=15)
                sr.raise_for_status()
                s_data = sr.json()
                for s in s_data.get("values", []):
                    all_sprint_meta.append({
                        "id": s["id"],
                        "name": s.get("name", "Unknown"),
                        "state": s.get("state", "unknown"),
                        "startDate": s.get("startDate", ""),
                        "endDate": s.get("endDate", ""),
                    })
                if s_start + len(s_data.get("values", [])) >= s_data.get("total", 0):
                    break
                s_start += len(s_data.get("values", []))
    except Exception:
        pass

    # ── 2. Fetch ALL tickets that have ever been in any sprint ──
    # Use two complementary JQL queries so we catch everything:
    #   Pass A: ORDER BY key ASC  — catches old tickets like JENG-177
    #   Pass B: ORDER BY created DESC — catches any the first pass may miss
    # seen_keys deduplicates across both passes.
    search_url = f"{JIRA_BASE}/rest/api/3/search/jql"
    all_tickets = []
    seen_keys = set()

    HISTORY_FIELDS = (
        "summary,status,assignee,reporter,customfield_10024,"
        "issuetype,fixVersions,customfield_10020,resolutiondate,"
        "created,priority,labels"
    )

    def _parse_ticket(issue):
        key = issue["key"]
        f = issue.get("fields", {})

        sprint_names = _parse_sprint_names(f.get("customfield_10020"))
        fix_versions = [fv.get("name", "") for fv in (f.get("fixVersions") or [])]
        reporter = (f.get("reporter") or {}).get("displayName", "Unknown")

        def _to_date(raw):
            if not raw:
                return ""
            try:
                return datetime.fromisoformat(
                    raw.replace("Z", "+00:00")
                ).date().isoformat()
            except Exception:
                return raw[:10]

        return {
            "key": key,
            "summary": clean_title(f.get("summary", "")),
            "status": f.get("status", {}).get("name", "Unknown"),
            "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
            "reporter": reporter,
            "sp": int(f["customfield_10024"]) if f.get("customfield_10024") else None,
            "type": f.get("issuetype", {}).get("name", "Task"),
            "sprints": sprint_names,
            "fix_versions": fix_versions,
            "labels": f.get("labels") or [],
            "priority": (f.get("priority") or {}).get("name", ""),
            "created_date": _to_date(f.get("created", "")),
            "resolution_date": _to_date(f.get("resolutiondate", "")),
            "carried_over": len(sprint_names) > 1,
        }

    for order in ["key ASC", "created DESC"]:
        start_at = 0
        consecutive_errors = 0
        while True:
            try:
                params = {
                    "jql": f"project = {PROJECT} AND sprint is not EMPTY ORDER BY {order}",
                    "maxResults": 100,
                    "startAt": start_at,
                    "fields": HISTORY_FIELDS,
                }
                resp = requests.get(search_url, headers=jira_headers(), auth=jira_auth(),
                                    params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                issues = data.get("issues", [])
                consecutive_errors = 0  # reset on success

                for issue in issues:
                    key = issue["key"]
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    all_tickets.append(_parse_ticket(issue))

                fetched_so_far = start_at + len(issues)
                total_available = data.get("total", 0)
                if fetched_so_far >= total_available or not issues:
                    break
                start_at += len(issues)

            except Exception as exc:
                consecutive_errors += 1
                # Retry up to 3 times on transient errors, then move on
                if consecutive_errors >= 3:
                    break
                start_at += 100  # skip the problematic page and continue

    # ── 3. Batch-fetch PR links for all tickets via Jira dev-info API ──
    pr_map = {}  # key -> list of {"title": ..., "url": ..., "state": ...}
    for ticket in all_tickets:
        try:
            dev_url = (
                f"{JIRA_BASE}/rest/dev-status/1.0/issue/detail"
                f"?issueId={ticket['key']}&applicationType=github&dataType=pullrequest"
            )
            # Jira dev-info needs the numeric issue ID, not the key — fetch it
            # We'll use the search result's id field; re-query per ticket only if needed
            # Use the simpler endpoint that accepts issue key via a different param
            dev_url2 = (
                f"{JIRA_BASE}/rest/dev-status/latest/issue/detail"
                f"?issueId={ticket['key']}&applicationType=github&dataType=pullrequest"
            )
            dr = requests.get(dev_url2, auth=jira_auth(), headers=jira_headers(), timeout=10)
            if dr.status_code == 200:
                detail = dr.json().get("detail", [])
                prs = []
                for d in detail:
                    for pr in d.get("pullRequests", []):
                        prs.append({
                            "title": pr.get("name", pr.get("id", "PR")),
                            "url": pr.get("url", ""),
                            "state": pr.get("status", pr.get("state", "")),
                        })
                if prs:
                    pr_map[ticket["key"]] = prs
        except Exception:
            pass

    # Attach PR data to each ticket
    for ticket in all_tickets:
        ticket["pull_requests"] = pr_map.get(ticket["key"], [])

    return all_tickets, all_sprint_meta


# ─── FETCH PR FOR A SINGLE ISSUE (uses numeric issue ID) ──
@st.cache_data(ttl=600)
def fetch_prs_for_issues(issue_keys_tuple):
    """
    Fetch PR links for a tuple of issue keys using Jira's dev-status API.
    Returns dict: {issue_key: [{"title":..,"url":..,"state":..}, ...]}
    The dev-status endpoint needs the numeric Jira issue ID, so we first
    resolve keys → IDs, then call the dev-status endpoint in bulk.
    """
    if not issue_keys_tuple:
        return {}

    pr_map = {}

    # Step 1: resolve issue keys to numeric IDs
    search_url = f"{JIRA_BASE}/rest/api/3/search/jql"
    key_to_id = {}
    keys_list = list(issue_keys_tuple)

    for batch_start in range(0, len(keys_list), 100):
        batch = keys_list[batch_start: batch_start + 100]
        jql = "issueKey in (" + ",".join(batch) + ")"
        try:
            r = requests.get(
                search_url, auth=jira_auth(), headers=jira_headers(),
                params={"jql": jql, "maxResults": 100, "fields": "id"},
                timeout=20,
            )
            r.raise_for_status()
            for iss in r.json().get("issues", []):
                key_to_id[iss["key"]] = iss["id"]
        except Exception:
            pass

    # Step 2: call dev-status per issue
    dev_base = f"{JIRA_BASE}/rest/dev-status/latest/issue/detail"
    for key, issue_id in key_to_id.items():
        try:
            dr = requests.get(
                dev_base,
                auth=jira_auth(), headers=jira_headers(),
                params={"issueId": issue_id, "applicationType": "github",
                        "dataType": "pullrequest"},
                timeout=10,
            )
            if dr.status_code != 200:
                # Try without applicationType filter to catch GitLab / Bitbucket too
                dr = requests.get(
                    dev_base,
                    auth=jira_auth(), headers=jira_headers(),
                    params={"issueId": issue_id, "dataType": "pullrequest"},
                    timeout=10,
                )
            if dr.status_code == 200:
                prs = []
                for detail in dr.json().get("detail", []):
                    for pr in detail.get("pullRequests", []):
                        state = pr.get("status", pr.get("state", "")).upper()
                        prs.append({
                            "title": pr.get("name") or pr.get("id") or "PR",
                            "url": pr.get("url", ""),
                            "state": state,
                        })
                if prs:
                    pr_map[key] = prs
        except Exception:
            pass

    return pr_map


# ─── BUILD METRICS ────────────────────────────────────────
def build_metrics(tickets, sprint_start=None, sprint_days=48):
    today = date.today()
    total = len(tickets)
    done_tickets = [t for t in tickets if t["status"] in DONE_STATUSES]
    blocked_tickets = [t for t in tickets if t["status"] in BLOCKED_STATUSES]
    active_tickets = [t for t in tickets if t["status"] in ACTIVE_STATUSES]
    todo_tickets = [t for t in tickets if t["status"] == "To Do"]

    total_sp = sum(t["sp"] or 0 for t in tickets)
    done_sp = sum(t["sp"] or 0 for t in done_tickets)

    # Status counts
    status_counts = {}
    for t in tickets:
        s = t["status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    # Developer breakdown
    dev_map = {}
    for t in tickets:
        name = t["assignee"]
        if name not in dev_map:
            dev_map[name] = {"total": 0, "done": 0, "active": 0, "blocked": 0, "todo": 0,
                             "sp": 0, "done_sp": 0, "active_sp": 0, "blocked_sp": 0, "todo_sp": 0}
        dev_map[name]["total"] += 1
        dev_map[name]["sp"] += t["sp"] or 0
        if t["status"] in DONE_STATUSES:
            dev_map[name]["done"] += 1
            dev_map[name]["done_sp"] += t["sp"] or 0
        elif t["status"] in BLOCKED_STATUSES:
            dev_map[name]["blocked"] += 1
            dev_map[name]["blocked_sp"] += t["sp"] or 0
        elif t["status"] in ACTIVE_STATUSES:
            dev_map[name]["active"] += 1
            dev_map[name]["active_sp"] += t["sp"] or 0
        else:
            dev_map[name]["todo"] += 1
            dev_map[name]["todo_sp"] += t["sp"] or 0

    # Sprint progress
    if sprint_start:
        current_day = max(1, min((today - sprint_start).days + 1, sprint_days))
    else:
        current_day = 1

    # True velocity: tickets resolved AFTER sprint start
    true_velocity = 0
    true_velocity_sp = 0
    pre_sprint_done = 0
    if sprint_start:
        for t in done_tickets:
            rd = t.get("resolution_date", "")
            if rd:
                try:
                    res_date = datetime.fromisoformat(rd.replace("Z", "+00:00")).date()
                    if res_date >= sprint_start:
                        true_velocity += 1
                        true_velocity_sp += t["sp"] or 0
                    else:
                        pre_sprint_done += 1
                except Exception:
                    true_velocity += 1
                    true_velocity_sp += t["sp"] or 0
            else:
                # No resolution date but in done status — count it
                true_velocity += 1
                true_velocity_sp += t["sp"] or 0

    # Sprint health
    expected_pct = (current_day / sprint_days) * 100 if sprint_days else 0
    actual_pct = (len(done_tickets) / total * 100) if total else 0
    if actual_pct >= expected_pct * 0.85:
        status = "on-track"
    elif actual_pct >= expected_pct * 0.65:
        status = "slight-risk"
    else:
        status = "behind"

    # Missing SP count
    missing_sp_tickets = [t for t in tickets if t.get("sp") is None]
    missing_sp_keys = [t["key"] for t in missing_sp_tickets]

    return {
        "total": total,
        "done_tickets": done_tickets,
        "blocked_tickets": blocked_tickets,
        "active_tickets": active_tickets,
        "todo_tickets": todo_tickets,
        "total_sp": total_sp,
        "done_sp": done_sp,
        "status_counts": status_counts,
        "dev_map": dev_map,
        "current_day": current_day,
        "status": status,
        "true_velocity": true_velocity,
        "true_velocity_sp": true_velocity_sp,
        "pre_sprint_done": pre_sprint_done,
        "missing_sp_count": len(missing_sp_tickets),
        "missing_sp_keys": missing_sp_keys,
    }


# ─── SLACK ────────────────────────────────────────────────
def post_to_slack(blocked_tickets, m):
    if not SLACK_WEBHOOK:
        return False, "No webhook"
    blocks = [{
        "type": "header",
        "text": {"type": "plain_text", "text": "🚨 Jules Sprint — Blocked Tickets"}
    }]
    for t in blocked_tickets[:10]:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*<{JIRA_BASE}/browse/{t['key']}|{t['key']}>* — {t['summary']}\n👤 {t['assignee']}"}
        })
    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"📊 {len(m['done_tickets'])}/{m['total']} done · {len(blocked_tickets)} blocked · {m['done_sp']}/{m['total_sp']} SP"}]
    })
    try:
        resp = requests.post(SLACK_WEBHOOK, json={"blocks": blocks}, timeout=10)
        return resp.status_code == 200, resp.text
    except Exception as e:
        return False, str(e)


# ─── KPI CARD ─────────────────────────────────────────────
def kpi_card(icon, label, value, color, subtitle=""):
    sub_html = f'<div style="font-size:9px;color:#475569;margin-top:2px;">{subtitle}</div>' if subtitle else ""
    st.html(f"""
    <div class="kpi-card" style="background:rgba(13,27,62,0.5);border:1px solid {color}22;border-radius:12px;padding:12px 14px;text-align:center;position:relative;overflow:hidden;">
        <div style="position:absolute;top:0;right:0;width:40px;height:40px;background:radial-gradient(circle,{color}15,transparent);border-radius:0 12px 0 40px;"></div>
        <div style="font-size:10px;color:#64748b;margin-bottom:2px;">{icon} {label}</div>
        <div style="font-size:22px;font-weight:900;color:{color};">{value}</div>
        {sub_html}
    </div>
    """)


# ─── RENDER HEADER ────────────────────────────────────────
def render_header(m, fetched_at, sprint_name, sprint_start, sprint_days):
    days_left = sprint_days - m["current_day"]
    pct = round(len(m["done_tickets"]) / m["total"] * 100) if m["total"] else 0
    sc = "#10b981" if m["status"] == "on-track" else "#fbbf24" if m["status"] == "slight-risk" else "#f87171"
    sl = "On Track 🎯" if m["status"] == "on-track" else "Slight Risk ⚠️" if m["status"] == "slight-risk" else "Behind 🚨"
    sprint_end = sprint_start + timedelta(days=sprint_days) if sprint_start else date.today()

    import random
    tip = random.choice(SPRINT_TIPS)

    # Floating particles
    particles = "".join([
        f'<div class="particle" style="left:{(i*37)%100}%;width:{3+i%4}px;height:{3+i%4}px;'
        f'background:{"#00d4ff" if i%3==0 else "#818cf8" if i%3==1 else "#10b981"};'
        f'opacity:0.12;animation-duration:{8+i*1.3:.1f}s;animation-delay:{i*0.7:.1f}s;"></div>'
        for i in range(10)
    ])

    st.html(f"""
    {particles}
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;flex-wrap:wrap;gap:12px;animation:fadeInLeft 0.6s ease both;">
        <div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <span style="width:7px;height:7px;border-radius:50%;background:#10b981;display:inline-block;animation:livePulse 1.5s ease-in-out infinite;"></span>
                <span style="font-size:10px;color:#10b981;text-transform:uppercase;letter-spacing:2px;font-weight:600;">Live · Jira · 5 min cache</span>
            </div>
            <h1 style="font-size:26px;font-weight:900;margin:0;background:linear-gradient(90deg,#00d4ff,#818cf8,#f472b6);background-size:300% auto;-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:shimmer 4s linear infinite;">
                Jules Sprint Dashboard
            </h1>
            <div style="font-size:12px;color:#475569;margin-top:4px;">
                {sprint_name} · {sprint_start.strftime('%b %d')} – {sprint_end.strftime('%b %d, %Y')} · {fetched_at}
            </div>
            <div style="font-size:11px;color:#334155;margin-top:4px;font-style:italic;">💡 {tip}</div>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
            <div style="background:rgba(0,212,255,0.07);border:1px solid rgba(0,212,255,0.18);border-radius:10px;padding:10px 16px;font-size:12px;color:#7dd3fc;text-align:center;animation:bounceIn 0.5s ease both;">
                📅 Day <strong>{m['current_day']}</strong> / {sprint_days}<br>
                <span style="color:#475569;font-size:10px;">{days_left} days left</span>
            </div>
            <div style="background:{sc}12;border:1px solid {sc}35;border-radius:10px;padding:10px 16px;font-size:12px;color:{sc};text-align:center;animation:bounceIn 0.7s ease both;">
                {sl}<br><span style="color:#475569;font-size:10px;">{pct}% done</span>
            </div>
        </div>
    </div>
    <style>
    @keyframes livePulse {{ 0%,100% {{ opacity:.5;box-shadow:0 0 0 0 rgba(16,185,129,0.4); }} 50% {{ opacity:1;box-shadow:0 0 0 6px rgba(16,185,129,0); }} }}
    @keyframes shimmer {{ 0%{{background-position:-300% center}} 100%{{background-position:300% center}} }}
    @keyframes fadeInLeft {{ from{{opacity:0;transform:translateX(-20px)}} to{{opacity:1;transform:translateX(0)}} }}
    @keyframes bounceIn {{ 0%{{opacity:0;transform:scale(0.3)}} 50%{{opacity:1;transform:scale(1.05)}} 70%{{transform:scale(0.95)}} 100%{{transform:scale(1)}} }}
    @keyframes float-particle {{ 0%{{transform:translateY(100vh) translateX(0) rotate(0deg);opacity:0}} 10%{{opacity:0.4}} 90%{{opacity:0.2}} 100%{{transform:translateY(-10vh) translateX(50px) rotate(360deg);opacity:0}} }}
    .particle {{ position:fixed;border-radius:50%;pointer-events:none;animation:float-particle linear infinite;z-index:0; }}
    </style>
    """)


# ─── OVERVIEW TAB ─────────────────────────────────────────
def render_overview(m, tickets):
    total = m["total"]
    done_ct = len(m["done_tickets"])
    blocked_ct = len(m["blocked_tickets"])
    carried_ct = sum(1 for t in tickets if t.get("carried_over", False))

    cols = st.columns(8)
    with cols[0]: kpi_card("🎯", "Total", total, "#00d4ff")
    with cols[1]: kpi_card("✅", "Done", done_ct, "#10b981", "Jules def.")
    with cols[2]: kpi_card("⚡", "True Velocity", f"{m['true_velocity_sp']} SP", "#818cf8", f"{m['true_velocity']} tickets")
    with cols[3]: kpi_card("⏳", "Remaining", total - done_ct, "#7dd3fc")
    with cols[4]: kpi_card("🚫", "Blocked", blocked_ct, "#f87171")
    with cols[5]: kpi_card("💎", "Total SP", m["total_sp"], "#fb923c")
    with cols[6]: kpi_card("✨", "SP Done", m["done_sp"], "#34d399", f"{round((m['done_sp']/m['total_sp'])*100) if m['total_sp'] else 0}%")
    with cols[7]:
        pct = round((done_ct / total) * 100) if total else 0
        kpi_card("📊", "Done %", f"{pct}%", "#00d4ff")

    st.markdown("<br>", unsafe_allow_html=True)

    # True velocity detail
    st.markdown(f"""
    <div class="dash-card" style="padding:10px 14px;">
        <span style="font-size:11px;color:#818cf8;font-weight:700;">⚡ True Sprint Velocity</span>
        <span style="font-size:11px;color:#475569;margin-left:8px;">Based on resolution date</span>
        <span style="font-size:11px;color:#64748b;margin-left:16px;">💎 {m['true_velocity_sp']} SP completed this sprint</span>
        <span style="font-size:11px;color:#64748b;margin-left:12px;">🎫 {m['true_velocity']} tickets</span>
        <span style="font-size:11px;color:#64748b;margin-left:12px;">📦 {m['pre_sprint_done']} pre-sprint done</span>
    </div>
    """, unsafe_allow_html=True)

    # Missing SP warning
    if m["missing_sp_count"] > 0:
        missing_pct = round(m["missing_sp_count"] / total * 100) if total else 0
        first_5 = ", ".join(m["missing_sp_keys"][:5])
        more = f" +{m['missing_sp_count'] - 5} more" if m["missing_sp_count"] > 5 else ""
        st.html(f"""
        <div style="background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.25);border-radius:12px;padding:10px 14px;margin-bottom:12px;animation:borderGlow 3s ease-in-out infinite;">
            <span style="font-size:11px;color:#fbbf24;font-weight:700;">⚠️ Missing Story Points</span>
            <span style="font-size:11px;color:#64748b;margin-left:8px;">{m['missing_sp_count']}/{total} tickets ({missing_pct}%) have no SP assigned</span>
            <span style="font-size:10px;color:#475569;margin-left:12px;">{first_5}{more}</span>
        </div>
        <style>@keyframes borderGlow {{ 0%,100%{{border-color:rgba(251,191,36,0.15);}} 50%{{border-color:rgba(251,191,36,0.4);}} }}</style>
        """)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown("**🍩 Status Distribution**")
        status_data = [(s, m["status_counts"].get(s, 0)) for s in STATUS_ORDER if m["status_counts"].get(s, 0) > 0]
        fig = go.Figure(go.Pie(
            labels=[s[0] for s in status_data], values=[s[1] for s in status_data],
            hole=0.55, marker=dict(colors=[STATUS_COLORS.get(s[0], "#475569") for s in status_data]),
            textinfo="label+value", textfont=dict(size=10, color="#e2e8f0"),
            hovertemplate="<b>%{label}</b><br>%{value} tickets<extra></extra>",
        ))
        fig.update_layout(showlegend=False, height=280, margin=dict(l=0, r=0, t=10, b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans", color="#e2e8f0"))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="dash-card">', unsafe_allow_html=True)
        st.markdown("**📋 Group Summary**")
        groups = [
            ("✅ Done (Jules def.)", done_ct, "#10b981"),
            ("⚡ Active", len(m["active_tickets"]), "#38bdf8"),
            ("📋 To Do", len(m["todo_tickets"]), "#64748b"),
            ("🚫 Blocked", blocked_ct, "#f87171"),
            ("↩ Carried Over", carried_ct, "#fbbf24"),
        ]
        for label, count, color in groups:
            pct = round(count / total * 100) if total else 0
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(0,212,255,0.04);">
                <span style="font-size:12px;color:#e2e8f0;">{label}</span>
                <div style="display:flex;align-items:center;gap:8px;">
                    <div style="width:80px;height:6px;background:#0d1528;border-radius:3px;overflow:hidden;">
                        <div style="width:{pct}%;height:100%;background:{color};border-radius:3px;"></div>
                    </div>
                    <span style="font-size:12px;color:{color};font-weight:700;min-width:30px;text-align:right;">{count}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ─── BURNDOWN TAB ─────────────────────────────────────────
def render_burndown(m, sprint_days):
    total = m["total"]
    done_ct = len(m["done_tickets"])
    current_day = m["current_day"]

    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.markdown("**🔥 Sprint Burndown**")

    # Build ideal and actual lines
    days = list(range(1, sprint_days + 1))
    ideal = [total - (total * (d / sprint_days)) for d in range(sprint_days)]

    # Actual: we only know today's remaining
    remaining = total - done_ct
    actual_days = list(range(1, current_day + 1))
    # Linear interpolation from total to remaining
    actual_vals = [total - ((total - remaining) * (i / max(current_day - 1, 1))) for i in range(current_day)]
    if len(actual_vals) > 0:
        actual_vals[-1] = remaining

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[f"Day {d}" for d in days], y=ideal, name="Ideal",
        mode="lines", line=dict(color="#334155", width=2, dash="dot"),
        hovertemplate="<b>%{x}</b><br>Ideal: %{y:.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[f"Day {d}" for d in actual_days], y=actual_vals, name="Actual",
        mode="lines+markers", line=dict(color="#00d4ff", width=3),
        marker=dict(size=4, color="#00d4ff"),
        fill="tozeroy", fillcolor="rgba(0,212,255,0.06)",
        hovertemplate="<b>%{x}</b><br>Actual: %{y:.0f}<extra></extra>"))

    fig.update_layout(height=340, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans", color="#64748b"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8")),
        xaxis=dict(gridcolor="#1e2d47", tickfont=dict(size=10), tickangle=-20),
        yaxis=dict(gridcolor="#1e2d47", tickfont=dict(size=10), range=[0, total + 3]),
        margin=dict(l=0, r=0, t=10, b=40), hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)

    elapsed_pct = round(((current_day - 1) / (sprint_days - 1)) * 100) if sprint_days > 1 else 0
    st.progress(min(elapsed_pct / 100, 1.0), text=f"Sprint {elapsed_pct}% elapsed · {sprint_days - current_day} days remaining")
    st.markdown('</div>', unsafe_allow_html=True)


# ─── VELOCITY TAB ─────────────────────────────────────────
def render_velocity(m):
    devs = [(n, d) for n, d in m["dev_map"].items() if n not in EXCLUDE_FROM_CARDS]
    devs.sort(key=lambda x: x[1]["sp"], reverse=True)

    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.markdown("**⚡ Developer Velocity** — by Story Points")
    names = [n.split()[0] for n, _ in devs]
    fig = go.Figure()
    for label, key, color in [("✅ Done SP","done_sp","#10b981"), ("⚡ Active SP","active_sp","#38bdf8"), ("🚫 Blocked SP","blocked_sp","#f87171"), ("📋 Todo SP","todo_sp","#334155")]:
        fig.add_trace(go.Bar(name=label, x=names, y=[d[key] for _, d in devs], marker_color=color,
            hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y}}<extra></extra>"))
    fig.update_layout(barmode="stack", height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans", color="#64748b"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8"), orientation="h", y=-0.15),
        xaxis=dict(gridcolor="#1e2d47"), yaxis=dict(gridcolor="#1e2d47", title=dict(text="Story Points", font=dict(size=10, color="#475569"))),
        margin=dict(l=0, r=0, t=10, b=40))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Dev cards — SP based progress
    cards_html = '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;">'
    for name, d in devs:
        color = get_dev_color(name)
        sp_pct = round((d["done_sp"] / d["sp"]) * 100) if d["sp"] else 0
        initials = "".join(p[0] for p in name.split()[:2])
        blocked_badge = ""
        if d["blocked"] > 0:
            blocked_badge = f'<span style="font-size:9px;background:rgba(248,113,113,0.15);border:1px solid rgba(248,113,113,0.4);color:#f87171;border-radius:4px;padding:1px 5px;">🚫 {d["blocked"]}</span>'
        missing_sp_badge = ""
        no_sp_count = d["total"] - (1 if d["sp"] > 0 else 0)  # rough indicator
        tickets_with_sp = d["done"] + d["active"] + d["blocked"] + d["todo"]
        if d["sp"] == 0 and d["total"] > 0:
            missing_sp_badge = f'<span style="font-size:9px;background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.3);color:#fbbf24;border-radius:4px;padding:1px 5px;">⚠️ No SP</span>'
        cards_html += f"""
        <div class="dev-card" style="flex:1;min-width:140px;background:rgba(13,27,62,0.5);border:1px solid {color}30;border-radius:12px;padding:12px;text-align:center;cursor:default;">
            <div style="width:36px;height:36px;border-radius:50%;background:{color}25;border:2px solid {color};display:flex;align-items:center;justify-content:center;margin:0 auto 6px;font-size:13px;font-weight:700;color:{color};">{initials}</div>
            <div style="font-size:12px;font-weight:700;color:#e2e8f0;">{name.split()[0]}</div>
            <div style="font-size:10px;color:#475569;">{d['done_sp']}/{d['sp']} SP done · {d['done']}/{d['total']} tickets</div>
            <div style="width:100%;height:5px;background:#0d1528;border-radius:3px;margin-top:6px;overflow:hidden;">
                <div style="width:{sp_pct}%;height:100%;background:linear-gradient(90deg,{color},{color}cc);border-radius:3px;"></div>
            </div>
            <div style="font-size:10px;color:{color};margin-top:3px;">{sp_pct}% SP</div>
            {blocked_badge}{missing_sp_badge}
        </div>
        """
    cards_html += '</div>'
    cards_html += '<style>.dev-card{transition:all 0.25s ease !important;}.dev-card:hover{transform:translateY(-3px) !important;box-shadow:0 12px 32px rgba(0,0,0,0.3) !important;}</style>'
    st.html(cards_html)


# ─── STORY POINTS TAB ────────────────────────────────────
def render_points(m):
    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.markdown("**💎 Story Points by Developer**")

    devs = [(n, d) for n, d in m["dev_map"].items() if d["sp"] > 0 and n not in EXCLUDE_FROM_CARDS]
    devs.sort(key=lambda x: x[1]["sp"], reverse=True)

    if devs:
        names = [n.split()[0] for n, _ in devs]
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Done SP", x=names, y=[d["done_sp"] for _, d in devs],
            marker_color="#10b981", hovertemplate="<b>%{x}</b><br>Done: %{y} SP<extra></extra>"))
        fig.add_trace(go.Bar(name="Remaining SP", x=names, y=[d["sp"] - d["done_sp"] for _, d in devs],
            marker_color="#334155", hovertemplate="<b>%{x}</b><br>Remaining: %{y} SP<extra></extra>"))
        fig.update_layout(barmode="stack", height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans", color="#64748b"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8"), orientation="h", y=-0.15),
            xaxis=dict(gridcolor="#1e2d47"), yaxis=dict(gridcolor="#1e2d47"),
            margin=dict(l=0, r=0, t=10, b=40))
        st.plotly_chart(fig, use_container_width=True)

    # SP summary table
    for name, d in devs:
        color = get_dev_color(name)
        pct = round((d["done_sp"] / d["sp"]) * 100) if d["sp"] else 0
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid rgba(0,212,255,0.04);">
            <span style="font-size:12px;color:{color};font-weight:600;">{name}</span>
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-size:11px;color:#64748b;">{d['done_sp']}/{d['sp']} SP</span>
                <div style="width:60px;height:5px;background:#0d1528;border-radius:3px;overflow:hidden;">
                    <div style="width:{pct}%;height:100%;background:{color};border-radius:3px;"></div>
                </div>
                <span style="font-size:11px;color:{color};">{pct}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)


# ─── ALL TICKETS TAB ──────────────────────────────────────
def render_tickets(m, tickets):
    st.markdown("**🎫 All Tickets** — grouped by status")

    # Group by status in order
    grouped = {}
    for t in tickets:
        s = t["status"]
        grouped.setdefault(s, []).append(t)

    # Show known statuses first, then any unknown ones
    all_statuses = list(STATUS_ORDER) + [s for s in grouped if s not in STATUS_ORDER]

    for status in all_statuses:
        group = grouped.get(status, [])
        if not group:
            continue
        color = STATUS_COLORS.get(status, "#64748b")

        rows_html = ""
        for t in sorted(group, key=lambda x: x["key"]):
            sp_badge = f'<span style="font-size:9px;background:rgba(251,146,60,0.12);color:#fb923c;border-radius:3px;padding:1px 5px;margin-left:auto;">{t["sp"]} SP</span>' if t["sp"] else ""
            dev_color = get_dev_color(t["assignee"])
            assignee_badge = f'<span style="font-size:9px;color:{dev_color};margin-left:6px;">{t["assignee"].split()[0]}</span>'

            carried_badge = ""
            if t.get("carried_over"):
                prev_sprints = t.get("sprints", [])
                src = prev_sprints[0] if prev_sprints else "prev sprint"
                all_sprints = " → ".join(prev_sprints) if prev_sprints else ""
                carried_badge = f'<span style="font-size:9px;background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.35);color:#fbbf24;border-radius:4px;padding:1px 6px;margin-right:4px;white-space:nowrap;" title="Sprint history: {all_sprints}">↩ {src}</span>'

            rows_html += f'<div class="ticket-row">{carried_badge}<a class="ticket-key" href="{JIRA_BASE}/browse/{t["key"]}" target="_blank">{t["key"]}</a><a href="{JIRA_BASE}/browse/{t["key"]}" target="_blank" style="font-size:12px;color:#cbd5e1;text-decoration:none;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{t["summary"]}</a>{assignee_badge}{sp_badge}</div>'

        st.html(f"""
        <style>.ticket-row{{display:flex;align-items:center;padding:5px 0;border-bottom:1px solid rgba(0,212,255,0.04);font-size:12px;gap:6px;}}.ticket-row:last-child{{border-bottom:none;}}.ticket-key{{font-family:monospace;font-size:11px;color:#00d4ff;text-decoration:none;margin-right:6px;}}.ticket-key:hover{{color:#c4b5fd;}}</style>
        <div style="background:rgba(13,27,62,0.4);border:1px solid rgba(0,212,255,0.08);border-radius:14px;padding:16px 18px;margin-bottom:12px;">
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
                <span style="width:10px;height:10px;border-radius:50%;background:{color};display:inline-block;"></span>
                <span style="font-size:13px;font-weight:700;color:{color};">{status}</span>
                <span style="font-size:11px;color:#334155;">({len(group)})</span>
            </div>
            {rows_html}
        </div>
        """)


# ─── DAILY STANDUP REPORT ─────────────────────────────────
def render_daily_report(m, tickets, sprint_name, sprint_start, sprint_days):
    today_str = date.today().strftime("%A, %d %b %Y")
    days_left = sprint_days - m["current_day"]
    pct = round(len(m["done_tickets"]) / m["total"] * 100) if m["total"] else 0

    # Header
    st.html(f"""
    <div style="background:linear-gradient(135deg,rgba(0,212,255,0.08),rgba(129,140,248,0.08));border:1px solid rgba(0,212,255,0.15);border-radius:16px;padding:20px 24px;margin-bottom:16px;">
        <div style="font-size:10px;color:#00d4ff;text-transform:uppercase;letter-spacing:2px;font-weight:600;margin-bottom:6px;">☀️ DAILY STANDUP REPORT</div>
        <div style="font-size:22px;font-weight:900;color:#e2e8f0;">{today_str}</div>
        <div style="font-size:12px;color:#475569;margin-top:4px;">
            {sprint_name} · Day {m['current_day']}/{sprint_days} · {days_left} days left · {pct}% done · {m['done_sp']}/{m['total_sp']} SP
        </div>
    </div>
    """)

    # ── AIM OF THE DAY section ──
    aim_tickets = [t for t in tickets if t["status"] == "AIM OF THE DAY"]
    aim_by_dev = {}
    for t in aim_tickets:
        aim_by_dev.setdefault(t["assignee"], []).append(t)

    st.html(f"""
    <div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#fbbf24;margin:16px 0 10px;display:flex;align-items:center;gap:8px;">
        🎯 AIM OF THE DAY — {len(aim_tickets)} tickets
        <span style="flex:1;height:1px;background:linear-gradient(90deg,rgba(251,191,36,0.3),transparent);"></span>
    </div>
    """)

    if not aim_tickets:
        st.html('<div style="color:#475569;font-size:12px;padding:12px;font-style:italic;">No tickets in Aim of the Day right now.</div>')
    else:
        for dev_name in sorted(aim_by_dev.keys()):
            dev_tickets = aim_by_dev[dev_name]
            color = get_dev_color(dev_name)
            initials = "".join(p[0] for p in dev_name.split()[:2])
            rows = ""
            for t in dev_tickets:
                sp_badge = f'<span style="font-size:9px;background:rgba(251,146,60,0.12);color:#fb923c;border-radius:3px;padding:1px 5px;">{t["sp"]} SP</span>' if t["sp"] else '<span style="font-size:9px;color:#475569;">—</span>'
                rows += f'<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid rgba(0,212,255,0.04);"><a href="{JIRA_BASE}/browse/{t["key"]}" target="_blank" style="font-family:monospace;font-size:11px;color:#00d4ff;text-decoration:none;">{t["key"]}</a><span style="font-size:12px;color:#cbd5e1;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">{t["summary"]}</span>{sp_badge}</div>'

            st.html(f"""
            <div style="background:rgba(13,27,62,0.4);border:1px solid {color}25;border-radius:12px;padding:14px 16px;margin-bottom:10px;">
                <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
                    <div style="width:32px;height:32px;border-radius:50%;background:{color}25;border:2px solid {color};display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:{color};">{initials}</div>
                    <div>
                        <div style="font-size:13px;font-weight:700;color:{color};">{dev_name}</div>
                        <div style="font-size:10px;color:#475569;">{len(dev_tickets)} ticket{"s" if len(dev_tickets) != 1 else ""} aimed for today</div>
                    </div>
                </div>
                {rows}
            </div>
            """)

    # ── DEVELOPER SCORECARD ──
    st.html("""
    <div style="font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#818cf8;margin:20px 0 10px;display:flex;align-items:center;gap:8px;">
        📊 DEVELOPER SCORECARD
        <span style="flex:1;height:1px;background:linear-gradient(90deg,rgba(129,140,248,0.3),transparent);"></span>
    </div>
    """)

    devs = [(n, d) for n, d in m["dev_map"].items() if n not in EXCLUDE_FROM_CARDS]
    devs.sort(key=lambda x: x[1]["sp"], reverse=True)

    scorecard_html = '<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;">'
    for name, d in devs:
        color = get_dev_color(name)
        initials = "".join(p[0] for p in name.split()[:2])
        sp_pct = round((d["done_sp"] / d["sp"]) * 100) if d["sp"] else 0
        ticket_pct = round((d["done"] / d["total"]) * 100) if d["total"] else 0
        aim_count = len(aim_by_dev.get(name, []))

        # Status bar
        bars_html = ""
        for label, count, bc in [("Done", d["done"], "#10b981"), ("Active", d["active"], "#38bdf8"), ("Blocked", d["blocked"], "#f87171"), ("To Do", d["todo"], "#334155")]:
            if count > 0:
                bars_html += f'<span style="font-size:9px;color:{bc};margin-right:8px;">{label}: {count}</span>'

        blocked_alert = ""
        if d["blocked"] > 0:
            blocked_alert = f'<div style="margin-top:6px;font-size:9px;background:rgba(248,113,113,0.1);border:1px solid rgba(248,113,113,0.3);color:#f87171;border-radius:6px;padding:3px 8px;animation:borderGlow 2s ease-in-out infinite;">🚫 {d["blocked"]} blocked</div>'

        aim_badge = ""
        if aim_count > 0:
            aim_badge = f'<div style="margin-top:4px;font-size:9px;background:rgba(251,191,36,0.1);border:1px solid rgba(251,191,36,0.25);color:#fbbf24;border-radius:6px;padding:3px 8px;">🎯 {aim_count} aimed today</div>'

        scorecard_html += f"""
        <div style="background:rgba(13,27,62,0.5);border:1px solid {color}20;border-radius:14px;padding:16px;transition:all 0.25s ease;">
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px;">
                <div style="width:40px;height:40px;border-radius:50%;background:{color}20;border:2px solid {color};display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700;color:{color};">{initials}</div>
                <div>
                    <div style="font-size:14px;font-weight:700;color:#e2e8f0;">{name}</div>
                    <div style="font-size:10px;color:#475569;">{d['total']} tickets · {d['sp']} SP assigned</div>
                </div>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:8px;">
                <div style="text-align:center;">
                    <div style="font-size:18px;font-weight:900;color:#10b981;">{d['done_sp']}</div>
                    <div style="font-size:9px;color:#475569;">SP Done</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:18px;font-weight:900;color:{color};">{d['sp'] - d['done_sp']}</div>
                    <div style="font-size:9px;color:#475569;">SP Left</div>
                </div>
                <div style="text-align:center;">
                    <div style="font-size:18px;font-weight:900;color:#7dd3fc;">{d['done']}</div>
                    <div style="font-size:9px;color:#475569;">Tickets Done</div>
                </div>
            </div>
            <div style="width:100%;height:6px;background:#0d1528;border-radius:3px;overflow:hidden;margin-bottom:6px;">
                <div style="width:{sp_pct}%;height:100%;background:linear-gradient(90deg,{color},{color}cc);border-radius:3px;"></div>
            </div>
            <div style="font-size:10px;color:{color};text-align:center;">{sp_pct}% SP complete</div>
            <div style="margin-top:6px;">{bars_html}</div>
            {blocked_alert}{aim_badge}
        </div>
        """
    scorecard_html += '</div><style>@keyframes borderGlow{0%,100%{border-color:rgba(248,113,113,0.15)}50%{border-color:rgba(248,113,113,0.5)}}</style>'
    st.html(scorecard_html)

    # ── Post to Slack button ──
    st.markdown("<br>", unsafe_allow_html=True)
    col1, col2 = st.columns([4, 1])
    with col2:
        if st.button("📣 Post to Slack", key="daily_slack"):
            ok, msg = post_daily_slack(m, tickets, sprint_name, sprint_days)
            st.toast("✅ Daily report posted to Slack!" if ok else f"❌ {msg}", icon="📣" if ok else "⚠️")


def post_daily_slack(m, tickets, sprint_name, sprint_days):
    """Post a rich daily standup report to Slack — exact Jules Bot format."""
    if not SLACK_WEBHOOK:
        return False, "No webhook configured"

    import random
    today_str = date.today().strftime("%A, %d %b %Y")
    days_left = sprint_days - m["current_day"]
    total = m["total"]
    done_ct = len(m["done_tickets"])
    blocked_ct = len(m["blocked_tickets"])
    pct = round(done_ct / total * 100) if total else 0
    time_pct = round(m["current_day"] / sprint_days * 100) if sprint_days else 0
    greeting = random.choice(GREETINGS)
    tip = random.choice(SPRINT_TIPS)

    # ── Progress bar builder using colored blocks ──
    def make_bar(percent, filled_emoji="🟩", empty_emoji="⬜", width=20):
        filled = round(percent / 100 * width)
        return filled_emoji * filled + empty_emoji * (width - filled)

    # ── Sprint health ──
    if pct >= time_pct * 0.85:
        health_emoji, health_text = "🟢", "On Track — Sprint is progressing well"
    elif pct >= time_pct * 0.65:
        health_emoji, health_text = "🟡", "Slight Risk — Keep an eye on velocity"
    else:
        health_emoji, health_text = "🔴", "Behind Schedule — Needs attention"

    tickets_per_day = round((total - done_ct) / max(days_left, 1), 1) if days_left > 0 else 0

    # ── Dev color mapping for Slack blocks (auto-assigns for new devs) ──
    _slack_blocks = {"Nikita Vaidya": "🟪", "Satadru Roy": "🟥", "Rizky Ario": "🟧", "Jay Pitroda": "🟦"}
    _auto_blocks = ["🟨", "🟫", "🟩", "⬛"]
    _ab_idx = [0]
    def get_block(n):
        if n not in _slack_blocks:
            _slack_blocks[n] = _auto_blocks[_ab_idx[0] % len(_auto_blocks)]
            _ab_idx[0] += 1
        return _slack_blocks[n]

    blocks = [
        # Header
        {"type": "header", "text": {"type": "plain_text", "text": f"🚀 Jules Daily Standup — {today_str}"}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"{sprint_name}  ·  Day {m['current_day']} of {sprint_days}  ·  {greeting}"}]},

        # Sprint Burndown
        {"type": "section", "text": {"type": "mrkdwn", "text": "*📉 Sprint Burndown*"}},
        {"type": "section", "text": {"type": "mrkdwn", "text":
            f"`Time elapsed` {make_bar(time_pct, '🟥', '⬜')}  *{time_pct}%*\n"
            f"`Work done   ` {make_bar(pct, '🟩', '⬜')}  *{pct}%*"}},
        {"type": "context", "elements": [{"type": "mrkdwn",
            "text": f"{health_emoji} *{health_text}*\nNeed ~{tickets_per_day} tickets/day to finish  ·  {days_left} days left"}]},

        {"type": "divider"},

        # Sprint Snapshot
        {"type": "section", "text": {"type": "mrkdwn", "text": "*🗂️ Sprint Snapshot*"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"✅ *Done*\n{done_ct} / {total} tickets"},
            {"type": "mrkdwn", "text": f"💎 *Story Points*\n{m['done_sp']} / {m['total_sp']} SP"},
            {"type": "mrkdwn", "text": f"🚫 *Blocked*\n{blocked_ct} tickets"},
            {"type": "mrkdwn", "text": f"🗓️ *Days Left*\n{days_left} of {sprint_days} days"},
        ]},

        {"type": "divider"},
    ]

    # ── Team Velocity ──
    devs = [(n, d) for n, d in m["dev_map"].items() if n not in EXCLUDE_FROM_CARDS]
    devs.sort(key=lambda x: x[1]["done"], reverse=True)

    velocity_lines = ["*👥 Team Velocity*\n"]
    for name, d in devs:
        first = name.split()[0]
        ticket_pct = round((d["done"] / d["total"]) * 100) if d["total"] else 0
        block = get_block(name)
        bar = make_bar(ticket_pct, block, "⬜", 10)
        blocked_flag = f"🚫 {d['blocked']} Blocked" if d["blocked"] > 0 else "✅ Clear"
        velocity_lines.append(
            f"{first}  {bar}  *{ticket_pct}%*  {d['done']}/{d['total']} tickets · {d['done_sp']}/{d['sp']} SP  {blocked_flag}"
        )

    blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(velocity_lines)}})

    # ── Active Blockers ──
    if m["blocked_tickets"]:
        blocks.append({"type": "divider"})
        blocker_lines = [f"*🚫 Active Blockers ({blocked_ct})*\n"]
        for t in m["blocked_tickets"][:8]:
            first = t["assignee"].split()[0]
            summary = t["summary"][:60] + ("..." if len(t["summary"]) > 60 else "")
            blocker_lines.append(
                f"`{t['key']}`  →  {summary}  —  *{first}*"
            )
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(blocker_lines)}})

    # ── Go-Live Blocker Tickets ──
    go_live_tickets = fetch_go_live_blocker_tickets()
    if go_live_tickets:
        open_gl = [t for t in go_live_tickets if t["status"] not in DONE_STATUSES]
        done_gl = [t for t in go_live_tickets if t["status"] in DONE_STATUSES]
        blocks.append({"type": "divider"})
        gl_lines = [f"*🚦 Go-Live Blockers ({len(go_live_tickets)} total · {len(open_gl)} open · {len(done_gl)} resolved)*\n"]
        for t in go_live_tickets[:20]:
            first = t["assignee"].split()[0]
            summary = t["summary"][:55] + ("..." if len(t["summary"]) > 55 else "")
            status_icon = "✅" if t["status"] in DONE_STATUSES else "🔴"
            gl_lines.append(
                f"{status_icon} `{t['key']}`  →  {summary}  —  *{first}*  _{t['status']}_"
            )
        if len(go_live_tickets) > 20:
            gl_lines.append(f"_... and {len(go_live_tickets) - 20} more_")
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "\n".join(gl_lines)}})

    # ── Tip of the Day ──
    blocks.append({"type": "divider"})
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"💡 *Tip of the Day*  —  {tip}"}]})

    # ── Action Buttons ──
    blocks.append({"type": "actions", "elements": [
        {"type": "button", "text": {"type": "plain_text", "text": "📊 Live Dashboard"},
         "url": "https://julesdashboard.streamlit.app", "style": "primary"},
        {"type": "button", "text": {"type": "plain_text", "text": "📋 Jira Board"},
         "url": f"{JIRA_BASE}/jira/software/c/projects/{PROJECT}/boards"},
    ]})

    try:
        resp = requests.post(SLACK_WEBHOOK, json={"blocks": blocks}, timeout=15)
        return resp.status_code == 200, resp.text
    except Exception as e:
        return False, str(e)


# ─── ALL HISTORY TAB (NEW) ────────────────────────────────
def render_all_history():
    """
    New tab: browse every ticket across ALL sprints with filters for
    Sprint, Assignee (company-proxy), Fix Version, and Created Date range.
    Includes summary KPIs and a paginated ticket table.
    """
    st.html("""
    <div style="background:linear-gradient(135deg,rgba(0,212,255,0.07),rgba(129,140,248,0.07));
        border:1px solid rgba(0,212,255,0.12);border-radius:14px;padding:16px 20px;margin-bottom:16px;">
        <div style="font-size:10px;color:#00d4ff;text-transform:uppercase;letter-spacing:2px;font-weight:600;margin-bottom:4px;">
            📜 ALL SPRINTS HISTORY
        </div>
        <div style="font-size:18px;font-weight:900;color:#e2e8f0;">Complete Ticket Archive</div>
        <div style="font-size:12px;color:#475569;margin-top:3px;">
            Browse every ticket across all sprints · Filter by sprint, assignee, fix version, or date
        </div>
    </div>
    """)

    # ── Load data ──
    with st.spinner("Loading full ticket history…"):
        try:
            all_tickets, all_sprint_meta = fetch_all_sprints_tickets()
        except Exception as e:
            st.error(f"Failed to load history: {e}")
            return

    if not all_tickets:
        st.info("No historical tickets found. Check your Jira connection.")
        return

    # ── Fetch PR links for all tickets (batched, cached) ──
    all_keys_tuple = tuple(t["key"] for t in all_tickets)
    with st.spinner("Loading pull request data…"):
        try:
            pr_map = fetch_prs_for_issues(all_keys_tuple)
        except Exception:
            pr_map = {}
    # Attach to tickets
    for t in all_tickets:
        if "pull_requests" not in t:
            t["pull_requests"] = pr_map.get(t["key"], [])

    # ── Build filter option lists ──

    # Sprints — sorted newest first using sprint name
    sprint_names_sorted = []
    seen_sprint_names = set()
    # Use sprint meta for ordering if available
    if all_sprint_meta:
        for sm in reversed(all_sprint_meta):  # reversed = newest first
            n = sm["name"]
            if n and n not in seen_sprint_names:
                sprint_names_sorted.append(n)
                seen_sprint_names.add(n)
    # Add any sprint names found in tickets but not in meta
    for t in all_tickets:
        for sn in t.get("sprints", []):
            if sn and sn not in seen_sprint_names:
                sprint_names_sorted.append(sn)
                seen_sprint_names.add(sn)

    sprint_options = ["🏃 All Sprints"] + sprint_names_sorted

    # Assignees (used as "company / person" filter)
    assignee_set = sorted({t["assignee"] for t in all_tickets if t["assignee"]})
    assignee_options = ["👤 All Assignees"] + assignee_set

    # Fix versions
    fv_set = set()
    for t in all_tickets:
        for fv in t.get("fix_versions", []):
            if fv:
                fv_set.add(fv)
    fv_options = ["📦 All Fix Versions"] + sorted(fv_set)

    # Date range bounds
    all_dates = [t["created_date"] for t in all_tickets if t.get("created_date")]
    if all_dates:
        min_date = date.fromisoformat(min(all_dates))
        max_date = date.fromisoformat(max(all_dates))
    else:
        min_date = date.today() - timedelta(days=180)
        max_date = date.today()

    # ── Filter UI ──
    # No pre-initialisation needed — widgets manage their own state.
    # Clear buttons use .pop() to delete the key, which lets the widget
    # re-initialise from its default on the next run (avoids StreamlitAPIException).

    st.markdown('<div class="dash-card" style="padding:14px 16px;margin-bottom:14px;">', unsafe_allow_html=True)
    st.markdown(
        '<div style="font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
        'color:#475569;margin-bottom:10px;">🔍 Filters</div>',
        unsafe_allow_html=True,
    )

    # ── Row 1: Sprint | Assignee | Fix Version — each with a ✕ clear button ──
    fc1, fx1, fc2, fx2, fc3, fx3 = st.columns([5, 1, 5, 1, 5, 1])
    with fc1:
        sel_sprint = st.selectbox("Sprint", sprint_options, key="hist_sprint")
    with fx1:
        st.markdown("<div style='padding-top:24px;'>", unsafe_allow_html=True)
        if st.button("✕", key="clr_sprint", help="Clear sprint filter",
                     disabled=(sel_sprint == sprint_options[0])):
            st.session_state.pop("hist_sprint", None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with fc2:
        sel_assignee = st.selectbox("Assignee / Company", assignee_options, key="hist_assignee")
    with fx2:
        st.markdown("<div style='padding-top:24px;'>", unsafe_allow_html=True)
        if st.button("✕", key="clr_assignee", help="Clear assignee filter",
                     disabled=(sel_assignee == assignee_options[0])):
            st.session_state.pop("hist_assignee", None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with fc3:
        sel_fv = st.selectbox("Fix Version", fv_options, key="hist_fv")
    with fx3:
        st.markdown("<div style='padding-top:24px;'>", unsafe_allow_html=True)
        if st.button("✕", key="clr_fv", help="Clear fix version filter",
                     disabled=(sel_fv == fv_options[0])):
            st.session_state.pop("hist_fv", None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Row 2: Date From | Date To | Status Group — each with a ✕ clear button ──
    fd1, fx4, fd2, fx5, fd3, fx6 = st.columns([5, 1, 5, 1, 4, 1])
    with fd1:
        date_from = st.date_input("Created From", value=min_date, min_value=min_date,
                                   max_value=max_date, key="hist_date_from")
    with fx4:
        st.markdown("<div style='padding-top:24px;'>", unsafe_allow_html=True)
        if st.button("✕", key="clr_date_from", help="Reset start date",
                     disabled=(date_from == min_date)):
            st.session_state.pop("hist_date_from", None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with fd2:
        date_to = st.date_input("Created To", value=max_date, min_value=min_date,
                                 max_value=max_date, key="hist_date_to")
    with fx5:
        st.markdown("<div style='padding-top:24px;'>", unsafe_allow_html=True)
        if st.button("✕", key="clr_date_to", help="Reset end date",
                     disabled=(date_to == max_date)):
            st.session_state.pop("hist_date_to", None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    with fd3:
        sel_status = st.selectbox(
            "Status Group",
            ["All Statuses", "✅ Done", "⚡ Active", "🚫 Blocked", "📋 To Do"],
            key="hist_status_group",
        )
    with fx6:
        st.markdown("<div style='padding-top:24px;'>", unsafe_allow_html=True)
        if st.button("✕", key="clr_status", help="Clear status filter",
                     disabled=(sel_status == "All Statuses")):
            st.session_state.pop("hist_status_group", None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Search + Reset All row ──
    fs1, fs2 = st.columns([5, 1])
    with fs1:
        search_text = st.text_input(
            "🔎 Search ticket key or summary", placeholder="e.g. JENG-123 or login bug",
            key="hist_search", label_visibility="visible"
        )
    with fs2:
        st.markdown("<div style='padding-top:24px;'>", unsafe_allow_html=True)
        if st.button("↺ Reset all", key="clr_all", help="Clear all filters"):
            for k in ["hist_sprint", "hist_assignee", "hist_fv",
                      "hist_status_group", "hist_date_from", "hist_date_to", "hist_search"]:
                st.session_state.pop(k, None)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Apply filters ──
    filtered = list(all_tickets)

    if sel_sprint != "🏃 All Sprints":
        filtered = [t for t in filtered if sel_sprint in t.get("sprints", [])]

    if sel_assignee != "👤 All Assignees":
        filtered = [t for t in filtered if t["assignee"] == sel_assignee]

    if sel_fv != "📦 All Fix Versions":
        filtered = [t for t in filtered if sel_fv in t.get("fix_versions", [])]

    if sel_status != "All Statuses":
        if sel_status == "✅ Done":
            filtered = [t for t in filtered if t["status"] in DONE_STATUSES]
        elif sel_status == "⚡ Active":
            filtered = [t for t in filtered if t["status"] in ACTIVE_STATUSES]
        elif sel_status == "🚫 Blocked":
            filtered = [t for t in filtered if t["status"] in BLOCKED_STATUSES]
        elif sel_status == "📋 To Do":
            filtered = [t for t in filtered if t["status"] == "To Do"]

    # Date filter on created_date
    filtered = [
        t for t in filtered
        if t.get("created_date") and
           date_from <= date.fromisoformat(t["created_date"]) <= date_to
    ]

    # Text search
    if search_text.strip():
        q = search_text.strip().lower()
        filtered = [
            t for t in filtered
            if q in t["key"].lower() or q in t["summary"].lower()
        ]

    # ── Summary KPIs ──
    total_h = len(filtered)
    done_h = sum(1 for t in filtered if t["status"] in DONE_STATUSES)
    blocked_h = sum(1 for t in filtered if t["status"] in BLOCKED_STATUSES)
    total_sp_h = sum(t["sp"] or 0 for t in filtered)
    done_sp_h = sum(t["sp"] or 0 for t in filtered if t["status"] in DONE_STATUSES)
    carried_h = sum(1 for t in filtered if t.get("carried_over"))

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1: kpi_card("🎫", "Tickets", total_h, "#00d4ff")
    with k2: kpi_card("✅", "Done", done_h, "#10b981", f"{round(done_h/total_h*100) if total_h else 0}%")
    with k3: kpi_card("🚫", "Blocked", blocked_h, "#f87171")
    with k4: kpi_card("💎", "Total SP", total_sp_h, "#fb923c")
    with k5: kpi_card("✨", "Done SP", done_sp_h, "#34d399")
    with k6: kpi_card("↩", "Carried Over", carried_h, "#fbbf24")

    st.markdown("<br>", unsafe_allow_html=True)

    if total_h == 0:
        st.info("No tickets match the selected filters.")
        return

    # ── Sprint breakdown chart ──
    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.markdown("**📊 Tickets per Sprint** — filtered view")

    sprint_counts: dict = {}
    sprint_done: dict = {}
    for t in filtered:
        for sn in (t.get("sprints") or []):
            sprint_counts[sn] = sprint_counts.get(sn, 0) + 1
            if t["status"] in DONE_STATUSES:
                sprint_done[sn] = sprint_done.get(sn, 0) + 1

    # Order by sprint_names_sorted list
    chart_sprints = [sn for sn in sprint_names_sorted if sn in sprint_counts]
    # Add any not in meta
    for sn in sprint_counts:
        if sn not in chart_sprints:
            chart_sprints.append(sn)

    if chart_sprints:
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            name="Total", x=chart_sprints,
            y=[sprint_counts.get(s, 0) for s in chart_sprints],
            marker_color="#1e3a5f",
            hovertemplate="<b>%{x}</b><br>Total: %{y}<extra></extra>",
        ))
        fig2.add_trace(go.Bar(
            name="Done", x=chart_sprints,
            y=[sprint_done.get(s, 0) for s in chart_sprints],
            marker_color="#10b981",
            hovertemplate="<b>%{x}</b><br>Done: %{y}<extra></extra>",
        ))
        fig2.update_layout(
            barmode="overlay", height=240,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans", color="#64748b"),
            legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8"),
                        orientation="h", y=-0.2),
            xaxis=dict(gridcolor="#1e2d47", tickangle=-30, tickfont=dict(size=10)),
            yaxis=dict(gridcolor="#1e2d47"),
            margin=dict(l=0, r=0, t=10, b=50),
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # ── Ticket table — all tickets, no pagination ──
    st.markdown(
        f'<div style="font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;'
        f'color:#475569;margin:16px 0 10px;">🎫 {total_h} TICKETS</div>',
        unsafe_allow_html=True,
    )

    # Sort options
    sort_by = st.selectbox(
        "Sort by",
        ["Key (newest)", "Key (oldest)", "Status", "Assignee", "Story Points ↓", "Created ↓"],
        key="hist_sort", label_visibility="collapsed",
    )

    # Apply sort
    def sort_key(t):
        if sort_by == "Key (newest)":
            try:
                return -int(t["key"].split("-")[1])
            except Exception:
                return 0
        elif sort_by == "Key (oldest)":
            try:
                return int(t["key"].split("-")[1])
            except Exception:
                return 0
        elif sort_by == "Status":
            idx = STATUS_ORDER.index(t["status"]) if t["status"] in STATUS_ORDER else 99
            return idx
        elif sort_by == "Assignee":
            return t["assignee"]
        elif sort_by == "Story Points ↓":
            return -(t["sp"] or 0)
        elif sort_by == "Created ↓":
            return t.get("created_date", "") or ""
        return t["key"]

    sorted_tickets = sorted(filtered, key=sort_key)

    # Render ticket rows
    rows_html = ""
    for t in sorted_tickets:
        status_color = STATUS_COLORS.get(t["status"], "#64748b")
        dev_color = get_dev_color(t["assignee"])
        sp_badge = (
            f'<span style="font-size:9px;background:rgba(251,146,60,0.12);color:#fb923c;'
            f'border-radius:3px;padding:1px 5px;">{t["sp"]} SP</span>'
            if t["sp"] else
            '<span style="font-size:9px;color:#334155;">— SP</span>'
        )
        carried_badge = (
            '<span style="font-size:9px;background:rgba(251,191,36,0.1);border:1px solid '
            'rgba(251,191,36,0.3);color:#fbbf24;border-radius:3px;padding:1px 5px;">↩</span> '
            if t.get("carried_over") else ""
        )
        fv_badge = ""
        if t.get("fix_versions"):
            fv_badge = (
                f'<span style="font-size:9px;background:rgba(129,140,248,0.1);color:#818cf8;'
                f'border-radius:3px;padding:1px 5px;margin-left:4px;">{t["fix_versions"][0]}</span>'
            )
        sprint_label = t["sprints"][-1] if t.get("sprints") else "—"
        created_str = t.get("created_date", "")[:10] or "—"

        # ── PR cell ──
        prs = t.get("pull_requests", [])
        if prs:
            pr_links = ""
            for pr in prs:
                state = pr.get("state", "").upper()
                if state in ("MERGED", "CLOSED", "DONE"):
                    pr_color = "#818cf8"
                    pr_icon  = "⛙"
                elif state in ("OPEN", "IN_PROGRESS"):
                    pr_color = "#10b981"
                    pr_icon  = "⛙"
                else:
                    pr_color = "#64748b"
                    pr_icon  = "⛙"
                title_short = pr["title"][:22] + "…" if len(pr["title"]) > 22 else pr["title"]
                pr_links += (
                    f'<a href="{pr["url"]}" target="_blank" '
                    f'title="{pr["title"]} [{state}]" '
                    f'style="font-size:9px;color:{pr_color};text-decoration:none;'
                    f'background:{pr_color}15;border:1px solid {pr_color}40;'
                    f'border-radius:4px;padding:1px 5px;white-space:nowrap;'
                    f'display:inline-block;margin-right:3px;">'
                    f'{pr_icon} {title_short}</a>'
                )
            pr_cell = f'<div style="min-width:110px;flex-shrink:0;overflow:hidden;">{pr_links}</div>'
        else:
            pr_cell = '<div style="min-width:110px;flex-shrink:0;font-size:9px;color:#1e2d47;">—</div>'

        rows_html += f"""
        <div style="display:flex;align-items:center;gap:6px;padding:6px 0;
            border-bottom:1px solid rgba(0,212,255,0.04);font-size:12px;flex-wrap:nowrap;">
            {carried_badge}
            <a href="{JIRA_BASE}/browse/{t['key']}" target="_blank"
               style="font-family:monospace;font-size:11px;color:#00d4ff;text-decoration:none;
                      min-width:80px;flex-shrink:0;">{t['key']}</a>
            <span style="flex:1;color:#cbd5e1;overflow:hidden;text-overflow:ellipsis;
                         white-space:nowrap;" title="{t['summary']}">{t['summary']}</span>
            <span style="font-size:9px;background:{status_color}18;color:{status_color};
                         border-radius:4px;padding:2px 6px;white-space:nowrap;flex-shrink:0;">
                {t['status']}</span>
            <span style="font-size:10px;color:{dev_color};white-space:nowrap;
                         flex-shrink:0;min-width:60px;">{t['assignee'].split()[0]}</span>
            <span style="font-size:9px;color:#334155;white-space:nowrap;
                         flex-shrink:0;min-width:80px;overflow:hidden;text-overflow:ellipsis;"
                  title="{sprint_label}">{sprint_label[:14]}…</span>
            {sp_badge}{fv_badge}
            {pr_cell}
            <span style="font-size:9px;color:#334155;flex-shrink:0;">{created_str}</span>
        </div>
        """

    st.html(f"""
    <div style="background:rgba(13,27,62,0.4);border:1px solid rgba(0,212,255,0.08);
        border-radius:14px;padding:14px 16px;">
        <div style="display:flex;gap:6px;padding:4px 0 8px;border-bottom:1px solid rgba(0,212,255,0.08);
            font-size:10px;font-weight:700;color:#334155;text-transform:uppercase;letter-spacing:1px;">
            <span style="min-width:80px;">Key</span>
            <span style="flex:1;">Summary</span>
            <span style="min-width:90px;">Status</span>
            <span style="min-width:60px;">Assignee</span>
            <span style="min-width:80px;">Sprint</span>
            <span style="min-width:45px;">SP</span>
            <span style="min-width:110px;">Pull Request</span>
            <span style="min-width:70px;">Created</span>
        </div>
        {rows_html}
    </div>
    """)

    st.markdown(
        f'<div style="font-size:10px;color:#334155;text-align:center;margin-top:8px;">'
        f'Showing all {total_h} tickets'
        f'</div>',
        unsafe_allow_html=True,
    )


# ─── MAIN APP ─────────────────────────────────────────────
def main():
    if not check_pin():
        return

    # Sidebar controls
    with st.sidebar:
        st.markdown("### ⚙️ Controls")
        if st.button("🔄 Force Refresh", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        st.markdown("**Slack Notifications**")
        auto_slack = st.toggle("Auto-post on load", value=False)
        st.markdown("---")
        st.markdown(f"**Project:** {PROJECT}")
        st.markdown(f"**Jira:** [minehub.atlassian.net]({JIRA_BASE})")

    # Fetch data with animated loading
    with st.spinner(""):
        loading_placeholder = st.empty()
        loading_placeholder.markdown("""
        <div style="text-align:center;padding:60px 20px;">
            <div style="font-size:52px;margin-bottom:16px;">🚀</div>
            <h2 style="background:linear-gradient(90deg,#00d4ff,#818cf8,#f472b6);
                -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                font-size:24px;font-weight:900;margin-bottom:8px;">Fetching Sprint Data</h2>
            <p style="color:#475569;font-size:13px;margin-bottom:28px;">Connecting to Jira...</p>
            <div style="display:flex;gap:10px;justify-content:center;">
                <div style="width:10px;height:10px;border-radius:50%;background:#00d4ff;animation:pulse 0.8s ease-in-out infinite;"></div>
                <div style="width:10px;height:10px;border-radius:50%;background:#818cf8;animation:pulse 0.8s ease-in-out 0.2s infinite;"></div>
                <div style="width:10px;height:10px;border-radius:50%;background:#f472b6;animation:pulse 0.8s ease-in-out 0.4s infinite;"></div>
            </div>
            <style>@keyframes pulse{0%,100%{opacity:.3;transform:scale(.8)}50%{opacity:1;transform:scale(1.2)}}</style>
        </div>
        """, unsafe_allow_html=True)

        try:
            tickets = fetch_jira_tickets()
            sprints = fetch_available_sprints()
            fetched_at = datetime.now().strftime("%d %b %Y, %H:%M")
        except Exception as e:
            loading_placeholder.empty()
            st.error(f"❌ Failed to fetch Jira data: {e}")
            st.info("Check your JIRA_EMAIL and JIRA_API_TOKEN in Streamlit secrets.")
            return

        loading_placeholder.empty()

    # Get active sprint dates
    sprint_start, sprint_end, sprint_name = get_active_sprint_dates(sprints)
    sprint_days = max((sprint_end - sprint_start).days, 1)

    # ── Controls row: Fix Version filter + Carried-over toggle ──
    # Get unique fix versions
    all_fix_versions = set()
    for t in tickets:
        for fv in t.get("fix_versions", []):
            all_fix_versions.add(fv)
    fix_version_list = ["📦 All Fix Versions"] + sorted(all_fix_versions)

    carried_ct = sum(1 for t in tickets if t.get("carried_over", False))

    ctrl1, ctrl2, ctrl3 = st.columns([2, 1, 1])
    with ctrl1:
        selected_fv = st.selectbox("Fix Version", fix_version_list, label_visibility="collapsed")
    with ctrl2:
        show_carried = st.toggle("↩ Show carried-over", value=True)
    with ctrl3:
        st.markdown(f'<div style="font-size:11px;color:#fbbf24;padding-top:8px;">↩ {carried_ct} carried</div>', unsafe_allow_html=True)

    # Apply filters
    filtered_tickets = tickets
    if selected_fv != "📦 All Fix Versions":
        filtered_tickets = [t for t in filtered_tickets if selected_fv in t.get("fix_versions", [])]
    if not show_carried:
        filtered_tickets = [t for t in filtered_tickets if not t.get("carried_over", False)]

    m = build_metrics(filtered_tickets, sprint_start=sprint_start, sprint_days=sprint_days)

    # Auto-post to Slack if enabled
    if auto_slack and SLACK_WEBHOOK and m["blocked_tickets"]:
        ok, _ = post_to_slack(m["blocked_tickets"], m)
        if ok:
            st.toast("✅ Posted to Slack!", icon="📣")

    # Header
    render_header(m, fetched_at, sprint_name, sprint_start, sprint_days)

    # Slack / Refresh buttons
    if SLACK_WEBHOOK:
        col1, col2, col3 = st.columns([6, 1, 1])
        with col2:
            if st.button("📣 Post to Slack"):
                ok, msg = post_to_slack(m["blocked_tickets"], m)
                st.toast("✅ Posted to Slack!" if ok else f"❌ {msg}", icon="📣" if ok else "⚠️")
        with col3:
            if st.button("🔄 Refresh"):
                st.cache_data.clear()
                st.rerun()
    else:
        col1, col2 = st.columns([7, 1])
        with col2:
            if st.button("🔄 Refresh"):
                st.cache_data.clear()
                st.rerun()

    # Tabs — new "📜 All History" tab added at the end
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📊 Overview", "🔥 Burndown", "⚡ Velocity", "💎 Story Points",
        "🎫 All Tickets", "☀️ Daily Standup", "📜 All History",
    ])
    with tab1: render_overview(m, filtered_tickets)
    with tab2: render_burndown(m, sprint_days)
    with tab3: render_velocity(m)
    with tab4: render_points(m)
    with tab5: render_tickets(m, filtered_tickets)
    with tab6: render_daily_report(m, filtered_tickets, sprint_name, sprint_start, sprint_days)
    with tab7: render_all_history()

    # Footer
    st.markdown(f"""
    <div style="text-align:center;font-size:9px;color:#1e2d47;border-top:1px solid #0d1528;padding-top:12px;margin-top:20px;">
        Jules Product · MineHub · {sprint_name} · {m['total']} tickets · {m['total_sp']} SP · {fetched_at}
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
