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
                     "PO/QA Test run", "Aim Of The week", "PO not valid"}

DEV_COLORS = {
    "Nikita Vaidya": "#818cf8",
    "Satadru Roy":   "#f472b6",
    "Rizky Ario":    "#fb923c",
    "Jay Pitroda":   "#34d399",
    "Unassigned":    "#64748b",
}

STATUS_COLORS = {
    "Done": "#10b981", "PO/QA VALID": "#34d399", "PO/QA Test run": "#6ee7b7",
    "Demo": "#a7f3d0", "In Production": "#059669", "CS Reviewed": "#065f46",
    "PO review": "#818cf8", "Tech review": "#a78bfa", "In Progress": "#38bdf8",
    "AIM OF THE DAY": "#7dd3fc", "Aim Of The week": "#bae6fd",
    "To Do": "#64748b", "Blocked": "#f87171", "PO not valid": "#f97316",
}

STATUS_ORDER = [
    "Done", "PO/QA VALID", "Demo", "In Production", "CS Reviewed",
    "PO/QA Test run", "Tech review", "PO review",
    "AIM OF THE DAY", "In Progress", "Aim Of The week",
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
.dash-card { background: rgba(13,27,62,0.4); border: 1px solid rgba(0,212,255,0.08); border-radius: 14px; padding: 16px 18px; margin-bottom: 12px; }
.live-dot { width: 7px; height: 7px; border-radius: 50%; background: #10b981; display: inline-block; animation: livePulse 1.5s ease-in-out infinite; }
@keyframes livePulse { 0%,100% { opacity: .5; box-shadow: 0 0 0 0 rgba(16,185,129,0.4); } 50% { opacity: 1; box-shadow: 0 0 0 6px rgba(16,185,129,0); } }
.ticket-key { font-family: 'Space Mono', monospace; font-size: 11px; color: #00d4ff; text-decoration: none; margin-right: 6px; }
.ticket-key:hover { color: #c4b5fd; }
.ticket-row { display: flex; align-items: center; padding: 5px 0; border-bottom: 1px solid rgba(0,212,255,0.04); font-size: 12px; gap: 6px; }
.ticket-row:last-child { border-bottom: none; }
</style>
""", unsafe_allow_html=True)


# ─── PIN PROTECTION ───────────────────────────────────────
def check_pin():
    if not DASHBOARD_PIN:
        return True
    if "pin_ok" not in st.session_state:
        st.session_state.pin_ok = False
    if st.session_state.pin_ok:
        return True
    st.markdown("""
    <div style="text-align:center;padding:80px 20px;">
        <div style="font-size:48px;margin-bottom:12px;">🔒</div>
        <h2 style="background:linear-gradient(90deg,#00d4ff,#818cf8);-webkit-background-clip:text;
        -webkit-text-fill-color:transparent;font-size:22px;font-weight:900;">Jules Sprint Dashboard</h2>
        <p style="color:#475569;font-size:13px;">Enter PIN to continue</p>
    </div>
    """, unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        pin = st.text_input("PIN", type="password", label_visibility="collapsed", placeholder="Enter PIN...")
        if st.button("Unlock 🔓", use_container_width=True):
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
    # Fallback defaults
    return date(2026, 2, 24), date(2026, 4, 12), "Release Sprint 3"


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
            # Extract sprint names from customfield_10020
            sprint_names = []
            sprints_raw = f.get("customfield_10020") or []
            if isinstance(sprints_raw, list):
                for sp in sprints_raw:
                    if isinstance(sp, dict):
                        sprint_names.append(sp.get("name", ""))
                    elif isinstance(sp, str):
                        m = re.search(r'name=([^,\]]+)', sp)
                        if m:
                            sprint_names.append(m.group(1))

            # Extract fix versions
            fix_versions = []
            for fv in (f.get("fixVersions") or []):
                fix_versions.append(fv.get("name", ""))

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

    return all_tickets


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
            dev_map[name] = {"total": 0, "done": 0, "active": 0, "blocked": 0, "todo": 0, "sp": 0, "done_sp": 0}
        dev_map[name]["total"] += 1
        dev_map[name]["sp"] += t["sp"] or 0
        if t["status"] in DONE_STATUSES:
            dev_map[name]["done"] += 1
            dev_map[name]["done_sp"] += t["sp"] or 0
        elif t["status"] in BLOCKED_STATUSES:
            dev_map[name]["blocked"] += 1
        elif t["status"] in ACTIVE_STATUSES:
            dev_map[name]["active"] += 1
        else:
            dev_map[name]["todo"] += 1

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
    st.markdown(f"""
    <div style="background:rgba(13,27,62,0.5);border:1px solid {color}22;border-radius:12px;padding:12px 14px;text-align:center;">
        <div style="font-size:10px;color:#64748b;margin-bottom:2px;">{icon} {label}</div>
        <div style="font-size:22px;font-weight:900;color:{color};">{value}</div>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)


# ─── RENDER HEADER ────────────────────────────────────────
def render_header(m, fetched_at, sprint_name, sprint_start, sprint_days):
    days_left = sprint_days - m["current_day"]
    pct = round(len(m["done_tickets"]) / m["total"] * 100) if m["total"] else 0
    sc = "#10b981" if m["status"] == "on-track" else "#fbbf24" if m["status"] == "slight-risk" else "#f87171"
    sl = "On Track 🎯" if m["status"] == "on-track" else "Slight Risk ⚠️" if m["status"] == "slight-risk" else "Behind 🚨"
    sprint_end = sprint_start + timedelta(days=sprint_days) if sprint_start else date.today()

    import random
    tip = random.choice(SPRINT_TIPS)
    greeting = random.choice(GREETINGS)

    st.markdown(f"""
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:16px;flex-wrap:wrap;gap:12px;">
        <div>
            <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px;">
                <span class="live-dot"></span>
                <span style="font-size:10px;color:#10b981;text-transform:uppercase;letter-spacing:2px;font-weight:600;">Live · Jira · 5 min cache</span>
            </div>
            <h1 style="font-size:26px;font-weight:900;margin:0;background:linear-gradient(90deg,#00d4ff,#818cf8,#f472b6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                Jules Sprint Dashboard
            </h1>
            <div style="font-size:12px;color:#475569;margin-top:4px;">
                {sprint_name} · {sprint_start.strftime('%b %d')} – {sprint_end.strftime('%b %d, %Y')} · {fetched_at}
            </div>
            <div style="font-size:11px;color:#334155;margin-top:4px;font-style:italic;">💡 {tip}</div>
        </div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;">
            <div style="background:rgba(0,212,255,0.07);border:1px solid rgba(0,212,255,0.18);border-radius:10px;padding:10px 16px;font-size:12px;color:#7dd3fc;text-align:center;">
                📅 Day <strong>{m['current_day']}</strong> / {sprint_days}<br>
                <span style="color:#475569;font-size:10px;">{days_left} days left</span>
            </div>
            <div style="background:{sc}12;border:1px solid {sc}35;border-radius:10px;padding:10px 16px;font-size:12px;color:{sc};text-align:center;">
                {sl}<br><span style="color:#475569;font-size:10px;">{pct}% done</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# ─── OVERVIEW TAB ─────────────────────────────────────────
def render_overview(m, tickets):
    total = m["total"]
    done_ct = len(m["done_tickets"])
    blocked_ct = len(m["blocked_tickets"])
    carried_ct = sum(1 for t in tickets if t.get("carried_over", False))

    cols = st.columns(8)
    with cols[0]: kpi_card("🎯", "Total", total, "#00d4ff")
    with cols[1]: kpi_card("✅", "Done", done_ct, "#10b981", "Jules def.")
    with cols[2]: kpi_card("⚡", "True Velocity", m["true_velocity"], "#818cf8", "This sprint")
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
        <span style="font-size:11px;color:#64748b;margin-left:16px;">✅ {m['true_velocity']} completed this sprint</span>
        <span style="font-size:11px;color:#64748b;margin-left:12px;">📦 {m['pre_sprint_done']} pre-sprint done</span>
        <span style="font-size:11px;color:#64748b;margin-left:12px;">💎 {m['true_velocity_sp']} SP this sprint</span>
    </div>
    """, unsafe_allow_html=True)

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
    devs = [(n, d) for n, d in m["dev_map"].items() if n != "Unassigned"]
    devs.sort(key=lambda x: x[1]["total"], reverse=True)

    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.markdown("**⚡ Developer Velocity**")
    names = [n.split()[0] for n, _ in devs]
    fig = go.Figure()
    for label, key, color in [("✅ Done","done","#10b981"), ("⚡ Active","active","#38bdf8"), ("🚫 Blocked","blocked","#f87171"), ("📋 Todo","todo","#334155")]:
        fig.add_trace(go.Bar(name=label, x=names, y=[d[key] for _, d in devs], marker_color=color,
            hovertemplate=f"<b>%{{x}}</b><br>{label}: %{{y}}<extra></extra>"))
    fig.update_layout(barmode="stack", height=260, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans", color="#64748b"),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#94a3b8"), orientation="h", y=-0.15),
        xaxis=dict(gridcolor="#1e2d47"), yaxis=dict(gridcolor="#1e2d47"),
        margin=dict(l=0, r=0, t=10, b=40))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Dev cards
    cards_html = '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;">'
    for name, d in devs:
        color = DEV_COLORS.get(name, "#64748b")
        pct = round((d["done"] / d["total"]) * 100) if d["total"] else 0
        initials = "".join(p[0] for p in name.split()[:2])
        blocked_badge = ""
        if d["blocked"] > 0:
            blocked_badge = f'<span style="font-size:9px;background:rgba(248,113,113,0.15);border:1px solid rgba(248,113,113,0.4);color:#f87171;border-radius:4px;padding:1px 5px;">🚫 {d["blocked"]}</span>'
        cards_html += f"""
        <div style="flex:1;min-width:140px;background:rgba(13,27,62,0.5);border:1px solid {color}30;border-radius:12px;padding:12px;text-align:center;">
            <div style="width:36px;height:36px;border-radius:50%;background:{color}25;border:2px solid {color};display:flex;align-items:center;justify-content:center;margin:0 auto 6px;font-size:13px;font-weight:700;color:{color};">{initials}</div>
            <div style="font-size:12px;font-weight:700;color:#e2e8f0;">{name.split()[0]}</div>
            <div style="font-size:10px;color:#475569;">{d['done']}/{d['total']} done · {d['sp']} SP</div>
            <div style="width:100%;height:5px;background:#0d1528;border-radius:3px;margin-top:6px;overflow:hidden;">
                <div style="width:{pct}%;height:100%;background:{color};border-radius:3px;"></div>
            </div>
            <div style="font-size:10px;color:{color};margin-top:3px;">{pct}%</div>
            {blocked_badge}
        </div>
        """
    cards_html += '</div>'
    st.markdown(cards_html, unsafe_allow_html=True)


# ─── STORY POINTS TAB ────────────────────────────────────
def render_points(m):
    st.markdown('<div class="dash-card">', unsafe_allow_html=True)
    st.markdown("**💎 Story Points by Developer**")

    devs = [(n, d) for n, d in m["dev_map"].items() if d["sp"] > 0]
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
        color = DEV_COLORS.get(name, "#64748b")
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

    grouped = {}
    for t in tickets:
        s = t["status"]
        grouped.setdefault(s, []).append(t)

    for status in STATUS_ORDER:
        group = grouped.get(status, [])
        if not group:
            continue
        color = STATUS_COLORS.get(status, "#64748b")

        rows_html = ""
        for t in sorted(group, key=lambda x: x["key"]):
            sp_badge = f'<span style="font-size:9px;background:rgba(251,146,60,0.12);color:#fb923c;border-radius:3px;padding:1px 5px;margin-left:auto;">{t["sp"]} SP</span>' if t["sp"] else ""
            dev_color = DEV_COLORS.get(t["assignee"], "#64748b")
            assignee_badge = f'<span style="font-size:9px;color:{dev_color};margin-left:6px;">{t["assignee"].split()[0]}</span>'

            carried_badge = ""
            if t.get("carried_over"):
                prev_sprints = t.get("sprints", [])
                src = prev_sprints[0] if prev_sprints else "prev sprint"
                all_sprints = " - ".join(prev_sprints) if prev_sprints else ""
                carried_badge = f'<span style="font-size:9px;background:rgba(251,191,36,0.12);border:1px solid rgba(251,191,36,0.35);color:#fbbf24;border-radius:4px;padding:1px 6px;margin-right:4px;white-space:nowrap;" title="Sprint history: {all_sprints}">&#8617; {src}</span>'

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

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Overview", "🔥 Burndown", "⚡ Velocity", "💎 Story Points", "🎫 All Tickets"
    ])
    with tab1: render_overview(m, filtered_tickets)
    with tab2: render_burndown(m, sprint_days)
    with tab3: render_velocity(m)
    with tab4: render_points(m)
    with tab5: render_tickets(m, filtered_tickets)

    # Footer
    st.markdown(f"""
    <div style="text-align:center;font-size:9px;color:#1e2d47;border-top:1px solid #0d1528;padding-top:12px;margin-top:20px;">
        Jules Product · MineHub · {sprint_name} · {m['total']} tickets · {m['total_sp']} SP · {fetched_at}
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
