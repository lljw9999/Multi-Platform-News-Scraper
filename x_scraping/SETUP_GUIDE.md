# X/Twitter Scraper Setup Guide

## Current Status

X (Twitter) has very aggressive anti-bot protection that blocks most automated access. The recommended approach is to use browser cookies.

## Option 1: Export Browser Cookies (Recommended)

### Step 1: Install a Cookie Exporter Extension

For Chrome: Install [Cookie-Editor](https://chrome.google.com/webstore/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm)

### Step 2: Export Cookies

1. Login to [x.com](https://x.com) in Chrome
2. Click the Cookie-Editor extension icon
3. Click **Export** → **Export as JSON**
4. Save the file as `x_scraping/cookies.json`

### Step 3: Test

```bash
python3 x_scraping/x_scraper_twikit.py --test
```

---

## Option 2: Use X's Official API (Paid)

X's official API costs $100+/month for basic access but is the most reliable.

1. Apply at [developer.twitter.com](https://developer.twitter.com)
2. Get API keys
3. Use `tweepy` library

---

## Option 3: Focus on HackerNews

The HackerNews scraper works without any authentication:

```bash
# Already working!
python3 hackernews_scraping/hn_scraper.py --top 30
python3 hackernews_scraping/hn_scraper.py --search "AI startups" --limit 50
```

---

## Troubleshooting

If you're getting Cloudflare errors:
1. X is blocking your IP - try again later or use a VPN
2. Your cookies are expired - re-export them
3. X has updated their anti-bot measures - wait for library updates
