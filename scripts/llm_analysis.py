#!/usr/bin/env python3
"""
LLM-based content analysis for crawled articles.

Uses GPT-4o-mini to verify if crawled content matches WSJ headline
and extract rich metadata (entities, sentiment, summary, etc.).

Usage:
    from llm_analysis import analyze_content, save_analysis_to_db

    analysis = analyze_content(wsj_title, wsj_description, crawled_content)
    if analysis:
        save_analysis_to_db(supabase, crawl_result_id, analysis)
"""
import json
import os
from typing import Optional

from openai import OpenAI

# Initialize OpenAI client (lazy loaded)
_client: Optional[OpenAI] = None


def get_openai_client() -> Optional[OpenAI]:
    """Get or create OpenAI client."""
    global _client
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    if _client is None:
        _client = OpenAI(api_key=api_key)
    return _client


# LLM prompt template with scoring guide
LLM_PROMPT = """Analyze this crawled article against the original WSJ headline.

WSJ Headline: "{wsj_title}"
WSJ Description: "{wsj_description}"

Crawled Content (first 800 chars):
\"\"\"
{crawled_content}
\"\"\"

Analyze and return ONLY valid JSON (no markdown, no explanation):
{{
  "relevance_score": <0-10 integer, how well does crawled content match the WSJ headline>,
  "is_same_event": <true if reporting same specific news event, false otherwise>,
  "confidence": "<high|medium|low>",
  "event_type": "<earnings|acquisition|merger|lawsuit|regulation|product|partnership|funding|ipo|bankruptcy|executive|layoffs|guidance|other>",
  "content_quality": "<article|list_page|profile|paywall|garbage|opinion>",
  "key_entities": ["<company/org names mentioned>"],
  "key_numbers": ["<dollar amounts, percentages, counts>"],
  "tickers_mentioned": ["<stock symbols if any>"],
  "people_mentioned": ["<person names if any>"],
  "sentiment": "<positive|negative|neutral|mixed>",
  "geographic_region": "<US|China|Europe|Asia|Global|Other>",
  "time_horizon": "<immediate|short_term|long_term>",
  "summary": "<1-2 sentence summary of the crawled article>",
  "importance": "<must_read|worth_reading|optional>",
  "keywords": ["<2-4 short topic keywords, e.g. Fed, interest rates, monetary policy>"]
}}

Importance criteria:
- must_read: Market-moving events, major policy shifts, significant earnings surprises, breaking news
- worth_reading: Notable developments, useful market context, sector trends
- optional: Routine updates, minor follow-ups, background pieces

Scoring Guide:
- 9-10: Exact same news event, high quality article
- 7-8: Same event, some missing details or different angle
- 5-6: Related topic but different specific event
- 3-4: Tangentially related, mostly different content
- 0-2: Completely unrelated or garbage content"""


def analyze_content(
    wsj_title: str,
    wsj_description: str,
    crawled_content: str,
    model: str = "gpt-4o-mini",
) -> Optional[dict]:
    """
    Analyze crawled content against WSJ headline using LLM.

    Args:
        wsj_title: Original WSJ article title
        wsj_description: Original WSJ article description
        crawled_content: Crawled article content (first 800 chars used)
        model: OpenAI model to use

    Returns:
        dict with analysis results, or None on error
    """
    client = get_openai_client()
    if not client:
        print("OPENAI_API_KEY not set, skipping LLM analysis")
        return None

    prompt = LLM_PROMPT.format(
        wsj_title=wsj_title,
        wsj_description=wsj_description or "",
        crawled_content=crawled_content[:800] if crawled_content else "",
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0,
            response_format={"type": "json_object"},
        )

        result = json.loads(response.choices[0].message.content)
        result["input_tokens"] = response.usage.prompt_tokens
        result["output_tokens"] = response.usage.completion_tokens
        result["model_used"] = model
        result["raw_response"] = response.choices[0].message.content

        return result

    except json.JSONDecodeError as e:
        print(f"LLM JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"LLM analysis error: {e}")
        return None


# Valid values for database constraints
VALID_EVENT_TYPES = {
    'earnings', 'acquisition', 'merger', 'lawsuit', 'regulation',
    'product', 'partnership', 'funding', 'ipo', 'bankruptcy',
    'executive', 'layoffs', 'guidance', 'other'
}
VALID_REGIONS = {'US', 'China', 'Europe', 'Asia', 'Global', 'Other'}
VALID_SENTIMENTS = {'positive', 'negative', 'neutral', 'mixed'}
VALID_QUALITIES = {'article', 'list_page', 'profile', 'paywall', 'garbage', 'opinion'}
VALID_CONFIDENCES = {'high', 'medium', 'low'}
VALID_TIME_HORIZONS = {'immediate', 'short_term', 'long_term'}
VALID_IMPORTANCES = {'must_read', 'worth_reading', 'optional'}


def normalize_value(value: str | None, valid_set: set, default: str = 'other') -> str | None:
    """Normalize a value to match database constraints."""
    if value is None:
        return None
    if value in valid_set:
        return value
    # Try lowercase match
    value_lower = value.lower()
    for valid in valid_set:
        if valid.lower() == value_lower:
            return valid
    return default


def save_analysis_to_db(supabase, crawl_result_id: str, analysis: dict) -> bool:
    """
    Save LLM analysis to wsj_llm_analysis table.

    Args:
        supabase: Supabase client instance
        crawl_result_id: UUID of the crawl result
        analysis: Dict from analyze_content()

    Returns:
        True on success, False on error
    """
    # Normalize values to match database constraints
    event_type = normalize_value(analysis.get("event_type"), VALID_EVENT_TYPES, "other")
    geographic_region = normalize_value(analysis.get("geographic_region"), VALID_REGIONS, "Other")
    sentiment = normalize_value(analysis.get("sentiment"), VALID_SENTIMENTS, "neutral")
    content_quality = normalize_value(analysis.get("content_quality"), VALID_QUALITIES, "article")
    confidence = normalize_value(analysis.get("confidence"), VALID_CONFIDENCES, "medium")
    time_horizon = normalize_value(analysis.get("time_horizon"), VALID_TIME_HORIZONS, "immediate")
    importance = normalize_value(analysis.get("importance"), VALID_IMPORTANCES, "optional")

    # Normalize keywords: ensure list of strings, max 4
    raw_keywords = analysis.get("keywords", [])
    keywords = [str(k).strip() for k in raw_keywords if k][:4] if isinstance(raw_keywords, list) else []

    record = {
        "crawl_result_id": crawl_result_id,
        "relevance_score": analysis.get("relevance_score"),
        "is_same_event": analysis.get("is_same_event"),
        "confidence": confidence,
        "event_type": event_type,
        "content_quality": content_quality,
        "key_entities": analysis.get("key_entities", []),
        "key_numbers": analysis.get("key_numbers", []),
        "tickers_mentioned": analysis.get("tickers_mentioned", []),
        "people_mentioned": analysis.get("people_mentioned", []),
        "sentiment": sentiment,
        "geographic_region": geographic_region,
        "time_horizon": time_horizon,
        "summary": analysis.get("summary"),
        "importance": importance,
        "keywords": keywords,
        "raw_response": analysis,
        "model_used": analysis.get("model_used", "gpt-4o-mini"),
        "input_tokens": analysis.get("input_tokens"),
        "output_tokens": analysis.get("output_tokens"),
    }

    try:
        supabase.table("wsj_llm_analysis").upsert(
            record, on_conflict="crawl_result_id"
        ).execute()
        return True
    except Exception as e:
        print(f"DB save error: {e}")
        return False


def update_domain_llm_failure(supabase, domain: str) -> bool:
    """
    Increment LLM failure count for a domain.

    Called when LLM analysis returns is_same_event=false.

    Args:
        supabase: Supabase client instance
        domain: Domain name to update

    Returns:
        True on success, False on error
    """
    try:
        supabase.rpc("increment_llm_fail_count", {"domain_name": domain}).execute()
        return True
    except Exception as e:
        print(f"Domain failure update error: {e}")
        return False


def reset_domain_llm_success(supabase, domain: str) -> bool:
    """
    Reset LLM failure count for a domain on success.

    Called when LLM analysis passes (is_same_event=true).

    Args:
        supabase: Supabase client instance
        domain: Domain name to update

    Returns:
        True on success, False on error
    """
    try:
        supabase.rpc("reset_llm_fail_count", {"domain_name": domain}).execute()
        return True
    except Exception as e:
        print(f"Domain success reset error: {e}")
        return False


# For testing
if __name__ == "__main__":
    # Test with sample data
    test_title = "China's CTG Duty Free to Buy LVMH's DFS Greater China Stores"
    test_description = "The deal marks LVMH's exit from duty-free retail in the region"
    test_content = """
    China Tourism Group Duty Free Corporation (CTG Duty Free) has agreed to acquire
    LVMH's DFS Group stores in Hong Kong and Macau, marking the French luxury
    conglomerate's exit from the duty-free retail business in Greater China.
    The deal, valued at approximately $2.1 billion, includes stores at major airports
    and downtown locations. CTG Duty Free is the world's largest travel retailer by revenue.
    """

    result = analyze_content(test_title, test_description, test_content)
    if result:
        print(json.dumps(result, indent=2))
    else:
        print("Analysis failed - check OPENAI_API_KEY")
