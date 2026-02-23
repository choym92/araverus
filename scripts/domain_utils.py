#!/usr/bin/env python3
"""
Shared Utility · Domain & Lifecycle — Domain status management and pipeline lifecycle operations.

Used across multiple phases:
- Phase 2: --mark-searched (after Google News search)
- Phase 4: --mark-processed-from-db, --update-domain-status

Library exports (imported by other scripts):
- get_supabase_client() / require_supabase_client() — DB client
- load_blocked_domains() / is_blocked_domain() — domain filtering
- wilson_lower_bound() — auto-blocking score

All blocked domains are managed in the wsj_domain_status table.
No hardcoded domain lists — add/remove via DB.

Usage:
    python scripts/domain_utils.py --mark-searched FILE
    python scripts/domain_utils.py --mark-processed FILE
    python scripts/domain_utils.py --mark-processed-from-db
    python scripts/domain_utils.py --update-domain-status
    python scripts/domain_utils.py --retry-low-relevance
    python scripts/domain_utils.py --stats
    python scripts/domain_utils.py --seed-blocked-from-json
"""
import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# ============================================================
# Supabase Client
# ============================================================

def get_supabase_client():
    """Get Supabase client if credentials are available. Returns None if missing."""
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env.local')

    supabase_url = os.getenv("NEXT_PUBLIC_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        return None

    from supabase import create_client
    return create_client(supabase_url, supabase_key)


def require_supabase_client():
    """Get Supabase client, exit if credentials missing. Use in CLI commands."""
    client = get_supabase_client()
    if not client:
        print("Error: Missing Supabase credentials. Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        sys.exit(1)
    return client


# ============================================================
# Domain Queries
# ============================================================

def load_blocked_domains(supabase=None) -> set[str]:
    """
    Load blocked domains from wsj_domain_status table.

    Args:
        supabase: Supabase client (optional, will create if None)

    Returns:
        Set of blocked domain strings
    """
    blocked = set()

    if supabase is None:
        supabase = get_supabase_client()

    if supabase:
        try:
            response = supabase.table('wsj_domain_status') \
                .select('domain') \
                .eq('status', 'blocked') \
                .execute()

            if response.data:
                blocked = {row['domain'] for row in response.data if row.get('domain')}
        except Exception as e:
            print(f"  Warning: Could not load blocked domains from DB: {e}")

    return blocked


def is_blocked_domain(domain: str, blocked_domains: set[str]) -> bool:
    """
    Check if domain is in blocked list.

    Args:
        domain: Domain to check
        blocked_domains: Set of blocked domains

    Returns:
        True if domain is blocked
    """
    if not domain or not blocked_domains:
        return False

    domain_lower = domain.lower()
    for blocked in blocked_domains:
        blocked_lower = blocked.lower()
        if blocked_lower in domain_lower or domain_lower in blocked_lower:
            return True

    return False


# ============================================================
# Error Normalization & Wilson Score
# ============================================================

# Crawl error → natural language key mapping (single source of truth)
# Used by both crawl_ranked.py (at crawl time) and cmd_update_domain_status (aggregation)
CRAWL_ERROR_MAP = {
    "TOO_SHORT": "content too short",
    "LINK_HEAVY": "too many links",
    "MENU_HEAVY": "navigation/menu content",
    "BOILERPLATE_HEAVY": "boilerplate content",
    "TOO_LONG": "content too long",
    "Content too short": "content too short",
    "paywall": "paywall",
    "css_js_code": "css/js instead of content",
    "copyright_unavailable": "copyright or unavailable",
    "repeated_words": "repeated content",
    "empty_content": "empty content",
    "Domain blocked (DB)": "domain blocked",
    "low_relevance": "low relevance",
    "Could not resolve Google News URL": "http error",
}

# Only infrastructure failures count toward auto-blocking.
# Parser failures, content mismatches, and circular "domain blocked"
# errors are excluded — they're not the domain's fault.
BLOCKABLE_FAILURES = {"http error", "timeout or network error"}


def normalize_crawl_error(raw_error: str | None) -> str:
    """Normalize crawl_error to natural language key for fail_counts tracking."""
    if not raw_error:
        return "content too short"
    if raw_error in CRAWL_ERROR_MAP:
        return CRAWL_ERROR_MAP[raw_error]
    # Already a natural language key (new format)
    if raw_error in BLOCKABLE_FAILURES:
        return raw_error
    low = raw_error.lower()
    if low.startswith("status "):
        return "http error"
    if any(code in low for code in ("403", "404", "429", "301", "http")):
        return "http error"
    if "social" in low or "twitter" in low or "facebook" in low:
        return "social media"
    if "timeout" in low or "timed out" in low or "network" in low:
        return "timeout or network error"
    return raw_error[:50]


def is_blockable_failure(reason: str) -> bool:
    """Check if a failure reason should count toward domain blocking."""
    return reason in BLOCKABLE_FAILURES


def wilson_lower_bound(success: int, total: int, z: float = 1.96) -> float:
    """Wilson score 95% CI lower bound."""
    if total == 0:
        return 0.0
    p = success / total
    denom = 1 + z * z / total
    center = p + z * z / (2 * total)
    spread = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (center - spread) / denom


# ============================================================
# Lifecycle Helpers
# ============================================================

def mark_items_searched(supabase, ids: list[str], batch_size: int = 100) -> int:
    """Mark items as searched in batches to avoid PostgREST URL length limits."""
    if not ids:
        return 0

    total_updated = 0
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        response = supabase.table('wsj_items') \
            .update({
                'searched': True,
                'searched_at': datetime.now(timezone.utc).isoformat(),
            }) \
            .in_('id', batch) \
            .execute()
        total_updated += len(response.data) if response.data else 0

    return total_updated


def get_stats(supabase) -> dict:
    """Get WSJ items statistics."""
    total_response = supabase.table('wsj_items').select('id', count='exact').execute()
    total = total_response.count or 0

    unprocessed_response = supabase.table('wsj_items') \
        .select('id', count='exact') \
        .eq('processed', False) \
        .execute()
    unprocessed = unprocessed_response.count or 0

    by_feed_response = supabase.table('wsj_items').select('feed_name').execute()
    by_feed = {}
    for item in (by_feed_response.data or []):
        feed = item['feed_name']
        by_feed[feed] = by_feed.get(feed, 0) + 1

    return {
        'total': total,
        'unprocessed': unprocessed,
        'processed': total - unprocessed,
        'by_feed': by_feed,
    }


# ============================================================
# File I/O Helpers
# ============================================================

def load_ids_from_file(file_path: Path) -> list[str]:
    """Load item IDs from JSONL or JSON file.

    Dispatches on file extension: .jsonl → line-by-line, .json → single parse.
    """
    ids = []

    with open(file_path) as f:
        content = f.read().strip()

    if file_path.suffix == '.jsonl':
        for line in content.split('\n'):
            if line.strip():
                item = json.loads(line)
                if 'id' in item:
                    ids.append(item['id'])
    else:
        data = json.loads(content)
        if 'ids' in data:
            return data['ids']
        if 'id' in data:
            return [data['id']]

    return ids


def mark_items_processed(supabase, ids: list[str], batch_size: int = 100) -> int:
    """Mark items as processed in batches to avoid PostgREST URL length limits."""
    if not ids:
        return 0

    total_updated = 0
    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        response = supabase.table('wsj_items') \
            .update({
                'processed': True,
                'processed_at': datetime.now(timezone.utc).isoformat(),
            }) \
            .in_('id', batch) \
            .execute()
        total_updated += len(response.data) if response.data else 0

    return total_updated


# ============================================================
# Commands
# ============================================================

def cmd_update_domain_status() -> None:
    """Update wsj_domain_status table from wsj_crawl_results.

    Aggregates crawl results by domain and upserts to wsj_domain_status.
    Tracks per-reason failure counts in fail_counts JSONB column.

    Auto-blocks domains with Wilson score < 0.15 (n >= 5), but only
    counting "blockable" failures (http error, timeout/network error).
    Parser failures, content mismatches, and circular "domain blocked"
    errors are excluded — they're not the domain's fault.

    Manually blocked domains (block_reason not starting with "Auto-blocked:")
    are preserved and never overwritten by auto-block logic.
    """
    print("=" * 60)
    print("Update Domain Status from Crawl Results")
    print("=" * 60)

    supabase = require_supabase_client()

    # Query all crawl results with domain info (paginated to avoid 1000-row limit)
    print("Querying wsj_crawl_results...")
    all_rows = []
    offset = 0
    batch_size = 1000
    while True:
        response = supabase.table('wsj_crawl_results') \
            .select('resolved_domain, crawl_status, crawl_error, relevance_flag, created_at, crawl_length, embedding_score, llm_score') \
            .not_.is_('resolved_domain', 'null') \
            .range(offset, offset + batch_size - 1) \
            .execute()
        if not response.data:
            break
        all_rows.extend(response.data)
        if len(response.data) < batch_size:
            break
        offset += batch_size
    print(f"Fetched {len(all_rows)} crawl results")

    if not all_rows:
        print("No crawl results found.")
        return

    # Aggregate by domain with per-reason fail_counts
    # NOTE: Only count as success if crawl_status='success' AND relevance_flag='ok'
    # All other terminal states are failures, tracked by normalized reason
    domain_stats: dict = {}
    skipped_blocked = 0
    domains_with_block_errors: set[str] = set()  # Domains that had "domain blocked" crawl errors
    for row in all_rows:
        domain = row.get('resolved_domain')
        if not domain:
            continue

        crawl_error = row.get('crawl_error')

        # "domain blocked" rows: don't count as success or fail (circular),
        # but track the domain so it stays blocked
        if normalize_crawl_error(crawl_error) == "domain blocked":
            skipped_blocked += 1
            domains_with_block_errors.add(domain)
            continue

        if domain not in domain_stats:
            domain_stats[domain] = {
                'success_count': 0,
                'fail_count': 0,
                'fail_counts': {},  # Per-reason JSONB: {"content too short": 3, ...}
                'last_error': None,
                'last_success_at': None,  # Actual crawl timestamp
                'last_failure_at': None,  # Actual crawl timestamp
                'crawl_lengths': [],      # For avg_crawl_length (success only)
                'embedding_scores': [],   # For avg_embedding_score (all rows)
                'llm_scores': [],         # For avg_llm_score (success only)
            }

        crawl_status = row.get('crawl_status')
        relevance_flag = row.get('relevance_flag')
        row_ts = row.get('created_at')  # Actual crawl time from DB

        # Collect scores for averages (regardless of success/fail)
        if row.get('embedding_score') is not None:
            domain_stats[domain]['embedding_scores'].append(row['embedding_score'])

        if crawl_status == 'success' and relevance_flag == 'ok':
            domain_stats[domain]['success_count'] += 1
            if row.get('crawl_length'):
                domain_stats[domain]['crawl_lengths'].append(row['crawl_length'])
            if row.get('llm_score') is not None:
                domain_stats[domain]['llm_scores'].append(row['llm_score'])
            if row_ts and (not domain_stats[domain]['last_success_at'] or row_ts > domain_stats[domain]['last_success_at']):
                domain_stats[domain]['last_success_at'] = row_ts
        elif crawl_status in ('failed', 'error', 'resolve_failed', 'garbage', 'low_relevance'):
            reason = normalize_crawl_error(crawl_error or crawl_status)
            domain_stats[domain]['fail_count'] += 1
            domain_stats[domain]['fail_counts'][reason] = domain_stats[domain]['fail_counts'].get(reason, 0) + 1
            domain_stats[domain]['last_error'] = crawl_error or crawl_status
            if row_ts and (not domain_stats[domain]['last_failure_at'] or row_ts > domain_stats[domain]['last_failure_at']):
                domain_stats[domain]['last_failure_at'] = row_ts
        elif crawl_status == 'success' and relevance_flag == 'low':
            # Low relevance or LLM rejected
            reason = normalize_crawl_error(crawl_error) if crawl_error else 'low relevance'
            domain_stats[domain]['fail_count'] += 1
            domain_stats[domain]['fail_counts'][reason] = domain_stats[domain]['fail_counts'].get(reason, 0) + 1
            domain_stats[domain]['last_error'] = crawl_error or 'low relevance'
            if row.get('llm_score') is not None:
                domain_stats[domain]['llm_scores'].append(row['llm_score'])
            if row_ts and (not domain_stats[domain]['last_failure_at'] or row_ts > domain_stats[domain]['last_failure_at']):
                domain_stats[domain]['last_failure_at'] = row_ts

    print(f"Found {len(domain_stats)} unique domains (skipped {skipped_blocked} 'domain blocked' rows)")

    # Wilson Score thresholds for auto-blocking
    WILSON_THRESHOLD = 0.15
    MIN_ATTEMPTS = 5

    # Load existing blocked domains to protect manual blocks from overwrite
    existing_blocked: dict[str, str] = {}  # {domain: block_reason}
    try:
        response = supabase.table('wsj_domain_status') \
            .select('domain, block_reason') \
            .eq('status', 'blocked') \
            .execute()
        for row in (response.data or []):
            existing_blocked[row['domain']] = row.get('block_reason') or ''
    except Exception as e:
        print(f"Warning: Could not load existing blocked domains: {e}")

    # Upsert to wsj_domain_status
    now = datetime.now(timezone.utc).isoformat()
    updated = 0
    blocked = 0
    manual_preserved = 0

    LLM_SCORE_BLOCK_THRESHOLD = 3.0  # Block if avg_llm_score below this (with enough data)
    LLM_SCORE_MIN_SAMPLES = 5        # Need at least this many LLM scores to block on quality

    for domain, stats in domain_stats.items():
        success = stats['success_count']
        fail = stats['fail_count']
        fail_counts = stats['fail_counts']
        total = success + fail

        # Calculate success rate (all failures)
        success_rate = success / total if total > 0 else 0

        # Compute averages for new columns
        avg_crawl_length = (
            round(sum(stats['crawl_lengths']) / len(stats['crawl_lengths']))
            if stats['crawl_lengths'] else None
        )
        avg_embedding_score = (
            round(sum(stats['embedding_scores']) / len(stats['embedding_scores']), 4)
            if stats['embedding_scores'] else None
        )
        avg_llm_score = (
            round(sum(stats['llm_scores']) / len(stats['llm_scores']), 2)
            if stats['llm_scores'] else None
        )

        # Blockable failures: exclude content_mismatch reasons (low relevance, llm rejected)
        blockable_fail = sum(v for k, v in fail_counts.items() if is_blockable_failure(k))
        blockable_total = success + blockable_fail
        wilson = wilson_lower_bound(success, blockable_total)

        # Auto-block: Wilson score on http/timeout failures OR consistently low LLM quality
        should_block_wilson = blockable_total >= MIN_ATTEMPTS and wilson < WILSON_THRESHOLD
        should_block_quality = (
            avg_llm_score is not None
            and len(stats['llm_scores']) >= LLM_SCORE_MIN_SAMPLES
            and avg_llm_score < LLM_SCORE_BLOCK_THRESHOLD
        )
        should_block = should_block_wilson or should_block_quality
        status = 'blocked' if should_block else 'active'

        if should_block_wilson:
            block_reason = f"Auto-blocked: wilson={wilson:.3f} < {WILSON_THRESHOLD} ({success}/{blockable_total} blockable, {success_rate:.0%} overall)"
        elif should_block_quality:
            block_reason = f"Auto-blocked: avg_llm_score={avg_llm_score:.1f} < {LLM_SCORE_BLOCK_THRESHOLD} ({len(stats['llm_scores'])} samples)"
        else:
            block_reason = None

        # Preserve manually blocked domains (block_reason not starting with "Auto-blocked:")
        was_manually_blocked = (
            domain in existing_blocked
            and not existing_blocked[domain].startswith('Auto-blocked:')
        )
        if was_manually_blocked:
            status = 'blocked'
            block_reason = existing_blocked[domain]
            manual_preserved += 1

        record = {
            'domain': domain,
            'status': status,
            'success_count': success,
            'fail_count': fail,
            'fail_counts': json.dumps(fail_counts),
            'block_reason': block_reason,
            'success_rate': round(success_rate, 4),
            'wilson_score': round(wilson, 4),
            'avg_crawl_length': avg_crawl_length,
            'avg_embedding_score': avg_embedding_score,
            'avg_llm_score': avg_llm_score,
            'updated_at': now,
        }

        # Use actual crawl timestamps from DB (not aggregation run time)
        if stats['last_success_at']:
            record['last_success'] = stats['last_success_at']
        if stats['last_failure_at']:
            record['last_failure'] = stats['last_failure_at']

        try:
            supabase.table('wsj_domain_status').upsert(
                record,
                on_conflict='domain'
            ).execute()
            updated += 1
            if should_block:
                blocked += 1
        except Exception as e:
            print(f"Error updating {domain}: {e}")

    # Ensure domains with "domain blocked" errors stay blocked
    # (they had no real crawl data, so they weren't in domain_stats)
    block_preserved = 0
    for domain in domains_with_block_errors:
        if domain in domain_stats:
            continue  # Already handled by main upsert
        try:
            supabase.table('wsj_domain_status').upsert(
                {
                    'domain': domain,
                    'status': 'blocked',
                    'block_reason': existing_blocked.get(domain) or 'Auto-blocked: only "domain blocked" crawl errors',
                    'success_count': 0,
                    'fail_count': 0,
                    'updated_at': now,
                },
                on_conflict='domain',
            ).execute()
            block_preserved += 1
        except Exception as e:
            print(f"Error preserving blocked domain {domain}: {e}")

    print(f"\nUpdated {updated} domains in wsj_domain_status")
    print(f"Auto-blocked {blocked} domains (wilson < {WILSON_THRESHOLD} or avg_llm_score < {LLM_SCORE_BLOCK_THRESHOLD})")
    if block_preserved:
        print(f"Preserved {block_preserved} domains with only 'domain blocked' errors")
    if manual_preserved:
        print(f"Preserved {manual_preserved} manually blocked domains")

    # Show auto-blocked domains
    if blocked > 0:
        print("\nAuto-blocked domains:")
        for domain, stats in domain_stats.items():
            success = stats['success_count']
            fail_counts = stats['fail_counts']
            blockable_fail = sum(v for k, v in fail_counts.items() if is_blockable_failure(k))
            blockable_total = success + blockable_fail
            total = success + stats['fail_count']
            rate = success / total if total > 0 else 0
            wilson = wilson_lower_bound(success, blockable_total)
            avg_llm = sum(stats['llm_scores']) / len(stats['llm_scores']) if stats['llm_scores'] else None

            is_wilson_blocked = blockable_total >= MIN_ATTEMPTS and wilson < WILSON_THRESHOLD
            is_quality_blocked = (
                avg_llm is not None
                and len(stats['llm_scores']) >= LLM_SCORE_MIN_SAMPLES
                and avg_llm < LLM_SCORE_BLOCK_THRESHOLD
            )
            if is_wilson_blocked or is_quality_blocked:
                reason = "wilson" if is_wilson_blocked else "quality"
                llm_str = f", llm={avg_llm:.1f}" if avg_llm is not None else ""
                print(f"  {domain}: [{reason}] wilson={wilson:.3f}, {rate:.0%} ({success}/{total}){llm_str}")


def cmd_mark_searched(jsonl_path: Path) -> None:
    """Mark WSJ items as searched based on exported JSONL file.

    After Google News search completes, this marks all items from the
    original export as 'searched' so they won't be searched again.
    """
    print("=" * 60)
    print("Mark Items as Searched")
    print("=" * 60)

    if not jsonl_path.exists():
        print(f"Error: File not found: {jsonl_path}")
        sys.exit(1)

    ids = load_ids_from_file(jsonl_path)
    if not ids:
        print("No item IDs found in file.")
        return

    print(f"Found {len(ids)} items in: {jsonl_path}")

    supabase = require_supabase_client()
    updated = mark_items_searched(supabase, ids)

    print(f"Marked {updated} items as searched.")


def cmd_stats() -> None:
    """Show current database statistics."""
    print("=" * 60)
    print("WSJ Items Statistics")
    print("=" * 60)

    supabase = require_supabase_client()
    stats = get_stats(supabase)

    print(f"Total items:   {stats['total']}")
    print(f"Unprocessed:   {stats['unprocessed']}")
    print(f"Processed:     {stats['processed']}")

    print("\nBy feed:")
    for feed, count in sorted(stats['by_feed'].items()):
        print(f"  {feed}: {count}")


def cmd_mark_processed(file_path: Path) -> None:
    """Mark items from JSONL or JSON file as processed."""
    print("=" * 60)
    print("Mark Items as Processed")
    print("=" * 60)

    if not file_path.exists():
        print(f"Error: File not found: {file_path}")
        sys.exit(1)

    ids = load_ids_from_file(file_path)
    if not ids:
        print("No item IDs found in file.")
        return

    print(f"Found {len(ids)} item IDs in: {file_path}")

    supabase = require_supabase_client()
    updated = mark_items_processed(supabase, ids)

    print(f"Marked {updated} items as processed.")


def cmd_mark_processed_from_db() -> None:
    """Mark WSJ items as processed by querying wsj_crawl_results table.

    Finds all wsj_item_id values where crawl_status = 'success' AND relevance_flag = 'ok',
    then marks those items as processed in wsj_items table.

    NOTE: Only marks items with good quality content. Items with low_relevance or
    garbage status are NOT marked as processed so backups can be retried.
    """
    print("=" * 60)
    print("Mark Processed from DB (wsj_crawl_results)")
    print("=" * 60)

    supabase = require_supabase_client()

    # Query wsj_crawl_results for successful crawls with good relevance
    print("Querying wsj_crawl_results for quality crawls (success + ok relevance)...")
    response = supabase.table('wsj_crawl_results') \
        .select('wsj_item_id') \
        .eq('crawl_status', 'success') \
        .eq('relevance_flag', 'ok') \
        .not_.is_('wsj_item_id', 'null') \
        .execute()

    if not response.data:
        print("No quality crawls found in wsj_crawl_results.")
        return

    # Get unique wsj_item_ids
    wsj_ids = list(set(
        row['wsj_item_id'] for row in response.data
        if row.get('wsj_item_id')
    ))
    print(f"Found {len(wsj_ids)} unique WSJ items with quality crawls")

    if not wsj_ids:
        print("No valid wsj_item_id values found.")
        return

    # Mark as processed
    updated = mark_items_processed(supabase, wsj_ids)
    print(f"Marked {updated} items as processed in wsj_items.")


def cmd_retry_low_relevance() -> None:
    """Reactivate backup articles for WSJ items with only low-relevance crawls.

    This command:
    1. Finds WSJ items that ONLY have low-relevance crawls (no good quality crawl)
    2. Reactivates their skipped backup articles (skipped → pending)
    3. Unmarks WSJ items as processed (so crawler will retry them)

    Use this after updating crawl_ranked.py to continue trying backups on low relevance.
    """
    print("=" * 60)
    print("Retry Low Relevance Items")
    print("=" * 60)

    supabase = require_supabase_client()

    # Step 1: Find WSJ items with low-relevance success but NO good success
    print("\n[1/4] Finding WSJ items with only low-relevance crawls...")

    # Get all WSJ item IDs that have at least one 'success' + 'ok' relevance
    good_response = supabase.table('wsj_crawl_results') \
        .select('wsj_item_id') \
        .eq('crawl_status', 'success') \
        .eq('relevance_flag', 'ok') \
        .not_.is_('wsj_item_id', 'null') \
        .execute()

    good_item_ids = set(
        row['wsj_item_id'] for row in (good_response.data or [])
        if row.get('wsj_item_id')
    )
    print(f"  WSJ items with good crawls: {len(good_item_ids)}")

    # Get all WSJ item IDs that have low-relevance crawls (success + low, or old low_relevance status)
    low_response = supabase.table('wsj_crawl_results') \
        .select('wsj_item_id') \
        .eq('crawl_status', 'success') \
        .eq('relevance_flag', 'low') \
        .not_.is_('wsj_item_id', 'null') \
        .execute()

    # Also check for old 'low_relevance' status records
    old_low_response = supabase.table('wsj_crawl_results') \
        .select('wsj_item_id') \
        .eq('crawl_status', 'low_relevance') \
        .not_.is_('wsj_item_id', 'null') \
        .execute()

    low_item_ids = set(
        row['wsj_item_id'] for row in (low_response.data or [])
        if row.get('wsj_item_id')
    )
    low_item_ids.update(
        row['wsj_item_id'] for row in (old_low_response.data or [])
        if row.get('wsj_item_id')
    )
    print(f"  WSJ items with low-relevance crawls: {len(low_item_ids)}")

    # Items to retry = have low relevance but NOT good quality
    items_to_retry = low_item_ids - good_item_ids
    print(f"  WSJ items needing retry: {len(items_to_retry)}")

    if not items_to_retry:
        print("\nNo items need retry. All low-relevance items already have a good crawl.")
        return

    # Step 2: Reactivate skipped backup articles for these items
    print(f"\n[2/4] Reactivating skipped backups for {len(items_to_retry)} items...")

    # Process in batches to avoid query limits
    items_list = list(items_to_retry)
    batch_size = 100
    total_reactivated = 0

    for i in range(0, len(items_list), batch_size):
        batch = items_list[i:i + batch_size]
        try:
            response = supabase.table('wsj_crawl_results') \
                .update({'crawl_status': 'pending', 'crawl_error': None}) \
                .eq('crawl_status', 'skipped') \
                .in_('wsj_item_id', batch) \
                .execute()
            total_reactivated += len(response.data) if response.data else 0
        except Exception as e:
            print(f"  Error updating batch: {e}")

    print(f"  Reactivated {total_reactivated} backup articles")

    # Step 3: Unmark WSJ items as processed
    print(f"\n[3/4] Unmarking {len(items_to_retry)} WSJ items as processed...")

    total_unmarked = 0
    for i in range(0, len(items_list), batch_size):
        batch = items_list[i:i + batch_size]
        try:
            response = supabase.table('wsj_items') \
                .update({'processed': False, 'processed_at': None}) \
                .in_('id', batch) \
                .execute()
            total_unmarked += len(response.data) if response.data else 0
        except Exception as e:
            print(f"  Error updating batch: {e}")

    print(f"  Unmarked {total_unmarked} WSJ items")

    # Step 4: Summary
    print("\n[4/4] Summary")
    print("=" * 60)
    print(f"WSJ items to retry: {len(items_to_retry)}")
    print(f"Backup articles reactivated: {total_reactivated}")
    print(f"WSJ items unmarked: {total_unmarked}")
    print("\nNext steps:")
    print("  1. Run: python scripts/crawl_ranked.py --update-db")
    print("  2. Run: python scripts/domain_utils.py --update-domain-status")


def cmd_seed_blocked_from_json() -> None:
    """One-time migration: seed blocked domains from JSON file to wsj_domain_status."""
    print("=" * 60)
    print("Seed Blocked Domains from JSON → DB")
    print("=" * 60)

    json_path = Path(__file__).parent / "data" / "blocked_domains.json"
    if not json_path.exists():
        print(f"Error: JSON file not found: {json_path}")
        sys.exit(1)

    with open(json_path) as f:
        data = json.load(f)

    blocked = data.get("blocked", {})
    if not blocked:
        print("No blocked domains found in JSON.")
        return

    print(f"Found {len(blocked)} blocked domains in JSON")

    supabase = require_supabase_client()
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0

    for domain, info in blocked.items():
        reason = info.get("reason", "Migrated from JSON")
        try:
            supabase.table('wsj_domain_status').upsert(
                {
                    'domain': domain,
                    'status': 'blocked',
                    'block_reason': f"JSON migration: {reason}",
                    'updated_at': now,
                },
                on_conflict='domain',
            ).execute()
            inserted += 1
        except Exception as e:
            print(f"  Error inserting {domain}: {e}")

    print(f"Upserted {inserted}/{len(blocked)} domains to wsj_domain_status")


# ============================================================
# CLI Entry Point
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Domain status management and pipeline lifecycle operations"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--mark-searched', metavar='FILE', help='Mark items in JSONL/JSON as searched')
    group.add_argument('--mark-processed', metavar='FILE', help='Mark items in JSONL/JSON as processed')
    group.add_argument('--mark-processed-from-db', action='store_true', help='Query wsj_crawl_results and mark processed')
    group.add_argument('--update-domain-status', action='store_true', help='Aggregate crawl results to wsj_domain_status')
    group.add_argument('--retry-low-relevance', action='store_true', help='Reactivate backups for low-relevance items')
    group.add_argument('--stats', action='store_true', help='Show database statistics')
    group.add_argument('--seed-blocked-from-json', action='store_true', help='One-time: migrate JSON blocked domains to DB')
    args = parser.parse_args()

    if args.mark_searched:
        cmd_mark_searched(Path(args.mark_searched))
    elif args.mark_processed:
        cmd_mark_processed(Path(args.mark_processed))
    elif args.mark_processed_from_db:
        cmd_mark_processed_from_db()
    elif args.update_domain_status:
        cmd_update_domain_status()
    elif args.retry_low_relevance:
        cmd_retry_low_relevance()
    elif args.stats:
        cmd_stats()
    elif args.seed_blocked_from_json:
        cmd_seed_blocked_from_json()


if __name__ == "__main__":
    main()
