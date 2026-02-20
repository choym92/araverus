#!/usr/bin/env python3
"""
WSJ item pre-processing with Gemini Flash-Lite.

Analyzes WSJ title + description to extract entities, keywords, tickers,
and optimized Google News search queries BEFORE the search step.

Usage:
    python scripts/wsj_preprocess.py              # unsearched items
    python scripts/wsj_preprocess.py --limit 10   # N items only
    python scripts/wsj_preprocess.py --dry-run    # no DB writes
    python scripts/wsj_preprocess.py --backfill   # include searched items
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env.local')

# Reuse Gemini client from llm_analysis
sys.path.insert(0, str(Path(__file__).parent))
from llm_analysis import get_gemini_client

# ============================================================
# Types
# ============================================================

class PreprocessResult:
    """Result of preprocessing a single WSJ item."""
    __slots__ = ('entities', 'keywords', 'tickers', 'search_queries')

    def __init__(
        self,
        entities: list[str],
        keywords: list[str],
        tickers: list[str],
        search_queries: list[str],
    ):
        self.entities = entities
        self.keywords = keywords
        self.tickers = tickers
        self.search_queries = search_queries


# ============================================================
# Gemini Preprocessor
# ============================================================

PROMPT_TEMPLATE = """Title: "{title}"
Description: "{description}"

Return ONLY valid JSON:
{{
  "entities": ["company/person/org names, max 5"],
  "keywords": ["3-5 search terms capturing the specific event"],
  "tickers": ["stock symbols if identifiable"],
  "search_queries": ["2-3 optimized Google News search queries, 5-10 words each"]
}}

Rules for search_queries:
- Find free articles covering the same news event
- Use entity names + key event terms
- Vary phrasing across queries for coverage
- Do NOT include source names (WSJ, Bloomberg, etc.)
- Do NOT add date filters"""


def preprocess_item(title: str, description: str) -> Optional[PreprocessResult]:
    """Extract metadata from title + description using Gemini Flash-Lite."""
    client = get_gemini_client()
    if client is None:
        print("  [ERROR] No Gemini API key configured")
        return None

    prompt = PROMPT_TEMPLATE.format(title=title, description=description or "")

    try:
        from google.genai import types
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
                max_output_tokens=512,
            ),
        )

        raw = response.text.strip()
        data = json.loads(raw)

        return PreprocessResult(
            entities=data.get("entities", [])[:5],
            keywords=data.get("keywords", [])[:5],
            tickers=data.get("tickers", [])[:5],
            search_queries=data.get("search_queries", [])[:3],
        )
    except json.JSONDecodeError as e:
        print(f"  [WARN] JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  [WARN] Gemini API error: {e}")
        return None


# ============================================================
# Database Operations
# ============================================================

def get_supabase_client() -> Client:
    """Create Supabase client from environment variables."""
    url = os.getenv('NEXT_PUBLIC_SUPABASE_URL') or os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
    if not url or not key:
        raise ValueError(
            "Missing Supabase credentials. Set NEXT_PUBLIC_SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in .env.local"
        )
    return create_client(url, key)


def get_items_to_preprocess(
    supabase: Client, backfill: bool = False, limit: int = 200
) -> list[dict]:
    """Get WSJ items needing preprocessing."""
    query = supabase.table('wsj_items') \
        .select('id, title, description') \
        .is_('preprocessed_at', 'null') \
        .order('published_at', desc=True) \
        .limit(limit)

    if not backfill:
        query = query.eq('searched', False)

    response = query.execute()
    return response.data or []


def save_preprocess_result(
    supabase: Client, item_id: str, result: PreprocessResult
) -> None:
    """Save preprocessing result to wsj_items."""
    supabase.table('wsj_items').update({
        'extracted_entities': result.entities,
        'extracted_keywords': result.keywords,
        'extracted_tickers': result.tickers,
        'llm_search_queries': result.search_queries,
        'preprocessed_at': datetime.now(timezone.utc).isoformat(),
    }).eq('id', item_id).execute()


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="WSJ pre-processing with Gemini Flash-Lite")
    parser.add_argument('--limit', type=int, default=200, help='Max items to process')
    parser.add_argument('--dry-run', action='store_true', help='Print results without DB writes')
    parser.add_argument('--backfill', action='store_true', help='Include already-searched items')
    args = parser.parse_args()

    print("=" * 60)
    print("WSJ Pre-processing (Gemini Flash-Lite)")
    print("=" * 60)

    supabase = get_supabase_client()
    items = get_items_to_preprocess(supabase, backfill=args.backfill, limit=args.limit)

    if not items:
        print("No items to preprocess.")
        return

    print(f"Items to process: {len(items)}")
    if args.dry_run:
        print("(dry-run mode — no DB writes)\n")

    success = 0
    failed = 0

    for i, item in enumerate(items):
        title = item['title']
        desc = item.get('description') or ''
        print(f"\n[{i+1}/{len(items)}] {title[:80]}")

        result = preprocess_item(title, desc)

        if result is None:
            failed += 1
            continue

        success += 1
        print(f"  entities: {result.entities}")
        print(f"  keywords: {result.keywords}")
        print(f"  tickers: {result.tickers}")
        print(f"  queries: {result.search_queries}")

        if not args.dry_run:
            save_preprocess_result(supabase, item['id'], result)

    print("\n" + "=" * 60)
    print(f"Done: {success} succeeded, {failed} failed out of {len(items)}")


if __name__ == '__main__':
    main()
