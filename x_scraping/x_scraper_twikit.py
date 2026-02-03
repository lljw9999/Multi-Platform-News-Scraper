#!/usr/bin/env python3
"""
X/Twitter Scraper using Twikit

Alternative scraper using the twikit library (more reliable than twscrape).
Requires cookies from your browser session.

Usage:
    python3 x_scraper_twikit.py --test         # Test connection
    python3 x_scraper_twikit.py --search "AI"  # Search for tweets
    python3 x_scraper_twikit.py --user elonmusk --limit 20
"""

import asyncio
import json
import os
import sys
import argparse
from datetime import datetime
from pathlib import Path

try:
    from twikit import Client
except ImportError:
    print("Error: twikit not installed. Run: pip install twikit")
    sys.exit(1)


class XScraperTwikit:
    """X/Twitter scraper using twikit library."""
    
    def __init__(self, config_path: str = None):
        self.client = Client('en-US')
        self.config_path = config_path or Path(__file__).parent / 'config' / 'accounts.json'
        self.output_dir = Path(__file__).parent / 'output'
        self.output_dir.mkdir(exist_ok=True)
        self.cookies_file = Path(__file__).parent / 'config' / 'browser_cookies.json'
        self.logged_in = False
        
    async def login_with_cookies(self) -> bool:
        """Login using cookies from config."""
        try:
            with open(self.config_path, 'r') as f:
                config = json.load(f)
        except FileNotFoundError:
            print(f"❌ Config not found: {self.config_path}")
            return False
            
        accounts = config.get('accounts', [])
        if not accounts:
            print("❌ No accounts configured")
            return False
            
        account = accounts[0]
        cookie_str = account.get('cookies', '')
        
        if not cookie_str:
            print("❌ No cookies in config")
            return False
        
        print("🍪 Setting up cookies...")
        
        # Parse the cookie string and create a proper cookies.json for twikit
        cookies_dict = {}
        for part in cookie_str.split(';'):
            part = part.strip()
            if '=' in part:
                key, value = part.split('=', 1)
                cookies_dict[key.strip()] = value.strip()
        
        # Save cookies in twikit format
        twikit_cookies = []
        for name, value in cookies_dict.items():
            twikit_cookies.append({
                "name": name,
                "value": value,
                "domain": ".x.com",
                "path": "/"
            })
        
        with open(self.cookies_file, 'w') as f:
            json.dump(twikit_cookies, f)
        
        try:
            self.client.load_cookies(str(self.cookies_file))
            print("✅ Cookies loaded!")
            self.logged_in = True
            return True
        except Exception as e:
            print(f"❌ Cookie load failed: {e}")
            return False
        
    async def login(self) -> bool:
        """Login using saved cookies."""
        # Load cookies from the JSON file (Cookie-Editor format)
        if not self.cookies_file.exists():
            print(f"❌ Cookies file not found: {self.cookies_file}")
            return False
            
        try:
            with open(self.cookies_file, 'r') as f:
                cookies_list = json.load(f)
            
            # Convert Cookie-Editor format to simple dict
            cookies_dict = {}
            for cookie in cookies_list:
                if isinstance(cookie, dict) and 'name' in cookie and 'value' in cookie:
                    cookies_dict[cookie['name']] = cookie['value']
            
            if not cookies_dict:
                print("⚠️ No valid cookies found in file")
                return False
                
            print(f"🍪 Found {len(cookies_dict)} cookies")
            
            # Get the essential cookies
            auth_token = cookies_dict.get('auth_token', '')
            ct0 = cookies_dict.get('ct0', '')
            
            if not auth_token or not ct0:
                print("❌ Missing auth_token or ct0 cookie")
                return False
            
            # Set cookies using twikit's method
            self.client.set_cookies(cookies_dict)
            
            # Also set the ct0 as the csrf token header
            if hasattr(self.client, 'http'):
                self.client.http.headers['x-csrf-token'] = ct0
            
            print(f"✅ Set auth_token and ct0 cookies!")
            self.logged_in = True
            return True
            
        except Exception as e:
            print(f"⚠️ Cookie load failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def search_tweets(self, query: str, limit: int = 20) -> list:
        """Search for tweets matching query."""
        if not self.logged_in:
            if not await self.login():
                return []
        
        print(f"🔍 Searching for: {query}")
        tweets = []
        
        try:
            results = await self.client.search_tweet(query, 'Latest')
            count = 0
            
            for tweet in results:
                if count >= limit:
                    break
                    
                tweet_data = {
                    'id': tweet.id,
                    'text': tweet.text,
                    'created_at': str(tweet.created_at) if hasattr(tweet, 'created_at') else None,
                    'user': {
                        'id': tweet.user.id if tweet.user else None,
                        'username': tweet.user.screen_name if tweet.user else None,
                        'name': tweet.user.name if tweet.user else None,
                    },
                    'retweet_count': getattr(tweet, 'retweet_count', 0),
                    'favorite_count': getattr(tweet, 'favorite_count', 0),
                }
                tweets.append(tweet_data)
                count += 1
                print(f"  ✓ {count}. @{tweet_data['user']['username']}: {tweet_data['text'][:60]}...")
                
        except Exception as e:
            print(f"❌ Search error: {e}")
            
        return tweets
    
    async def get_user_tweets(self, username: str, limit: int = 20) -> list:
        """Get tweets from a specific user."""
        if not self.logged_in:
            if not await self.login():
                return []
        
        print(f"👤 Getting tweets from @{username}")
        tweets = []
        
        try:
            user = await self.client.get_user_by_screen_name(username)
            if not user:
                print(f"❌ User not found: {username}")
                return []
                
            results = await self.client.get_user_tweets(user.id, 'Tweets')
            count = 0
            
            for tweet in results:
                if count >= limit:
                    break
                    
                tweet_data = {
                    'id': tweet.id,
                    'text': tweet.text,
                    'created_at': str(tweet.created_at) if hasattr(tweet, 'created_at') else None,
                    'user': {
                        'id': user.id,
                        'username': username,
                        'name': user.name,
                    },
                    'retweet_count': getattr(tweet, 'retweet_count', 0),
                    'favorite_count': getattr(tweet, 'favorite_count', 0),
                }
                tweets.append(tweet_data)
                count += 1
                print(f"  ✓ {count}. {tweet_data['text'][:70]}...")
                
        except Exception as e:
            print(f"❌ Error getting user tweets: {e}")
            
        return tweets
    
    def save_results(self, tweets: list, prefix: str = "tweets"):
        """Save tweets to JSON file."""
        if not tweets:
            print("No tweets to save")
            return
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.output_dir / f"{prefix}_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(tweets, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 Saved {len(tweets)} tweets to: {filename}")


async def main():
    parser = argparse.ArgumentParser(description='X/Twitter Scraper (twikit)')
    parser.add_argument('--test', action='store_true', help='Test connection')
    parser.add_argument('--search', type=str, help='Search query')
    parser.add_argument('--user', type=str, help='Get tweets from user')
    parser.add_argument('--limit', type=int, default=20, help='Max tweets to fetch')
    parser.add_argument('--save', action='store_true', help='Save to JSON')
    
    args = parser.parse_args()
    
    scraper = XScraperTwikit()
    
    if args.test:
        print("=" * 60)
        print("X/Twitter Scraper Test (twikit)")
        print("=" * 60)
        
        if await scraper.login():
            print("\n🎉 Connection successful!")
            print("\nTrying a quick search...")
            tweets = await scraper.search_tweets("news", limit=3)
            if tweets:
                print("\n✅ Test passed! Scraper is working.")
            else:
                print("\n⚠️ Login worked but search returned no results")
        else:
            print("\n❌ Test failed - could not login")
            print("\nTroubleshooting:")
            print("1. Check cookies in x_scraping/config/accounts.json")
            print("2. Make sure your X account isn't locked")
            print("3. Get fresh cookies from browser (see below)")
            print("\nTo get cookies:")
            print("  1. Login to x.com in Chrome")
            print("  2. Open DevTools (F12) → Application → Cookies → x.com")
            print("  3. Copy auth_token and ct0 values")
            print("  4. Format as: auth_token=XXX; ct0=YYY")
        return
    
    if args.search:
        tweets = await scraper.search_tweets(args.search, args.limit)
        if args.save and tweets:
            scraper.save_results(tweets, f"search_{args.search.replace(' ', '_')}")
            
    elif args.user:
        tweets = await scraper.get_user_tweets(args.user, args.limit)
        if args.save and tweets:
            scraper.save_results(tweets, f"user_{args.user}")
            
    else:
        parser.print_help()


if __name__ == '__main__':
    asyncio.run(main())
