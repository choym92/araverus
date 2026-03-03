#!/usr/bin/env python3
"""
Phase 3 · LLM Analysis (library) — 2-step LLM content analysis for crawled articles.

Step 1 (Gate): Gemini 2.5 Flash Lite — quick relevance/quality check.
Step 2 (Analysis): Gemini 2.5 Flash — full content analysis with original headline.

Usage:
    from llm_analysis import analyze_content, save_analysis_to_db
    from llm_analysis import analyze_content_detailed, save_step2_to_db

    # Step 1: Gate check
    gate = analyze_content(wsj_title, wsj_description, crawled_content)
    if gate:
        save_analysis_to_db(supabase, crawl_result_id, gate)

    # Step 2: Full analysis (only for 'ok' articles)
    analysis = analyze_content_detailed(wsj_title, wsj_description, crawled_content)
    if analysis:
        save_step2_to_db(supabase, crawl_result_id, analysis)
"""
import json
import os
import re
from typing import Optional

_client = None


def get_gemini_client():
    """Get or create Gemini client."""
    global _client
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=api_key)
    return _client


# Step 1: Gate-only prompt (Flash Lite) — slim, fast, cheap
GATE_PROMPT = """Analyze this crawled article against the original WSJ headline.

WSJ Headline: "{wsj_title}"
WSJ Description: "{wsj_description}"

Crawled Content:
\"\"\"
{crawled_content}
\"\"\"

Return ONLY valid JSON (no markdown, no explanation):
{{
  "relevance_score": <0-10 integer, how well does crawled content match the WSJ headline>,
  "is_same_event": <true if reporting same specific news event, false otherwise>,
  "confidence": "<high|medium|low>",
  "content_quality": "<article|list_page|profile|paywall|garbage|opinion>"
}}

Scoring Guide:
- 9-10: Exact same news event, high quality article
- 7-8: Same event, some missing details or different angle
- 5-6: Related topic but different specific event
- 3-4: Tangentially related, mostly different content
- 0-2: Completely unrelated or garbage content"""


# Step 2: Full analysis prompt (Flash) — original headline + deep analysis
ANALYSIS_PROMPT = """You are a senior financial analyst writing for an investor audience.

Analyze this article and produce an original headline and detailed analysis.
The WSJ title is provided for REFERENCE ONLY — do NOT copy it.

WSJ Title (reference only): "{wsj_title}"

Article Content:
\"\"\"
{crawled_content}
\"\"\"

Return ONLY valid JSON (no markdown, no explanation):
{{
  "headline": "<ORIGINAL headline: 8-15 words, active voice, specific, never copy WSJ title>",
  "summary": "<150-250 words: analytical, cover key facts/numbers/context/implications. Do NOT repeat the headline.>",
  "key_takeaway": "<1-2 sentences: cross-domain impact analysis for investors>",
  "keywords": ["<2-4 short topic keywords>"],
  "importance": "<must_read|worth_reading|optional>",
  "event_type": "<earnings|acquisition|merger|lawsuit|regulation|product|partnership|funding|ipo|bankruptcy|executive|layoffs|guidance|other>",
  "key_entities": ["<company/org names mentioned>"],
  "key_numbers": ["<dollar amounts, percentages, counts>"],
  "tickers_mentioned": ["<stock symbols if any>"],
  "people_mentioned": ["<person names if any>"],
  "sentiment": "<positive|negative|neutral|mixed>",
  "geographic_region": "<US|China|Europe|Asia|Global|Other>",
  "time_horizon": "<immediate|short_term|long_term>"
}}

Headline rules:
- MUST be original — never copy or closely paraphrase the WSJ title
- 8-15 words, active voice, specific numbers/names when available
- Focus on the investor angle or market impact

Importance criteria:
- must_read: Market-moving events, major policy shifts, significant earnings surprises, breaking news
- worth_reading: Notable developments, useful market context, sector trends
- optional: Routine updates, minor follow-ups, background pieces"""


def _call_gemini(prompt: str, model: str) -> Optional[dict]:
    """Call Gemini and parse JSON response. Returns dict or None."""
    client = get_gemini_client()
    if not client:
        print("GEMINI_API_KEY not set, skipping LLM analysis")
        return None

    from google.genai import types

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        result = json.loads(response.text)
        usage = response.usage_metadata
        result["input_tokens"] = usage.prompt_token_count if usage else None
        result["output_tokens"] = usage.candidates_token_count if usage else None
        result["model_used"] = model
        result["raw_response"] = response.text

        return result

    except json.JSONDecodeError as e:
        # Try to extract JSON object from malformed response
        match = re.search(r'\{[\s\S]*\}', response.text)
        if match:
            try:
                result = json.loads(match.group())
                usage = response.usage_metadata
                result["input_tokens"] = usage.prompt_token_count if usage else None
                result["output_tokens"] = usage.candidates_token_count if usage else None
                result["model_used"] = model
                result["raw_response"] = response.text
                return result
            except json.JSONDecodeError:
                pass
        print(f"LLM JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"LLM analysis error: {e}")
        return None


def analyze_content(
    wsj_title: str,
    wsj_description: str,
    crawled_content: str,
    model: str = "gemini-2.5-flash-lite",
) -> Optional[dict]:
    """
    Step 1: Gate check — quick relevance/quality assessment.

    Returns dict with relevance_score, is_same_event, confidence, content_quality.
    """
    prompt = GATE_PROMPT.format(
        wsj_title=wsj_title,
        wsj_description=wsj_description or "",
        crawled_content=crawled_content or "",
    )
    return _call_gemini(prompt, model)


def analyze_content_detailed(
    wsj_title: str,
    wsj_description: str,
    crawled_content: str,
    model: str = "gemini-2.5-flash",
) -> Optional[dict]:
    """
    Step 2: Full content analysis — original headline, summary, key takeaway.

    Only call for articles that passed the gate (relevance_flag='ok').
    Uses crawled content as primary input; falls back to description if no content.
    """
    content = crawled_content or wsj_description or ""
    if not content.strip():
        print("Step 2: No content available, skipping")
        return None

    prompt = ANALYSIS_PROMPT.format(
        wsj_title=wsj_title,
        crawled_content=content,
    )
    return _call_gemini(prompt, model)


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
    Save Step 1 (gate) analysis to wsj_llm_analysis table.

    Only writes gate fields: relevance_score, is_same_event, confidence, content_quality.
    Other columns stay null until Step 2.
    """
    content_quality = normalize_value(analysis.get("content_quality"), VALID_QUALITIES, "article")
    confidence = normalize_value(analysis.get("confidence"), VALID_CONFIDENCES, "medium")

    record = {
        "crawl_result_id": crawl_result_id,
        "relevance_score": analysis.get("relevance_score"),
        "is_same_event": analysis.get("is_same_event"),
        "confidence": confidence,
        "content_quality": content_quality,
        "raw_response": analysis,
        "model_used": analysis.get("model_used", "gemini-2.5-flash-lite"),
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


def save_step2_to_db(supabase, crawl_result_id: str, analysis: dict) -> bool:
    """
    Save Step 2 (full analysis) to wsj_llm_analysis table.

    Upserts on crawl_result_id — merges with existing gate record.
    """
    event_type = normalize_value(analysis.get("event_type"), VALID_EVENT_TYPES, "other")
    geographic_region = normalize_value(analysis.get("geographic_region"), VALID_REGIONS, "Other")
    sentiment = normalize_value(analysis.get("sentiment"), VALID_SENTIMENTS, "neutral")
    time_horizon = normalize_value(analysis.get("time_horizon"), VALID_TIME_HORIZONS, "immediate")
    importance = normalize_value(analysis.get("importance"), VALID_IMPORTANCES, "optional")

    raw_keywords = analysis.get("keywords", [])
    keywords = [str(k).strip() for k in raw_keywords if k][:4] if isinstance(raw_keywords, list) else []

    record = {
        "crawl_result_id": crawl_result_id,
        "headline": analysis.get("headline"),
        "summary": analysis.get("summary"),
        "key_takeaway": analysis.get("key_takeaway"),
        "event_type": event_type,
        "key_entities": analysis.get("key_entities", []),
        "key_numbers": analysis.get("key_numbers", []),
        "tickers_mentioned": analysis.get("tickers_mentioned", []),
        "people_mentioned": analysis.get("people_mentioned", []),
        "sentiment": sentiment,
        "geographic_region": geographic_region,
        "time_horizon": time_horizon,
        "importance": importance,
        "keywords": keywords,
        "model_used": analysis.get("model_used", "gemini-2.5-flash"),
        "input_tokens": analysis.get("input_tokens"),
        "output_tokens": analysis.get("output_tokens"),
    }

    try:
        # Use update to avoid overwriting Step 1 gate fields (relevance_score, etc.)
        supabase.table("wsj_llm_analysis").update(record).eq(
            "crawl_result_id", crawl_result_id
        ).execute()
        return True
    except Exception as e:
        print(f"Step 2 DB save error: {e}")
        return False


def update_domain_llm_failure(supabase, domain: str) -> bool:
    """
    Increment LLM failure count for a domain.

    Called when LLM analysis returns is_same_event=false.
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
    """
    try:
        supabase.rpc("reset_llm_fail_count", {"domain_name": domain}).execute()
        return True
    except Exception as e:
        print(f"Domain success reset error: {e}")
        return False


# For testing
if __name__ == "__main__":
    test_title = "China's CTG Duty Free to Buy LVMH's DFS Greater China Stores"
    test_description = "The deal marks LVMH's exit from duty-free retail in the region"
    test_content = """
    China Tourism Group Duty Free Corporation (CTG Duty Free) has agreed to acquire
    LVMH's DFS Group stores in Hong Kong and Macau, marking the French luxury
    conglomerate's exit from the duty-free retail business in Greater China.
    The deal, valued at approximately $2.1 billion, includes stores at major airports
    and downtown locations. CTG Duty Free is the world's largest travel retailer by revenue.
    """

    print("=== Step 1: Gate Check ===")
    gate = analyze_content(test_title, test_description, test_content)
    if gate:
        print(json.dumps(gate, indent=2))
    else:
        print("Gate failed - check GEMINI_API_KEY")

    print("\n=== Step 2: Full Analysis ===")
    detail = analyze_content_detailed(test_title, test_description, test_content)
    if detail:
        print(json.dumps(detail, indent=2))
    else:
        print("Analysis failed")
