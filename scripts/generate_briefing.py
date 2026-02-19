#!/usr/bin/env python3
"""
Daily finance briefing generator.

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
KO_TTS_MODEL = "gemini-2.5-pro-preview-tts"
KO_TTS_VOICE = "Kore"
KO_TTS_STYLE_PREFIX = (
    "[차분하고 또렷한 팟캐스트 진행자 톤, "
    "문장 사이에 자연스러운 호흡을 넣고, 적당한 속도로 명확하게] "
)

# Approximate costs per 1M tokens (USD) for tracking
COST_PER_1M = {
    "gemini-2.5-pro-input": 1.25,
    "gemini-2.5-pro-output": 10.0,
    "gemini-2.5-pro-thinking": 3.75,
    "gemini-2.5-flash-input": 0.15,
    "gemini-2.5-flash-output": 0.60,
    "chirp3-hd-per-1m-chars": 16.0,
    "gemini-tts-per-1m-chars": 10.0,  # preview pricing estimate
}

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

CURATION_PROMPT = """You are a senior financial news editor. From the article list below, pick the 10-15 most important stories that deserve deep coverage in a daily briefing.

Selection criteria (in priority order):
1. Macroeconomic impact: interest rates, inflation, GDP, employment, central bank decisions
2. AI/Tech major moves: big product launches, regulatory shifts, large deals, industry trends
3. Market-wide impact: major M&A, significant earnings beats/misses, policy changes
4. Geopolitical events with direct market implications

Mandatory inclusion:
- ALWAYS include ALL articles tagged [TECH] or related to AI/technology, unless they are purely lifestyle/opinion pieces with no market relevance.

Exclusion:
- SKIP executive personnel stories (CEO/CFO/lawyer hired, fired, stepped down, pay raises) unless the departure signals a major corporate crisis or strategic shift.
- SKIP "Roundup: Market Talk" digest articles — they are low-value summaries.

Rules:
- If multiple articles cover the same event, pick only the one with the richest detail.
- Return ONLY a JSON array of article numbers (1-indexed), nothing else.
- No explanation, no text before or after. Just the array.
- Example: [3, 7, 12, 15, 22, 28, 33, 41, 45, 50, 55]
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
        # TTS
        cost += self.en_tts_chars / 1e6 * COST_PER_1M["chirp3-hd-per-1m-chars"]
        cost += self.ko_tts_chars / 1e6 * COST_PER_1M["gemini-tts-per-1m-chars"]
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
    if not skip_tts and "en" in langs:
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
    if not skip_tts and "en" in langs:
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
            .select("crawl_result_id,summary,key_entities,key_numbers,event_type,sentiment")
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
) -> set[str]:
    """Use LLM to pick top 10-15 articles. Returns set of wsj_item_ids."""
    from google.genai import types  # noqa: F811

    # Build article list for curation
    lines = []
    for i, item in enumerate(items, 1):
        crawl = crawl_map.get(item["id"])
        llm = llm_map.get(crawl["id"]) if crawl and crawl["id"] in llm_map else {}
        entities = ", ".join(llm.get("key_entities", []))[:80]
        line = f"{i}. [{item['feed_name']}] {item['title']}"
        if item.get("description"):
            line += f" — {item['description'][:120]}"
        if entities:
            line += f" (Entities: {entities})"
        lines.append(line)

    curation_input = CURATION_PROMPT + "\n\n" + "\n".join(lines)

    log.info("Curating %d articles...", len(items))
    raw = None
    resp = None

    # Try Pro up to 3 times
    for attempt in range(CURATION_MAX_RETRIES):
        log.info("  Curation attempt %d/%d (Pro)", attempt + 1, CURATION_MAX_RETRIES)
        raw, resp = _try_curation(
            gemini,
            CURATION_MODEL_PRIMARY,
            types.GenerateContentConfig(
                max_output_tokens=4096,
                temperature=0.1,
                thinking_config=types.ThinkingConfig(thinking_budget=1024),
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
                max_output_tokens=1024,
                temperature=0.0,
            ),
            curation_input,
            "Flash",
        )

    if not raw:
        log.error("Curation failed on both Pro and Flash")
        sys.exit(1)

    # Parse JSON array
    cleaned = re.sub(r"```json\s*", "", raw.strip())
    cleaned = re.sub(r"```\s*", "", cleaned).strip()
    match = re.search(r"\[[\d,\s]+\]", cleaned)
    if not match:
        log.error("Could not parse JSON array from curation: %s", raw[:200])
        sys.exit(1)

    curated_indices = json.loads(match.group())
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
            log.info("  %3d. [%-18s] %s", i, items[i - 1]["feed_name"], items[i - 1]["title"][:70])

    return curated_ids


# ---------------------------------------------------------------------------
# Article assembly
# ---------------------------------------------------------------------------


def assemble_articles(
    items: list[dict],
    crawl_map: dict[str, dict],
    llm_map: dict[str, dict],
    curated_ids: set[str],
) -> list[Article]:
    """Assemble articles with tiered content: curated (full), standard (truncated), title-only."""
    articles: list[Article] = []
    for item in items:
        wid = item["id"]
        crawl = crawl_map.get(wid)
        is_curated = wid in curated_ids

        has_quality = False
        if crawl:
            score = crawl.get("relevance_score") or 0
            same_event = crawl.get("llm_same_event", False)
            has_quality = score >= RELEVANCE_THRESHOLD or same_event

        if has_quality:
            llm = llm_map.get(crawl["id"], {})
            content = crawl.get("content") or ""
            if not is_curated:
                content = content[:CONTENT_TRUNCATE_STD]
            articles.append(
                Article(
                    id=wid,
                    title=item["title"],
                    description=item.get("description") or "",
                    category=item["feed_name"],
                    published_at=item.get("published_at", ""),
                    has_quality_crawl=True,
                    is_curated=is_curated,
                    content=content,
                    key_entities=llm.get("key_entities", []),
                    key_numbers=[str(n) for n in llm.get("key_numbers", [])],
                    event_type=llm.get("event_type", ""),
                )
            )
        else:
            articles.append(
                Article(
                    id=wid,
                    title=item["title"],
                    description=item.get("description") or "",
                    category=item["feed_name"],
                    published_at=item.get("published_at", ""),
                    has_quality_crawl=False,
                    is_curated=False,
                )
            )

    curated_count = sum(1 for a in articles if a.is_curated and a.has_quality_crawl)
    quality_count = sum(1 for a in articles if a.has_quality_crawl)
    title_count = sum(1 for a in articles if not a.has_quality_crawl)
    log.info(
        "Assembled %d articles: %d curated, %d standard, %d title-only",
        len(articles), curated_count, quality_count - curated_count, title_count,
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
    gemini, text: str, out_path: Path, cost: CostTracker
) -> Optional[TTSResult]:
    """Generate KO audio using Gemini Pro Preview TTS (single pass)."""
    from google.genai import types  # noqa: F811

    tts_input = KO_TTS_STYLE_PREFIX + text
    cost.ko_tts_chars += len(tts_input)

    log.info("KO TTS: %d chars (model: %s, voice: %s)", len(tts_input), KO_TTS_MODEL, KO_TTS_VOICE)
    start = time.time()

    try:
        resp = gemini.models.generate_content(
            model=KO_TTS_MODEL,
            contents=tts_input,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=KO_TTS_VOICE,
                        )
                    )
                ),
            ),
        )
        audio_data = resp.candidates[0].content.parts[0].inline_data.data
    except Exception as e:
        log.error("KO TTS failed: %s: %s", e.__class__.__name__, e)
        return None

    elapsed = time.time() - start

    import subprocess
    import tempfile

    duration = len(audio_data) / (24000 * 2)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Write temp WAV, convert to MP3
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_wav = tmp.name
        with wave.open(tmp_wav, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_data)

    mp3_path = out_path.with_suffix(".mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-i", tmp_wav, "-codec:a", "libmp3lame", "-b:a", "128k", str(mp3_path)],
        capture_output=True, check=True,
    )
    os.unlink(tmp_wav)

    size_kb = mp3_path.stat().st_size / 1024

    log.info("KO TTS done: %.1fs, %.0fKB (~%.1fmin), saved as MP3", elapsed, size_kb, duration / 60)
    return TTSResult(path=mp3_path, duration_sec=duration, size_kb=size_kb, elapsed_sec=elapsed)


# ---------------------------------------------------------------------------
# Whisper sentence alignment
# ---------------------------------------------------------------------------


def extract_sentences(mp3_path: Path, lang: str) -> list[dict]:
    """Run Whisper on TTS audio and return sentence-level timestamps."""
    try:
        import whisper
    except ImportError:
        log.warning("whisper not installed — skipping sentence extraction")
        return []

    start = time.time()
    whisper_lang = "en" if lang == "en" else "ko"
    log.info("Whisper alignment for %s: %s...", lang.upper(), mp3_path.name)

    model = whisper.load_model("base")
    result = model.transcribe(str(mp3_path), language=whisper_lang, word_timestamps=True, verbose=False)

    # Merge segments into full sentences
    segments = [
        {"text": s["text"].strip(), "start": round(s["start"], 2), "end": round(s["end"], 2)}
        for s in result["segments"]
    ]
    sentences = _merge_into_sentences(segments)

    elapsed = time.time() - start
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
        log.info("KO TTS (Gemini):     %s chars", f"{cost.ko_tts_chars:,}")
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
    log.info("=" * 50)

    # Load env
    env_path = Path(".env.local")
    load_dotenv(env_path)

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

    # --- Step 3: LLM curation ---
    curated_ids = curate_articles(gemini, items, crawl_map, llm_map, cost)

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
            elif lang == "ko":
                tts_result = generate_tts_ko(gemini, result.text, audio_path, cost)

        # Whisper sentence alignment
        sentences = None
        if tts_result:
            try:
                sentences = extract_sentences(tts_result.path, lang)
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
