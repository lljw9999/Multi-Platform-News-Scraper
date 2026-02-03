# Multi-Platform News Scraper

Complete solution for scraping AI/tech news from **HackerNews**, **X/Twitter**, and **WeChat**.

## Quick Start

| Platform | Folder | Auth | Status |
|----------|--------|------|--------|
| **HackerNews** | `hackernews_scraping/` | ❌ None | ✅ Ready |
| **X/Twitter** | `x_scraping/` | ✅ Cookies | ✅ Ready |
| **WeChat** | `wechat_scraping/` | ✅ mitmproxy | ⚠️ Setup needed |

---

## 🚀 Production Commands (Copy-Paste Ready)

### HackerNews - Full Newsletter Pipeline

```bash
cd hackernews_scraping

# Step 1: Scrape all HN sections (Top, Best, New, Ask, Show, Jobs)
python3 hn_scraper.py --newsletter

# Step 2: Curate & filter for AI/tech relevance
python3 curator.py --input output/newsletter_enhanced_*.json --preview

# OR one-step (scrape + curate combined):
python3 curator.py --scrape-and-curate --preview
```

**Output:** Curated JSON with 8-25 AI-relevant stories, classified by theme.

---

### X/Twitter - Scrape AI Accounts

```bash
cd x_scraping

# Scrape from specific users
python3 x_scraper_twikit.py --user AnthropicAI --limit 20 --save
python3 x_scraper_twikit.py --user OpenAI --limit 20 --save
python3 x_scraper_twikit.py --user _akhaliq --limit 20 --save

# Search for topics
python3 x_scraper_twikit.py --search "AI news" --limit 20 --save

# Test connection
python3 x_scraper_twikit.py --test
```

**Output:** JSON files saved to `x_scraping/output/`

---

### Recommended AI News Accounts for X

| Handle | Description |
|--------|-------------|
| `@AnthropicAI` | Official Anthropic (Claude) |
| `@OpenAI` | Official OpenAI |
| `@GoogleDeepMind` | DeepMind research |
| `@_akhaliq` | Papers/research curator |
| `@karpathy` | Andrej Karpathy |
| `@huggingface` | Open-source ML |
| `@DrJimFan` | Jim Fan (NVIDIA) |
| `@ylecun` | Yann LeCun (Meta AI) |

---

## Output Files

| Source | Location | Format |
|--------|----------|--------|
| HN Raw | `hackernews_scraping/output/newsletter_enhanced_*.json` | Full scrape |
| HN Curated | `hackernews_scraping/output/newsletter_curated_*.json` | Filtered & classified |
| X/Twitter | `x_scraping/output/user_*.json` | Per-account tweets |

---

## Setup (One-Time)

### HackerNews
```bash
cd hackernews_scraping
pip install -r requirements.txt
# No auth needed - uses free official API
```

### X/Twitter
```bash
cd x_scraping
pip install -r requirements.txt
```

Cookies already configured in `config/browser_cookies.json`. If expired:
1. Login to X in Chrome
2. Use Cookie-Editor extension to export cookies as JSON
3. Save to `x_scraping/config/browser_cookies.json`

### WeChat
See `wechat_scraping/README.md` for mitmproxy setup.

---

## Project Structure

```
├── hackernews_scraping/
│   ├── hn_scraper.py      # Scraper
│   ├── curator.py         # AI/tech filter & classifier
│   └── output/            # JSON outputs
│
├── x_scraping/
│   ├── x_scraper_twikit.py
│   ├── config/browser_cookies.json
│   └── output/
│
├── wechat_scraping/
│   └── ...
│
└── README.md
```

---

## Legal Disclaimer

For personal use and educational purposes only. Respect each platform's Terms of Service and rate limits.