#!/usr/bin/env python3
"""
Newsletter Curator - AI Classification & Editorial Layer

Transforms raw HN/X data into curated newsletter content:
- AI/tech topic classification
- Relevance scoring (not just likes)
- Editorial takeaways
- Theme grouping
- Smart engagement interpretation

Usage:
    python3 curator.py --input raw_data.json --output curated.json
    python3 curator.py --scrape-and-curate  # Full pipeline
"""

import json
import re
import os
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output"

# ============================================================================
# TOPIC TAXONOMY - What we care about for an AI/tech newsletter
# ============================================================================

AI_TOPICS = {
    "llm": {
        "keywords": ["llm", "gpt", "claude", "gemini", "openai", "anthropic", "deepseek", 
                     "language model", "chatgpt", "transformer", "llama", "mistral", "phi-3",
                     "copilot", "cursor", "coding agent", "ai agent", "agentic"],
        "weight": 1.0,
        "label": "Large Language Models"
    },
    "ml_research": {
        "keywords": ["neural network", "deep learning", "machine learning", "training", 
                     "inference", "model", "benchmark", "fine-tuning", "rlhf", "reasoning",
                     "diffusion", "attention", "embedding", "vector"],
        "weight": 0.9,
        "label": "ML Research"
    },
    "ai_product": {
        "keywords": ["ai-powered", "ai app", "ai startup", "ai tool", "ai api",
                     "generative ai", "ai feature", "ai integration"],
        "weight": 0.85,
        "label": "AI Products"
    },
    "ai_infra": {
        "keywords": ["gpu", "cuda", "tpu", "nvidia", "h100", "inference server",
                     "model serving", "vllm", "triton", "onnx", "tensorrt"],
        "weight": 0.9,
        "label": "AI Infrastructure"
    },
    "ai_ethics": {
        "keywords": ["ai safety", "alignment", "hallucination", "bias", "regulation",
                     "ai policy", "ai governance", "responsible ai"],
        "weight": 0.8,
        "label": "AI Ethics & Safety"
    },
    "developer_tools": {
        "keywords": ["developer", "devtools", "ide", "vscode", "programming", "coding",
                     "software engineering", "api", "sdk", "framework", "library"],
        "weight": 0.6,
        "label": "Developer Tools"
    },
    "tech_industry": {
        "keywords": ["startup", "funding", "acquisition", "layoff", "hiring",
                     "tech company", "silicon valley", "yc", "vc", "series a"],
        "weight": 0.5,
        "label": "Tech Industry"
    },
    "data_engineering": {
        "keywords": ["database", "sql", "postgres", "data pipeline", "etl",
                     "data warehouse", "analytics", "bigquery", "snowflake"],
        "weight": 0.5,
        "label": "Data Engineering"
    }
}

# Topics to FILTER OUT (noise for AI newsletter)
NOISE_TOPICS = {
    "travel", "music", "art", "sports", "gaming", "food", "cooking",
    "linguistics", "philosophy", "history", "politics", "cern", "physics",
    "astronomy", "biology", "chemistry", "medical", "health", "fitness"
}

NOISE_KEYWORDS = [
    "sleep in lax", "where to sleep", "music club", "diy music",
    "linguistics", "passive voice", "grammar", "heating homes",
    "weather satellite", "cancer treatment", "drug trial",
    "wifi only works", "curved things", "board games"
]

# ============================================================================
# ENGAGEMENT QUALITY SCORING
# ============================================================================

def calculate_engagement_quality(item: Dict) -> Dict[str, Any]:
    """
    Smart engagement interpretation beyond raw numbers.
    
    Returns quality signals, not just counts.
    """
    likes = item.get("impressions_likes", 0) or 0
    replies = item.get("impressions_replies", 0) or 0
    
    # Engagement ratio: high replies relative to likes = contentious/flamewar
    engagement_ratio = replies / max(likes, 1)
    
    # Quality signals
    is_flamewar = engagement_ratio > 1.5 and replies > 100  # Way more replies than likes
    is_high_signal = likes > 200 and engagement_ratio < 0.5  # High likes, moderate discussion
    is_emerging = likes > 50 and likes < 200 and engagement_ratio < 0.8
    
    # Kids count (direct replies) vs descendants (all replies)
    kids = item.get("metadata", {}).get("kids_count", 0)
    discussion_depth = replies / max(kids, 1) if kids else 1
    
    # Time-based: newer items with high engagement = trending
    try:
        published = datetime.fromisoformat(item.get("published_at", ""))
        hours_old = (datetime.now() - published).total_seconds() / 3600
        velocity = likes / max(hours_old, 1)  # Likes per hour
    except:
        velocity = 0
        hours_old = 24
    
    return {
        "engagement_ratio": round(engagement_ratio, 2),
        "is_flamewar": is_flamewar,
        "is_high_signal": is_high_signal,
        "is_emerging": is_emerging,
        "discussion_depth": round(discussion_depth, 2),
        "velocity": round(velocity, 2),
        "hours_old": round(hours_old, 1),
        "quality_tier": _calculate_quality_tier(likes, engagement_ratio, is_flamewar, velocity)
    }


def _calculate_quality_tier(likes: int, ratio: float, is_flamewar: bool, velocity: float) -> str:
    """Tier items by newsletter worthiness."""
    if is_flamewar:
        return "skip_flamewar"
    if velocity > 20 and likes > 100:
        return "trending_must_include"
    if likes > 300 and ratio < 0.6:
        return "high_quality"
    if likes > 100:
        return "good"
    if likes > 30:
        return "moderate"
    return "low"


# ============================================================================
# AI/TECH CLASSIFICATION
# ============================================================================

def classify_item(item: Dict) -> Dict[str, Any]:
    """
    Classify item by AI/tech relevance.
    
    Returns:
        {
            "is_ai_relevant": bool,
            "primary_topic": str,
            "all_topics": list,
            "relevance_score": float,
            "is_noise": bool,
            "filter_reason": str or None
        }
    """
    title = (item.get("title") or "").lower()
    content = (item.get("content") or "").lower()
    text = f"{title} {content}"
    
    # Check for noise first
    for noise_kw in NOISE_KEYWORDS:
        if noise_kw.lower() in text:
            return {
                "is_ai_relevant": False,
                "primary_topic": None,
                "all_topics": [],
                "relevance_score": 0,
                "is_noise": True,
                "filter_reason": f"noise_keyword: {noise_kw}"
            }
    
    # Score against AI topics
    topic_scores = {}
    for topic_id, topic_data in AI_TOPICS.items():
        score = 0
        matched_keywords = []
        for keyword in topic_data["keywords"]:
            if keyword.lower() in text:
                # Title matches worth more
                if keyword.lower() in title:
                    score += 2
                else:
                    score += 1
                matched_keywords.append(keyword)
        
        if score > 0:
            topic_scores[topic_id] = {
                "raw_score": score,
                "weighted_score": score * topic_data["weight"],
                "matched_keywords": matched_keywords,
                "label": topic_data["label"]
            }
    
    if not topic_scores:
        return {
            "is_ai_relevant": False,
            "primary_topic": None,
            "all_topics": [],
            "relevance_score": 0,
            "is_noise": True,
            "filter_reason": "no_ai_keywords_matched"
        }
    
    # Get primary topic (highest weighted score)
    primary = max(topic_scores.items(), key=lambda x: x[1]["weighted_score"])
    
    # Calculate overall relevance
    total_score = sum(t["weighted_score"] for t in topic_scores.values())
    relevance = min(total_score / 10, 1.0)  # Normalize to 0-1
    
    return {
        "is_ai_relevant": True,
        "primary_topic": primary[0],
        "primary_topic_label": primary[1]["label"],
        "all_topics": list(topic_scores.keys()),
        "topic_details": topic_scores,
        "relevance_score": round(relevance, 2),
        "is_noise": False,
        "filter_reason": None
    }


# ============================================================================
# EDITORIAL LAYER
# ============================================================================

def generate_editorial(item: Dict, classification: Dict, engagement: Dict) -> Dict[str, str]:
    """
    Generate editorial content for newsletter.
    
    Returns:
        {
            "one_liner": str,  # TL;DR
            "why_it_matters": str,
            "audience_fit": str  # Who should care
        }
    """
    title = item.get("title", "")
    primary_topic = classification.get("primary_topic_label", "Tech")
    quality = engagement.get("quality_tier", "moderate")
    velocity = engagement.get("velocity", 0)
    
    # Generate contextual one-liner
    one_liner = _generate_one_liner(title, primary_topic)
    
    # Why it matters
    why_matters = _generate_why_matters(item, classification, engagement)
    
    # Audience fit
    audience = _determine_audience(classification)
    
    return {
        "one_liner": one_liner,
        "why_it_matters": why_matters,
        "audience_fit": audience,
        "newsletter_priority": _calculate_priority(classification, engagement)
    }


def _generate_one_liner(title: str, topic: str) -> str:
    """Generate editorial one-liner based on title patterns."""
    title_lower = title.lower()
    
    # Pattern matching for common HN title types
    if "show hn" in title_lower:
        return f"New {topic.lower()} project worth checking out"
    elif "launch hn" in title_lower:
        return f"YC startup launching in {topic.lower()} space"
    elif "ask hn" in title_lower:
        return f"Community discussion on {topic.lower()}"
    elif any(x in title_lower for x in ["benchmark", "comparison", "vs"]):
        return f"Performance/comparison data for {topic.lower()}"
    elif any(x in title_lower for x in ["raises", "funding", "acquisition"]):
        return f"Industry news: funding/M&A in {topic.lower()}"
    elif any(x in title_lower for x in ["release", "announce", "introducing"]):
        return f"New release or announcement in {topic.lower()}"
    elif any(x in title_lower for x in ["tutorial", "guide", "how to"]):
        return f"Learning resource for {topic.lower()}"
    else:
        return f"{topic} insight worth reading"


def _generate_why_matters(item: Dict, classification: Dict, engagement: Dict) -> str:
    """Generate 'why this matters' based on signals."""
    likes = item.get("impressions_likes", 0)
    velocity = engagement.get("velocity", 0)
    primary = classification.get("primary_topic", "")
    
    signals = []
    
    if velocity > 20:
        signals.append("rapidly gaining attention")
    if likes > 300:
        signals.append("highly upvoted by HN community")
    if engagement.get("is_high_signal"):
        signals.append("quality discussion")
    if "llm" in primary or "ml_research" in primary:
        signals.append("directly relevant to AI practitioners")
    if "ai_infra" in primary:
        signals.append("infrastructure implications for AI deployment")
    if "ai_product" in primary:
        signals.append("commercial AI application")
        
    if not signals:
        signals.append("worth monitoring")
    
    return "; ".join(signals[:2])


def _determine_audience(classification: Dict) -> str:
    """Determine target audience."""
    topic = classification.get("primary_topic", "")
    
    if topic in ["llm", "ml_research"]:
        return "AI engineers & researchers"
    elif topic == "ai_infra":
        return "ML platform engineers"
    elif topic == "ai_product":
        return "Product managers & founders"
    elif topic == "ai_ethics":
        return "AI policy & safety researchers"
    elif topic == "developer_tools":
        return "Software developers"
    elif topic == "tech_industry":
        return "Tech industry watchers"
    else:
        return "General tech audience"


def _calculate_priority(classification: Dict, engagement: Dict) -> int:
    """Calculate newsletter priority (1-5, 1 being highest)."""
    relevance = classification.get("relevance_score", 0)
    quality = engagement.get("quality_tier", "low")
    
    if quality == "trending_must_include" and relevance > 0.6:
        return 1
    elif quality == "high_quality" and relevance > 0.5:
        return 2
    elif quality in ["good", "high_quality"]:
        return 3
    elif relevance > 0.3:
        return 4
    else:
        return 5


# ============================================================================
# THEME GROUPING
# ============================================================================

def group_by_theme(items: List[Dict]) -> Dict[str, List[Dict]]:
    """Group curated items into newsletter themes."""
    themes = defaultdict(list)
    
    for item in items:
        topic = item.get("classification", {}).get("primary_topic", "other")
        label = item.get("classification", {}).get("primary_topic_label", "Other")
        
        # Map to broader newsletter sections
        if topic in ["llm", "ml_research"]:
            themes["🤖 AI & LLMs"].append(item)
        elif topic == "ai_infra":
            themes["🔧 AI Infrastructure"].append(item)
        elif topic == "ai_product":
            themes["📱 AI Products & Startups"].append(item)
        elif topic == "ai_ethics":
            themes["⚖️ AI Ethics & Policy"].append(item)
        elif topic == "developer_tools":
            themes["💻 Developer Tools"].append(item)
        elif topic == "tech_industry":
            themes["📰 Tech Industry News"].append(item)
        else:
            themes["📌 Other Notable"].append(item)
    
    # Sort each theme by priority
    for theme in themes:
        themes[theme].sort(key=lambda x: x.get("editorial", {}).get("newsletter_priority", 5))
    
    return dict(themes)


# ============================================================================
# MAIN CURATION PIPELINE
# ============================================================================

class NewsletterCurator:
    """Main curator that transforms raw scrape data into newsletter content."""
    
    def __init__(self, min_relevance: float = 0.2, pool_size: int = 25, publish_count: int = 8):
        self.min_relevance = min_relevance
        self.pool_size = pool_size  # Internal candidate pool
        self.publish_count = publish_count  # Actually published items
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    def curate(self, raw_items: List[Dict]) -> Dict[str, Any]:
        """
        Full curation pipeline.
        
        Args:
            raw_items: List of raw scraped items
            
        Returns:
            Curated newsletter data with themes and editorial
        """
        print(f"\n📊 Curating {len(raw_items)} items...")
        
        curated = []
        filtered_out = {"noise": [], "low_relevance": [], "flamewar": []}
        
        for item in raw_items:
            # Step 1: Classify
            classification = classify_item(item)
            
            # Step 2: Filter noise
            if classification["is_noise"]:
                filtered_out["noise"].append({
                    "title": item.get("title"),
                    "reason": classification["filter_reason"]
                })
                continue
            
            # Step 3: Calculate engagement quality
            engagement = calculate_engagement_quality(item)
            
            # Step 4: Filter flamewars
            if engagement.get("quality_tier") == "skip_flamewar":
                filtered_out["flamewar"].append({"title": item.get("title")})
                continue
            
            # Step 5: Filter low relevance
            if classification["relevance_score"] < self.min_relevance:
                filtered_out["low_relevance"].append({"title": item.get("title")})
                continue
            
            # Step 6: Generate editorial
            editorial = generate_editorial(item, classification, engagement)
            
            # Build curated item
            curated_item = {
                **item,
                "classification": classification,
                "engagement_quality": engagement,
                "editorial": editorial
            }
            curated.append(curated_item)
        
        # =====================================================================
        # SORTING LOGIC (ordered by importance)
        # 1. trending_must_include items first
        # 2. Then by newsletter_priority (1=highest)
        # 3. Then by velocity × discussion_depth (engagement quality)
        # =====================================================================
        def sort_key(item):
            quality = item["engagement_quality"].get("quality_tier", "low")
            priority = item["editorial"]["newsletter_priority"]
            velocity = item["engagement_quality"].get("velocity", 0)
            depth = item["engagement_quality"].get("discussion_depth", 1)
            
            # Tier 0: trending_must_include
            tier = 0 if quality == "trending_must_include" else 1
            
            # Composite score: velocity × discussion_depth
            engagement_score = velocity * depth
            
            return (tier, priority, -engagement_score)
        
        curated.sort(key=sort_key)
        
        # Keep internal pool
        pool = curated[:self.pool_size]
        
        # =====================================================================
        # QUALITY FILTERING FOR PUBLISH
        # Hide "low" quality tier unless:
        #   - extremely fresh (< 4 hours old), OR
        #   - fills a thematic gap (only item in its theme)
        # =====================================================================
        published = []
        theme_counts = defaultdict(int)
        filtered_out["low_quality_hidden"] = []
        
        for item in pool:
            quality = item["engagement_quality"].get("quality_tier", "low")
            hours_old = item["engagement_quality"].get("hours_old", 24)
            topic = item.get("classification", {}).get("primary_topic", "other")
            
            # Apply quality filter
            if quality == "low":
                is_fresh = hours_old < 4
                fills_gap = theme_counts.get(topic, 0) == 0
                
                if not (is_fresh or fills_gap):
                    filtered_out["low_quality_hidden"].append({
                        "title": item.get("title"),
                        "reason": f"low_quality, {hours_old:.1f}h old, topic '{topic}' has {theme_counts.get(topic, 0)} items"
                    })
                    continue
            
            published.append(item)
            theme_counts[topic] += 1
            
            if len(published) >= self.publish_count:
                break
        
        # Group published items into themes
        themes = group_by_theme(published)
        
        # Build output
        output = {
            "schema_version": "3.1",
            "curated_at": datetime.now().isoformat(),
            "source": "hackernews",
            "curation_config": {
                "min_relevance": self.min_relevance,
                "pool_size": self.pool_size,
                "publish_count": self.publish_count
            },
            "stats": {
                "input_items": len(raw_items),
                "pool_items": len(pool),
                "published_items": len(published),
                "filtered_noise": len(filtered_out["noise"]),
                "filtered_low_relevance": len(filtered_out["low_relevance"]),
                "filtered_flamewar": len(filtered_out["flamewar"]),
                "filtered_low_quality": len(filtered_out.get("low_quality_hidden", [])),
                "themes": {theme: len(items) for theme, items in themes.items()}
            },
            "themes": themes,
            "published_items": published,
            "pool_items": pool,  # Full pool for reference
            "filtered_out": filtered_out
        }
        
        print(f"✅ Pool: {len(pool)} items → Published: {len(published)} items across {len(themes)} themes")
        print(f"   Filtered: {len(filtered_out['noise'])} noise, "
              f"{len(filtered_out['low_relevance'])} low relevance, "
              f"{len(filtered_out['flamewar'])} flamewars, "
              f"{len(filtered_out.get('low_quality_hidden', []))} low quality hidden")
        
        return output
    
    def curate_from_file(self, input_path: str, output_path: str = None) -> Dict:
        """Load raw data from file, curate, and save."""
        with open(input_path, 'r') as f:
            raw_data = json.load(f)
        
        raw_items = raw_data.get("items", [])
        curated = self.curate(raw_items)
        
        if not output_path:
            output_path = OUTPUT_DIR / f"newsletter_curated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(output_path, 'w') as f:
            json.dump(curated, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Saved to {output_path}")
        return curated
    
    def generate_markdown_preview(self, curated_data: Dict) -> str:
        """Generate markdown preview of curated newsletter."""
        lines = [
            f"# AI & Tech Newsletter Preview",
            f"*Curated: {curated_data['curated_at'][:10]}*",
            f"",
            f"**{curated_data['stats'].get('published_items', curated_data['stats'].get('curated_items', 0))} stories** curated from {curated_data['stats']['input_items']} scraped",
            f"",
        ]
        
        for theme, items in curated_data.get("themes", {}).items():
            lines.append(f"## {theme}")
            lines.append("")
            
            for item in items[:5]:  # Top 5 per theme
                title = item.get("title", "Untitled")
                url = item.get("url") or item.get("metadata", {}).get("hn_url", "#")
                one_liner = item.get("editorial", {}).get("one_liner", "")
                why = item.get("editorial", {}).get("why_it_matters", "")
                likes = item.get("impressions_likes", 0)
                
                lines.append(f"### [{title}]({url})")
                lines.append(f"*{one_liner}*")
                lines.append(f"")
                lines.append(f"**Why it matters:** {why}")
                lines.append(f"")
                lines.append(f"📊 {likes} points")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Newsletter Curator")
    parser.add_argument("--input", help="Input JSON file with raw items")
    parser.add_argument("--output", help="Output JSON file")
    parser.add_argument("--min-relevance", type=float, default=0.2, help="Min relevance score")
    parser.add_argument("--pool-size", type=int, default=25, help="Internal pool size")
    parser.add_argument("--publish", type=int, default=8, help="Items to publish (8 daily, 12 weekly)")
    parser.add_argument("--preview", action="store_true", help="Generate markdown preview")
    parser.add_argument("--scrape-and-curate", action="store_true", help="Scrape HN then curate")
    
    args = parser.parse_args()
    
    curator = NewsletterCurator(
        min_relevance=args.min_relevance,
        pool_size=args.pool_size,
        publish_count=args.publish
    )
    
    if args.scrape_and_curate:
        # Import scraper and run
        from hn_scraper import HackerNewsScraper
        
        scraper = HackerNewsScraper(fetch_content=False)
        raw = scraper.scrape_for_newsletter(fetch_content=False)
        curated = curator.curate(raw["items"])
        
        output_path = OUTPUT_DIR / f"newsletter_curated_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_path, 'w') as f:
            json.dump(curated, f, indent=2, ensure_ascii=False)
        
        if args.preview:
            md = curator.generate_markdown_preview(curated)
            print("\n" + md)
            
    elif args.input:
        curated = curator.curate_from_file(args.input, args.output)
        
        if args.preview:
            md = curator.generate_markdown_preview(curated)
            print("\n" + md)
    else:
        # Default: use most recent raw file
        raw_files = sorted(OUTPUT_DIR.glob("newsletter_enhanced_*.json"), reverse=True)
        if raw_files:
            print(f"Using most recent: {raw_files[0]}")
            curated = curator.curate_from_file(str(raw_files[0]))
            
            if args.preview:
                md = curator.generate_markdown_preview(curated)
                print("\n" + md)
        else:
            parser.print_help()


if __name__ == "__main__":
    main()
