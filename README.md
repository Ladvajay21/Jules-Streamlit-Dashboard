# Jules Sprint Dashboard — Streamlit

Live Jira sprint dashboard for MineHub Jules team. Free hosting on Streamlit Community Cloud.

## Features
- Live Jira data (5 min cache, zero AI cost)
- Animated loading screen with pulsing dots
- 5 tabs: Overview, Burndown, Velocity, Story Points, All Tickets
- True Velocity (resolution-date based — counts only tickets completed during current sprint)
- Carried-over ticket detection with sprint history badges
- Fix Version filter dropdown
- Clickable ticket links → open directly in Jira
- Post blocked tickets to Slack (button or auto)
- PIN protection
- Dark theme with DM Sans font
- Developer workload cards with progress bars

## Setup

### 1. Get Jira API Token
1. Go to https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token" → name it "Jules Dashboard"
3. Copy the token

### 2. Local Setup
```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
streamlit run app.py
```

### 3. Deploy to Streamlit Community Cloud (FREE)
1. Push this folder to a GitHub repo
2. Go to https://share.streamlit.io
3. Click "New app" → connect your GitHub repo
4. Set the main file as `app.py`
5. Go to "Advanced settings" → "Secrets" and add:

```toml
JIRA_EMAIL = "jay.ladva@julesai.com"
JIRA_API_TOKEN = "your_token_here"
JIRA_BASE_URL = "https://minehub.atlassian.net"
SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
DASHBOARD_PIN = "1234"
```

6. Choose a custom URL like `julesdashboard.streamlit.app`
7. Click Deploy!

### 4. Get Slack Webhook URL (optional)
1. Go to https://api.slack.com/apps
2. Create new app → "Incoming Webhooks"
3. Add webhook to your #jules-dev channel
4. Copy the webhook URL

## Cost
- Streamlit hosting: FREE
- Jira API calls: FREE
- Slack webhooks: FREE
- Total: $0/month
