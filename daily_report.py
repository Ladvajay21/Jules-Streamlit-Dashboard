"""
Jules Daily Standup Report — Standalone Slack Poster
Runs via GitHub Actions cron at 9:00 AM IST (3:30 AM UTC) every weekday.
Posts a rich daily standup report matching the Jules Bot format.
"""
import requests
import re
import os
import random
from datetime import datetime, date, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

JIRA_EMAIL    = os.environ.get("JIRA_EMAIL", "")
JIRA_TOKEN    = os.environ.get("JIRA_API_TOKEN", "").strip()
JIRA_BASE     = os.environ.get("JIRA_BASE_URL", "https://minehub.atlassian.net")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "https://julesdashboard.streamlit.app")
PROJECT       = "JENG"

DONE_STATUSES    = {"Done", "PO/QA VALID", "Demo", "In Production", "CS Reviewed"}
BLOCKED_STATUSES = {"Blocked"}
ACTIVE_STATUSES  = {"In Progress", "AIM OF THE DAY", "Tech review", "PO review",
                     "PO/QA Test run", "Aim Of The week", "PO not valid", "TECH GROOMED"}
EXCLUDE_FROM_CARDS = {"Unassigned", "Jay Ladva"}
DEV_BLOCK_COLORS = {"Nikita Vaidya": "\U0001f7ea", "Satadru Roy": "\U0001f7e5",
                     "Rizky Ario": "\U0001f7e7", "Jay Pitroda": "\U0001f7e6"}
GREETINGS = ["Let's make today count! \U0001f4aa", "Another day, another ticket shipped! \U0001f680",
             "Stay focused, stay unblocked! \U0001f3af", "Great work so far \u2014 keep the momentum! \u26a1",
             "Sprint strong, team Jules! \U0001f3c3"]
SPRINT_TIPS = ["A blocker today is a fire tomorrow. Escalate early! \U0001f525",
               "Small PRs get reviewed faster. Ship in slices. \u26a1",
               "Done = merged + deployed + verified. All three. \U0001f680",
               "Sprint health = team health. Look out for each other. \U0001f91d",
               "Write the test first, thank yourself later. \U0001f9ea",
               "If it's unclear, clarify it now \u2014 not on the last day. \U0001f4ac"]

def jira_auth(): return (JIRA_EMAIL, JIRA_TOKEN)
def jira_headers(): return {"Accept": "application/json", "Content-Type": "application/json"}
def clean_title(s):
    s = re.sub(r'^(AAWU,?\s*|AAD,?\s*)', '', s, flags=re.IGNORECASE)
    return s.lstrip(',').strip()
def make_bar(pct, filled="\U0001f7e9", empty="\u2b1c", w=20):
    f = round(pct / 100 * w)
    return filled * f + empty * (w - f)

def fetch_sprint_info():
    try:
        r = requests.get(f"{JIRA_BASE}/rest/agile/1.0/board", auth=jira_auth(), headers=jira_headers(),
                         params={"projectKeyOrId": PROJECT, "maxResults": 10}, timeout=15)
        r.raise_for_status()
        boards = r.json().get("values", [])
        if not boards: return date.today(), date.today() + timedelta(days=14), "Sprint"
        r2 = requests.get(f"{JIRA_BASE}/rest/agile/1.0/board/{boards[0]['id']}/sprint", auth=jira_auth(),
                          headers=jira_headers(), params={"state": "active", "maxResults": 5}, timeout=15)
        r2.raise_for_status()
        for s in r2.json().get("values", []):
            if s.get("state") == "active":
                return (datetime.fromisoformat(s["startDate"].replace("Z", "+00:00")).date(),
                        datetime.fromisoformat(s["endDate"].replace("Z", "+00:00")).date(), s.get("name", "Sprint"))
    except Exception as e: print(f"  Warn: {e}")
    return date.today(), date.today(), "Sprint"

def fetch_tickets():
    url = f"{JIRA_BASE}/rest/api/3/search/jql"
    all_t, start_at = [], 0
    while True:
        r = requests.get(url, headers=jira_headers(), auth=jira_auth(), timeout=30,
                         params={"jql": f"project = {PROJECT} AND sprint in openSprints()", "maxResults": 200,
                                 "startAt": start_at, "fields": "summary,status,assignee,customfield_10024"})
        r.raise_for_status()
        d = r.json()
        for i in d.get("issues", []):
            f = i.get("fields", {})
            all_t.append({"key": i["key"], "summary": clean_title(f.get("summary", "")),
                          "status": f.get("status", {}).get("name", "Unknown"),
                          "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
                          "sp": int(f["customfield_10024"]) if f.get("customfield_10024") else None})
        if start_at + len(d.get("issues", [])) >= d.get("total", 0): break
        start_at += len(d.get("issues", []))

    # Catch-all verification: re-fetch all sprint tickets to fix stale/missing data
    existing = {t["key"]: t for t in all_t}
    v_start = 0
    while True:
        try:
            vr = requests.get(url, headers=jira_headers(), auth=jira_auth(), timeout=30,
                              params={"jql": f"project = {PROJECT} AND sprint in openSprints() ORDER BY key ASC",
                                      "maxResults": 200, "startAt": v_start,
                                      "fields": "summary,status,assignee,customfield_10024"})
            vr.raise_for_status()
            vd = vr.json()
            for i in vd.get("issues", []):
                f = i.get("fields", {})
                key = i["key"]
                new_status = f.get("status", {}).get("name", "Unknown")
                if key in existing:
                    existing[key]["status"] = new_status
                else:
                    t = {"key": key, "summary": clean_title(f.get("summary", "")),
                         "status": new_status,
                         "assignee": (f.get("assignee") or {}).get("displayName", "Unassigned"),
                         "sp": int(f["customfield_10024"]) if f.get("customfield_10024") else None}
                    all_t.append(t)
                    existing[key] = t
            if v_start + len(vd.get("issues", [])) >= vd.get("total", 0): break
            v_start += len(vd.get("issues", []))
        except Exception:
            break
    return all_t

def build_metrics(tickets, sprint_start, sprint_days):
    today = datetime.now(IST).date()
    done_t = [t for t in tickets if t["status"] in DONE_STATUSES]
    blocked_t = [t for t in tickets if t["status"] in BLOCKED_STATUSES]
    dev_map = {}
    for t in tickets:
        n = t["assignee"]
        if n not in dev_map:
            dev_map[n] = {"total":0,"done":0,"active":0,"blocked":0,"todo":0,"sp":0,"done_sp":0,"active_sp":0,"blocked_sp":0,"todo_sp":0}
        dev_map[n]["total"] += 1; dev_map[n]["sp"] += t["sp"] or 0
        if t["status"] in DONE_STATUSES: dev_map[n]["done"] += 1; dev_map[n]["done_sp"] += t["sp"] or 0
        elif t["status"] in BLOCKED_STATUSES: dev_map[n]["blocked"] += 1; dev_map[n]["blocked_sp"] += t["sp"] or 0
        elif t["status"] in ACTIVE_STATUSES: dev_map[n]["active"] += 1; dev_map[n]["active_sp"] += t["sp"] or 0
        else: dev_map[n]["todo"] += 1; dev_map[n]["todo_sp"] += t["sp"] or 0
    return {"total": len(tickets), "done_tickets": done_t, "blocked_tickets": blocked_t,
            "total_sp": sum(t["sp"] or 0 for t in tickets), "done_sp": sum(t["sp"] or 0 for t in done_t),
            "current_day": max(1, min((today - sprint_start).days + 1, sprint_days)) if sprint_start else 1,
            "dev_map": dev_map}

def post_daily_slack(m, tickets, sprint_name, sprint_days):
    today_str = datetime.now(IST).strftime("%A, %d %b %Y")
    days_left = sprint_days - m["current_day"]
    total, done_ct, blocked_ct = m["total"], len(m["done_tickets"]), len(m["blocked_tickets"])
    pct = round(done_ct / total * 100) if total else 0
    time_pct = round(m["current_day"] / sprint_days * 100) if sprint_days else 0
    greeting, tip = random.choice(GREETINGS), random.choice(SPRINT_TIPS)
    if pct >= time_pct * 0.85: he, ht = "\U0001f7e2", "On Track \u2014 Sprint is progressing well"
    elif pct >= time_pct * 0.65: he, ht = "\U0001f7e1", "Slight Risk \u2014 Keep an eye on velocity"
    else: he, ht = "\U0001f534", "Behind Schedule \u2014 Needs attention"
    tpd = round((total - done_ct) / max(days_left, 1), 1) if days_left > 0 else 0

    blocks = [
        {"type":"header","text":{"type":"plain_text","text":f"\U0001f680 Jules Daily Standup \u2014 {today_str}"}},
        {"type":"context","elements":[{"type":"mrkdwn","text":f"{sprint_name}  \u00b7  Day {m['current_day']} of {sprint_days}  \u00b7  {greeting}"}]},
        {"type":"section","text":{"type":"mrkdwn","text":"*\U0001f4c9 Sprint Burndown*"}},
        {"type":"section","text":{"type":"mrkdwn","text":
            f"`Time elapsed` {make_bar(time_pct, '\U0001f7e5', '\u2b1c')}  *{time_pct}%*\n"
            f"`Work done   ` {make_bar(pct, '\U0001f7e9', '\u2b1c')}  *{pct}%*"}},
        {"type":"context","elements":[{"type":"mrkdwn","text":f"{he} *{ht}*\nNeed ~{tpd} tickets/day to finish  \u00b7  {days_left} days left"}]},
        {"type":"divider"},
        {"type":"section","text":{"type":"mrkdwn","text":"*\U0001f5c2\ufe0f Sprint Snapshot*"}},
        {"type":"section","fields":[
            {"type":"mrkdwn","text":f"\u2705 *Done*\n{done_ct} / {total} tickets"},
            {"type":"mrkdwn","text":f"\U0001f48e *Story Points*\n{m['done_sp']} / {m['total_sp']} SP"},
            {"type":"mrkdwn","text":f"\U0001f6ab *Blocked*\n{blocked_ct} tickets"},
            {"type":"mrkdwn","text":f"\U0001f5d3\ufe0f *Days Left*\n{days_left} of {sprint_days} days"}]},
        {"type":"divider"},
    ]
    devs = [(n, d) for n, d in m["dev_map"].items() if n not in EXCLUDE_FROM_CARDS]
    devs.sort(key=lambda x: x[1]["done"], reverse=True)
    vl = ["*\U0001f465 Team Velocity*\n"]
    for name, d in devs:
        tp = round((d["done"]/d["total"])*100) if d["total"] else 0
        b = make_bar(tp, DEV_BLOCK_COLORS.get(name, "\U0001f7e6"), "\u2b1c", 10)
        bf = f"\U0001f6ab {d['blocked']} Blocked" if d["blocked"] > 0 else "\u2705 Clear"
        vl.append(f"{name.split()[0]}  {b}  *{tp}%*  {d['done']}/{d['total']} tickets \u00b7 {d['done_sp']}/{d['sp']} SP  {bf}")
    blocks.append({"type":"section","text":{"type":"mrkdwn","text":"\n".join(vl)}})
    if m["blocked_tickets"]:
        blocks.append({"type":"divider"})
        bl = [f"*\U0001f6ab Active Blockers ({blocked_ct})*\n"]
        for t in m["blocked_tickets"][:8]:
            s = t["summary"][:60]+("..." if len(t["summary"])>60 else "")
            bl.append(f"`{t['key']}`  \u2192  {s}  \u2014  *{t['assignee'].split()[0]}*")
        blocks.append({"type":"section","text":{"type":"mrkdwn","text":"\n".join(bl)}})
    blocks.append({"type":"divider"})
    blocks.append({"type":"context","elements":[{"type":"mrkdwn","text":f"\U0001f4a1 *Tip of the Day*  \u2014  {tip}"}]})
    blocks.append({"type":"actions","elements":[
        {"type":"button","text":{"type":"plain_text","text":"\U0001f4ca Live Dashboard"},"url":DASHBOARD_URL,"style":"primary"},
        {"type":"button","text":{"type":"plain_text","text":"\U0001f4cb Jira Board"},
         "url":f"{JIRA_BASE}/jira/software/c/projects/{PROJECT}/boards"}]})
    resp = requests.post(SLACK_WEBHOOK, json={"blocks": blocks}, timeout=15)
    return resp.status_code == 200

def main():
    print("\U0001f680 Jules Daily Standup Report")
    print("\u2500" * 40)
    if not JIRA_EMAIL or not JIRA_TOKEN: print("\u274c Missing JIRA_EMAIL or JIRA_API_TOKEN"); return
    if not SLACK_WEBHOOK: print("\u274c Missing SLACK_WEBHOOK_URL"); return
    print("\U0001f4e1 Fetching sprint info...")
    ss, se, sn = fetch_sprint_info()
    sd = max((se - ss).days, 1)
    print("\U0001f3ab Fetching tickets...")
    tickets = fetch_tickets()
    print(f"   Found {len(tickets)} tickets")
    print("\U0001f4ca Building metrics...")
    m = build_metrics(tickets, ss, sd)
    print(f"   \u2705 {len(m['done_tickets'])}/{m['total']} done ({m['done_sp']}/{m['total_sp']} SP)")
    print(f"   \U0001f6ab {len(m['blocked_tickets'])} blocked")
    print("\U0001f4e3 Posting to Slack...")
    ok = post_daily_slack(m, tickets, sn, sd)
    print(f"   {'\u2705 Posted!' if ok else '\u274c Failed'}")

if __name__ == "__main__":
    main()
