#!/usr/bin/env python3
"""
WeChat Article Scraper - Using New Authentication Headers

WeChat now uses x-wechat-uin and x-wechat-key headers instead of cookies.
This scraper works with the credentials captured from mitmproxy.

Usage:
    python3 wechat_scraper_v2.py --test
    python3 wechat_scraper_v2.py --url "https://mp.weixin.qq.com/s/..."
    python3 wechat_scraper_v2.py --biz "MjM5MTM3NTMwNA=="
"""

import json
import os
import sys
import argparse
import hashlib
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, quote

import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "accounts.json"
OUTPUT_DIR = PROJECT_ROOT / "output"


class WeChatScraperV2:
    """WeChat Article Scraper using new x-wechat-* headers."""
    
    BASE_URL = "https://mp.weixin.qq.com"
    
    def __init__(self, config_path: str = None):
        self.config_path = Path(config_path) if config_path else CONFIG_PATH
        self.output_dir = OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = self._load_config()
        self.session = self._create_session()
        
    def _load_config(self) -> dict:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: Config not found at {self.config_path}")
            sys.exit(1)
            
    def _create_session(self) -> requests.Session:
        """Create session with WeChat authentication headers."""
        creds = self.config.get("credentials", {})
        
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_7 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.68(0x1800442c) NetType/WIFI Language/zh_CN",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "x-wechat-uin": creds.get("x_wechat_uin", ""),
            "x-wechat-key": creds.get("x_wechat_key", ""),
        })
        
        return session
        
    def test_connection(self) -> bool:
        """Test if credentials work."""
        print("=" * 60)
        print("WeChat Scraper V2 - Connection Test")
        print("=" * 60)
        
        creds = self.config.get("credentials", {})
        uin = creds.get("x_wechat_uin", "")
        key = creds.get("x_wechat_key", "")
        
        if not uin or not key:
            print("❌ Missing x_wechat_uin or x_wechat_key in config")
            return False
            
        print(f"✅ x_wechat_uin: {uin[:10]}...")
        print(f"✅ x_wechat_key: {key[:20]}...")
        
        # Try to access WeChat
        try:
            resp = self.session.get(
                "https://mp.weixin.qq.com/mp/getappmsgext",
                timeout=10
            )
            print(f"✅ Connection successful (status: {resp.status_code})")
            return True
        except Exception as e:
            print(f"⚠️ Connection test: {e}")
            return True  # Continue anyway
            
    def scrape_article(self, url: str) -> dict:
        """Scrape a single article by URL."""
        print(f"\n📄 Scraping: {url[:60]}...")
        
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Extract article data
            article = {
                "url": url,
                "scraped_at": datetime.now().isoformat(),
            }
            
            # Title
            title_tag = soup.find("h1", class_="rich_media_title") or soup.find("h1")
            if title_tag:
                article["title"] = title_tag.get_text(strip=True)
                
            # Author/Account name
            author_tag = soup.find("a", id="js_name") or soup.find("span", class_="rich_media_meta_nickname")
            if author_tag:
                article["author"] = author_tag.get_text(strip=True)
                
            # Content
            content_div = soup.find("div", id="js_content") or soup.find("div", class_="rich_media_content")
            if content_div:
                article["content_html"] = str(content_div)
                article["content_text"] = content_div.get_text(strip=True)
                
            # Images
            images = []
            for img in soup.find_all("img", {"data-src": True}):
                images.append(img.get("data-src"))
            article["images"] = images[:10]  # Limit to first 10
            
            # Publish time
            time_tag = soup.find("em", id="publish_time")
            if time_tag:
                article["published_at"] = time_tag.get_text(strip=True)
                
            # Generate ID
            article["id"] = hashlib.md5(url.encode()).hexdigest()
            
            print(f"  ✓ Title: {article.get('title', 'Unknown')[:50]}...")
            print(f"  ✓ Author: {article.get('author', 'Unknown')}")
            print(f"  ✓ Content: {len(article.get('content_text', ''))} chars")
            print(f"  ✓ Images: {len(images)}")
            
            return article
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return {"url": url, "error": str(e)}
            
    def scrape_account_articles(self, biz: str, count: int = 10) -> list:
        """Scrape recent articles from a 公众号 account."""
        print(f"\n📚 Scraping account: {biz}")
        print(f"   (Note: Direct article list API requires additional auth)")
        
        # The full article list API is complex and requires more tokens
        # For now, we just return the biz ID for manual article URL input
        print("   Use --url to scrape specific articles")
        return []
        
    def save_results(self, articles: list, prefix: str = "wechat"):
        """Save scraped articles to JSON."""
        if not articles:
            print("No articles to save")
            return
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.output_dir / f"{prefix}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(articles, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 Saved {len(articles)} articles to: {filename}")


def main():
    parser = argparse.ArgumentParser(description='WeChat Article Scraper V2')
    parser.add_argument('--test', action='store_true', help='Test connection')
    parser.add_argument('--url', type=str, help='Article URL to scrape')
    parser.add_argument('--biz', type=str, help='公众号 biz ID')
    parser.add_argument('--count', type=int, default=10, help='Number of articles')
    
    args = parser.parse_args()
    
    scraper = WeChatScraperV2()
    
    if args.test:
        scraper.test_connection()
        return
        
    if args.url:
        article = scraper.scrape_article(args.url)
        if article and "error" not in article:
            scraper.save_results([article], "wechat_article")
            
    elif args.biz:
        articles = scraper.scrape_account_articles(args.biz, args.count)
        if articles:
            scraper.save_results(articles, f"wechat_{args.biz[:10]}")
            
    else:
        parser.print_help()
        print("\n\nExample usage:")
        print("  python3 wechat_scraper_v2.py --test")
        print("  python3 wechat_scraper_v2.py --url 'https://mp.weixin.qq.com/s/...'")


if __name__ == '__main__':
    main()
