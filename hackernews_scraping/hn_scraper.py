#!/usr/bin/env python3
"""
HackerNews Scraper - Enhanced for Newsletter Pipeline

Scrapes HN with full data matching the newsletter pipeline schema:
- Full article content
- All engagement metrics
- Classification-ready structure
- Deduplication support

Usage:
    python3 hn_scraper.py --test
    python3 hn_scraper.py --newsletter    # Full newsletter scrape
    python3 hn_scraper.py --top 20
"""

import json
import sys
import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output"


@dataclass
class RawItem:
    """
    Matches the colleague's raw_items table schema.
    """
    # Core identifiers
    id: str  # UUID generated from source + source_id
    source: str  # "hackernews"
    source_id: str  # HN item ID
    
    # Content
    title: Optional[str]
    content: str  # Full article content or HN text
    url: Optional[str]
    
    # Author info
    author_username: str
    author_category: str = "unknown"  # Will be classified later
    
    # Media (images, videos from article)
    media: List[Dict[str, str]] = field(default_factory=list)
    
    # Engagement metrics
    impressions_views: Optional[int] = None
    impressions_likes: int = 0  # HN score
    impressions_reposts: int = 0
    impressions_replies: int = 0  # HN comments
    impressions_bookmarks: Optional[int] = None
    impressions_clicks: Optional[int] = None
    impressions_quotes: Optional[int] = None
    impressions_updated_at: Optional[str] = None
    
    # Timestamps
    published_at: str = ""
    scraped_at: str = ""
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # For deduplication
    content_hash: str = ""
    
    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()
        if not self.content_hash and self.content:
            self.content_hash = hashlib.md5(self.content.encode()).hexdigest()


class HackerNewsScraper:
    """Enhanced HN scraper matching newsletter pipeline schema."""
    
    FIREBASE_URL = "https://hacker-news.firebaseio.com/v0"
    ALGOLIA_URL = "https://hn.algolia.com/api/v1"
    
    def __init__(self, fetch_content: bool = True):
        self.fetch_content = fetch_content
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        })
    
    def _generate_uuid(self, source: str, source_id: str) -> str:
        """Generate deterministic UUID from source and ID."""
        combined = f"{source}:{source_id}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _get_story_ids(self, endpoint: str, limit: int = 30) -> List[int]:
        """Get story IDs from Firebase API."""
        url = f"{self.FIREBASE_URL}/{endpoint}.json"
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        return response.json()[:limit]
    
    def _get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get a single item by ID."""
        url = f"{self.FIREBASE_URL}/item/{item_id}.json"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception:
            return None
    
    def _fetch_article_content(self, url: str) -> Dict[str, Any]:
        """Fetch full article content from URL."""
        if not url or not url.startswith('http'):
            return {"content": "", "media": []}
        
        try:
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script, style, nav elements
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()
            
            # Try to find main content
            article = soup.find('article') or soup.find('main') or soup.find('body')
            
            # Extract text
            content = ""
            if article:
                paragraphs = article.find_all(['p', 'h1', 'h2', 'h3', 'li'])
                content = "\n\n".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
            
            # Extract images
            media = []
            for img in soup.find_all('img', src=True)[:5]:
                src = img.get('src', '')
                if src.startswith('http') and not any(x in src.lower() for x in ['logo', 'icon', 'avatar', 'ad']):
                    media.append({
                        "type": "image",
                        "url": src,
                        "alt": img.get('alt', '')
                    })
            
            return {"content": content[:10000], "media": media}  # Cap content at 10k chars
            
        except Exception as e:
            return {"content": "", "media": [], "error": str(e)}
    
    def _item_to_raw_item(self, item: Dict[str, Any], fetch_content: bool = None) -> RawItem:
        """Convert HN item to RawItem matching pipeline schema."""
        if fetch_content is None:
            fetch_content = self.fetch_content
            
        source_id = str(item.get("id", ""))
        url = item.get("url")
        hn_text = item.get("text", "")
        
        # Fetch article content if URL exists and flag is set
        article_data = {"content": "", "media": []}
        if fetch_content and url:
            article_data = self._fetch_article_content(url)
        
        # Content is either fetched article or HN text (for Ask HN, etc.)
        content = article_data.get("content") or hn_text or item.get("title", "")
        
        # Determine item type for metadata
        item_type = "story"
        title = item.get("title", "")
        if title.startswith("Ask HN:"):
            item_type = "ask_hn"
        elif title.startswith("Show HN:"):
            item_type = "show_hn"
        elif item.get("type") == "job":
            item_type = "job"
        
        return RawItem(
            id=self._generate_uuid("hackernews", source_id),
            source="hackernews",
            source_id=source_id,
            title=title,
            content=content,
            url=url,
            author_username=item.get("by", ""),
            author_category="unknown",
            media=article_data.get("media", []),
            impressions_likes=item.get("score", 0),
            impressions_replies=item.get("descendants", 0),
            impressions_updated_at=datetime.now().isoformat(),
            published_at=datetime.fromtimestamp(item.get("time", 0)).isoformat(),
            scraped_at=datetime.now().isoformat(),
            metadata={
                "item_type": item_type,
                "hn_url": f"https://news.ycombinator.com/item?id={source_id}",
                "kids_count": len(item.get("kids", [])),
            }
        )
    
    def _fetch_items_parallel(self, story_ids: List[int], fetch_content: bool = None) -> List[RawItem]:
        """Fetch multiple items in parallel."""
        items = []
        
        # First, fetch all HN items
        with ThreadPoolExecutor(max_workers=10) as executor:
            hn_items = list(executor.map(self._get_item, story_ids))
        
        # Then convert to RawItems (with optional content fetching)
        for item in hn_items:
            if item and item.get("type") in ("story", "job"):
                try:
                    raw_item = self._item_to_raw_item(item, fetch_content)
                    items.append(raw_item)
                    if fetch_content and raw_item.url:
                        print(f"  ✓ Fetched: {raw_item.title[:50]}...")
                except Exception as e:
                    print(f"  ✗ Error: {e}")
        
        return items
    
    def get_top_stories(self, limit: int = 30, fetch_content: bool = None) -> List[RawItem]:
        """Get top stories with full data."""
        story_ids = self._get_story_ids("topstories", limit)
        return self._fetch_items_parallel(story_ids, fetch_content)
    
    def get_new_stories(self, limit: int = 30, fetch_content: bool = None) -> List[RawItem]:
        """Get newest stories."""
        story_ids = self._get_story_ids("newstories", limit)
        return self._fetch_items_parallel(story_ids, fetch_content)
    
    def get_best_stories(self, limit: int = 30, fetch_content: bool = None) -> List[RawItem]:
        """Get best stories."""
        story_ids = self._get_story_ids("beststories", limit)
        return self._fetch_items_parallel(story_ids, fetch_content)
    
    def get_ask_hn(self, limit: int = 30) -> List[RawItem]:
        """Get Ask HN (no external content to fetch)."""
        story_ids = self._get_story_ids("askstories", limit)
        return self._fetch_items_parallel(story_ids, fetch_content=False)
    
    def get_show_hn(self, limit: int = 30, fetch_content: bool = None) -> List[RawItem]:
        """Get Show HN."""
        story_ids = self._get_story_ids("showstories", limit)
        return self._fetch_items_parallel(story_ids, fetch_content)
    
    def get_jobs(self, limit: int = 30) -> List[RawItem]:
        """Get job postings."""
        story_ids = self._get_story_ids("jobstories", limit)
        return self._fetch_items_parallel(story_ids, fetch_content=False)
    
    def search(self, query: str, limit: int = 50) -> List[RawItem]:
        """Full-text search via Algolia."""
        params = {"query": query, "tags": "story", "hitsPerPage": min(limit, 100)}
        response = self.session.get(f"{self.ALGOLIA_URL}/search", params=params, timeout=10)
        response.raise_for_status()
        
        items = []
        for hit in response.json().get("hits", []):
            items.append(RawItem(
                id=self._generate_uuid("hackernews", hit.get("objectID", "")),
                source="hackernews",
                source_id=hit.get("objectID", ""),
                title=hit.get("title", ""),
                content=hit.get("story_text", "") or hit.get("title", ""),
                url=hit.get("url"),
                author_username=hit.get("author", ""),
                impressions_likes=hit.get("points", 0) or 0,
                impressions_replies=hit.get("num_comments", 0) or 0,
                published_at=hit.get("created_at", ""),
                metadata={"item_type": "story", "search_query": query}
            ))
        
        return items
    
    def scrape_for_newsletter(self, fetch_content: bool = True) -> Dict[str, Any]:
        """
        Full newsletter scrape with all sections and deduplication.
        """
        print("=" * 60)
        print("HackerNews Newsletter Scrape (Enhanced Schema)")
        print("=" * 60)
        print()
        
        all_items: Dict[str, RawItem] = {}  # Deduplicate by source_id
        
        sections = {
            "top_stories": ("📰 Top Stories", lambda: self.get_top_stories(50, fetch_content)),
            "best_stories": ("🏆 Best Stories", lambda: self.get_best_stories(30, fetch_content)),
            "new_stories": ("🆕 New Stories", lambda: self.get_new_stories(30, fetch_content)),
            "ask_hn": ("❓ Ask HN", lambda: self.get_ask_hn(20)),
            "show_hn": ("🚀 Show HN", lambda: self.get_show_hn(20, fetch_content)),
            "jobs": ("💼 Jobs", lambda: self.get_jobs(15)),
        }
        
        section_counts = {}
        
        for section_key, (section_name, fetch_func) in sections.items():
            print(f"{section_name}...")
            items = fetch_func()
            section_counts[section_key] = len(items)
            
            for item in items:
                if item.source_id not in all_items:
                    item.metadata["sections"] = [section_key]
                    all_items[item.source_id] = item
                else:
                    # Item exists, add section
                    existing_sections = all_items[item.source_id].metadata.get("sections", [])
                    if section_key not in existing_sections:
                        existing_sections.append(section_key)
                        all_items[item.source_id].metadata["sections"] = existing_sections
            
            print(f"   Got {len(items)} items")
        
        # Build output
        unique_items = list(all_items.values())
        
        output = {
            "schema_version": "2.0",
            "scraped_at": datetime.now().isoformat(),
            "source": "hackernews",
            "scrape_config": {
                "fetch_content": fetch_content,
                "sections_scraped": list(sections.keys()),
            },
            "stats": {
                "total_items": len(unique_items),
                "items_by_section": section_counts,
                "items_with_content": sum(1 for i in unique_items if len(i.content) > 100),
                "items_with_media": sum(1 for i in unique_items if i.media),
            },
            "items": [asdict(item) for item in unique_items]
        }
        
        # Save
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = OUTPUT_DIR / f"newsletter_enhanced_{timestamp}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print()
        print("=" * 60)
        print(f"✅ Saved {len(unique_items)} unique items to {output_file}")
        print(f"   Items with content: {output['stats']['items_with_content']}")
        print(f"   Items with media: {output['stats']['items_with_media']}")
        print("=" * 60)
        
        return output


def test_connection():
    """Test with enhanced schema."""
    print("=" * 60)
    print("HackerNews Scraper - Enhanced Schema Test")
    print("=" * 60)
    
    scraper = HackerNewsScraper(fetch_content=True)
    
    print("\nFetching 3 top stories with full content...\n")
    
    items = scraper.get_top_stories(3, fetch_content=True)
    
    for item in items:
        print(f"📰 {item.title}")
        print(f"   URL: {item.url}")
        print(f"   Author: {item.author_username}")
        print(f"   Score: {item.impressions_likes} | Comments: {item.impressions_replies}")
        print(f"   Content length: {len(item.content)} chars")
        print(f"   Media: {len(item.media)} items")
        print(f"   Content preview: {item.content[:200]}..." if item.content else "   (no content)")
        print()
    
    print("✅ Test successful!")
    return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="HackerNews Enhanced Scraper")
    parser.add_argument("--test", action="store_true", help="Test with content fetching")
    parser.add_argument("--newsletter", action="store_true", help="Full newsletter scrape")
    parser.add_argument("--no-content", action="store_true", help="Skip article content fetching")
    parser.add_argument("--top", type=int, metavar="N", help="Get top N stories")
    parser.add_argument("--search", help="Search query")
    
    args = parser.parse_args()
    fetch_content = not args.no_content
    
    if args.test:
        test_connection()
    elif args.newsletter:
        scraper = HackerNewsScraper(fetch_content=fetch_content)
        scraper.scrape_for_newsletter(fetch_content=fetch_content)
    elif args.top:
        scraper = HackerNewsScraper(fetch_content=fetch_content)
        items = scraper.get_top_stories(args.top, fetch_content=fetch_content)
        for item in items:
            print(f"[{item.impressions_likes}] {item.title}")
    elif args.search:
        scraper = HackerNewsScraper()
        items = scraper.search(args.search)
        for item in items:
            print(f"[{item.impressions_likes}] {item.title}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
