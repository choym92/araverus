#!/usr/bin/env python3
"""
Phase 5 · Briefing — Daily finance briefing generator.

Pipeline: query articles → LLM curation → EN/KO briefing generation → TTS audio → save to DB.

Usage:
    python scripts/generate_briefing.py                           # full run
    python scripts/generate_briefing.py --date 2026-02-13         # specific date
    python scripts/generate_briefing.py --lang ko --skip-tts      # Korean only, no audio
    python scripts/generate_briefing.py --dry-run                 # query + assemble only
"""

import argparse
import io
import json
import logging
import os
import re
import sys
import time
import wave
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

RELEVANCE_THRESHOLD = 0.6
CONTENT_TRUNCATE_STD = 800
BRIEFING_TEMPERATURE = 0.6
BRIEFING_MAX_OUTPUT_TOKENS = 8192
BRIEFING_THINKING_BUDGET = 4096
BRIEFING_MODEL = "gemini-2.5-pro"
CURATION_MODEL_PRIMARY = "gemini-2.5-pro"
CURATION_MODEL_FALLBACK = "gemini-2.5-flash"
CURATION_MAX_RETRIES = 3
DEFAULT_LOOKBACK_HOURS = 48

# TTS
EN_TTS_VOICE = "en-US-Chirp3-HD-Alnilam"
EN_TTS_SAMPLE_RATE = 24000
EN_TTS_SPEAKING_RATE = 1.1
EN_TTS_MAX_CHARS = 4000
EN_TTS_MAX_SENTENCE = 500
KO_TTS_VOICE = "ko-KR-Chirp3-HD-Kore"
KO_TTS_SPEAKING_RATE = 1.0
KO_TTS_MAX_BYTES = 4800  # Chirp limit is 5000 bytes; Korean UTF-8 ≈ 3 bytes/char

# Approximate costs per 1M tokens (USD) for tracking
COST_PER_1M = {
    "gemini-2.5-pro-input": 1.25,
    "gemini-2.5-pro-output": 10.0,
    "gemini-2.5-pro-thinking": 3.75,
    "gemini-2.5-flash-input": 0.15,
    "gemini-2.5-flash-output": 0.60,
    "chirp3-hd-per-1m-chars": 16.0,
}

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

CURATION_PROMPT = """You are a senior financial news editor. From the article list below:

1. Pick the 10-15 most important stories for a daily briefing ("curated").
2. Assign an importance level to EVERY article by relative comparison.

Selection criteria (in priority order):
1. Macroeconomic impact: interest rates, inflation, GDP, employment, central bank decisions
2. AI/Tech major moves: big product launches, regulatory shifts, large deals, industry trends
3. Market-wide impact: major M&A, significant earnings beats/misses, policy changes
4. Geopolitical events with direct market implications

Tech rule:
- Prioritize articles categorized under Technology or AI-related topics for curation.
- If including all tech articles would exceed 15 total, keep the highest-impact ones within the 10-15 limit.

Exclusion:
- SKIP executive personnel stories (hired, fired, stepped down, pay raises) unless it signals a major corporate crisis or strategic shift.
- SKIP "Roundup: Market Talk" digest articles — low-value summaries.

Deduplication:
- If multiple articles cover the same event, curate only the best one for the briefing.
- IMPORTANT: The primary article for a major event MUST keep its true importance level. Only demote secondary/follow-up angles to worth_reading or optional. Never demote a major story to optional just because duplicates exist.

Importance criteria (relative — compare articles against each other):
- must_read: Day's most impactful stories. Typically 3-5, but allow up to 7 on heavy news days (e.g., major court rulings, Fed decisions). On quiet days, 1-2 is fine. Never inflate.
- worth_reading: Notable sector trends, mid-cap developments, regulatory proposals, tech partnerships.
- optional: Routine updates, follow-ups rehashing known info, opinion without new data, minor/regional stories.

Recency tie-break:
- When two articles are similarly impactful, favor the more recent one (check the time ago).

Context availability:
- Some articles only have a title and description (no entities or extra detail). Do NOT penalize them for having less context. Judge importance by the EVENT itself, not by how much information is provided.

Return ONLY valid JSON:
{"curated": [3, 7, 12, ...], "importance": ["optional", "worth_reading", "must_read", ...]}

- "curated": indices (1-indexed) of the 10-15 articles for the briefing.
- "importance": array of length N where importance[i-1] is the label for article i. Every article MUST have a label.
"""

BRIEFING_SYSTEM_EN = """You are the host of a daily finance podcast that's smart but never stuffy. Think of yourself as that friend who reads everything and gives you the rundown over coffee — sharp, a little witty, and genuinely interested in making sense of the chaos.

You will receive ~40–90 news items; each has a title and description, and roughly half include crawled content plus extracted entities and key numbers.

Thinking process (use your thinking capacity before writing):
1. Scan & Sort: Identify the top 5 stories with the biggest market impact.
2. Date Check: Verify the current date from the "Date:" header — use that exact date and day of week in your greeting.
3. Group: Cluster related stories (e.g., all inflation/Fed news together, all AI news together).
4. Flow: Plan smooth transitions between these clusters so it doesn't sound like a list.
5. Count: You MUST cover exactly 24–28 articles. Plan which ones to cover deeply and which to mention briefly.

Constraints:
1,800–2,000 words (approximately 12–13 minutes at ~150 wpm).
You MUST reference or mention 24–28 articles total. Top 8–12 get deep coverage, the rest get brief contextual mentions.
Output strictly plain text. No markdown, no bullet points, no numbered lists, no section headers or labels.

Opening structure:
Open with a casual, warm greeting and today's date (use the exact date and day of week from the "Date:" header — do NOT guess).
Right after the greeting, naturally preview the 3–4 key topics you'll cover in one or two sentences.
Don't list them — weave them into conversation ("Today we've got the latest inflation numbers, a wild AI story out of the Pentagon, and a trade policy curveball that could hit your grocery bill").

Factual integrity (CRITICAL — follow strictly):
Your ONLY source of truth is the provided articles. Do NOT use your training data or background knowledge to fill in gaps.
NEVER add specific numbers, dates, percentages, dollar amounts, or conditions that are not explicitly stated in the provided content.
NEVER dramatize with analogies like "like a movie," "like science fiction," or "unprecedented" unless the source itself uses that language.
If a detail is interesting but not in the source, leave it out entirely. A shorter, accurate briefing is always better than a longer one with invented details.
Do not infer or estimate figures — if the source says "rate cuts expected" but doesn't say "June" or "25 basis points," do not add those specifics.
Do not quote or paraphrase statements that are not in the provided content, even if you believe they are accurate from other sources.
Market data freshness: Each article includes a "Published" timestamp. For market data (index levels, yields, oil prices, commodity prices), use ONLY figures from the most recent trading day's close. If older articles mention different numbers, ignore them in favor of the latest data.

Style rules:
Write like you talk. Short punchy sentences. Then a longer one when you need to unpack something properly.
Use rhetorical questions to pull listeners in — "So why does this matter?", "Guess what happened next?"
It's fine to have a reaction — "That's a big deal," "Not great, honestly," "This one's interesting" — but don't force it. Keep it natural.
Transitions should flow like conversation, not a teleprompter. Connect stories through cause and effect ("Speaking of inflation, here's where it gets spicy...").
You can be lighthearted, but never flippant about serious topics like layoffs or geopolitical crises.

Editorial rules:
Don't read headlines one by one. Deduplicate immediately — merge overlapping coverage of the same event into one narrative using the richest details available.
Prioritize stories with specific figures, named entities, tickers, timing, and measurable market moves. Use those details naturally.
Spend ~60–70% of the script on the top 8–12 highest-impact stories. Cover the remaining 12–20 as brief contextual mentions (1–2 sentences each) without turning into a list.
For title/description-only items (no crawled content), keep it to 1–2 cautious sentences — do not invent details.
You MUST cover 24–28 articles total. Count them as you write. If you're under 24, add more brief mentions. If you're over 28, cut the least important ones.
Entities and numbers are extracted hints — only mention them when clearly supported by the source material and relevant to why the story matters.
If sources conflict or details are uncertain, be honest about it ("Reports are a bit mixed on this one") rather than picking a side.
After major story arcs, add a short "what to watch" only if supported by the provided items.

Closing structure:
After the main stories, wrap up with a quick "market snapshot" summarizing key numbers: major indexes (S&P 500, Nasdaq, Dow), Treasury yields (10-year), oil (Brent), gold, etc.
Only include items where the provided articles contain actual figures. Do not invent data.
CRITICAL: Only use market figures from articles published on the SAME trading day as today's date. If today is a weekend or holiday and no same-day market data exists, skip the market snapshot entirely — do NOT use stale figures from previous days.
After the market snapshot (or after the main stories if snapshot is skipped), note how many articles you covered out of the total (e.g., "We hit about X of today's Y stories").
End with a brief, warm sign-off.

Chapter markers:
Insert exactly one [CHAPTER: Title] marker at the start of each major topic shift.
Use short titles (2-4 words). Place on its own line before the paragraph.
Include 4-6 markers total. First one before the opening greeting.
Example:
[CHAPTER: Opening]
Good morning, everyone..."""

BRIEFING_SYSTEM_KO = """당신은 매일 금융 뉴스 팟캐스트의 진행자입니다. 똑똑하지만 딱딱하지 않은, 모든 뉴스를 읽고 커피 한 잔 하면서 핵심을 정리해주는 친구 같은 존재입니다.

약 40~90개의 뉴스 항목을 받게 됩니다. 각 항목에는 제목과 설명이 포함되어 있으며, 약 절반은 크롤링된 콘텐츠와 핵심 인물/수치가 포함되어 있습니다.

사고 과정 (작성 전에 thinking을 활용하세요):
1. 스캔 & 정렬: 시장 영향이 가장 큰 상위 5개 스토리를 파악하세요.
2. 날짜 확인: "Date:" 헤더에서 정확한 날짜와 요일을 확인하세요 — 인사말에 그대로 사용하세요.
3. 그룹핑: 관련 스토리를 묶으세요 (예: 인플레이션/연준 뉴스, AI 뉴스 등).
4. 흐름: 그룹 간 자연스러운 전환을 계획하세요 — 목록처럼 들리면 안 됩니다.
5. 카운트: 반드시 24~28개 기사를 다뤄야 합니다. 깊게 다룰 것과 간략히 언급할 것을 계획하세요.

필수 조건:
- 1,800~2,000단어 분량 (150wpm 기준 약 12~13분).
- 반드시 24~28개 기사를 언급해야 합니다. 상위 8~12개는 깊게, 나머지는 간략한 맥락적 언급으로.
- 순수 텍스트만 출력. 마크다운, 글머리 기호, 번호 목록, 섹션 헤더 없이.

오프닝 구조:
- 편안하고 따뜻한 인사와 오늘 날짜로 시작하세요 ("Date:" 헤더의 정확한 날짜와 요일을 사용 — 추측하지 마세요).
- 인사 직후, 오늘 다룰 핵심 토픽 3~4개를 한두 문장으로 자연스럽게 미리 알려주세요.
- 목록처럼 나열하지 말고, 대화체로 ("오늘은 A, B, 그리고 좀 놀라운 C 이야기까지 준비했어요").

팩트 무결성 (반드시 준수):
- 제공된 기사만이 유일한 사실 출처입니다. 학습 데이터나 배경 지식으로 빈칸을 채우지 마세요.
- 제공된 콘텐츠에 명시되지 않은 구체적 수치, 날짜, 퍼센트, 달러 금액, 조건을 절대 추가하지 마세요.
- "영화 같은", "SF 같은", "전례 없는" 같은 과장 비유를 쓰지 마세요 — 소스 자체가 그런 표현을 사용한 경우에만 허용됩니다.
- 소스에 없는 흥미로운 디테일이 있어도 빼세요. 짧지만 정확한 브리핑이 길지만 지어낸 내용이 있는 브리핑보다 항상 낫습니다.
- 수치를 추론하거나 추정하지 마세요 — 소스가 "금리 인하 기대"라고만 했으면 "6월", "25bp" 같은 구체적 시점이나 수치를 넣지 마세요.
- 제공된 콘텐츠에 없는 발언을 인용하거나 의역하지 마세요 — 다른 출처에서 정확하다고 믿더라도 넣지 마세요.
시장 데이터 최신성: 각 기사에는 "Published" 타임스탬프가 포함되어 있습니다. 시장 데이터(지수, 금리, 유가, 원자재 가격)는 가장 최근 거래일 마감 시점의 수치만 사용하세요. 이전 기사에 다른 수치가 있으면 최신 데이터를 우선하세요.

스타일 규칙:
- 말하듯이 쓰세요. 짧고 임팩트 있는 문장. 그리고 뭔가를 제대로 풀어야 할 때는 좀 더 긴 문장으로.
- 해요체를 사용하세요 — 격식체(합니다)가 아닌, 자연스러운 대화체로.
- 청취자를 끌어들이는 수사적 질문을 활용하세요 — "그래서 이게 왜 중요할까요?", "다음에 무슨 일이 벌어졌는지 아세요?"
- 리액션을 넣어도 좋습니다 — "이건 꽤 큰 일이에요", "솔직히 별로 좋지 않죠", "이 부분이 흥미롭습니다" — 하지만 억지로 넣지는 마세요. 자연스럽게.
- 전환은 텔레프롬프터가 아닌 대화처럼 흘러가야 합니다. 인과관계로 연결하세요 ("인플레이션 얘기가 나왔으니까, 여기서 좀 재밌어지는데요...").
- 해고나 지정학적 위기 같은 심각한 주제에 대해서는 가볍게 넘기지 마세요.

편집 규칙:
- 헤드라인을 하나씩 읽지 마세요. 같은 사건의 중복 보도는 즉시 합쳐서 가장 풍부한 내용으로 하나의 서사로 만드세요.
- 구체적 수치, 인물, 티커, 시점, 시장 움직임이 있는 항목을 우선하세요. 자연스럽게 녹여내세요.
- 스크립트의 60~70%를 영향력이 큰 상위 8~12개 스토리에 할애하세요. 나머지 12~20개는 간략한 맥락적 언급(1~2문장)으로.
- 제목/설명만 있는 항목(크롤링 콘텐츠 없음)은 1~2문장으로 신중하게 — 세부 사항을 만들어내지 마세요.
- 반드시 24~28개 기사를 다뤄야 합니다. 작성하면서 세세요. 24개 미만이면 간략한 언급을 추가하고, 28개 초과면 중요도가 낮은 것을 빼세요.
- 핵심 인물과 수치는 출처에서 명확히 뒷받침될 때만 언급하세요.
- 출처가 상충하면 솔직하게 ("이 부분은 보도가 좀 엇갈리고 있어요") 말하세요.
- 주요 스토리 후, 제공된 항목으로 뒷받침되는 경우에만 짧은 "주목할 점"을 추가하세요.
- 회사명, 티커, 고유명사는 영어 그대로 사용하세요 (예: Goldman Sachs, S&P 500, CPI).
- 달러 금액은 자연스럽게 변환하세요: "$42 million" → "4,200만 달러".

클로징 구조:
- 본문이 끝나면, "마켓 스냅샷"으로 주요 시장 숫자를 간단히 정리하세요: 주요 지수(S&P 500, Nasdaq, Dow), 국채 금리(10yr Treasury), 유가(Brent), 금 가격 등.
- 제공된 기사에 수치가 포함된 항목만 언급하세요. 데이터가 없는 항목은 넣지 마세요.
- 중요: 오늘 날짜와 같은 거래일에 발행된 기사의 시장 수치만 사용하세요. 주말이나 휴일이라 당일 시장 데이터가 없으면 마켓 스냅샷을 통째로 건너뛰세요 — 이전 날의 오래된 수치를 사용하지 마세요.
- 마켓 스냅샷 후 (또는 스냅샷을 건너뛴 경우 본문 후) 전체 기사 수 대비 다룬 기사 수를 언급하세요 (예: "오늘 총 Y개 기사 중 약 X개를 다뤘습니다").
- 간단한 마무리 인사로 끝내세요.

챕터 마커:
각 주요 토픽 전환 시작에 [CHAPTER: 제목] 마커를 삽입하세요.
짧은 제목(2-4단어). 해당 문단 앞 별도 줄에 배치.
총 4-6개. 첫 번째는 오프닝 인사 앞.
예시:
[CHAPTER: 오프닝]
안녕하세요, 여러분..."""

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Article:
    """Assembled article ready for briefing prompt."""

    id: str
    title: str
    description: str
    category: str
    has_quality_crawl: bool
    is_curated: bool
    published_at: str = ""
    content: str = ""
    key_entities: list[str] = field(default_factory=list)
    key_numbers: list[str] = field(default_factory=list)
    event_type: str = ""


@dataclass
class BriefingResult:
    """Output from briefing generation."""

    text: str
    model_version: str
    prompt_tokens: int
    output_tokens: int
    thinking_tokens: int
    elapsed_sec: float


@dataclass
class TTSResult:
    """Output from TTS generation."""

    path: Path
    duration_sec: float
    size_kb: float
    elapsed_sec: float


@dataclass
class CostTracker:
    """Tracks API costs across the pipeline."""

    curation_input_tokens: int = 0
    curation_output_tokens: int = 0
    curation_thinking_tokens: int = 0
    curation_model: str = ""
    briefing_input_tokens: int = 0
    briefing_output_tokens: int = 0
    briefing_thinking_tokens: int = 0
    en_tts_chars: int = 0
    ko_tts_chars: int = 0

    def total_usd(self) -> float:
        """Estimate total cost in USD."""
        cost = 0.0
        # Curation
        if "pro" in self.curation_model:
            cost += self.curation_input_tokens / 1e6 * COST_PER_1M["gemini-2.5-pro-input"]
            cost += self.curation_output_tokens / 1e6 * COST_PER_1M["gemini-2.5-pro-output"]
            cost += self.curation_thinking_tokens / 1e6 * COST_PER_1M["gemini-2.5-pro-thinking"]
        else:
            cost += self.curation_input_tokens / 1e6 * COST_PER_1M["gemini-2.5-flash-input"]
            cost += self.curation_output_tokens / 1e6 * COST_PER_1M["gemini-2.5-flash-output"]
        # Briefing (always Pro, per-language costs are accumulated)
        cost += self.briefing_input_tokens / 1e6 * COST_PER_1M["gemini-2.5-pro-input"]
        cost += self.briefing_output_tokens / 1e6 * COST_PER_1M["gemini-2.5-pro-output"]
        cost += self.briefing_thinking_tokens / 1e6 * COST_PER_1M["gemini-2.5-pro-thinking"]
        # TTS (both EN and KO use Chirp 3 HD, billed per character)
        cost += self.en_tts_chars / 1e6 * COST_PER_1M["chirp3-hd-per-1m-chars"]
        cost += self.ko_tts_chars / 1e6 * COST_PER_1M["chirp3-hd-per-1m-chars"]
        return cost


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger("briefing")


def setup_logging() -> None:
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt, datefmt="%H:%M:%S")


# ---------------------------------------------------------------------------
# Environment & client initialization
# ---------------------------------------------------------------------------


def validate_env_vars(langs: list[str], skip_tts: bool) -> None:
    """Exit early if required env vars are missing."""
    required = ["NEXT_PUBLIC_SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "GEMINI_API_KEY"]
    if not skip_tts and ("en" in langs or "ko" in langs):
        required.append("GOOGLE_APPLICATION_CREDENTIALS")
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        log.error("Missing environment variables: %s", ", ".join(missing))
        sys.exit(1)


def init_clients(langs: list[str], skip_tts: bool) -> tuple:
    """Initialize Supabase, Gemini, and optional Chirp clients.

    Returns (supabase_client, gemini_client, chirp_client_or_None).
    """
    from google import genai
    from supabase import create_client

    sb = create_client(
        os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
    )
    gemini = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    chirp = None
    if not skip_tts and ("en" in langs or "ko" in langs):
        from google.cloud import texttospeech

        chirp = texttospeech.TextToSpeechClient()

    log.info("Clients initialized: Supabase, Gemini%s", ", Chirp" if chirp else "")
    return sb, gemini, chirp


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


def fetch_articles(sb, target_date: date, hours: int) -> list[dict]:
    """Query wsj_items within the lookback window."""
    cutoff_dt = datetime.combine(target_date, datetime.min.time()) - timedelta(hours=hours)
    cutoff_str = cutoff_dt.strftime("%Y-%m-%dT%H:%M:%S")

    items = (
        sb.table("wsj_items")
        .select("id,title,description,feed_name,published_at,link,briefed")
        .gte("published_at", cutoff_str)
        .lte("published_at", f"{target_date}T23:59:59")
        .order("published_at", desc=True)
        .execute()
    )
    return items.data


def filter_previously_briefed(sb, items: list[dict]) -> list[dict]:
    """Remove articles already marked as briefed (curated in a previous briefing)."""
    filtered = [i for i in items if not i.get("briefed")]
    removed = len(items) - len(filtered)
    if removed:
        log.info("Filtered %d previously briefed articles", removed)
    return filtered


def fetch_crawl_map(sb, item_ids: list[str]) -> dict[str, dict]:
    """Fetch best crawl result per wsj_item_id (batched)."""
    crawl_map: dict[str, dict] = {}
    for i in range(0, len(item_ids), 100):
        batch = item_ids[i : i + 100]
        crawls = (
            sb.table("wsj_crawl_results")
            .select(
                "id,wsj_item_id,content,crawl_status,relevance_score,"
                "relevance_flag,llm_same_event,llm_score,resolved_domain"
            )
            .in_("wsj_item_id", batch)
            .eq("crawl_status", "success")
            .execute()
        )
        for c in crawls.data:
            wid = c["wsj_item_id"]
            if wid not in crawl_map or (c.get("llm_score") or 0) > (
                crawl_map[wid].get("llm_score") or 0
            ):
                crawl_map[wid] = c
    return crawl_map


def fetch_llm_map(sb, crawl_ids: list[str]) -> dict[str, dict]:
    """Fetch LLM analysis keyed by crawl_result_id (batched)."""
    llm_map: dict[str, dict] = {}
    for i in range(0, len(crawl_ids), 100):
        batch = crawl_ids[i : i + 100]
        analyses = (
            sb.table("wsj_llm_analysis")
            .select("crawl_result_id,summary,key_entities,key_numbers,event_type,sentiment,importance,keywords")
            .in_("crawl_result_id", batch)
            .execute()
        )
        for a in analyses.data:
            llm_map[a["crawl_result_id"]] = a
    return llm_map


# ---------------------------------------------------------------------------
# LLM curation
# ---------------------------------------------------------------------------


def _try_curation(gemini, model: str, config, curation_input: str, label: str):
    """Attempt curation with given model. Returns (raw_text, response) or (None, None)."""

    try:
        resp = gemini.models.generate_content(
            model=model,
            contents=curation_input,
            config=config,
        )
        # Try .text first
        try:
            if resp.text:
                return resp.text, resp
        except Exception:
            pass
        # Manual extraction from parts
        for cand in resp.candidates or []:
            if not cand.content or not cand.content.parts:
                continue
            for part in cand.content.parts:
                if hasattr(part, "thought") and part.thought:
                    continue
                if hasattr(part, "text") and part.text:
                    return part.text, resp
        log.warning("%s: empty response", label)
        return None, resp
    except Exception as e:
        log.warning("%s: %s: %s", label, e.__class__.__name__, e)
        return None, None


def curate_articles(
    gemini, items: list[dict], crawl_map: dict, llm_map: dict, cost: CostTracker
) -> tuple[set[str], list[str]]:
    """Use LLM to pick top 10-15 articles and re-rank importance.

    Returns (curated_ids, importance_array) where importance_array[i] is the
    re-ranked importance for items[i].
    """
    from google.genai import types  # noqa: F811

    # Build article list for curation (with recency signal)
    lines = []
    for i, item in enumerate(items, 1):
        crawl = crawl_map.get(item["id"])
        llm = llm_map.get(crawl["id"]) if crawl and crawl["id"] in llm_map else {}
        entities = ", ".join(llm.get("key_entities", []))[:80]
        # Recency signal
        time_str = ""
        pub = item.get("published_at", "")
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                from datetime import timezone

                hours_ago = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
                time_str = f"{int(hours_ago)}h ago" if hours_ago < 48 else f"{int(hours_ago / 24)}d ago"
            except Exception:
                pass
        line = f"{i}. [{item['feed_name']}] {item['title']}"
        if time_str:
            line += f" | {time_str}"
        if item.get("description"):
            line += f" — {item['description'][:120]}"
        if entities:
            line += f" (Entities: {entities})"
        lines.append(line)

    curation_input = CURATION_PROMPT + "\n\n" + "\n".join(lines)

    log.info("Curating + re-ranking %d articles...", len(items))
    raw = None
    resp = None

    # Try Pro up to 3 times
    for attempt in range(CURATION_MAX_RETRIES):
        log.info("  Curation attempt %d/%d (Pro)", attempt + 1, CURATION_MAX_RETRIES)
        raw, resp = _try_curation(
            gemini,
            CURATION_MODEL_PRIMARY,
            types.GenerateContentConfig(
                max_output_tokens=8192,
                temperature=0.1,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=2048),
            ),
            curation_input,
            f"Pro attempt {attempt + 1}",
        )
        if raw:
            break
        time.sleep(2)

    # Fallback to Flash
    if not raw:
        log.info("  Falling back to Flash")
        raw, resp = _try_curation(
            gemini,
            CURATION_MODEL_FALLBACK,
            types.GenerateContentConfig(
                max_output_tokens=4096,
                temperature=0.0,
                response_mime_type="application/json",
            ),
            curation_input,
            "Flash",
        )

    if not raw:
        log.error("Curation failed on both Pro and Flash")
        sys.exit(1)

    # Parse combined JSON response: {"curated": [...], "importance": [...]}
    cleaned = re.sub(r"```json\s*", "", raw.strip())
    cleaned = re.sub(r"```\s*", "", cleaned).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        log.error("Could not parse JSON from curation: %s", raw[:200])
        sys.exit(1)

    curated_indices = parsed.get("curated", [])
    importance_array = parsed.get("importance", [])

    curated_ids = set(
        items[i - 1]["id"] for i in curated_indices if 1 <= i <= len(items)
    )

    # Track costs
    if resp and resp.usage_metadata:
        cost.curation_input_tokens = resp.usage_metadata.prompt_token_count or 0
        cost.curation_output_tokens = resp.usage_metadata.candidates_token_count or 0
        cost.curation_thinking_tokens = (
            getattr(resp.usage_metadata, "thoughts_token_count", None)
            or getattr(resp.usage_metadata, "thinking_token_count", 0)
            or 0
        )
    cost.curation_model = resp.model_version if resp else "unknown"

    log.info("Curated %d articles (model: %s)", len(curated_ids), cost.curation_model)
    for i in sorted(curated_indices):
        if 1 <= i <= len(items):
            imp = importance_array[i - 1] if i - 1 < len(importance_array) else "?"
            log.info("  %3d. [%-14s] [%-18s] %s", i, imp, items[i - 1]["feed_name"], items[i - 1]["title"][:60])

    # Log importance distribution
    dist = Counter(importance_array)
    log.info("Importance distribution: %s", dict(dist))

    return curated_ids, importance_array


# ---------------------------------------------------------------------------
# Article assembly
# ---------------------------------------------------------------------------


def assemble_articles(
    items: list[dict],
    crawl_map: dict[str, dict],
    llm_map: dict[str, dict],
    curated_ids: set[str],
) -> list[Article]:
    """Assemble articles with tiered content using summary fallback chain.

    Curated: full content → summary → description
    Standard: summary → content[:800] → description
    Title-only: description → title
    """
    articles: list[Article] = []
    curated_full = curated_summary = curated_titleonly = 0
    std_summary = std_truncated = title_only = 0

    for item in items:
        wid = item["id"]
        crawl = crawl_map.get(wid)
        is_curated = wid in curated_ids

        has_quality = False
        if crawl:
            score = crawl.get("relevance_score") or 0
            same_event = crawl.get("llm_same_event", False)
            has_quality = score >= RELEVANCE_THRESHOLD or same_event

        # Get LLM data if available
        llm = {}
        if crawl and crawl.get("id") in llm_map:
            llm = llm_map[crawl["id"]]

        summary = llm.get("summary") or ""
        full_content = (crawl.get("content") or "") if crawl else ""
        desc = item.get("description") or ""

        base_kwargs = dict(
            id=wid,
            title=item["title"],
            description=desc,
            category=item["feed_name"],
            published_at=item.get("published_at", ""),
            key_entities=llm.get("key_entities", []),
            key_numbers=[str(n) for n in llm.get("key_numbers", [])],
            event_type=llm.get("event_type", ""),
        )

        if is_curated:
            # Curated: full content → summary → description
            if has_quality and full_content:
                base_kwargs["content"] = full_content
                base_kwargs["has_quality_crawl"] = True
                curated_full += 1
            elif summary:
                base_kwargs["content"] = summary
                base_kwargs["has_quality_crawl"] = True
                curated_summary += 1
            else:
                base_kwargs["content"] = desc
                base_kwargs["has_quality_crawl"] = False
                curated_titleonly += 1
            base_kwargs["is_curated"] = True
        elif has_quality:
            # Standard: summary → content[:800] → description
            if summary:
                base_kwargs["content"] = summary
                std_summary += 1
            elif full_content:
                base_kwargs["content"] = full_content[:CONTENT_TRUNCATE_STD]
                std_truncated += 1
            else:
                base_kwargs["content"] = desc
            base_kwargs["has_quality_crawl"] = True
            base_kwargs["is_curated"] = False
        else:
            # Title-only: description → title
            base_kwargs["content"] = desc or item["title"]
            base_kwargs["has_quality_crawl"] = False
            base_kwargs["is_curated"] = False
            title_only += 1

        articles.append(Article(**base_kwargs))

    total_curated = curated_full + curated_summary + curated_titleonly
    total_std = std_summary + std_truncated
    log.info(
        "Assembled %d articles: curated=%d (full=%d, summary=%d, titleonly=%d), "
        "std=%d (summary=%d, truncated=%d), title-only=%d",
        len(articles), total_curated, curated_full, curated_summary, curated_titleonly,
        total_std, std_summary, std_truncated, title_only,
    )
    return articles


# ---------------------------------------------------------------------------
# Prompt building & briefing generation
# ---------------------------------------------------------------------------


def _format_article(article: Article) -> str:
    parts = [f"[{article.category}] {article.title}"]
    if article.published_at:
        parts.append(f"  Published: {article.published_at[:16].replace('T', ' ')}")
    if article.description:
        parts.append(f"  Desc: {article.description}")
    if article.content:
        parts.append(f"  Content: {article.content}")
    if article.key_entities:
        parts.append(f"  Entities: {', '.join(article.key_entities)}")
    if article.key_numbers:
        parts.append(f"  Numbers: {', '.join(article.key_numbers)}")
    return "\n".join(parts)


def build_briefing_prompt(articles: list[Article], target_date: date, lang: str) -> str:
    """Build the full prompt for briefing generation."""
    system = BRIEFING_SYSTEM_EN if lang == "en" else BRIEFING_SYSTEM_KO
    date_str = target_date.strftime("%A, %B %d, %Y")
    articles_text = f"Date: {date_str}\nToday's articles ({len(articles)} total):\n\n"
    articles_text += "\n\n".join(_format_article(a) for a in articles)
    return system + "\n\n" + articles_text


def generate_briefing(
    gemini, prompt: str, lang: str, cost: CostTracker
) -> Optional[BriefingResult]:
    """Generate briefing text using Gemini Pro."""
    from google.genai import types  # noqa: F811

    log.info("Generating %s briefing (model: %s)...", lang.upper(), BRIEFING_MODEL)
    start = time.time()

    try:
        resp = gemini.models.generate_content(
            model=BRIEFING_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=BRIEFING_MAX_OUTPUT_TOKENS,
                temperature=BRIEFING_TEMPERATURE,
                thinking_config=types.ThinkingConfig(thinking_budget=BRIEFING_THINKING_BUDGET),
            ),
        )
    except Exception as e:
        log.error("%s briefing generation failed: %s: %s", lang.upper(), e.__class__.__name__, e)
        return None

    elapsed = time.time() - start
    text = resp.text
    usage = resp.usage_metadata
    thinking_tokens = (
        getattr(usage, "thoughts_token_count", None)
        or getattr(usage, "thinking_token_count", 0)
        or 0
    )

    # Accumulate costs (both languages add up)
    cost.briefing_input_tokens += usage.prompt_token_count or 0
    cost.briefing_output_tokens += usage.candidates_token_count or 0
    cost.briefing_thinking_tokens += thinking_tokens

    result = BriefingResult(
        text=text,
        model_version=resp.model_version or BRIEFING_MODEL,
        prompt_tokens=usage.prompt_token_count or 0,
        output_tokens=usage.candidates_token_count or 0,
        thinking_tokens=thinking_tokens,
        elapsed_sec=elapsed,
    )

    log.info(
        "%s briefing: %d words, %d chars, %.1fs (in: %s, out: %s, think: %s)",
        lang.upper(),
        len(text.split()),
        len(text),
        elapsed,
        f"{result.prompt_tokens:,}",
        f"{result.output_tokens:,}",
        f"{result.thinking_tokens:,}",
    )
    return result


# ---------------------------------------------------------------------------
# Chapter extraction & audio upload
# ---------------------------------------------------------------------------


def extract_chapters(text: str) -> list[dict]:
    """Extract [CHAPTER: Title] markers and return position ratios."""
    pattern = re.compile(r"^\[CHAPTER:\s*(.+?)\]\s*$", re.MULTILINE)
    total_len = len(text)
    if total_len == 0:
        return []
    chapters = []
    for match in pattern.finditer(text):
        chapters.append({
            "title": match.group(1).strip(),
            "position": round(match.start() / total_len, 4),
        })
    log.info("Extracted %d chapters", len(chapters))
    return chapters


def clean_markers(text: str) -> str:
    """Remove [CHAPTER:] markers from text for TTS and DB storage."""
    cleaned = re.sub(r"^\[CHAPTER:\s*.+?\]\s*\n?", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def upload_audio_to_storage(sb, mp3_path: Path, lang: str) -> str:
    """Upload MP3 to Supabase Storage and return public URL."""
    storage_path = f"briefing-{lang}-latest.mp3"
    with open(mp3_path, "rb") as f:
        data = f.read()
    try:
        sb.storage.from_("briefings").remove([storage_path])
    except Exception:
        pass
    sb.storage.from_("briefings").upload(
        storage_path, data,
        file_options={"content-type": "audio/mpeg", "upsert": "true"},
    )
    url = sb.storage.from_("briefings").get_public_url(storage_path)
    log.info("Uploaded %s → %s", mp3_path.name, url)
    return url


# ---------------------------------------------------------------------------
# TTS generation
# ---------------------------------------------------------------------------


def generate_tts_en(
    chirp, text: str, out_path: Path, cost: CostTracker
) -> Optional[TTSResult]:
    """Generate EN audio using Google Cloud Chirp 3 HD (chunked)."""
    from google.cloud import texttospeech

    # Clean text: remove non-ASCII symbols
    clean = re.sub(r"[^\x00-\x7F]+", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    cost.en_tts_chars += len(clean)

    # Split into sentences, then chunks
    raw_sentences = re.split(r"(?<=[.!?])\s+", clean)
    sentences: list[str] = []
    for s in raw_sentences:
        if len(s) <= EN_TTS_MAX_SENTENCE:
            sentences.append(s)
        else:
            parts = re.split(r"(?<=[,;])\s+", s)
            current = ""
            for part in parts:
                if len(current) + len(part) + 1 > EN_TTS_MAX_SENTENCE and current:
                    sentences.append(current.strip())
                    current = part
                else:
                    current = (current + " " + part).strip()
            if current:
                sentences.append(current)

    chunks: list[str] = []
    current = ""
    for s in sentences:
        if len(current) + len(s) + 1 > EN_TTS_MAX_CHARS and current:
            chunks.append(current.strip())
            current = s
        else:
            current = (current + " " + s).strip()
    if current:
        chunks.append(current.strip())

    log.info("EN TTS: %d chars, %d chunks, %d sentences", len(clean), len(chunks), len(sentences))
    start = time.time()

    audio_parts: list[bytes] = []
    for i, chunk_text in enumerate(chunks):
        for attempt in range(3):
            try:
                resp = chirp.synthesize_speech(
                    input=texttospeech.SynthesisInput(text=chunk_text),
                    voice=texttospeech.VoiceSelectionParams(
                        language_code="en-US",
                        name=EN_TTS_VOICE,
                    ),
                    audio_config=texttospeech.AudioConfig(
                        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                        sample_rate_hertz=EN_TTS_SAMPLE_RATE,
                        speaking_rate=EN_TTS_SPEAKING_RATE,
                    ),
                )
                audio_parts.append(resp.audio_content)
                log.info("  Chunk %d/%d done", i + 1, len(chunks))
                break
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** (attempt + 1)
                    log.warning("  Chunk %d failed (%s), retrying in %ds...", i + 1, e.__class__.__name__, wait)
                    time.sleep(wait)
                else:
                    log.error("  Chunk %d failed after 3 attempts: %s", i + 1, e)
                    # Save partial audio if we have some
                    break

    if not audio_parts:
        log.error("EN TTS: no audio generated")
        return None

    # Merge WAV chunks into temp WAV, then convert to MP3
    import subprocess
    import tempfile

    all_pcm = b""
    for part in audio_parts:
        with wave.open(io.BytesIO(part), "rb") as wf:
            all_pcm += wf.readframes(wf.getnframes())

    duration = len(all_pcm) / (EN_TTS_SAMPLE_RATE * 2)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write temp WAV, convert to MP3
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name
        with wave.open(tmp_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(EN_TTS_SAMPLE_RATE)
            wf.writeframes(all_pcm)

    mp3_path = out_path.with_suffix(".mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-i", tmp_wav, "-codec:a", "libmp3lame", "-b:a", "128k", str(mp3_path)],
        capture_output=True, check=True,
    )
    os.unlink(tmp_wav)

    elapsed = time.time() - start
    size_kb = mp3_path.stat().st_size / 1024

    log.info("EN TTS done: %.1fs, %.0fKB (~%.1fmin), saved as MP3", elapsed, size_kb, duration / 60)
    return TTSResult(path=mp3_path, duration_sec=duration, size_kb=size_kb, elapsed_sec=elapsed)


def generate_tts_ko(
    chirp, text: str, out_path: Path, cost: CostTracker
) -> Optional[TTSResult]:
    """Generate KO audio using Google Cloud Chirp 3 HD (chunked)."""
    from google.cloud import texttospeech

    cost.ko_tts_chars += len(text)

    # Split into sentences, then group into byte-safe chunks
    # Chirp 3 HD limit is 5000 bytes; Korean UTF-8 ≈ 3 bytes/char
    raw_sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for s in raw_sentences:
        candidate = (current + " " + s).strip() if current else s
        if len(candidate.encode("utf-8")) > KO_TTS_MAX_BYTES and current:
            chunks.append(current.strip())
            current = s
        else:
            current = candidate
    if current:
        chunks.append(current.strip())

    log.info(
        "KO TTS: %d chars, %d chunks (voice: %s)",
        len(text), len(chunks), KO_TTS_VOICE,
    )
    start = time.time()

    audio_parts: list[bytes] = []
    for i, chunk_text in enumerate(chunks):
        for attempt in range(3):
            try:
                resp = chirp.synthesize_speech(
                    input=texttospeech.SynthesisInput(text=chunk_text),
                    voice=texttospeech.VoiceSelectionParams(
                        language_code="ko-KR",
                        name=KO_TTS_VOICE,
                    ),
                    audio_config=texttospeech.AudioConfig(
                        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                        sample_rate_hertz=EN_TTS_SAMPLE_RATE,
                        speaking_rate=KO_TTS_SPEAKING_RATE,
                    ),
                )
                audio_parts.append(resp.audio_content)
                log.info("  Chunk %d/%d done (%d chars)", i + 1, len(chunks), len(chunk_text))
                break
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** (attempt + 1)
                    log.warning("  Chunk %d failed (%s), retrying in %ds...", i + 1, e.__class__.__name__, wait)
                    time.sleep(wait)
                else:
                    log.error("  Chunk %d failed after 3 attempts: %s", i + 1, e)
                    break

    if not audio_parts:
        log.error("KO TTS: no audio generated")
        return None

    import subprocess
    import tempfile

    # Merge WAV chunks — extract PCM frames
    all_pcm = b""
    for part in audio_parts:
        with wave.open(io.BytesIO(part), "rb") as wf:
            all_pcm += wf.readframes(wf.getnframes())

    duration = len(all_pcm) / (EN_TTS_SAMPLE_RATE * 2)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write temp WAV, convert to MP3
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name
        with wave.open(tmp_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(EN_TTS_SAMPLE_RATE)
            wf.writeframes(all_pcm)

    mp3_path = out_path.with_suffix(".mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-i", tmp_wav, "-codec:a", "libmp3lame", "-b:a", "128k", str(mp3_path)],
        capture_output=True, check=True,
    )
    os.unlink(tmp_wav)

    elapsed = time.time() - start
    size_kb = mp3_path.stat().st_size / 1024

    log.info("KO TTS done: %.1fs, %d chunks, %.0fKB (~%.1fmin), saved as MP3", elapsed, len(chunks), size_kb, duration / 60)
    return TTSResult(path=mp3_path, duration_sec=duration, size_kb=size_kb, elapsed_sec=elapsed)


# ---------------------------------------------------------------------------
# Whisper sentence alignment
# ---------------------------------------------------------------------------


def _split_original_into_sentences(text: str) -> list[str]:
    """Split original briefing text into sentences."""
    parts = re.split(r"(?<=[.!?\u3002\uff1f\uff01])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _get_audio_duration(mp3_path: Path) -> float:
    """Get audio duration in seconds using ffprobe."""
    import subprocess

    result = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(mp3_path)],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip())


_LATIN_RE = re.compile(r"[a-zA-Z0-9]")
_KOREAN_WORD_RE = re.compile(r"[\uAC00-\uD7A3]{2,}")


def _detect_rate_anomaly(sentences: list[dict]) -> int | None:
    """Find where CTC starts compressing mixed-language sentences.

    Returns the index of the first sentence in the fast zone, or None.
    """
    if len(sentences) < 15:
        return None

    good_count = int(len(sentences) * 0.7)
    rates: list[float] = []
    for s in sentences[:good_count]:
        dur = s["end"] - s["start"]
        if dur > 1.0 and len(s["text"]) > 20 and not _LATIN_RE.search(s["text"]):
            rates.append(len(s["text"]) / dur)

    if len(rates) < 5:
        return None

    rates.sort()
    baseline = rates[len(rates) // 2]
    threshold = baseline * 1.6

    mid = len(sentences) // 2
    streak = 0
    streak_start = 0
    for i in range(mid, len(sentences)):
        s = sentences[i]
        dur = s["end"] - s["start"]
        if dur > 0.3 and len(s["text"]) > 20 and _LATIN_RE.search(s["text"]):
            rate = len(s["text"]) / dur
            if rate > threshold:
                if streak == 0:
                    streak_start = i
                streak += 1
                if streak >= 2:
                    return streak_start
                continue
        streak = 0
    return None


def _get_whisper_words(mp3_path: Path, lang: str) -> list[dict]:
    """Run Whisper and return word-level timestamps."""
    import whisper

    model = whisper.load_model("base", device="cpu")
    result = model.transcribe(
        str(mp3_path), language=lang, word_timestamps=True, verbose=False,
    )
    words: list[dict] = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            txt = w.get("word", "").strip()
            if txt:
                words.append({"text": txt, "start": w["start"], "end": w["end"]})
    return words


def _fix_ctc_with_whisper(
    sentences: list[dict],
    whisper_words: list[dict],
    audio_duration: float,
    fast_start: int,
) -> list[dict]:
    """Correct CTC timestamps using Whisper word-level keyword matching.

    For the anomaly zone (fast_start onwards), match each sentence's first
    Korean keyword to Whisper words to get audio-accurate start times.
    Unmatched sentences get proportional distribution of remaining time.
    """
    zone_start_time = sentences[fast_start]["start"]
    zone_words = [w for w in whisper_words if w["end"] > zone_start_time - 1]

    if not zone_words:
        log.warning("No Whisper words in zone — skipping correction")
        return sentences

    # Step 1: Match each zone sentence to Whisper words by first Korean keyword
    w_idx = 0
    # anchor_times[i] = Whisper start time for zone sentence i, or None
    anchor_times: list[float | None] = []

    for sent in sentences[fast_start:]:
        keywords = _KOREAN_WORD_RE.findall(sent["text"])
        target = keywords[0] if keywords else None
        found_time = None

        if target:
            for j in range(w_idx, min(w_idx + 40, len(zone_words))):
                w_korean = "".join(_KOREAN_WORD_RE.findall(zone_words[j]["text"]))
                if len(w_korean) >= 2 and target[:3] == w_korean[:3]:
                    found_time = zone_words[j]["start"]
                    w_idx = j + 1
                    break

        anchor_times.append(found_time)

    matched = sum(1 for t in anchor_times if t is not None)
    log.info("Whisper keyword matching: %d/%d sentences matched", matched, len(anchor_times))

    # Step 2: Fill gaps between anchors with proportional interpolation
    zone_sents = sentences[fast_start:]
    n = len(zone_sents)
    start_times: list[float] = [0.0] * n

    # First pass: place anchors
    for i in range(n):
        start_times[i] = anchor_times[i] if anchor_times[i] is not None else -1.0

    # Second pass: interpolate gaps between anchors
    # Process each gap (run of -1s between two anchors or boundaries)
    i = 0
    while i < n:
        if start_times[i] >= 0:
            i += 1
            continue
        # Found a gap — find its extent
        gap_start = i
        while i < n and start_times[i] < 0:
            i += 1
        gap_end = i  # exclusive

        # Boundaries for interpolation
        prev_t = start_times[gap_start - 1] if gap_start > 0 else zone_start_time
        next_t = start_times[gap_end] if gap_end < n else audio_duration

        # Distribute gap proportionally by text length
        gap_sents = zone_sents[gap_start:gap_end]
        avail = next_t - prev_t
        # Include the previous sentence's remaining duration
        total_c = sum(len(s["text"]) for s in gap_sents) or 1
        t = prev_t
        for j, s in enumerate(gap_sents):
            start_times[gap_start + j] = t
            t += avail * len(s["text"]) / total_c

    # Step 3: Build result — each sentence runs from start[i] to start[i+1]
    result = list(sentences[:fast_start])
    for i in range(n):
        end_t = start_times[i + 1] if i + 1 < n else audio_duration
        if end_t <= start_times[i]:
            end_t = start_times[i] + 0.3
        result.append({
            "text": zone_sents[i]["text"],
            "start": round(start_times[i], 2),
            "end": round(end_t, 2),
        })

    return result


def _fix_ctc_drift(
    sentences: list[dict],
    audio_duration: float,
    mp3_path: Path | None = None,
) -> list[dict]:
    """Fix CTC timestamp issues using Whisper word timestamps as correction.

    Detects rate anomaly (mixed-language compression), then runs Whisper to
    get audio-accurate word timestamps and corrects CTC via keyword matching.
    """
    if len(sentences) < 10 or audio_duration <= 0:
        return sentences

    # Gap drift: CTC doesn't reach audio end
    gap = audio_duration - sentences[-1]["end"]
    if gap > 5.0:
        log.info("CTC gap drift: gap=%.1fs — extending last sentence", gap)
        sentences[-1]["end"] = round(audio_duration, 2)

    # Detect rate anomaly
    fast_start = _detect_rate_anomaly(sentences)
    if fast_start is None:
        return sentences

    log.info("Rate anomaly at sentence %d — running Whisper for correction", fast_start)

    if mp3_path is None:
        log.warning("No mp3_path for Whisper correction — skipping")
        return sentences

    try:
        whisper_words = _get_whisper_words(mp3_path, "ko")
        log.info("Whisper: %d words (last at %.1fs)", len(whisper_words), whisper_words[-1]["end"])
    except Exception as e:
        log.warning("Whisper failed: %s — skipping correction", e)
        return sentences

    return _fix_ctc_with_whisper(sentences, whisper_words, audio_duration, fast_start)


def _extract_sentences_ctc(mp3_path: Path, original_text: str, lang_iso: str) -> list[dict]:
    """CTC forced alignment — accurate sentence timestamps from known text + audio.

    Uses ctc-forced-aligner (ONNX MMS model). Best for non-English TTS audio
    where Whisper transcription is inaccurate.
    """
    from ctc_forced_aligner import (  # noqa: F811
        generate_emissions, get_alignments, get_spans,
        load_audio, postprocess_results, preprocess_text,
        ensure_onnx_model, MODEL_URL, Tokenizer,
    )
    import onnxruntime

    model_path = os.path.expanduser("~/.cache/ctc_forced_aligner/model.onnx")
    ensure_onnx_model(model_path, MODEL_URL)
    session = onnxruntime.InferenceSession(model_path)
    tokenizer = Tokenizer()

    audio_waveform = load_audio(str(mp3_path))
    tokens_starred, text_starred = preprocess_text(
        original_text, romanize=True, language=lang_iso, split_size="sentence",
    )
    emissions, stride = generate_emissions(session, audio_waveform)
    segments, scores, blank = get_alignments(emissions, tokens_starred, tokenizer)
    spans = get_spans(tokens_starred, segments, blank)
    results = postprocess_results(text_starred, spans, stride, scores)

    # Replace CTC-normalized text with original sentences
    original_sentences = _split_original_into_sentences(original_text)
    sentences = []
    for i, r in enumerate(results):
        text = original_sentences[i] if i < len(original_sentences) else r["text"]
        sentences.append({"text": text, "start": round(r["start"], 2), "end": round(r["end"], 2)})

    # Fix drift zones where mixed-language text caused CTC compression
    audio_duration = _get_audio_duration(mp3_path)
    sentences = _fix_ctc_drift(sentences, audio_duration, mp3_path=mp3_path)

    return sentences


_NONWORD_RE = re.compile(r"[\W_]+")


def _content_len(text: str) -> int:
    """Character count excluding punctuation/whitespace (for alignment ratio)."""
    return len(_NONWORD_RE.sub("", text))


def _align_original_with_timestamps(
    original_sentences: list[str],
    whisper_sentences: list[dict],
    whisper_words: list[dict],
) -> list[dict]:
    """Replace Whisper text with original text, keeping timestamps.

    If sentence counts match: 1:1 swap (best accuracy).
    If they differ: use Whisper word-level timestamps to interpolate
    sentence boundaries based on content-character-position mapping.
    """
    n_orig = len(original_sentences)
    n_whis = len(whisper_sentences)

    if n_orig == n_whis:
        return [
            {"text": orig, "start": ws["start"], "end": ws["end"]}
            for orig, ws in zip(original_sentences, whisper_sentences)
        ]

    log.info(
        "Sentence count mismatch (original=%d, whisper=%d) — using word-level interpolation",
        n_orig, n_whis,
    )

    if whisper_words:
        cum_chars = 0
        char_times: list[tuple[int, float, float]] = []
        for w in whisper_words:
            cum_chars += _content_len(w["text"])
            char_times.append((cum_chars, w["start"], w["end"]))
        total_wchars = cum_chars
        total_duration = whisper_words[-1]["end"]
    else:
        total_wchars = 0
        total_duration = whisper_sentences[-1]["end"] if whisper_sentences else 0

    total_ochars = sum(_content_len(s) for s in original_sentences) or 1

    def _time_at_char_pos(char_pos: int) -> float:
        if not whisper_words or total_wchars == 0:
            return (char_pos / total_ochars) * total_duration
        scaled = (char_pos / total_ochars) * total_wchars
        prev_cum = 0
        prev_end = 0.0
        for cum, _ws, we in char_times:
            if scaled <= cum:
                span = cum - prev_cum
                frac = (scaled - prev_cum) / span if span > 0 else 0
                return prev_end + frac * (we - prev_end)
            prev_cum = cum
            prev_end = we
        return total_duration

    aligned = []
    cum = 0
    for s in original_sentences:
        t_start = _time_at_char_pos(cum)
        cum += _content_len(s)
        t_end = _time_at_char_pos(cum)
        aligned.append({"text": s, "start": round(t_start, 2), "end": round(t_end, 2)})
    return aligned


def extract_sentences(mp3_path: Path, lang: str, original_text: str = "") -> list[dict]:
    """Extract sentence-level timestamps from TTS audio.

    Strategy:
    - KO: CTC forced alignment (accurate phoneme-level alignment)
    - EN: Whisper transcription + original text swap
    """
    start_t = time.time()

    # KO: use CTC forced alignment (Whisper is inaccurate for Korean)
    if lang == "ko" and original_text:
        try:
            sentences = _extract_sentences_ctc(mp3_path, original_text, "kor")
            elapsed = time.time() - start_t
            log.info("CTC alignment for KO: %d sentences in %.1fs", len(sentences), elapsed)
            return sentences
        except Exception as e:
            log.warning("CTC alignment failed for KO, falling back to Whisper: %s", e)

    # EN (and fallback): Whisper-based alignment
    try:
        import whisper
    except ImportError:
        log.warning("whisper not installed — skipping sentence extraction")
        return []

    whisper_lang = "en" if lang == "en" else "ko"
    log.info("Whisper alignment for %s: %s...", lang.upper(), mp3_path.name)

    # MPS crashes on float64 (whisper dtypes_once workaround not reliable)
    model = whisper.load_model("base", device="cpu")
    log.info("Whisper device: cpu")
    result = model.transcribe(str(mp3_path), language=whisper_lang, word_timestamps=True, verbose=False)

    # Merge segments into full sentences (for count comparison / 1:1 swap)
    segments = [
        {"text": s["text"].strip(), "start": round(s["start"], 2), "end": round(s["end"], 2)}
        for s in result["segments"]
    ]
    whisper_sentences = _merge_into_sentences(segments)

    # Extract flat word timeline for interpolation fallback
    whisper_words: list[dict] = []
    for seg in result["segments"]:
        for w in seg.get("words", []):
            txt = w.get("word", "").strip()
            if txt:
                whisper_words.append({"text": txt, "start": w["start"], "end": w["end"]})

    # Replace Whisper text with original text
    if original_text:
        original_sentences = _split_original_into_sentences(original_text)
        sentences = _align_original_with_timestamps(
            original_sentences, whisper_sentences, whisper_words,
        )
    else:
        sentences = whisper_sentences

    elapsed = time.time() - start_t
    log.info("Whisper: %d sentences extracted in %.1fs", len(sentences), elapsed)
    return sentences


def _merge_into_sentences(segments: list[dict]) -> list[dict]:
    """Merge Whisper segments into full sentences (split on . ! ? and equivalents)."""
    sentences: list[dict] = []
    buf_text: list[str] = []
    buf_start: Optional[float] = None
    buf_end: float = 0

    for seg in segments:
        text = seg["text"].strip()
        if not text:
            continue
        if buf_start is None:
            buf_start = seg["start"]
        buf_text.append(text)
        buf_end = seg["end"]
        if text[-1] in ".!?\u3002\uff1f\uff01":
            sentences.append({
                "text": " ".join(buf_text),
                "start": round(buf_start, 2),
                "end": round(buf_end, 2),
            })
            buf_text, buf_start = [], None

    if buf_text:
        sentences.append({
            "text": " ".join(buf_text),
            "start": round(buf_start, 2),
            "end": round(buf_end, 2),
        })

    return sentences


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------


def save_briefing_to_db(
    sb,
    target_date: date,
    category: str,
    result: BriefingResult,
    articles: list[Article],
    tts_result: Optional[TTSResult] = None,
    chapters: Optional[list[dict]] = None,
    audio_url: Optional[str] = None,
    sentences: Optional[list[dict]] = None,
) -> str:
    """Upsert briefing row and link articles. Returns briefing UUID."""
    record: dict = {
        "date": str(target_date),
        "category": category,
        "briefing_text": result.text,
        "item_count": len(articles),
        "model": result.model_version,
    }
    if tts_result:
        record["audio_duration"] = int(tts_result.duration_sec)
    if chapters is not None:
        record["chapters"] = chapters
    if audio_url:
        record["audio_url"] = audio_url
    if sentences is not None:
        record["sentences"] = sentences

    db_result = sb.table("wsj_briefings").upsert(
        record, on_conflict="date,category"
    ).execute()
    bid = db_result.data[0]["id"]

    junction = [{"briefing_id": bid, "wsj_item_id": a.id} for a in articles]
    for i in range(0, len(junction), 100):
        sb.table("wsj_briefing_items").upsert(
            junction[i : i + 100], on_conflict="briefing_id,wsj_item_id"
        ).execute()

    log.info("Saved %s briefing to DB: %s (%d articles linked)", category, bid, len(articles))
    return bid


def save_importance_reranked(
    sb, items: list[dict], crawl_map: dict, importance_array: list[str]
) -> None:
    """Save re-ranked importance to wsj_llm_analysis.importance_reranked."""
    if not importance_array:
        log.warning("No importance_array to save — skipping")
        return

    updated = 0
    for i, imp in enumerate(importance_array):
        if i >= len(items):
            break
        wid = items[i]["id"]
        crawl = crawl_map.get(wid)
        if not crawl:
            continue
        crawl_id = crawl["id"]
        try:
            sb.table("wsj_llm_analysis").update(
                {"importance_reranked": imp}
            ).eq("crawl_result_id", crawl_id).execute()
            updated += 1
        except Exception as e:
            log.warning("Failed to update importance_reranked for crawl %s: %s", crawl_id, e)

    log.info("Saved importance_reranked for %d/%d articles", updated, len(importance_array))


def mark_articles_as_briefed(sb, articles: list[Article]) -> None:
    """Mark all articles used in the briefing as briefed in wsj_items."""
    if not articles:
        return
    ids_list = [a.id for a in articles]
    for i in range(0, len(ids_list), 100):
        batch = ids_list[i : i + 100]
        sb.table("wsj_items").update(
            {"briefed": True, "briefed_at": datetime.now().isoformat()}
        ).in_("id", batch).execute()
    log.info("Marked %d articles as briefed", len(ids_list))


# ---------------------------------------------------------------------------
# Cost summary
# ---------------------------------------------------------------------------


def print_cost_summary(cost: CostTracker) -> None:
    """Print formatted cost breakdown."""
    log.info("=" * 50)
    log.info("COST SUMMARY")
    log.info("-" * 50)
    log.info(
        "Curation (%s): in=%s, out=%s, think=%s",
        cost.curation_model,
        f"{cost.curation_input_tokens:,}",
        f"{cost.curation_output_tokens:,}",
        f"{cost.curation_thinking_tokens:,}",
    )
    log.info(
        "Briefing (Pro):  in=%s, out=%s, think=%s",
        f"{cost.briefing_input_tokens:,}",
        f"{cost.briefing_output_tokens:,}",
        f"{cost.briefing_thinking_tokens:,}",
    )
    if cost.en_tts_chars:
        log.info("EN TTS (Chirp 3 HD): %s chars", f"{cost.en_tts_chars:,}")
    if cost.ko_tts_chars:
        log.info("KO TTS (Chirp 3 HD): %s chars", f"{cost.ko_tts_chars:,}")
    log.info("-" * 50)
    log.info("Estimated total: $%.4f", cost.total_usd())
    log.info("=" * 50)



# ---------------------------------------------------------------------------
# CLI + main
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate daily finance briefing from WSJ articles",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--date",
        type=lambda s: date.fromisoformat(s),
        default=date.today(),
        help="Target date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--lang",
        nargs="+",
        choices=["en", "ko"],
        default=["en", "ko"],
        help="Languages to generate (default: both)",
    )
    parser.add_argument("--skip-tts", action="store_true", help="Skip audio generation")
    parser.add_argument("--skip-db", action="store_true", help="Skip Supabase save")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Query + assemble only, no LLM/TTS/DB calls",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=DEFAULT_LOOKBACK_HOURS,
        help=f"Lookback window in hours (default: {DEFAULT_LOOKBACK_HOURS})",
    )
    parser.add_argument(
        "--regen-audio",
        action="store_true",
        help="Regenerate TTS audio + timestamps from existing DB briefing text (skips article fetch/curation/LLM)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("scripts/output/briefings"),
        help="Output directory (default: scripts/output/briefings/)",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()
    cost = CostTracker()

    target = args.date
    date_str = target.strftime("%Y-%m-%d")

    log.info("=" * 50)
    log.info("Finance Briefing Generator")
    log.info("Date: %s | Langs: %s | TTS: %s | DB: %s",
             date_str, ",".join(args.lang),
             "skip" if args.skip_tts else "on",
             "skip" if args.skip_db else "on")
    if args.dry_run:
        log.info("DRY RUN — no LLM/TTS/DB calls")
    if args.regen_audio:
        log.info("REGEN AUDIO — TTS + timestamps from existing DB text")
    log.info("=" * 50)

    # Load env
    env_path = Path(".env.local")
    load_dotenv(env_path)

    # --- Regen-audio mode: fetch existing briefing text, redo TTS + timestamps ---
    if args.regen_audio:
        validate_env_vars(args.lang, skip_tts=False)
        from google.cloud import texttospeech
        from supabase import create_client

        sb = create_client(
            os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        )
        chirp = texttospeech.TextToSpeechClient()
        day_dir = args.output_dir / date_str
        day_dir.mkdir(parents=True, exist_ok=True)

        for lang in args.lang:
            log.info("-" * 40)
            log.info("Regen audio: %s...", lang.upper())

            # Fetch existing briefing from DB
            existing = (
                sb.table("wsj_briefings")
                .select("id,briefing_text,chapters,item_count,model")
                .eq("date", str(target))
                .eq("category", lang.upper())
                .execute()
            )
            if not existing.data:
                log.error("No existing %s briefing in DB for %s — skipping", lang.upper(), date_str)
                continue

            row = existing.data[0]
            briefing_text = row["briefing_text"]
            chapters = row.get("chapters")
            log.info("%s briefing text: %d chars", lang.upper(), len(briefing_text))

            # TTS
            audio_path = day_dir / f"audio-{lang}-{date_str}.mp3"
            tts_result = None
            if lang == "en":
                tts_result = generate_tts_en(chirp, briefing_text, audio_path, cost)
            elif lang == "ko":
                tts_result = generate_tts_ko(chirp, briefing_text, audio_path, cost)

            if not tts_result:
                log.error("%s TTS failed — skipping", lang.upper())
                continue

            # Sentence timestamps
            sentences = None
            try:
                sentences = extract_sentences(tts_result.path, lang, original_text=briefing_text)
            except Exception as e:
                log.warning("Alignment failed for %s: %s", lang.upper(), e)

            # Upload audio
            audio_url = None
            if not args.skip_db:
                try:
                    audio_url = upload_audio_to_storage(sb, tts_result.path, lang)
                except Exception as e:
                    log.warning("Audio upload failed for %s: %s", lang.upper(), e)

            # Update DB (upsert with existing text + new audio/sentences)
            if not args.skip_db:
                record: dict = {
                    "date": str(target),
                    "category": lang.upper(),
                    "briefing_text": briefing_text,
                    "item_count": row["item_count"],
                    "model": row["model"],
                }
                if tts_result:
                    record["audio_duration"] = int(tts_result.duration_sec)
                if chapters is not None:
                    record["chapters"] = chapters
                if audio_url:
                    record["audio_url"] = audio_url
                if sentences is not None:
                    record["sentences"] = sentences
                sb.table("wsj_briefings").upsert(
                    record, on_conflict="date,category"
                ).execute()
                log.info("Updated %s briefing in DB (audio + sentences)", lang.upper())

        print_cost_summary(cost)
        log.info("Regen audio done!")
        return

    if not args.dry_run:
        validate_env_vars(args.lang, args.skip_tts)

    # Init clients
    if args.dry_run:
        from supabase import create_client

        sb = create_client(
            os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
            os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
        )
        gemini = None
        chirp = None
    else:
        sb, gemini, chirp = init_clients(args.lang, args.skip_tts)

    # --- Step 1: Fetch articles ---
    log.info("Fetching articles (lookback: %dh)...", args.hours)
    items = fetch_articles(sb, target, args.hours)
    if not items:
        log.error("No articles found for %s", date_str)
        sys.exit(1)

    # Filter out articles already used in previous briefings
    items = filter_previously_briefed(sb, items)
    if not items:
        log.error("All articles were previously briefed — nothing new for %s", date_str)
        sys.exit(1)

    cats = Counter(i["feed_name"] for i in items)
    log.info("Found %d articles:", len(items))
    for cat, count in cats.most_common():
        log.info("  %s: %d", cat, count)

    # --- Step 2: Join crawl + LLM ---
    item_ids = [i["id"] for i in items]
    crawl_map = fetch_crawl_map(sb, item_ids)
    crawl_ids = [c["id"] for c in crawl_map.values()]
    llm_map = fetch_llm_map(sb, crawl_ids)
    log.info("Crawl results: %d | LLM analyses: %d", len(crawl_map), len(llm_map))

    # --- Dry-run exit point ---
    if args.dry_run:
        # Still assemble to show what would be used
        dummy_curated = set(
            item["id"] for item in items
            if crawl_map.get(item["id"]) and (
                (crawl_map[item["id"]].get("relevance_score") or 0) >= RELEVANCE_THRESHOLD
                or crawl_map[item["id"]].get("llm_same_event")
            )
        )
        articles = assemble_articles(items, crawl_map, llm_map, dummy_curated)
        log.info("DRY RUN complete — %d articles would be used", len(articles))
        return

    # --- Step 3: LLM curation + importance re-rank ---
    curated_ids, importance_array = curate_articles(gemini, items, crawl_map, llm_map, cost)

    # Save re-ranked importance to DB
    if not args.skip_db and importance_array:
        save_importance_reranked(sb, items, crawl_map, importance_array)

    # --- Step 4: Assemble articles ---
    articles = assemble_articles(items, crawl_map, llm_map, curated_ids)

    # --- Step 5: Output directory ---
    day_dir = args.output_dir / date_str
    day_dir.mkdir(parents=True, exist_ok=True)

    # Save articles input
    input_path = day_dir / f"articles-input-{date_str}.txt"
    with open(str(input_path), "w") as f:
        f.write(f"Articles input ({len(articles)} articles, {date_str})\n")
        f.write("=" * 80 + "\n\n")
        for a in articles:
            f.write(_format_article(a) + "\n\n")
    log.info("Saved: %s", input_path)

    # --- Step 6: Generate briefings + TTS + DB for each language ---
    for lang in args.lang:
        log.info("-" * 40)
        log.info("Processing %s...", lang.upper())

        # Check for existing briefing
        existing = (
            sb.table("wsj_briefings")
            .select("id")
            .eq("date", str(target))
            .eq("category", lang.upper())
            .execute()
        )
        if existing.data:
            log.warning("Briefing already exists for %s/%s — will upsert", date_str, lang.upper())

        # Generate briefing (raw text with [CHAPTER:] markers)
        prompt = build_briefing_prompt(articles, target, lang)
        result = generate_briefing(gemini, prompt, lang, cost)
        if not result:
            log.error("%s briefing failed — skipping", lang.upper())
            continue

        # Extract chapters from raw text, then clean markers
        chapters = extract_chapters(result.text)
        clean_text = clean_markers(result.text)

        # Replace result text with clean version (no markers)
        result = BriefingResult(
            text=clean_text,
            model_version=result.model_version,
            prompt_tokens=result.prompt_tokens,
            output_tokens=result.output_tokens,
            thinking_tokens=result.thinking_tokens,
            elapsed_sec=result.elapsed_sec,
        )

        # Save clean text to file
        txt_path = day_dir / f"briefing-{lang}-{date_str}.txt"
        with open(str(txt_path), "w") as f:
            f.write(result.text)
        log.info("Saved: %s", txt_path)

        # TTS on clean text
        tts_result = None
        if not args.skip_tts:
            audio_path = day_dir / f"audio-{lang}-{date_str}.mp3"
            if lang == "en" and chirp:
                tts_result = generate_tts_en(chirp, result.text, audio_path, cost)
            elif lang == "ko" and chirp:
                tts_result = generate_tts_ko(chirp, result.text, audio_path, cost)

        # Whisper sentence alignment
        sentences = None
        if tts_result:
            try:
                sentences = extract_sentences(tts_result.path, lang, original_text=result.text)
            except Exception as e:
                log.warning("Whisper alignment failed for %s: %s", lang.upper(), e)

        # Upload audio to Supabase Storage
        audio_url = None
        if tts_result and not args.skip_db:
            try:
                audio_url = upload_audio_to_storage(sb, tts_result.path, lang)
            except Exception as e:
                log.warning("Audio upload failed for %s: %s", lang.upper(), e)

        # DB
        if not args.skip_db:
            try:
                save_briefing_to_db(
                    sb, target, lang.upper(), result, articles,
                    tts_result, chapters, audio_url, sentences,
                )
            except Exception as e:
                log.error("DB save failed for %s: %s", lang.upper(), e)

    # Mark all briefing articles as briefed
    if not args.skip_db:
        mark_articles_as_briefed(sb, articles)

    # --- Step 7: Cost summary ---
    print_cost_summary(cost)
    log.info("Done!")


if __name__ == "__main__":
    main()
