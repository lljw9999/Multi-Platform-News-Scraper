#!/usr/bin/env python3
"""
WeChat 公众号 Article Scraper - Enhanced for Newsletter Pipeline

Scrapes WeChat articles with full data matching the newsletter pipeline schema:
- Full article content (HTML and text)
- Engagement metrics (reads, likes, comments)
- Media extraction
- Author info

Usage:
    python3 scrapers/article_scraper.py -i
    python3 scrapers/article_scraper.py --url "https://mp.weixin.qq.com/s/..."
"""

import json
import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from wechatarticles import ArticlesAPI, ArticlesInfo
except ImportError:
    print("Warning: wechatarticles not installed")
    print("Run: pip install wechatarticles")


@dataclass
class RawItem:
    """
    Matches the colleague's raw_items table schema.
    """
    # Core identifiers
    id: str
    source: str  # "wechat"
    source_id: str
    
    # Content
    title: Optional[str]
    content: str  # Full article text
    url: Optional[str]
    
    # Author info
    author_username: str  # 公众号 name
    author_category: str = "unknown"
    
    # Media
    media: List[Dict[str, str]] = field(default_factory=list)
    
    # Engagement metrics
    impressions_views: Optional[int] = None  # read_count
    impressions_likes: int = 0  # like_count (new likes)
    impressions_reposts: int = 0
    impressions_replies: int = 0  # comment_count
    impressions_bookmarks: Optional[int] = None
    impressions_clicks: Optional[int] = None
    impressions_quotes: Optional[int] = None
    impressions_updated_at: Optional[str] = None
    
    # Timestamps
    published_at: str = ""
    scraped_at: str = ""
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    content_html: str = ""  # Keep HTML for rich formatting
    
    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()
        if not self.content_hash and self.content:
            self.content_hash = hashlib.md5(self.content.encode()).hexdigest()


class WeChatArticleScraper:
    """Enhanced scraper for WeChat Official Account articles."""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or str(PROJECT_ROOT / "config" / "accounts.json")
        self.output_dir = PROJECT_ROOT / "output"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.config = self._load_config()
        self.api = None
        self.info_api = None
        
    def _load_config(self) -> dict:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Config not found: {self.config_path}")
            self._create_template_config()
            return {}
            
    def _create_template_config(self):
        template = {
            "accounts": [
                {
                    "name": "Example Account",
                    "biz": "MzI3MDA5NzxxxAA==",
                    "description": "Replace with actual 公众号 biz ID"
                }
            ],
            "settings": {
                "delay_between_articles": 8,
                "delay_between_accounts": 60,
                "max_articles_per_account": 100,
                "output_format": "json"
            },
            "credentials": {
                "cookie": "",
                "appmsg_token": "",
                "note": "Fill these from mitmproxy capture"
            }
        }
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=4, ensure_ascii=False)
            
    def _generate_uuid(self, url: str) -> str:
        return hashlib.md5(url.encode()).hexdigest()
            
    def _validate_credentials(self) -> bool:
        creds = self.config.get("credentials", {})
        if not creds.get("cookie") or not creds.get("appmsg_token"):
            print("=" * 60)
            print("ERROR: Credentials not configured!")
            print("=" * 60)
            print("\nTo capture credentials:")
            print("1. Run: bash scripts/setup_mitmproxy.sh")
            print("2. Start mitmproxy: mitmweb --listen-port 8080")
            print("3. Configure iPhone proxy to your Mac's IP:8080")
            print("4. Install mitmproxy CA cert (visit http://mitm.it)")
            print("5. Open any 公众号 article in WeChat")
            print("6. In mitmproxy, find request to mp.weixin.qq.com")
            print("7. Copy 'cookie' header and 'appmsg_token' parameter")
            print("8. Update config/accounts.json with these values")
            return False
        return True
    
    def initialize_apis(self):
        creds = self.config["credentials"]
        self.info_api = ArticlesInfo(
            appmsg_token=creds["appmsg_token"],
            cookie=creds["cookie"]
        )
        print("APIs initialized successfully!")
        
    def get_article_info(self, article_url: str) -> dict:
        """Get article metrics."""
        try:
            info = self.info_api.get_read_like_comment(article_url)
            return {
                "read_count": info.get("read_num", 0),
                "like_count": info.get("like_num", 0),
                "old_like_count": info.get("old_like_num", 0),
                "comment_count": info.get("comment_count", 0),
            }
        except Exception as e:
            print(f"  Warning: Could not get article info: {e}")
            return {}
            
    def scrape_article_content(self, url: str) -> Dict[str, Any]:
        """Scrape full article content from URL."""
        import requests
        from bs4 import BeautifulSoup
        
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15"
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Extract article content
            title_elem = soup.find('h1', class_='rich_media_title')
            content_elem = soup.find('div', class_='rich_media_content')
            author_elem = soup.find('span', class_='rich_media_meta_nickname')
            date_elem = soup.find('em', id='publish_time')
            
            # Extract images
            media = []
            if content_elem:
                for img in content_elem.find_all('img', {'data-src': True})[:10]:
                    media.append({
                        "type": "image",
                        "url": img.get('data-src', ''),
                    })
            
            return {
                "title": title_elem.get_text(strip=True) if title_elem else "",
                "content": content_elem.get_text(strip=True) if content_elem else "",
                "content_html": str(content_elem) if content_elem else "",
                "author": author_elem.get_text(strip=True) if author_elem else "",
                "publish_time": date_elem.get_text(strip=True) if date_elem else "",
                "media": media,
            }
        except Exception as e:
            print(f"  Warning: Could not scrape content: {e}")
            return {}
    
    def scrape_single_url(self, url: str) -> RawItem:
        """Scrape a single article and return as RawItem."""
        print(f"\nScraping: {url[:60]}...")
        
        # Get content
        article = self.scrape_article_content(url)
        
        # Get engagement metrics
        metrics = {}
        if self.info_api:
            metrics = self.get_article_info(url)
        
        return RawItem(
            id=self._generate_uuid(url),
            source="wechat",
            source_id=self._generate_uuid(url),
            title=article.get("title"),
            content=article.get("content", ""),
            content_html=article.get("content_html", ""),
            url=url,
            author_username=article.get("author", ""),
            author_category="official_account",
            media=article.get("media", []),
            impressions_views=metrics.get("read_count"),
            impressions_likes=metrics.get("like_count", 0) + metrics.get("old_like_count", 0),
            impressions_replies=metrics.get("comment_count", 0),
            impressions_updated_at=datetime.now().isoformat(),
            published_at=article.get("publish_time", ""),
            scraped_at=datetime.now().isoformat(),
            metadata={
                "platform": "wechat_gongzhonghao",
                "old_likes": metrics.get("old_like_count", 0),
                "new_likes": metrics.get("like_count", 0),
            }
        )
    
    def save_item(self, item: RawItem, filename: str = None) -> Path:
        """Save single item to JSON."""
        if not filename:
            filename = f"wechat_article_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        output = {
            "schema_version": "2.0",
            "scraped_at": datetime.now().isoformat(),
            "source": "wechat",
            "items": [asdict(item)]
        }
        
        output_file = self.output_dir / filename
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved to {output_file}")
        return output_file
    
    def run_interactive(self):
        """Run in interactive mode."""
        print("=" * 60)
        print("WeChat 公众号 Scraper (Enhanced Schema)")
        print("=" * 60)
        
        if not self._validate_credentials():
            return
            
        self.initialize_apis()
        
        print("\nOptions:")
        print("1. Scrape single article URL")
        print("2. Exit")
        
        while True:
            choice = input("\nEnter choice (1-2): ").strip()
            
            if choice == "1":
                url = input("Enter article URL: ").strip()
                if url:
                    item = self.scrape_single_url(url)
                    self.save_item(item)
                    
                    print(f"\n📰 Title: {item.title}")
                    print(f"   Author: {item.author_username}")
                    print(f"   👁 Reads: {item.impressions_views or 'N/A'}")
                    print(f"   ❤️ Likes: {item.impressions_likes}")
                    print(f"   💬 Comments: {item.impressions_replies}")
                    print(f"   📷 Media: {len(item.media)} items")
                    print(f"   Content: {len(item.content)} chars")
                    
            elif choice == "2":
                print("Goodbye!")
                break


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="WeChat Enhanced Scraper")
    parser.add_argument("--url", help="Single article URL to scrape")
    parser.add_argument("--config", help="Path to config file")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    scraper = WeChatArticleScraper(config_path=args.config)
    
    if args.url:
        if not scraper._validate_credentials():
            return
        scraper.initialize_apis()
        item = scraper.scrape_single_url(args.url)
        scraper.save_item(item)
        print(json.dumps(asdict(item), indent=2, ensure_ascii=False))
    else:
        scraper.run_interactive()


if __name__ == "__main__":
    main()
