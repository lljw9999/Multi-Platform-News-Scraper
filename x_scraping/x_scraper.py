#!/usr/bin/env python3
"""
X/Twitter Scraper - Enhanced for Newsletter Pipeline

Scrapes X with full data matching the newsletter pipeline schema:
- Full tweet content
- All engagement metrics (views, likes, reposts, replies, bookmarks, quotes)
- Media attachments
- Author categorization ready
- Deduplication support

Usage:
    python3 x_scraper.py --test
    python3 x_scraper.py --search "AI" --limit 50
    python3 x_scraper.py -i
"""

import asyncio
import json
import os
import sys
import hashlib
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output"
CONFIG_PATH = PROJECT_ROOT / "config" / "accounts.json"


@dataclass
class RawItem:
    """
    Matches the colleague's raw_items table schema.
    """
    # Core identifiers
    id: str
    source: str  # "twitter"
    source_id: str
    
    # Content
    title: Optional[str]  # First 200 chars of tweet
    content: str  # Full tweet text
    url: Optional[str]
    
    # Author info
    author_username: str
    author_category: str = "unknown"
    
    # Media
    media: List[Dict[str, str]] = field(default_factory=list)
    
    # Engagement metrics - X has all of these!
    impressions_views: Optional[int] = None
    impressions_likes: int = 0
    impressions_reposts: int = 0  # retweets
    impressions_replies: int = 0
    impressions_bookmarks: Optional[int] = None
    impressions_clicks: Optional[int] = None
    impressions_quotes: int = 0
    impressions_updated_at: Optional[str] = None
    
    # Timestamps
    published_at: str = ""
    scraped_at: str = ""
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""
    
    def __post_init__(self):
        if not self.scraped_at:
            self.scraped_at = datetime.now().isoformat()
        if not self.content_hash and self.content:
            self.content_hash = hashlib.md5(self.content.encode()).hexdigest()


class XScraper:
    """Enhanced X/Twitter scraper matching newsletter pipeline schema."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(PROJECT_ROOT / "accounts.db")
        self.api = None
        self.config = self._load_config()
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        
    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"accounts": [], "settings": {"delay_between_requests": 2}}
    
    def _generate_uuid(self, source: str, source_id: str) -> str:
        combined = f"{source}:{source_id}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    async def init(self):
        """Initialize the API."""
        try:
            from twscrape import API
        except ImportError:
            print("Error: twscrape not installed")
            print("Run: pip install twscrape")
            sys.exit(1)
            
        self.api = API(self.db_path)
        
        for account in self.config.get("accounts", []):
            if account.get("cookies"):
                await self.api.pool.add_account(
                    account.get("username", "user"),
                    account.get("password", "pass"),
                    account.get("email", "email@mail.com"),
                    account.get("email_password", "pass"),
                    cookies=account["cookies"]
                )
            elif account.get("username") and account.get("password"):
                await self.api.pool.add_account(
                    account["username"],
                    account["password"],
                    account.get("email", ""),
                    account.get("email_password", "")
                )
        
        try:
            await self.api.pool.login_all()
        except Exception as e:
            print(f"Warning: Login issue - {e}")
    
    def _tweet_to_raw_item(self, tweet) -> RawItem:
        """Convert twscrape tweet to RawItem."""
        source_id = str(tweet.id)
        content = tweet.rawContent or ""
        
        # Extract media
        media = []
        if hasattr(tweet, 'media') and tweet.media:
            for m in tweet.media:
                media.append({
                    "type": m.type if hasattr(m, 'type') else "unknown",
                    "url": m.url if hasattr(m, 'url') else "",
                })
        
        # Build metadata
        metadata = {
            "is_retweet": tweet.retweetedTweet is not None if hasattr(tweet, 'retweetedTweet') else False,
            "is_quote": tweet.quotedTweet is not None if hasattr(tweet, 'quotedTweet') else False,
            "is_reply": tweet.inReplyToTweetId is not None if hasattr(tweet, 'inReplyToTweetId') else False,
            "lang": tweet.lang if hasattr(tweet, 'lang') else None,
            "hashtags": [h.text for h in tweet.hashtags] if hasattr(tweet, 'hashtags') and tweet.hashtags else [],
            "mentions": [m.username for m in tweet.mentionedUsers] if hasattr(tweet, 'mentionedUsers') and tweet.mentionedUsers else [],
        }
        
        # Author info
        author_metadata = {}
        if hasattr(tweet, 'user') and tweet.user:
            author_metadata = {
                "author_display_name": tweet.user.displayname if hasattr(tweet.user, 'displayname') else None,
                "author_followers": tweet.user.followersCount if hasattr(tweet.user, 'followersCount') else None,
                "author_verified": tweet.user.verified if hasattr(tweet.user, 'verified') else False,
                "author_description": tweet.user.description if hasattr(tweet.user, 'description') else None,
            }
        metadata.update(author_metadata)
        
        return RawItem(
            id=self._generate_uuid("twitter", source_id),
            source="twitter",
            source_id=source_id,
            title=content[:200] if content else None,
            content=content,
            url=f"https://twitter.com/{tweet.user.username}/status/{tweet.id}" if hasattr(tweet, 'user') else None,
            author_username=f"@{tweet.user.username}" if hasattr(tweet, 'user') else "",
            author_category="unknown",
            media=media,
            impressions_views=tweet.viewCount if hasattr(tweet, 'viewCount') else None,
            impressions_likes=tweet.likeCount if hasattr(tweet, 'likeCount') else 0,
            impressions_reposts=tweet.retweetCount if hasattr(tweet, 'retweetCount') else 0,
            impressions_replies=tweet.replyCount if hasattr(tweet, 'replyCount') else 0,
            impressions_bookmarks=tweet.bookmarkCount if hasattr(tweet, 'bookmarkCount') else None,
            impressions_quotes=tweet.quoteCount if hasattr(tweet, 'quoteCount') else 0,
            impressions_updated_at=datetime.now().isoformat(),
            published_at=tweet.date.isoformat() if hasattr(tweet, 'date') and tweet.date else "",
            scraped_at=datetime.now().isoformat(),
            metadata=metadata
        )
    
    async def search(self, query: str, limit: int = 50) -> List[RawItem]:
        """Search tweets with full engagement data."""
        from twscrape import gather
        
        items = []
        try:
            tweets = await gather(self.api.search(query, limit=limit))
            for tweet in tweets:
                items.append(self._tweet_to_raw_item(tweet))
        except Exception as e:
            print(f"Search error: {e}")
        
        return items
    
    async def get_user_tweets(self, user_id: int, limit: int = 50) -> List[RawItem]:
        """Get tweets from specific user."""
        from twscrape import gather
        
        items = []
        try:
            tweets = await gather(self.api.user_tweets(user_id, limit=limit))
            for tweet in tweets:
                items.append(self._tweet_to_raw_item(tweet))
        except Exception as e:
            print(f"User tweets error: {e}")
        
        return items
    
    async def get_trending(self) -> List[Dict[str, Any]]:
        """Get trending topics."""
        try:
            trends = await self.api.trends("news")
            return [{"name": t.name, "tweet_count": t.tweetCount} for t in trends]
        except Exception as e:
            print(f"Trends error: {e}")
            return []
    
    def save_items(self, items: List[RawItem], filename: str = None) -> Path:
        """Save items to JSON."""
        if not filename:
            filename = f"x_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        output = {
            "schema_version": "2.0",
            "scraped_at": datetime.now().isoformat(),
            "source": "twitter",
            "stats": {
                "total_items": len(items),
                "items_with_media": sum(1 for i in items if i.media),
                "total_likes": sum(i.impressions_likes for i in items),
                "total_reposts": sum(i.impressions_reposts for i in items),
            },
            "items": [asdict(item) for item in items]
        }
        
        output_file = OUTPUT_DIR / filename
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Saved {len(items)} items to {output_file}")
        return output_file


async def test_connection():
    """Test the scraper."""
    print("=" * 60)
    print("X/Twitter Scraper - Enhanced Schema Test")
    print("=" * 60)
    
    scraper = XScraper()
    
    if not scraper.config.get("accounts"):
        print("\n⚠️  No accounts configured!")
        print("\nTo use this scraper, add credentials to:")
        print(f"  {CONFIG_PATH}")
        print("\nExample config:")
        print(json.dumps({
            "accounts": [{
                "username": "your_username",
                "cookies": "auth_token=xxx; ct0=yyy; ..."
            }]
        }, indent=2))
        return False
    
    try:
        await scraper.init()
        print("\n✅ API initialized!")
        
        # Test search
        print("\nTesting search...")
        items = await scraper.search("AI", limit=5)
        
        for item in items:
            print(f"\n📱 {item.author_username}")
            print(f"   {item.content[:100]}...")
            print(f"   👁 {item.impressions_views or 'N/A'} | ❤️ {item.impressions_likes} | 🔄 {item.impressions_reposts}")
        
        return True
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return False


async def interactive_mode():
    """Interactive mode."""
    print("=" * 60)
    print("X/Twitter Scraper - Interactive Mode")
    print("=" * 60)
    
    scraper = XScraper()
    await scraper.init()
    
    while True:
        print("\nOptions:")
        print("1. Search tweets")
        print("2. Get user tweets")
        print("3. Exit")
        
        choice = input("\nChoice: ").strip()
        
        if choice == "1":
            query = input("Search query: ").strip()
            limit = int(input("Limit (default 50): ").strip() or "50")
            items = await scraper.search(query, limit)
            print(f"\nFound {len(items)} tweets")
            for item in items[:5]:
                print(f"  {item.author_username}: {item.content[:80]}...")
            if items:
                scraper.save_items(items)
                
        elif choice == "2":
            user_id = int(input("User ID: ").strip())
            limit = int(input("Limit (default 50): ").strip() or "50")
            items = await scraper.get_user_tweets(user_id, limit)
            if items:
                scraper.save_items(items)
                
        elif choice == "3":
            break


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="X/Twitter Enhanced Scraper")
    parser.add_argument("--test", action="store_true", help="Test connection")
    parser.add_argument("--search", help="Search query")
    parser.add_argument("--user-id", type=int, help="User ID for tweets")
    parser.add_argument("--limit", type=int, default=50, help="Max results")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode")
    
    args = parser.parse_args()
    
    if args.test:
        asyncio.run(test_connection())
    elif args.search:
        async def do_search():
            scraper = XScraper()
            await scraper.init()
            items = await scraper.search(args.search, args.limit)
            for item in items:
                print(f"{item.author_username}: {item.content[:80]}...")
            if items:
                scraper.save_items(items)
        asyncio.run(do_search())
    elif args.user_id:
        async def do_user():
            scraper = XScraper()
            await scraper.init()
            items = await scraper.get_user_tweets(args.user_id, args.limit)
            if items:
                scraper.save_items(items)
        asyncio.run(do_user())
    elif args.interactive:
        asyncio.run(interactive_mode())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
