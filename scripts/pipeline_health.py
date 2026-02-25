#!/usr/bin/env python3
"""
Pipeline Health · Daily Report — Generate a daily health report for the news pipeline.

Combines two data sources:
1. DB queries (wsj_items, wsj_crawl_results, wsj_domain_status)
2. Log parsing (logs/pipeline-YYYY-MM-DD.log)

Outputs: terminal (colored), markdown file, optional email.

Usage:
    python scripts/pipeline_health.py                    # today
    python scripts/pipeline_health.py --date 2026-02-24  # specific date
    python scripts/pipeline_health.py --verbose           # detailed mode
    python scripts/pipeline_health.py --no-email          # skip email

Environment:
    NEXT_PUBLIC_SUPABASE_URL - Supabase URL
    SUPABASE_SERVICE_ROLE_KEY - Supabase service role key
    GMAIL_ADDRESS - Gmail address for sending reports (optional)
    GMAIL_APP_PASSWORD - Gmail app password (optional)
"""
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from domain_utils import require_supabase_client


# ============================================================
# Constants
# ============================================================

PROJECT_DIR = Path(__file__).parent.parent
LOG_DIR = PROJECT_DIR / "logs"
HEALTH_DIR = LOG_DIR / "health"

# ANSI colors
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_RED = "\033[31m"
C_CYAN = "\033[36m"
C_DIM = "\033[2m"

# Health thresholds
THRESHOLDS = {
    "ingest_min": 20,
    "preprocess_fail_max": 0,
    "filter_rate_low": 1.0,
    "filter_rate_high": 10.0,
    "resolve_success_min": 95.0,
    "crawl_ok_min": 35.0,
    "garbage_max": 15.0,
}


# ============================================================
# Log Parsing
# ============================================================

def parse_pipeline_log(log_path: str) -> dict:
    """Parse pipeline log file and extract per-phase summary metrics."""
    metrics: dict = {}

    path = Path(log_path)
    if not path.exists():
        return metrics

    text = path.read_text(encoding="utf-8", errors="replace")

    # --- Pipeline timing ---
    m = re.search(r"Started: (.+)", text)
    if m:
        metrics["started"] = m.group(1).strip()
    m = re.search(r"Pipeline complete — (.+)", text)
    if m:
        metrics["completed"] = m.group(1).strip()

    # --- Ingest ---
    m = re.search(r"Total fetched:\s+(\d+)", text)
    if m:
        metrics["ingest_fetched"] = int(m.group(1))
    m = re.search(r"Total inserted:\s+(\d+)", text)
    if m:
        metrics["ingest_inserted"] = int(m.group(1))
    m = re.search(r"Total skipped:\s+(\d+)", text)
    if m:
        metrics["ingest_skipped"] = int(m.group(1))

    # Feed distribution
    feeds = re.findall(r"  (\w+):\s+(\d+)/(\d+)\s+inserted", text)
    if feeds:
        metrics["ingest_feeds"] = {f: (int(ins), int(tot)) for f, ins, tot in feeds}

    # --- Preprocess ---
    m = re.search(r"Done:\s+(\d+)\s+succeeded,\s+(\d+)\s+failed\s+out\s+of\s+(\d+)", text)
    if m:
        metrics["preprocess_succeeded"] = int(m.group(1))
        metrics["preprocess_failed"] = int(m.group(2))
        metrics["preprocess_total"] = int(m.group(3))

    # --- Search ---
    m = re.search(r"WSJ items processed:\s+(\d+)", text)
    if m:
        metrics["search_items"] = int(m.group(1))
    m = re.search(r"With articles:\s+(\d+)", text)
    if m:
        metrics["search_with_articles"] = int(m.group(1))
    m = re.search(r"No articles found:\s+(\d+)", text)
    if m:
        metrics["search_no_articles"] = int(m.group(1))
    m = re.search(r"Total articles found:\s+(\d+)", text)
    if m:
        metrics["search_total_articles"] = int(m.group(1))
    m = re.search(r"Loaded\s+(\d+)\s+blocked domains", text)
    if m:
        metrics["search_blocked_domains"] = int(m.group(1))
    m = re.search(r"Search hit counts:\s+(\d+)\s+domains tracked,\s+(\d+)\s+updated", text)
    if m:
        metrics["search_domains_tracked"] = int(m.group(1))
        metrics["search_domains_updated"] = int(m.group(2))

    # --- Rank ---
    m = re.search(r"Total candidates:\s+(\d+)", text)
    if m:
        metrics["rank_total"] = int(m.group(1))
    m = re.search(r"After Embedding filter:\s+(\d+)", text)
    if m:
        metrics["rank_filtered"] = int(m.group(1))
    # Score distribution
    m = re.search(r"Score distribution:\s*\n\s*Min:\s+([\d.]+)\s*\n\s*Max:\s+([\d.]+)\s*\n\s*Avg:\s+([\d.]+)", text)
    if m:
        metrics["rank_score_min"] = float(m.group(1))
        metrics["rank_score_max"] = float(m.group(2))
        metrics["rank_score_avg"] = float(m.group(3))

    # --- Resolve ---
    m = re.search(r"Resolved:\s+(\d+)", text)
    if m:
        metrics["resolve_success"] = int(m.group(1))
    # Match "Failed: N" that appears after "Resolved:" (resolve summary section)
    resolve_section = re.search(r"Resolved:\s+\d+.*?Failed:\s+(\d+)", text, re.DOTALL)
    if resolve_section:
        metrics["resolve_failed"] = int(resolve_section.group(1))
    # Reason codes (stop at blank line)
    reason_block = re.search(r"Reason codes:\s*\n((?:\s+\S+:\s+\d+\n)+)", text)
    if reason_block:
        reasons = re.findall(r"\s+(\S+):\s+(\d+)", reason_block.group(1))
        metrics["resolve_reasons"] = {k: int(v) for k, v in reasons}
    # Resolved domains (top 10, stop at blank line)
    domain_block = re.search(r"Resolved domains:\s*\n((?:\s+[\w.]+:\s+\d+\n)+)", text)
    if domain_block:
        domains = re.findall(r"\s+([\w.]+):\s+(\d+)", domain_block.group(1))
        metrics["resolve_domains"] = [(d, int(c)) for d, c in domains[:10]]

    # --- Crawl ---
    m = re.search(r"WSJ items:\s+(\d+)\s*\n\s+. Success:\s+(\d+)\s*\n\s+. Failed:\s+(\d+)", text)
    if m:
        metrics["crawl_wsj_total"] = int(m.group(1))
        metrics["crawl_wsj_success"] = int(m.group(2))
        metrics["crawl_wsj_failed"] = int(m.group(3))
    m = re.search(r"Total crawl attempts:\s+(\d+)", text)
    if m:
        metrics["crawl_attempts"] = int(m.group(1))
    # Crawl relevance scores
    m = re.search(r"Relevance scores:\s*\n\s*Min:\s+([\d.]+)\s*\n\s*Max:\s+([\d.]+)\s*\n\s*Avg:\s+([\d.]+)", text)
    if m:
        metrics["crawl_rel_min"] = float(m.group(1))
        metrics["crawl_rel_max"] = float(m.group(2))
        metrics["crawl_rel_avg"] = float(m.group(3))
    m = re.search(r"Low relevance \(<[\d.]+\):\s+(\d+)", text)
    if m:
        metrics["crawl_low_relevance"] = int(m.group(1))

    # --- Domain blocking ---
    m = re.search(r"Auto-blocked\s+(\d+)\s+domains", text)
    if m:
        metrics["domains_auto_blocked"] = int(m.group(1))
    # Blocked domain details
    blocked_block = re.search(r"Blocked domains:\s*\n((?:\s+[\w.]+:.*\n)+)", text)
    if blocked_block:
        blocked = re.findall(
            r"\s+([\w.]+):\s+wilson=([\d.]+),\s+(\d+)%\s+\((\d+)/(\d+)\),\s+\[(.+)\]",
            blocked_block.group(1),
        )
        metrics["blocked_details"] = [
            {
                "domain": d,
                "wilson": float(w),
                "rate_pct": int(p),
                "success": int(s),
                "total": int(t),
                "reasons": r.strip(),
            }
            for d, w, p, s, t, r in blocked
        ]

    # --- Embed & Thread ---
    m = re.search(r"Embedded:\s+(\d+)", text)
    if m:
        metrics["embed_count"] = int(m.group(1))
    m = re.search(r"Matched:\s+(\d+),\s+New threads:\s+(\d+)", text)
    if m:
        metrics["thread_matched"] = int(m.group(1))
        metrics["thread_new"] = int(m.group(2))

    # --- Briefing ---
    m = re.search(r"Assembled\s+(\d+)\s+articles:\s+(\d+)\s+curated,\s+(\d+)\s+standard,\s+(\d+)\s+title-only", text)
    if m:
        metrics["briefing_total"] = int(m.group(1))
        metrics["briefing_curated"] = int(m.group(2))
        metrics["briefing_standard"] = int(m.group(3))
        metrics["briefing_title_only"] = int(m.group(4))

    # EN TTS
    m = re.search(r"EN TTS done:\s+([\d.]+)s,\s+(\d+)KB\s+\(~([\d.]+)min\)", text)
    if m:
        metrics["tts_en_seconds"] = float(m.group(1))
        metrics["tts_en_size_kb"] = int(m.group(2))
        metrics["tts_en_duration_min"] = float(m.group(3))

    # KO TTS
    if re.search(r"KO TTS: no audio generated", text):
        metrics["tts_ko_ok"] = False
    elif re.search(r"KO TTS done:", text):
        metrics["tts_ko_ok"] = True

    # Cost — sum all "Estimated total: $X.XXXX" lines across stages
    cost_matches = re.findall(r"Estimated total:\s+\$([\d.]+)", text)
    if cost_matches:
        metrics["cost_total"] = sum(float(v) for v in cost_matches)

    return metrics


# ============================================================
# DB Queries
# ============================================================

def fetch_db_metrics(supabase, date_str: str) -> dict:
    """Fetch pipeline metrics from DB for a given date."""
    metrics: dict = {}
    day_start = f"{date_str}T00:00:00+00:00"
    day_end = f"{date_str}T23:59:59+00:00"

    # --- Preprocess counts ---
    resp = (
        supabase.table("wsj_items")
        .select("id", count="exact")
        .gte("preprocessed_at", day_start)
        .lte("preprocessed_at", day_end)
        .execute()
    )
    metrics["db_preprocessed"] = resp.count or 0

    # --- Crawl results ---
    crawl_data = []
    offset = 0
    batch = 1000
    while True:
        resp = (
            supabase.table("wsj_crawl_results")
            .select("crawl_status,relevance_flag,crawl_error,resolved_domain")
            .gte("crawled_at", day_start)
            .lte("crawled_at", day_end)
            .range(offset, offset + batch - 1)
            .execute()
        )
        crawl_data.extend(resp.data)
        if len(resp.data) < batch:
            break
        offset += batch

    metrics["db_crawl_total"] = len(crawl_data)
    if crawl_data:
        status_counts: dict[str, int] = {}
        error_counts: dict[str, int] = {}
        domain_counts: dict[str, int] = {}
        ok_count = 0
        low_count = 0
        garbage_count = 0
        failed_count = 0

        for row in crawl_data:
            st = row.get("crawl_status", "unknown")
            status_counts[st] = status_counts.get(st, 0) + 1
            dom = row.get("resolved_domain", "unknown")
            domain_counts[dom] = domain_counts.get(dom, 0) + 1

            if st == "success" and row.get("relevance_flag") == "ok":
                ok_count += 1
            elif st == "success" and row.get("relevance_flag") == "low":
                low_count += 1
            elif st == "failed":
                failed_count += 1
                err = row.get("crawl_error", "unknown")
                error_counts[err] = error_counts.get(err, 0) + 1

            # Garbage: success but with known garbage errors
            if row.get("crawl_error") and st == "success":
                garbage_count += 1

        metrics["db_crawl_status"] = status_counts
        metrics["db_crawl_ok"] = ok_count
        metrics["db_crawl_low"] = low_count
        metrics["db_crawl_garbage"] = garbage_count
        metrics["db_crawl_failed"] = failed_count
        metrics["db_crawl_errors"] = dict(
            sorted(error_counts.items(), key=lambda x: -x[1])[:10]
        )
        metrics["db_crawl_domains"] = dict(
            sorted(domain_counts.items(), key=lambda x: -x[1])[:10]
        )

    # --- LLM scores for today's crawls ---
    llm_data = []
    offset = 0
    while True:
        resp = (
            supabase.table("wsj_llm_analysis")
            .select("relevance_score")
            .gte("created_at", day_start)
            .lte("created_at", day_end)
            .range(offset, offset + batch - 1)
            .execute()
        )
        llm_data.extend(resp.data)
        if len(resp.data) < batch:
            break
        offset += batch

    if llm_data:
        scores = [r["relevance_score"] for r in llm_data if r.get("relevance_score") is not None]
        if scores:
            metrics["db_llm_avg"] = sum(scores) / len(scores)
            metrics["db_llm_min"] = min(scores)
            metrics["db_llm_max"] = max(scores)
            metrics["db_llm_count"] = len(scores)

    # --- Domain health ---
    # Top domains by today's crawl volume (from db_crawl_domains)
    # High-performance domains
    resp = (
        supabase.table("wsj_domain_status")
        .select("domain,status,wilson_score,avg_llm_score,success_count,fail_count")
        .eq("status", "active")
        .gt("wilson_score", 0.6)
        .gt("avg_llm_score", 6.0)
        .order("wilson_score", desc=True)
        .limit(15)
        .execute()
    )
    metrics["db_high_perf_domains"] = resp.data

    # Blocked domain count
    resp = (
        supabase.table("wsj_domain_status")
        .select("domain", count="exact")
        .eq("status", "blocked")
        .execute()
    )
    metrics["db_blocked_count"] = resp.count or 0

    # --- Pipeline funnel (cumulative) ---
    for col in ["searched", "processed", "briefed"]:
        resp = (
            supabase.table("wsj_items")
            .select("id", count="exact")
            .eq(col, True)
            .execute()
        )
        metrics[f"db_funnel_{col}"] = resp.count or 0

    # Total items
    resp = (
        supabase.table("wsj_items")
        .select("id", count="exact")
        .execute()
    )
    metrics["db_funnel_total"] = resp.count or 0

    # Stuck items: searched but not processed, older than 24h
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    resp = (
        supabase.table("wsj_items")
        .select("id", count="exact")
        .eq("searched", True)
        .eq("processed", False)
        .lt("searched_at", cutoff)
        .execute()
    )
    metrics["db_funnel_stuck"] = resp.count or 0

    return metrics


# ============================================================
# Decision Support Metrics
# ============================================================

def fetch_decision_metrics(supabase, date_str: str, top_k: int = 40) -> dict:
    """Fetch decision-support metrics for Section 9.

    Returns dict with keys: rank_buckets, max_first_ok_rank, top_k_headroom,
    llm_dist, llm_accept, coverage_today, coverage_yesterday, domain_best, domain_worst.
    """
    from collections import defaultdict

    ds: dict = {}
    day_start = f"{date_str}T00:00:00+00:00"
    day_end = f"{date_str}T23:59:59+00:00"

    # --- Main query: today's crawl results ---
    resp = (
        supabase.table("wsj_crawl_results")
        .select("wsj_item_id,embedding_score,relevance_flag,llm_score,llm_same_event,resolved_domain,crawl_status,weighted_score,attempt_order")
        .gte("crawled_at", day_start)
        .lte("crawled_at", day_end)
        .execute()
    )
    rows = resp.data or []
    ds["total_rows"] = len(rows)

    if not rows:
        return ds

    # ── A. Candidate Rank Effectiveness ──
    # Group by wsj_item_id, sort by embedding_score DESC, find rank of first ok
    items: dict[str, list] = defaultdict(list)
    for r in rows:
        items[r["wsj_item_id"]].append(r)

    first_ok_ranks: list[int] = []
    for item_id, candidates in items.items():
        candidates.sort(key=lambda x: x.get("embedding_score") or 0, reverse=True)
        found = False
        for rank, c in enumerate(candidates, 1):
            if c.get("relevance_flag") == "ok":
                first_ok_ranks.append(rank)
                found = True
                break
        if not found:
            first_ok_ranks.append(0)  # 0 = no ok found

    buckets = {"1-5": 0, "6-10": 0, "11-20": 0, "21-30": 0, "31-40": 0, "no_ok": 0}
    for rank in first_ok_ranks:
        if rank == 0:
            buckets["no_ok"] += 1
        elif rank <= 5:
            buckets["1-5"] += 1
        elif rank <= 10:
            buckets["6-10"] += 1
        elif rank <= 20:
            buckets["11-20"] += 1
        elif rank <= 30:
            buckets["21-30"] += 1
        else:
            buckets["31-40"] += 1

    ok_ranks = [r for r in first_ok_ranks if r > 0]
    max_first_ok = max(ok_ranks) if ok_ranks else 0

    ds["rank_buckets"] = buckets
    ds["max_first_ok_rank"] = max_first_ok
    ds["top_k"] = top_k
    ds["top_k_headroom"] = top_k - max_first_ok if max_first_ok else top_k

    # ── B. LLM Threshold ──
    llm_dist: dict[str, int] = {"≤5": 0, "6": 0, "7": 0, "≥8": 0}
    ok_same = 0
    ok_diff = 0
    low_count = 0

    for r in rows:
        score = r.get("llm_score")
        flag = r.get("relevance_flag")
        same = r.get("llm_same_event")

        if score is not None:
            if score <= 5:
                llm_dist["≤5"] += 1
            elif score == 6:
                llm_dist["6"] += 1
            elif score == 7:
                llm_dist["7"] += 1
            else:
                llm_dist["≥8"] += 1

        if flag == "ok":
            if same:
                ok_same += 1
            else:
                ok_diff += 1
        elif flag == "low":
            low_count += 1

    ds["llm_dist"] = llm_dist
    ds["ok_same"] = ok_same
    ds["ok_diff"] = ok_diff
    ds["ok_total"] = ok_same + ok_diff
    ds["low_count"] = low_count

    # ── C. Briefing Coverage ──
    # Today's EN briefing
    today_briefing = (
        supabase.table("wsj_briefings")
        .select("id")
        .eq("date", date_str)
        .eq("category", "ALL")
        .limit(1)
        .execute()
    )
    if today_briefing.data:
        briefing_id = today_briefing.data[0]["id"]
        # Get wsj_item_ids in this briefing
        bi_resp = (
            supabase.table("wsj_briefing_items")
            .select("wsj_item_id")
            .eq("briefing_id", briefing_id)
            .execute()
        )
        item_ids = [r["wsj_item_id"] for r in (bi_resp.data or [])]
        total_items = len(item_ids)

        # Count how many have at least one ok crawl
        if item_ids:
            ok_items = set()
            for r in rows:
                if r["wsj_item_id"] in item_ids and r.get("relevance_flag") == "ok":
                    ok_items.add(r["wsj_item_id"])
            # Also check crawl results outside today's window for these items
            all_ok_resp = (
                supabase.table("wsj_crawl_results")
                .select("wsj_item_id")
                .in_("wsj_item_id", item_ids)
                .eq("relevance_flag", "ok")
                .execute()
            )
            for r in (all_ok_resp.data or []):
                ok_items.add(r["wsj_item_id"])
            ds["coverage_today_ok"] = len(ok_items)
        else:
            ds["coverage_today_ok"] = 0
        ds["coverage_today_total"] = total_items
    else:
        ds["coverage_today_total"] = 0
        ds["coverage_today_ok"] = 0

    # Yesterday's EN briefing for delta
    from datetime import timedelta
    yesterday = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    yest_briefing = (
        supabase.table("wsj_briefings")
        .select("id")
        .eq("date", yesterday)
        .eq("category", "ALL")
        .limit(1)
        .execute()
    )
    if yest_briefing.data:
        yest_id = yest_briefing.data[0]["id"]
        ybi_resp = (
            supabase.table("wsj_briefing_items")
            .select("wsj_item_id")
            .eq("briefing_id", yest_id)
            .execute()
        )
        yest_items = [r["wsj_item_id"] for r in (ybi_resp.data or [])]
        yest_total = len(yest_items)
        if yest_items:
            yest_ok_resp = (
                supabase.table("wsj_crawl_results")
                .select("wsj_item_id")
                .in_("wsj_item_id", yest_items)
                .eq("relevance_flag", "ok")
                .execute()
            )
            yest_ok = len({r["wsj_item_id"] for r in (yest_ok_resp.data or [])})
        else:
            yest_ok = 0
        ds["coverage_yesterday_ok"] = yest_ok
        ds["coverage_yesterday_total"] = yest_total
    else:
        ds["coverage_yesterday_total"] = 0
        ds["coverage_yesterday_ok"] = 0

    # ── D. Domain ROI ──
    domain_stats: dict[str, dict] = defaultdict(lambda: {
        "attempts": 0, "ok": 0, "llm_scores": [], "same_count": 0,
    })
    for r in rows:
        dom = r.get("resolved_domain") or "unknown"
        domain_stats[dom]["attempts"] += 1
        if r.get("relevance_flag") == "ok":
            domain_stats[dom]["ok"] += 1
        if r.get("llm_score") is not None:
            domain_stats[dom]["llm_scores"].append(r["llm_score"])
        if r.get("llm_same_event"):
            domain_stats[dom]["same_count"] += 1

    # Best: sort by ok% DESC (min 3 attempts)
    best = []
    for dom, s in domain_stats.items():
        if s["attempts"] >= 3:
            ok_pct = s["ok"] / s["attempts"] * 100
            avg_llm = sum(s["llm_scores"]) / len(s["llm_scores"]) if s["llm_scores"] else 0
            same_pct = s["same_count"] / s["ok"] * 100 if s["ok"] else 0
            best.append({
                "domain": dom, "attempts": s["attempts"], "ok": s["ok"],
                "ok_pct": ok_pct, "avg_llm": avg_llm, "same_pct": same_pct,
            })
    best.sort(key=lambda x: (-x["ok_pct"], -x["attempts"]))
    ds["domain_best"] = best[:10]

    # Worst: ≥3 attempts, 0 ok
    worst = []
    for dom, s in domain_stats.items():
        if s["attempts"] >= 3 and s["ok"] == 0:
            avg_llm = sum(s["llm_scores"]) / len(s["llm_scores"]) if s["llm_scores"] else 0
            worst.append({
                "domain": dom, "attempts": s["attempts"], "avg_llm": avg_llm,
            })
    worst.sort(key=lambda x: -x["attempts"])
    ds["domain_worst"] = worst[:10]

    # ── E. Score Effectiveness ──
    # Only compute when weighted_score data exists (Phase 2 data)
    ws_rows = [r for r in rows if r.get("weighted_score") is not None]
    if ws_rows:
        ok_scores = [r["weighted_score"] for r in ws_rows if r.get("relevance_flag") == "ok"]
        low_scores = [r["weighted_score"] for r in ws_rows if r.get("relevance_flag") == "low"]
        ds["score_avg_ok"] = sum(ok_scores) / len(ok_scores) if ok_scores else None
        ds["score_avg_low"] = sum(low_scores) / len(low_scores) if low_scores else None

        # ok at rank 1: how often does the first candidate succeed?
        rank_rows = [r for r in ws_rows if r.get("attempt_order") is not None]
        ok_at_1 = sum(1 for r in rank_rows if r.get("attempt_order") == 1 and r.get("relevance_flag") == "ok")
        ok_with_rank = sum(1 for r in rank_rows if r.get("relevance_flag") == "ok")
        ds["ok_at_rank_1"] = ok_at_1
        ds["ok_total_with_rank"] = ok_with_rank
        ds["ok_rank_1_pct"] = (ok_at_1 / ok_with_rank * 100) if ok_with_rank else None

    return ds


# ============================================================
# Report Rendering
# ============================================================

def _status_icon(good: bool) -> str:
    return f"{C_GREEN}OK{C_RESET}" if good else f"{C_RED}!!{C_RESET}"


def _pct(num: int | float, denom: int | float) -> str:
    if denom == 0:
        return "N/A"
    return f"{num / denom * 100:.1f}%"


def render_report(log_m: dict, db_m: dict, date_str: str, verbose: bool = False, ds_m: dict | None = None) -> tuple[str, str]:
    """Render the health report. Returns (terminal_output, markdown_output)."""
    term_lines: list[str] = []
    md_lines: list[str] = []

    def section(title: str, num: int):
        term_lines.append(f"\n{C_BOLD}{C_CYAN}{'=' * 60}{C_RESET}")
        term_lines.append(f"{C_BOLD}{C_CYAN}{num}. {title}{C_RESET}")
        term_lines.append(f"{C_BOLD}{C_CYAN}{'=' * 60}{C_RESET}")
        md_lines.append(f"\n## {num}. {title}\n")

    def line(text: str, md_text: str | None = None):
        term_lines.append(text)
        md_lines.append(md_text or _strip_ansi(text))

    header = f"Pipeline Health Report — {date_str}"
    term_lines.append(f"\n{C_BOLD}{'#' * 64}{C_RESET}")
    term_lines.append(f"{C_BOLD}  {header}{C_RESET}")
    term_lines.append(f"{C_BOLD}{'#' * 64}{C_RESET}")
    md_lines.append(f"# {header}\n")

    if log_m.get("started"):
        line(f"  Started:   {log_m['started']}")
    if log_m.get("completed"):
        line(f"  Completed: {log_m['completed']}")

    # ── 1. Ingest ──
    section("Ingest (RSS)", 1)
    fetched = log_m.get("ingest_fetched", "?")
    inserted = log_m.get("ingest_inserted", "?")
    skipped = log_m.get("ingest_skipped", "?")
    line(f"  Fetched: {fetched}  |  Inserted: {inserted}  |  Skipped: {skipped}")
    if log_m.get("ingest_feeds"):
        line("  Feed breakdown:")
        for feed, (ins, tot) in log_m["ingest_feeds"].items():
            line(f"    {feed}: {ins}/{tot}")

    # ── 2. Preprocess ──
    section("Preprocess", 2)
    pp_ok = log_m.get("preprocess_succeeded", "?")
    pp_fail = log_m.get("preprocess_failed", "?")
    pp_total = log_m.get("preprocess_total", "?")
    db_pp = db_m.get("db_preprocessed", "?")
    line(f"  Log: {pp_ok} succeeded, {pp_fail} failed / {pp_total}")
    line(f"  DB:  {db_pp} items preprocessed today")

    # ── 3. Search ──
    section("Search (Google News)", 3)
    items = log_m.get("search_items", "?")
    with_art = log_m.get("search_with_articles", "?")
    no_art = log_m.get("search_no_articles", "?")
    total_art = log_m.get("search_total_articles", "?")
    blocked = log_m.get("search_blocked_domains", "?")
    line(f"  WSJ items processed: {items}")
    line(f"  With articles: {with_art}  |  No articles: {no_art}")
    line(f"  Total articles found: {total_art}")
    line(f"  Blocked domains loaded: {blocked}")
    if log_m.get("search_domains_tracked"):
        line(f"  Search hits: {log_m['search_domains_tracked']} domains tracked, {log_m.get('search_domains_updated', '?')} updated")

    # ── 4. Rank ──
    section("Rank (Embedding Filter)", 4)
    total_cand = log_m.get("rank_total", "?")
    filtered = log_m.get("rank_filtered", "?")
    if isinstance(total_cand, int) and isinstance(filtered, int) and total_cand > 0:
        rate = filtered / total_cand * 100
        line(f"  Candidates: {total_cand}  →  After filter: {filtered}  ({rate:.1f}% pass)")
    else:
        line(f"  Candidates: {total_cand}  →  After filter: {filtered}")
    if log_m.get("rank_score_min") is not None:
        line(f"  Scores: min={log_m['rank_score_min']:.3f}  max={log_m['rank_score_max']:.3f}  avg={log_m['rank_score_avg']:.3f}")

    # ── 5. Resolve ──
    section("Resolve", 5)
    res_ok = log_m.get("resolve_success", "?")
    res_fail = log_m.get("resolve_failed", "?")
    if isinstance(res_ok, int) and isinstance(res_fail, int):
        total = res_ok + res_fail
        line(f"  Resolved: {res_ok}/{total}  ({_pct(res_ok, total)} success)")
    else:
        line(f"  Resolved: {res_ok}  |  Failed: {res_fail}")
    if log_m.get("resolve_reasons"):
        line("  Reason codes:")
        for reason, count in log_m["resolve_reasons"].items():
            line(f"    {reason}: {count}")
    if verbose and log_m.get("resolve_domains"):
        line("  Top resolved domains:")
        for dom, cnt in log_m["resolve_domains"]:
            line(f"    {dom}: {cnt}")

    # ── 6. Crawl ──
    section("Crawl", 6)
    # Log-based
    if log_m.get("crawl_wsj_total"):
        line(f"  WSJ items: {log_m['crawl_wsj_total']} (success: {log_m.get('crawl_wsj_success', '?')}, failed: {log_m.get('crawl_wsj_failed', '?')})")
        line(f"  Total crawl attempts: {log_m.get('crawl_attempts', '?')}")
    if log_m.get("crawl_rel_avg") is not None:
        line(f"  Relevance: min={log_m['crawl_rel_min']:.3f}  max={log_m['crawl_rel_max']:.3f}  avg={log_m['crawl_rel_avg']:.3f}")
        line(f"  Low relevance: {log_m.get('crawl_low_relevance', '?')}")
    # DB-based
    if db_m.get("db_crawl_total"):
        total = db_m["db_crawl_total"]
        ok = db_m.get("db_crawl_ok", 0)
        low = db_m.get("db_crawl_low", 0)
        failed = db_m.get("db_crawl_failed", 0)
        line(f"  DB crawl results today: {total}")
        line(f"    success+ok: {ok} ({_pct(ok, total)})  |  success+low: {low} ({_pct(low, total)})  |  failed: {failed} ({_pct(failed, total)})")
    if db_m.get("db_crawl_errors"):
        line("  Top error reasons:")
        for err, cnt in list(db_m["db_crawl_errors"].items())[:7]:
            line(f"    {err}: {cnt}")
    if db_m.get("db_llm_count"):
        line(f"  LLM scores: avg={db_m['db_llm_avg']:.1f}  min={db_m['db_llm_min']}  max={db_m['db_llm_max']}  (n={db_m['db_llm_count']})")

    # ── 7. Domain Health ──
    section("Domain Health", 7)
    if db_m.get("db_crawl_domains"):
        line("  Top 10 domains (today's crawl volume):")
        for dom, cnt in list(db_m["db_crawl_domains"].items())[:10]:
            line(f"    {dom}: {cnt}")
    line(f"  Total blocked domains: {db_m.get('db_blocked_count', '?')}")
    if log_m.get("domains_auto_blocked"):
        line(f"  Newly auto-blocked today: {log_m['domains_auto_blocked']}")
    if verbose and log_m.get("blocked_details"):
        for bd in log_m["blocked_details"]:
            line(f"    {bd['domain']}: wilson={bd['wilson']:.3f}, {bd['rate_pct']}% ({bd['success']}/{bd['total']}), [{bd['reasons']}]")
    if db_m.get("db_high_perf_domains"):
        line("  High-performance domains (wilson>0.6, avg_llm>6.0):")
        for d in db_m["db_high_perf_domains"][:10]:
            line(f"    {d['domain']}: wilson={d.get('wilson_score', 0):.3f}, llm={d.get('avg_llm_score', 0):.1f}, ok={d.get('success_count', 0)}")

    # ── 8. Pipeline Funnel + Briefing ──
    section("Pipeline Funnel + Briefing", 8)
    line(f"  Total items:  {db_m.get('db_funnel_total', '?')}")
    line(f"  Searched:     {db_m.get('db_funnel_searched', '?')}")
    line(f"  Processed:    {db_m.get('db_funnel_processed', '?')}")
    line(f"  Briefed:      {db_m.get('db_funnel_briefed', '?')}")
    stuck = db_m.get("db_funnel_stuck", 0)
    if stuck > 0:
        line(f"  {C_YELLOW}Stuck (>24h): {stuck}{C_RESET}", f"  **Stuck (>24h): {stuck}**")
    # Embed & Thread
    if log_m.get("embed_count"):
        line(f"  Embedded: {log_m['embed_count']}  |  Thread matched: {log_m.get('thread_matched', '?')}, new: {log_m.get('thread_new', '?')}")
    # Briefing
    if log_m.get("briefing_total"):
        line(f"  Briefing: {log_m['briefing_curated']} curated, {log_m['briefing_standard']} standard, {log_m['briefing_title_only']} title-only / {log_m['briefing_total']} total")
    if log_m.get("tts_en_duration_min"):
        line(f"  EN TTS: {log_m['tts_en_duration_min']:.1f}min, {log_m['tts_en_size_kb']}KB")
    tts_ko = log_m.get("tts_ko_ok")
    if tts_ko is True:
        line(f"  KO TTS: {C_GREEN}OK{C_RESET}", "  KO TTS: OK")
    elif tts_ko is False:
        line(f"  KO TTS: {C_RED}FAILED{C_RESET}", "  KO TTS: **FAILED**")
    if log_m.get("cost_total") is not None:
        line(f"  Estimated cost: ${log_m['cost_total']:.4f}")

    # ── 9. Decision Support ──
    if ds_m and ds_m.get("total_rows"):
        section("Decision Support", 9)

        # A. Candidate Rank
        if ds_m.get("rank_buckets"):
            b = ds_m["rank_buckets"]
            line("  Candidate Rank (where was first ok found?):")
            line(f"    Rank 1-5: {b['1-5']}  |  6-10: {b['6-10']}  |  11-20: {b['11-20']}  |  21-30: {b['21-30']}  |  31-40: {b['31-40']}  |  No ok: {b['no_ok']}")
            max_r = ds_m.get("max_first_ok_rank", 0)
            headroom = ds_m.get("top_k_headroom", 0)
            if max_r > 0:
                line(f"    Max first-ok rank: {max_r}  (headroom: {headroom})")
            else:
                line("    Max first-ok rank: N/A (no ok found)")

        # B. LLM Threshold
        if ds_m.get("llm_dist"):
            d = ds_m["llm_dist"]
            line("  LLM Threshold:")
            line(f"    Score ≤5: {d['≤5']}  |  6: {d['6']}  |  7: {d['7']}  |  ≥8: {d['≥8']}")
            ok_t = ds_m.get("ok_total", 0)
            ok_s = ds_m.get("ok_same", 0)
            ok_d = ds_m.get("ok_diff", 0)
            low = ds_m.get("low_count", 0)
            line(f"    ok: {ok_t} (same={ok_s}, diff={ok_d})  |  low: {low}")

        # C. Briefing Coverage
        t_total = ds_m.get("coverage_today_total", 0)
        t_ok = ds_m.get("coverage_today_ok", 0)
        y_total = ds_m.get("coverage_yesterday_total", 0)
        y_ok = ds_m.get("coverage_yesterday_ok", 0)
        if t_total:
            t_pct = t_ok / t_total * 100
            line("  Briefing Coverage:")
            cov = f"    Today: {t_ok}/{t_total} with crawl ({t_pct:.1f}%)"
            if y_total:
                y_pct = y_ok / y_total * 100
                delta = t_pct - y_pct
                sign = "+" if delta >= 0 else ""
                cov += f"  |  Yesterday: {y_pct:.1f}%  |  Δ: {sign}{delta:.1f}%"
            line(cov)

        # D. Domain ROI
        if ds_m.get("domain_best") or ds_m.get("domain_worst"):
            line("  Domain ROI (today):")
            if ds_m.get("domain_best"):
                line(f"    {'Best:':<10} {'att':>5} {'ok':>5} {'ok%':>5} {'llm':>5} {'same%':>6}")
                for d in ds_m["domain_best"][:5]:
                    line(f"      {d['domain']:<28} {d['attempts']:>3}  {d['ok']:>4}  {d['ok_pct']:>4.0f}%  {d['avg_llm']:>4.1f}  {d['same_pct']:>5.0f}%")
            if ds_m.get("domain_worst"):
                line("    Worst (≥3 att, 0 ok):")
                for d in ds_m["domain_worst"][:5]:
                    line(f"      {d['domain']:<28} {d['attempts']:>3}         {d['avg_llm']:>4.1f} avg")

        # E. Score Effectiveness
        if ds_m.get("score_avg_ok") is not None or ds_m.get("ok_rank_1_pct") is not None:
            line("  Score Effectiveness:")
            avg_ok = ds_m.get("score_avg_ok")
            avg_low = ds_m.get("score_avg_low")
            if avg_ok is not None:
                parts_str = f"    Avg weighted_score: ok={avg_ok:.3f}"
                if avg_low is not None:
                    parts_str += f", low={avg_low:.3f}"
                line(parts_str)
            ok_at_1 = ds_m.get("ok_at_rank_1")
            ok_total_r = ds_m.get("ok_total_with_rank")
            rank_pct = ds_m.get("ok_rank_1_pct")
            if rank_pct is not None:
                line(f"    ok at rank 1: {ok_at_1}/{ok_total_r} ({rank_pct:.1f}%)")

    # ── Summary ──
    term_lines.append(f"\n{C_BOLD}{'=' * 60}{C_RESET}")
    term_lines.append(f"{C_BOLD}HEALTH SUMMARY{C_RESET}")
    term_lines.append(f"{C_BOLD}{'=' * 60}{C_RESET}")
    md_lines.append("\n## Health Summary\n")
    md_lines.append("| Metric | Value | Status |")
    md_lines.append("|--------|-------|--------|")

    checks = _compute_health_checks(log_m, db_m, ds_m)
    for name, value, is_good in checks:
        icon = _status_icon(is_good)
        line(f"  {icon}  {name}: {value}", f"| {name} | {value} | {'OK' if is_good else 'WARNING'} |")

    term_output = "\n".join(term_lines)
    md_output = "\n".join(md_lines) + "\n"
    return term_output, md_output


def _compute_health_checks(log_m: dict, db_m: dict, ds_m: dict | None = None) -> list[tuple[str, str, bool]]:
    """Compute health check results. Returns list of (name, value_str, is_good)."""
    checks: list[tuple[str, str, bool]] = []

    # Ingest
    inserted = log_m.get("ingest_inserted")
    if inserted is not None:
        checks.append(("Ingest", f"{inserted} inserted", inserted >= THRESHOLDS["ingest_min"]))

    # Preprocess
    failed = log_m.get("preprocess_failed")
    if failed is not None:
        checks.append(("Preprocess", f"{failed} failed", failed <= THRESHOLDS["preprocess_fail_max"]))

    # Filter rate
    total_cand = log_m.get("rank_total")
    filtered = log_m.get("rank_filtered")
    if total_cand and filtered and total_cand > 0:
        rate = filtered / total_cand * 100
        good = THRESHOLDS["filter_rate_low"] <= rate <= THRESHOLDS["filter_rate_high"]
        checks.append(("Search→Rank filter", f"{rate:.1f}% pass", good))

    # Resolve success rate
    res_ok = log_m.get("resolve_success")
    res_fail = log_m.get("resolve_failed")
    if res_ok is not None and res_fail is not None:
        total = res_ok + res_fail
        if total > 0:
            pct = res_ok / total * 100
            checks.append(("Resolve", f"{pct:.1f}% success", pct >= THRESHOLDS["resolve_success_min"]))

    # Crawl success+ok rate
    db_total = db_m.get("db_crawl_total", 0)
    db_ok = db_m.get("db_crawl_ok", 0)
    if db_total > 0:
        ok_pct = db_ok / db_total * 100
        checks.append(("Crawl success+ok", f"{ok_pct:.1f}%", ok_pct >= THRESHOLDS["crawl_ok_min"]))

    # Garbage rate
    db_failed = db_m.get("db_crawl_failed", 0)
    if db_total > 0:
        garbage_pct = db_failed / db_total * 100
        checks.append(("Crawl garbage/fail", f"{garbage_pct:.1f}%", garbage_pct < THRESHOLDS["garbage_max"]))

    # Briefing + TTS
    if log_m.get("briefing_total"):
        tts_ko = log_m.get("tts_ko_ok")
        tts_en = log_m.get("tts_en_duration_min") is not None
        if tts_ko is False:
            checks.append(("Briefing+TTS", "KO TTS failed", False))
        elif tts_en:
            checks.append(("Briefing+TTS", "Complete", True))
        else:
            checks.append(("Briefing+TTS", "Briefing done, TTS unknown", True))

    # Decision support checks
    if ds_m and ds_m.get("total_rows"):
        # Top-k headroom
        max_r = ds_m.get("max_first_ok_rank", 0)
        top_k = ds_m.get("top_k", 40)
        if max_r > 0:
            headroom = top_k - max_r
            checks.append(("Top-k headroom", f"{headroom} (max rank {max_r}/{top_k})", headroom >= 5))

        # Risky accepts (ok + different event)
        ok_diff = ds_m.get("ok_diff", 0)
        if ds_m.get("ok_total", 0) > 0:
            checks.append(("Risky accepts", f"{ok_diff} ok+diff_event", ok_diff <= 10))

        # Score rank-1 hit rate
        rank1_pct = ds_m.get("ok_rank_1_pct")
        if rank1_pct is not None:
            checks.append(("Score rank-1 hit", f"{rank1_pct:.0f}%", rank1_pct >= 50))

    return checks


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return re.sub(r"\033\[[0-9;]*m", "", text)


# ============================================================
# Output: Markdown File
# ============================================================

def save_markdown(md_content: str, date_str: str) -> Path:
    """Save markdown report to logs/health/health-YYYY-MM-DD.md."""
    HEALTH_DIR.mkdir(parents=True, exist_ok=True)
    path = HEALTH_DIR / f"health-{date_str}.md"
    path.write_text(f"<!-- Generated: {datetime.now(timezone.utc).isoformat()} -->\n{md_content}", encoding="utf-8")
    return path



# ============================================================
# Output: Email
# ============================================================

def send_email(
    md_content: str,
    date_str: str,
    checks: list[tuple[str, str, bool]],
    log_m: dict,
    db_m: dict,
    ds_m: dict | None = None,
) -> bool:
    """Send health report via Gmail SMTP. Returns True on success."""
    gmail_addr = os.getenv("GMAIL_ADDRESS")
    gmail_pass = os.getenv("GMAIL_APP_PASSWORD")
    recipient = os.getenv("GMAIL_RECIPIENT", gmail_addr)
    if not gmail_addr or not gmail_pass:
        print("  Email skipped: GMAIL_ADDRESS or GMAIL_APP_PASSWORD not set")
        return False

    warnings = sum(1 for _, _, ok in checks if not ok)
    if warnings:
        subject = f"[WARN] Pipeline Health — {date_str} ({warnings} warning{'s' if warnings > 1 else ''})"
    else:
        subject = f"[OK] Pipeline Health — {date_str}"

    html_content = render_html(log_m, db_m, date_str, checks, ds_m)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = gmail_addr
    msg["To"] = recipient

    msg.attach(MIMEText(md_content, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(gmail_addr, gmail_pass)
            server.sendmail(gmail_addr, recipient, msg.as_string())
        return True
    except Exception as e:
        print(f"  Email failed: {e}")
        return False


# ============================================================
# Output: HTML Email
# ============================================================

# Styles
_S = {
    "body": (
        "margin:0;padding:0;background:#0f172a;color:#e2e8f0;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
        "font-size:14px;line-height:1.6"
    ),
    "wrap": "max-width:680px;margin:0 auto;padding:24px 16px",
    "header": (
        "text-align:center;padding:32px 24px;border-radius:12px 12px 0 0;"
        "background:linear-gradient(135deg,#1e293b 0%,#0f172a 100%);"
        "border-bottom:2px solid #334155"
    ),
    "h1": "margin:0;font-size:22px;font-weight:700;color:#f8fafc;letter-spacing:-0.3px",
    "subtitle": "margin:8px 0 0;font-size:13px;color:#94a3b8",
    "card": (
        "background:#1e293b;border-radius:10px;padding:20px 24px;"
        "margin-top:16px;border:1px solid #334155"
    ),
    "card_title": "margin:0 0 14px;font-size:15px;font-weight:600;color:#38bdf8",
    "kv_row": "display:flex;justify-content:space-between;padding:6px 0;border-bottom:1px solid #1e293b",
    "kv_label": "color:#94a3b8;font-size:13px",
    "kv_value": "color:#f1f5f9;font-size:13px;font-weight:500;font-variant-numeric:tabular-nums",
    "table": "width:100%;border-collapse:collapse;font-size:13px",
    "th": (
        "text-align:left;padding:8px 12px;color:#94a3b8;font-weight:500;"
        "border-bottom:1px solid #334155;font-size:11px;text-transform:uppercase;letter-spacing:0.5px"
    ),
    "td": "padding:8px 12px;border-bottom:1px solid #1e293b4d;color:#e2e8f0",
    "td_num": "padding:8px 12px;border-bottom:1px solid #1e293b4d;color:#e2e8f0;text-align:right;font-variant-numeric:tabular-nums",
    "badge_ok": (
        "display:inline-block;padding:2px 10px;border-radius:99px;font-size:11px;"
        "font-weight:600;background:#065f46;color:#6ee7b7"
    ),
    "badge_warn": (
        "display:inline-block;padding:2px 10px;border-radius:99px;font-size:11px;"
        "font-weight:600;background:#78350f;color:#fbbf24"
    ),
    "badge_fail": (
        "display:inline-block;padding:2px 10px;border-radius:99px;font-size:11px;"
        "font-weight:600;background:#7f1d1d;color:#fca5a5"
    ),
    "bar_bg": "height:6px;border-radius:3px;background:#334155;margin-top:4px",
    "footer": "text-align:center;padding:20px;font-size:11px;color:#64748b",
}


def _badge(ok: bool, label: str) -> str:
    s = _S["badge_ok"] if ok else _S["badge_warn"]
    return f"<span style='{s}'>{_esc(label)}</span>"


def _kv(label: str, value: str) -> str:
    return (
        f"<div style='{_S['kv_row']}'>"
        f"<span style='{_S['kv_label']}'>{_esc(label)}</span>"
        f"<span style='{_S['kv_value']}'>{value}</span>"
        f"</div>"
    )


def _bar(pct: float, color: str = "#38bdf8") -> str:
    """Horizontal progress bar."""
    w = max(0, min(100, pct))
    return (
        f"<div style='{_S['bar_bg']}'>"
        f"<div style='height:6px;border-radius:3px;width:{w:.0f}%;background:{color}'></div>"
        f"</div>"
    )


def _card(title: str, body: str) -> str:
    return (
        f"<div style='{_S['card']}'>"
        f"<h3 style='{_S['card_title']}'>{_esc(title)}</h3>"
        f"{body}"
        f"</div>"
    )


def render_html(log_m: dict, db_m: dict, date_str: str, checks: list[tuple[str, str, bool]], ds_m: dict | None = None) -> str:
    """Render a styled HTML email from metrics data."""
    parts: list[str] = []

    # ── Header ──
    started = log_m.get("started", "")
    completed = log_m.get("completed", "")
    duration = ""
    if started and completed:
        # Extract just time parts for display
        s_time = started.split()[-3] if len(started.split()) >= 3 else started
        c_time = completed.split()[-3] if len(completed.split()) >= 3 else completed
        duration = f"{s_time} — {c_time}"

    warnings = sum(1 for _, _, ok in checks if not ok)
    status_html = _badge(warnings == 0, "ALL CLEAR") if warnings == 0 else (
        f"<span style='{_S['badge_warn']}'>{warnings} WARNING{'S' if warnings > 1 else ''}</span>"
    )

    parts.append(
        f"<div style='{_S['header']}'>"
        f"<h1 style='{_S['h1']}'>Pipeline Health Report</h1>"
        f"<p style='{_S['subtitle']}'>{date_str} &nbsp;&middot;&nbsp; {duration}</p>"
        f"<div style='margin-top:12px'>{status_html}</div>"
        f"</div>"
    )

    # ── Health Summary (top) ──
    summary_rows = ""
    for name, value, is_good in checks:
        icon = f"<span style='{_S['badge_ok']}'>OK</span>" if is_good else f"<span style='{_S['badge_fail']}'>WARN</span>"
        bg = "" if is_good else "background:#7f1d1d20;"
        summary_rows += (
            f"<tr style='{bg}'>"
            f"<td style='{_S['td']}'>{_esc(name)}</td>"
            f"<td style='{_S['td_num']}'>{_esc(value)}</td>"
            f"<td style='{_S['td']};text-align:center'>{icon}</td>"
            f"</tr>"
        )
    parts.append(_card("Health Summary", (
        f"<table style='{_S['table']}'>"
        f"<tr><th style='{_S['th']}'>Metric</th><th style='{_S['th']};text-align:right'>Value</th><th style='{_S['th']};text-align:center'>Status</th></tr>"
        f"{summary_rows}</table>"
    )))

    # ── 1. Ingest ──
    inserted = log_m.get("ingest_inserted", 0)
    fetched = log_m.get("ingest_fetched", 0)
    skipped = log_m.get("ingest_skipped", 0)
    body = _kv("Fetched", str(fetched))
    body += _kv("Inserted", f"<strong style='color:#34d399'>{inserted}</strong>")
    body += _kv("Skipped (dups)", str(skipped))
    if log_m.get("ingest_feeds"):
        body += "<div style='margin-top:12px;font-size:12px;color:#64748b'>Feed breakdown</div>"
        for feed, (ins, tot) in log_m["ingest_feeds"].items():
            pct = ins / tot * 100 if tot else 0
            body += (
                f"<div style='display:flex;justify-content:space-between;padding:3px 0;font-size:12px'>"
                f"<span style='color:#94a3b8'>{_esc(feed)}</span>"
                f"<span style='color:#e2e8f0'>{ins}/{tot}</span>"
                f"</div>"
                f"{_bar(pct, '#38bdf8')}"
            )
    parts.append(_card("1. Ingest (RSS)", body))

    # ── 2. Preprocess ──
    pp_ok = log_m.get("preprocess_succeeded", "?")
    pp_fail = log_m.get("preprocess_failed", "?")
    db_pp = db_m.get("db_preprocessed", "?")
    body = _kv("Succeeded", str(pp_ok))
    fail_color = "#fca5a5" if pp_fail and pp_fail != "?" and pp_fail > 0 else "#34d399"
    body += _kv("Failed", f"<span style='color:{fail_color}'>{pp_fail}</span>")
    body += _kv("DB confirmed", str(db_pp))
    parts.append(_card("2. Preprocess", body))

    # ── 3. Search ──
    body = _kv("WSJ items processed", str(log_m.get("search_items", "?")))
    body += _kv("With articles", str(log_m.get("search_with_articles", "?")))
    body += _kv("No articles", str(log_m.get("search_no_articles", "?")))
    total_art = log_m.get("search_total_articles", "?")
    body += _kv("Total articles found", f"<strong>{total_art:,}</strong>" if isinstance(total_art, int) else str(total_art))
    body += _kv("Blocked domains loaded", str(log_m.get("search_blocked_domains", "?")))
    if log_m.get("search_domains_tracked"):
        body += _kv("Domains tracked", f"{log_m['search_domains_tracked']:,}")
    parts.append(_card("3. Search (Google News)", body))

    # ── 4. Rank ──
    total_cand = log_m.get("rank_total")
    filtered = log_m.get("rank_filtered")
    body = ""
    if isinstance(total_cand, int) and isinstance(filtered, int) and total_cand > 0:
        rate = filtered / total_cand * 100
        body += _kv("Candidates", f"{total_cand:,}")
        body += _kv("After filter", f"<strong>{filtered:,}</strong>")
        body += _kv("Pass rate", f"{rate:.1f}%")
        body += _bar(rate, "#a78bfa")
    if log_m.get("rank_score_avg") is not None:
        body += "<div style='margin-top:10px'></div>"
        body += _kv("Score min", f"{log_m['rank_score_min']:.3f}")
        body += _kv("Score max", f"{log_m['rank_score_max']:.3f}")
        body += _kv("Score avg", f"{log_m['rank_score_avg']:.3f}")
    parts.append(_card("4. Rank (Embedding Filter)", body))

    # ── 5. Resolve ──
    res_ok = log_m.get("resolve_success")
    res_fail = log_m.get("resolve_failed")
    body = ""
    if isinstance(res_ok, int) and isinstance(res_fail, int):
        total = res_ok + res_fail
        pct = res_ok / total * 100 if total else 0
        body += _kv("Resolved", f"{res_ok} / {total}")
        body += _kv("Success rate", f"<strong style='color:#34d399'>{pct:.1f}%</strong>")
        body += _bar(pct, "#34d399")
    if log_m.get("resolve_reasons"):
        body += "<div style='margin-top:10px'></div>"
        for reason, count in log_m["resolve_reasons"].items():
            body += _kv(reason, str(count))
    parts.append(_card("5. Resolve", body))

    # ── 6. Crawl ──
    body = ""
    if log_m.get("crawl_wsj_total"):
        body += _kv("WSJ items", f"{log_m['crawl_wsj_success']} / {log_m['crawl_wsj_total']} success")
        body += _kv("Total attempts", str(log_m.get("crawl_attempts", "?")))
    if db_m.get("db_crawl_total"):
        total = db_m["db_crawl_total"]
        ok = db_m.get("db_crawl_ok", 0)
        low = db_m.get("db_crawl_low", 0)
        failed = db_m.get("db_crawl_failed", 0)
        body += "<div style='margin-top:10px'></div>"
        ok_pct = ok / total * 100 if total else 0
        low_pct = low / total * 100 if total else 0
        fail_pct = failed / total * 100 if total else 0
        body += _kv("Success + OK", f"<span style='color:#34d399'>{ok} ({ok_pct:.0f}%)</span>")
        body += _kv("Success + Low", f"<span style='color:#fbbf24'>{low} ({low_pct:.0f}%)</span>")
        body += _kv("Failed", f"<span style='color:#fca5a5'>{failed} ({fail_pct:.0f}%)</span>")
        # Stacked bar
        body += (
            f"<div style='display:flex;height:8px;border-radius:4px;overflow:hidden;margin-top:6px;background:#334155'>"
            f"<div style='width:{ok_pct:.0f}%;background:#34d399'></div>"
            f"<div style='width:{low_pct:.0f}%;background:#fbbf24'></div>"
            f"<div style='width:{fail_pct:.0f}%;background:#ef4444'></div>"
            f"</div>"
        )
    if log_m.get("crawl_rel_avg") is not None:
        body += "<div style='margin-top:10px'></div>"
        body += _kv("Relevance avg", f"{log_m['crawl_rel_avg']:.3f}")
        body += _kv("Relevance range", f"{log_m['crawl_rel_min']:.3f} — {log_m['crawl_rel_max']:.3f}")
    if db_m.get("db_llm_count"):
        body += _kv("LLM score avg", f"{db_m['db_llm_avg']:.1f} (n={db_m['db_llm_count']})")
    if db_m.get("db_crawl_errors"):
        body += "<div style='margin-top:10px;font-size:12px;color:#64748b'>Top errors</div>"
        for err, cnt in list(db_m["db_crawl_errors"].items())[:5]:
            body += _kv(err, str(cnt))
    parts.append(_card("6. Crawl", body))

    # ── 7. Domain Health ──
    body = ""
    body += _kv("Total blocked", str(db_m.get("db_blocked_count", "?")))
    if log_m.get("domains_auto_blocked"):
        body += _kv("Newly blocked today", f"<span style='color:#fbbf24'>{log_m['domains_auto_blocked']}</span>")
    if db_m.get("db_crawl_domains"):
        body += "<div style='margin-top:12px;font-size:12px;color:#64748b'>Top domains today</div>"
        dom_rows = ""
        for dom, cnt in list(db_m["db_crawl_domains"].items())[:8]:
            dom_rows += f"<tr><td style='{_S['td']};font-size:12px'>{_esc(dom)}</td><td style='{_S['td_num']};font-size:12px'>{cnt}</td></tr>"
        body += f"<table style='{_S['table']}'>{dom_rows}</table>"
    if db_m.get("db_high_perf_domains"):
        body += "<div style='margin-top:12px;font-size:12px;color:#64748b'>High-performance domains</div>"
        hp_rows = ""
        for d in db_m["db_high_perf_domains"][:8]:
            wilson = d.get("wilson_score", 0)
            llm = d.get("avg_llm_score", 0)
            ok_n = d.get("success_count", 0)
            hp_rows += (
                f"<tr><td style='{_S['td']};font-size:12px'>{_esc(d['domain'])}</td>"
                f"<td style='{_S['td_num']};font-size:12px'>{wilson:.2f}</td>"
                f"<td style='{_S['td_num']};font-size:12px'>{llm:.1f}</td>"
                f"<td style='{_S['td_num']};font-size:12px'>{ok_n}</td></tr>"
            )
        body += (
            f"<table style='{_S['table']}'>"
            f"<tr><th style='{_S['th']}'>Domain</th><th style='{_S['th']};text-align:right'>Wilson</th>"
            f"<th style='{_S['th']};text-align:right'>LLM</th><th style='{_S['th']};text-align:right'>OK</th></tr>"
            f"{hp_rows}</table>"
        )
    parts.append(_card("7. Domain Health", body))

    # ── 8. Funnel + Briefing ──
    body = ""
    funnel_total = db_m.get("db_funnel_total", 0)
    funnel_data = [
        ("Total", funnel_total, "#64748b"),
        ("Searched", db_m.get("db_funnel_searched", 0), "#38bdf8"),
        ("Processed", db_m.get("db_funnel_processed", 0), "#a78bfa"),
        ("Briefed", db_m.get("db_funnel_briefed", 0), "#34d399"),
    ]
    for label, val, color in funnel_data:
        pct = val / funnel_total * 100 if funnel_total else 0
        body += (
            f"<div style='display:flex;justify-content:space-between;padding:4px 0;font-size:13px'>"
            f"<span style='color:#94a3b8'>{label}</span>"
            f"<span style='color:{color};font-weight:600;font-variant-numeric:tabular-nums'>{val:,}</span>"
            f"</div>"
            f"{_bar(pct, color)}"
        )
    stuck = db_m.get("db_funnel_stuck", 0)
    if stuck > 0:
        body += f"<div style='margin-top:8px'>{_kv('Stuck (>24h)', f'<span style=\"color:#fbbf24\">{stuck}</span>')}</div>"

    if log_m.get("embed_count") or log_m.get("briefing_total"):
        body += "<div style='margin-top:14px;border-top:1px solid #334155;padding-top:12px'></div>"
    if log_m.get("embed_count"):
        body += _kv("Embedded", str(log_m["embed_count"]))
        body += _kv("Threads", f"{log_m.get('thread_matched', '?')} matched, {log_m.get('thread_new', '?')} new")
    if log_m.get("briefing_total"):
        body += _kv("Briefing", f"{log_m['briefing_curated']} curated, {log_m['briefing_standard']} standard, {log_m['briefing_title_only']} title-only")
    if log_m.get("tts_en_duration_min") is not None:
        body += _kv("EN TTS", f"{log_m['tts_en_duration_min']:.1f} min, {log_m['tts_en_size_kb']:,} KB")
    tts_ko = log_m.get("tts_ko_ok")
    if tts_ko is True:
        body += _kv("KO TTS", "<span style='color:#34d399'>OK</span>")
    elif tts_ko is False:
        body += _kv("KO TTS", f"<span style='{_S['badge_fail']}'>FAILED</span>")
    if log_m.get("cost_total") is not None:
        body += _kv("Estimated cost", f"${log_m['cost_total']:.4f}")
    parts.append(_card("8. Pipeline Funnel + Briefing", body))

    # ── 9. Decision Support ──
    if ds_m and ds_m.get("total_rows"):
        body = ""

        # A. Candidate Rank — stacked bar
        if ds_m.get("rank_buckets"):
            b = ds_m["rank_buckets"]
            total_b = sum(b.values()) or 1
            body += "<div style='font-size:12px;color:#64748b;margin-bottom:6px'>Candidate Rank (first ok found at)</div>"
            colors = {"1-5": "#34d399", "6-10": "#38bdf8", "11-20": "#a78bfa", "21-30": "#fbbf24", "31-40": "#f97316", "no_ok": "#ef4444"}
            bar_parts = ""
            for bucket_name in ["1-5", "6-10", "11-20", "21-30", "31-40", "no_ok"]:
                pct = b[bucket_name] / total_b * 100
                if pct > 0:
                    label = bucket_name if bucket_name != "no_ok" else "none"
                    bar_parts += (
                        f"<div style='width:{pct:.0f}%;background:{colors[bucket_name]};text-align:center;"
                        f"font-size:10px;color:#0f172a;font-weight:600;min-width:20px'>"
                        f"{b[bucket_name]}"
                        f"</div>"
                    )
            body += (
                f"<div style='display:flex;height:22px;border-radius:4px;overflow:hidden;background:#334155'>"
                f"{bar_parts}</div>"
            )
            # Legend
            legend = " &nbsp;".join(
                f"<span style='color:{colors[k]};font-size:11px'>{k}: {b[k]}</span>"
                for k in ["1-5", "6-10", "11-20", "21-30", "31-40", "no_ok"]
            )
            body += f"<div style='margin-top:4px'>{legend}</div>"
            max_r = ds_m.get("max_first_ok_rank", 0)
            headroom = ds_m.get("top_k_headroom", 0)
            if max_r > 0:
                hr_color = "#34d399" if headroom >= 5 else "#fbbf24"
                body += _kv("Max first-ok rank", f"{max_r}")
                body += _kv("Headroom", f"<span style='color:{hr_color}'>{headroom}</span>")

        # B. LLM Threshold
        if ds_m.get("llm_dist"):
            body += "<div style='margin-top:14px;border-top:1px solid #334155;padding-top:12px'></div>"
            body += "<div style='font-size:12px;color:#64748b;margin-bottom:6px'>LLM Threshold</div>"
            d = ds_m["llm_dist"]
            for label, count in d.items():
                body += _kv(f"Score {label}", str(count))
            ok_s = ds_m.get("ok_same", 0)
            ok_d = ds_m.get("ok_diff", 0)
            low = ds_m.get("low_count", 0)
            body += "<div style='margin-top:6px'></div>"
            body += _kv("Accepted (same event)", f"<span style='color:#34d399'>{ok_s}</span>")
            diff_color = "#fbbf24" if ok_d > 10 else "#38bdf8"
            body += _kv("Accepted (diff event)", f"<span style='color:{diff_color}'>{ok_d}</span>")
            body += _kv("Rejected (low)", str(low))

        # C. Briefing Coverage
        t_total = ds_m.get("coverage_today_total", 0)
        t_ok = ds_m.get("coverage_today_ok", 0)
        if t_total:
            body += "<div style='margin-top:14px;border-top:1px solid #334155;padding-top:12px'></div>"
            body += "<div style='font-size:12px;color:#64748b;margin-bottom:6px'>Briefing Coverage</div>"
            t_pct = t_ok / t_total * 100
            cov_color = "#34d399" if t_pct >= 90 else "#fbbf24"
            body += _kv("Today", f"<span style='color:{cov_color}'>{t_ok}/{t_total} ({t_pct:.1f}%)</span>")
            body += _bar(t_pct, cov_color)
            y_total = ds_m.get("coverage_yesterday_total", 0)
            y_ok = ds_m.get("coverage_yesterday_ok", 0)
            if y_total:
                y_pct = y_ok / y_total * 100
                delta = t_pct - y_pct
                sign = "+" if delta >= 0 else ""
                delta_color = "#34d399" if delta >= 0 else "#fca5a5"
                body += _kv("Yesterday", f"{y_pct:.1f}%")
                body += _kv("Delta", f"<span style='color:{delta_color}'>{sign}{delta:.1f}%</span>")

        # D. Domain ROI
        if ds_m.get("domain_best"):
            body += "<div style='margin-top:14px;border-top:1px solid #334155;padding-top:12px'></div>"
            body += "<div style='font-size:12px;color:#64748b;margin-bottom:6px'>Domain ROI — Best</div>"
            dom_rows = ""
            for d in ds_m["domain_best"][:5]:
                dom_rows += (
                    f"<tr><td style='{_S['td']};font-size:12px'>{_esc(d['domain'])}</td>"
                    f"<td style='{_S['td_num']};font-size:12px'>{d['attempts']}</td>"
                    f"<td style='{_S['td_num']};font-size:12px'>{d['ok']}</td>"
                    f"<td style='{_S['td_num']};font-size:12px'>{d['ok_pct']:.0f}%</td>"
                    f"<td style='{_S['td_num']};font-size:12px'>{d['avg_llm']:.1f}</td>"
                    f"<td style='{_S['td_num']};font-size:12px'>{d['same_pct']:.0f}%</td></tr>"
                )
            body += (
                f"<table style='{_S['table']}'>"
                f"<tr><th style='{_S['th']}'>Domain</th>"
                f"<th style='{_S['th']};text-align:right'>Att</th>"
                f"<th style='{_S['th']};text-align:right'>OK</th>"
                f"<th style='{_S['th']};text-align:right'>OK%</th>"
                f"<th style='{_S['th']};text-align:right'>LLM</th>"
                f"<th style='{_S['th']};text-align:right'>Same%</th></tr>"
                f"{dom_rows}</table>"
            )
        if ds_m.get("domain_worst"):
            body += "<div style='margin-top:10px;font-size:12px;color:#64748b'>Worst (≥3 att, 0 ok)</div>"
            worst_rows = ""
            for d in ds_m["domain_worst"][:5]:
                worst_rows += (
                    f"<tr><td style='{_S['td']};font-size:12px'>{_esc(d['domain'])}</td>"
                    f"<td style='{_S['td_num']};font-size:12px'>{d['attempts']}</td>"
                    f"<td style='{_S['td_num']};font-size:12px'>{d['avg_llm']:.1f}</td></tr>"
                )
            body += (
                f"<table style='{_S['table']}'>"
                f"<tr><th style='{_S['th']}'>Domain</th>"
                f"<th style='{_S['th']};text-align:right'>Att</th>"
                f"<th style='{_S['th']};text-align:right'>Avg LLM</th></tr>"
                f"{worst_rows}</table>"
            )

        # E. Score Effectiveness
        if ds_m.get("score_avg_ok") is not None or ds_m.get("ok_rank_1_pct") is not None:
            body += "<div style='margin-top:14px;border-top:1px solid #334155;padding-top:12px'></div>"
            body += "<div style='font-size:12px;color:#64748b;margin-bottom:6px'>Score Effectiveness</div>"
            avg_ok = ds_m.get("score_avg_ok")
            avg_low = ds_m.get("score_avg_low")
            if avg_ok is not None:
                body += _kv("Avg w_score (ok)", f"{avg_ok:.3f}")
            if avg_low is not None:
                body += _kv("Avg w_score (low)", f"{avg_low:.3f}")
            rank_pct = ds_m.get("ok_rank_1_pct")
            if rank_pct is not None:
                ok_at_1 = ds_m.get("ok_at_rank_1", 0)
                ok_total_r = ds_m.get("ok_total_with_rank", 0)
                r1_color = "#34d399" if rank_pct >= 50 else "#fbbf24"
                body += _kv("ok at rank 1", f"<span style='color:{r1_color}'>{ok_at_1}/{ok_total_r} ({rank_pct:.1f}%)</span>")

        parts.append(_card("9. Decision Support", body))

    # ── Footer ──
    parts.append(
        f"<div style='{_S['footer']}'>"
        f"Generated by pipeline_health.py &middot; {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        f"</div>"
    )

    return (
        f"<html><body style='{_S['body']}'>"
        f"<div style='{_S['wrap']}'>{''.join(parts)}</div>"
        f"</body></html>"
    )


def _esc(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ============================================================
# Main
# ============================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Pipeline Health · Daily Report")
    parser.add_argument("--date", type=str, default=None, help="Date to report on (YYYY-MM-DD, default: today)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed breakdowns")
    parser.add_argument("--no-email", action="store_true", help="Skip email sending")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    # Validate date format
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"Error: Invalid date format '{date_str}'. Use YYYY-MM-DD.")
        sys.exit(1)

    print(f"\nGenerating health report for {date_str}...")

    # 1. Parse log
    log_path = LOG_DIR / f"pipeline-{date_str}.log"
    log_m = parse_pipeline_log(str(log_path))
    if not log_m:
        print(f"  Warning: No log found at {log_path}")
    else:
        print(f"  Log parsed: {log_path}")

    # 2. Query DB
    supabase = require_supabase_client()
    print("  Querying database...")
    db_m = fetch_db_metrics(supabase, date_str)
    print(f"  DB metrics fetched ({db_m.get('db_crawl_total', 0)} crawl results)")

    # 3. Decision support metrics
    print("  Fetching decision metrics...")
    ds_m = fetch_decision_metrics(supabase, date_str)
    print(f"  Decision metrics fetched ({ds_m.get('total_rows', 0)} rows)")

    # 4. Render
    term_output, md_output = render_report(log_m, db_m, date_str, verbose=args.verbose, ds_m=ds_m)
    print(term_output)

    # 5. Save markdown
    md_path = save_markdown(md_output, date_str)
    print(f"\nMarkdown saved: {md_path}")

    # 6. Email
    if not args.no_email:
        checks = _compute_health_checks(log_m, db_m, ds_m)
        print("Sending email...")
        if send_email(md_output, date_str, checks, log_m, db_m, ds_m):
            print("  Email sent successfully")
    else:
        print("Email skipped (--no-email)")


if __name__ == "__main__":
    main()
