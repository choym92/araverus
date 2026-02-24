#!/usr/bin/env python3
"""One-time reset: rebuild wsj_domain_status from scratch.

Fixes:
1. Circular "domain blocked" errors inflating fail_count
2. 531 missing domains (in crawl_results but not in domain_status)
3. Timestamps using now() instead of actual crawl times
4. Missing SNS domain blocks (x.com, facebook.com, etc.)

Steps:
1. Backup manual blocks and search_hit_count
2. Clear table
3. Restore manual blocks + search_hit_count
4. Add SNS domain blocks
5. Run updated cmd_update_domain_status() to re-aggregate from crawl_results

Usage:
    python scripts/reset_domain_status.py
    python scripts/reset_domain_status.py --dry-run
"""
import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from domain_utils import cmd_update_domain_status, require_supabase_client

SNS_DOMAINS = [
    "x.com",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "threads.com",
]
SNS_BLOCK_REASON = "Manual: Social media - no article content"


def main():
    parser = argparse.ArgumentParser(description="Reset wsj_domain_status table")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen without modifying DB")
    args = parser.parse_args()

    supabase = require_supabase_client()
    now = datetime.now(timezone.utc).isoformat()

    # ── Step 1: Backup manual blocks + search_hit_count ──
    print("=" * 60)
    print("[1/5] Backing up manual blocks and search_hit_count...")
    print("=" * 60)

    all_rows = []
    offset = 0
    batch_size = 1000
    while True:
        response = supabase.table("wsj_domain_status").select("*").range(offset, offset + batch_size - 1).execute()
        if not response.data:
            break
        all_rows.extend(response.data)
        if len(response.data) < batch_size:
            break
        offset += batch_size
    print(f"  Total rows in wsj_domain_status: {len(all_rows)}")

    # Backup manual blocks (block_reason starts with 'JSON migration:' or 'Manual:')
    manual_blocks: list[dict] = []
    for row in all_rows:
        reason = row.get("block_reason") or ""
        if reason.startswith("JSON migration:") or reason.startswith("Manual:"):
            manual_blocks.append({
                "domain": row["domain"],
                "status": "blocked",
                "block_reason": reason,
            })
    print(f"  Manual blocks to preserve: {len(manual_blocks)}")

    # Backup search_hit_count (non-zero only)
    hit_counts: dict[str, int] = {}
    for row in all_rows:
        count = row.get("search_hit_count") or 0
        if count > 0:
            hit_counts[row["domain"]] = count
    print(f"  Domains with search_hit_count > 0: {len(hit_counts)}")

    if args.dry_run:
        print("\n[DRY RUN] Would clear table, restore manual blocks, add SNS blocks, re-aggregate")
        print(f"  Manual blocks: {len(manual_blocks)}")
        print(f"  Hit counts: {len(hit_counts)}")
        print(f"  SNS domains: {SNS_DOMAINS}")
        return

    # ── Step 2: Clear table + drop failure_type column ──
    print("\n" + "=" * 60)
    print("[2/5] Clearing wsj_domain_status + dropping failure_type column...")
    print("=" * 60)

    # Delete all rows (Supabase requires a filter, use neq on non-null domain)
    supabase.table("wsj_domain_status").delete().neq("domain", "").execute()
    verify = supabase.table("wsj_domain_status").select("domain", count="exact").execute()
    print(f"  Rows after clear: {verify.count}")

    # Schema changes: drop deprecated columns, add new ones
    schema_sql = """
        ALTER TABLE wsj_domain_status
            DROP COLUMN IF EXISTS failure_type,
            DROP COLUMN IF EXISTS llm_fail_count,
            DROP COLUMN IF EXISTS last_llm_failure,
            DROP COLUMN IF EXISTS weighted_score,
            ADD COLUMN IF NOT EXISTS avg_crawl_length INTEGER,
            ADD COLUMN IF NOT EXISTS avg_embedding_score NUMERIC,
            ADD COLUMN IF NOT EXISTS avg_llm_score NUMERIC;
    """
    try:
        supabase.rpc("exec_sql", {"query": schema_sql}).execute()
        print("  Schema updated (dropped: failure_type, llm_fail_count, last_llm_failure, weighted_score)")
        print("  Schema updated (added: avg_crawl_length, avg_embedding_score, avg_llm_score)")
    except Exception as e:
        print(f"  Could not run schema migration via RPC: {e}")
        print("  Run manually in Supabase SQL editor:")
        print(schema_sql)

    # ── Step 3: Restore manual blocks ──
    print("\n" + "=" * 60)
    print("[3/5] Restoring manual blocks...")
    print("=" * 60)

    restored = 0
    for block in manual_blocks:
        try:
            supabase.table("wsj_domain_status").upsert(
                {**block, "updated_at": now},
                on_conflict="domain",
            ).execute()
            restored += 1
        except Exception as e:
            print(f"  Error restoring {block['domain']}: {e}")
    print(f"  Restored {restored}/{len(manual_blocks)} manual blocks")

    # ── Step 4: Add SNS domain blocks ──
    print("\n" + "=" * 60)
    print("[4/5] Adding SNS domain blocks...")
    print("=" * 60)

    for domain in SNS_DOMAINS:
        try:
            supabase.table("wsj_domain_status").upsert(
                {
                    "domain": domain,
                    "status": "blocked",
                    "block_reason": SNS_BLOCK_REASON,
                    "updated_at": now,
                },
                on_conflict="domain",
            ).execute()
            print(f"  + {domain}")
        except Exception as e:
            print(f"  Error adding {domain}: {e}")

    # ── Step 5: Re-aggregate from crawl_results ──
    print("\n" + "=" * 60)
    print("[5/5] Re-aggregating from wsj_crawl_results...")
    print("=" * 60)

    cmd_update_domain_status()

    # ── Restore search_hit_count (after re-aggregate so we don't lose them) ──
    if hit_counts:
        print(f"\nRestoring search_hit_count for {len(hit_counts)} domains...")
        restored_hits = 0
        for domain, count in hit_counts.items():
            try:
                supabase.table("wsj_domain_status").upsert(
                    {"domain": domain, "search_hit_count": count},
                    on_conflict="domain",
                ).execute()
                restored_hits += 1
            except Exception as e:
                print(f"  Error restoring hit count for {domain}: {e}")
        print(f"  Restored {restored_hits}/{len(hit_counts)} hit counts")

    # ── Summary ──
    print("\n" + "=" * 60)
    print("RESET COMPLETE — Verification")
    print("=" * 60)

    final = supabase.table("wsj_domain_status").select("domain, status", count="exact").execute()
    total = final.count or 0
    blocked_count = sum(1 for r in (final.data or []) if r.get("status") == "blocked")
    active_count = total - blocked_count
    print(f"  Total domains: {total}")
    print(f"  Active: {active_count}")
    print(f"  Blocked: {blocked_count}")

    # Check SNS domains
    for domain in SNS_DOMAINS:
        check = supabase.table("wsj_domain_status").select("status").eq("domain", domain).execute()
        status = check.data[0]["status"] if check.data else "MISSING"
        print(f"  {domain}: {status}")


if __name__ == "__main__":
    main()
