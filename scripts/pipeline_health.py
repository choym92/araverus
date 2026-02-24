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

    # Cost
    m = re.search(r"Estimated total:\s+\$([\d.]+)", text)
    if m:
        metrics["cost_total"] = float(m.group(1))

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
# Report Rendering
# ============================================================

def _status_icon(good: bool) -> str:
    return f"{C_GREEN}OK{C_RESET}" if good else f"{C_RED}!!{C_RESET}"


def _pct(num: int | float, denom: int | float) -> str:
    if denom == 0:
        return "N/A"
    return f"{num / denom * 100:.1f}%"


def render_report(log_m: dict, db_m: dict, date_str: str, verbose: bool = False) -> tuple[str, str]:
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

    # ── Summary ──
    term_lines.append(f"\n{C_BOLD}{'=' * 60}{C_RESET}")
    term_lines.append(f"{C_BOLD}HEALTH SUMMARY{C_RESET}")
    term_lines.append(f"{C_BOLD}{'=' * 60}{C_RESET}")
    md_lines.append("\n## Health Summary\n")
    md_lines.append("| Metric | Value | Status |")
    md_lines.append("|--------|-------|--------|")

    checks = _compute_health_checks(log_m, db_m)
    for name, value, is_good in checks:
        icon = _status_icon(is_good)
        line(f"  {icon}  {name}: {value}", f"| {name} | {value} | {'OK' if is_good else 'WARNING'} |")

    term_output = "\n".join(term_lines)
    md_output = "\n".join(md_lines) + "\n"
    return term_output, md_output


def _compute_health_checks(log_m: dict, db_m: dict) -> list[tuple[str, str, bool]]:
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

    html_content = render_html(log_m, db_m, date_str, checks)

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


def render_html(log_m: dict, db_m: dict, date_str: str, checks: list[tuple[str, str, bool]]) -> str:
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

    # 3. Render
    term_output, md_output = render_report(log_m, db_m, date_str, verbose=args.verbose)
    print(term_output)

    # 4. Save markdown
    md_path = save_markdown(md_output, date_str)
    print(f"\nMarkdown saved: {md_path}")

    # 5. Email
    if not args.no_email:
        checks = _compute_health_checks(log_m, db_m)
        print("Sending email...")
        if send_email(md_output, date_str, checks, log_m, db_m):
            print("  Email sent successfully")
    else:
        print("Email skipped (--no-email)")


if __name__ == "__main__":
    main()
