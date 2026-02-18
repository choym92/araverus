#!/usr/bin/env python3
"""
Supabase Postgres SQL Runner.

Thin wrapper for executing SQL against Supabase Postgres.
Read-only by default; use --allow-write for DML operations.

Usage:
    # Simple read query
    python scripts/db_query.py "SELECT count(*) FROM wsj_items"

    # JSON output for machine parsing
    python scripts/db_query.py --json "SELECT feed_name, count(*) FROM wsj_items GROUP BY 1"

    # Dry-run a write query (wraps in ROLLBACK transaction)
    python scripts/db_query.py --allow-write --dry-run "DELETE FROM wsj_crawl_results WHERE crawl_status='pending'"

    # Execute a write query
    python scripts/db_query.py --allow-write "DELETE FROM wsj_crawl_results WHERE id IS NULL"

Environment:
    DATABASE_URL - Supabase direct Postgres connection string
"""
import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env.local
load_dotenv(Path(__file__).resolve().parent.parent.parent / '.env.local')

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SQL Safety
# ---------------------------------------------------------------------------

# Patterns that are always blocked (destructive DDL)
DANGEROUS_PATTERNS = [
    r'\bDROP\s+(TABLE|DATABASE|SCHEMA|INDEX)\b',
    r'\bTRUNCATE\b',
    r'\bALTER\s+TABLE\b',
    r'\bCREATE\s+(TABLE|DATABASE|SCHEMA)\b',
    r'\bGRANT\b',
    r'\bREVOKE\b',
]

WRITE_PATTERNS = [
    r'\bINSERT\b',
    r'\bUPDATE\b',
    r'\bDELETE\b',
]


def classify_sql(sql: str) -> str:
    """Classify SQL as 'read', 'write', or 'dangerous'.

    Returns:
        'dangerous' — always blocked (DROP, TRUNCATE, ALTER, etc.)
        'write'     — DML that modifies data (INSERT/UPDATE/DELETE)
        'read'      — SELECT and other read-only statements
    """
    normalized = sql.strip().upper()

    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, normalized):
            return 'dangerous'

    for pattern in WRITE_PATTERNS:
        if re.search(pattern, normalized):
            return 'write'

    return 'read'


# ---------------------------------------------------------------------------
# Query Execution
# ---------------------------------------------------------------------------

def run_query(dsn: str, sql: str, *, allow_write: bool, dry_run: bool, limit: int) -> dict:
    """Execute SQL and return results.

    Returns:
        dict with keys: columns, rows, row_count, warning (optional)
    """
    import psycopg2
    import psycopg2.extras

    classification = classify_sql(sql)

    if classification == 'dangerous':
        return {
            'error': 'BLOCKED: Query classified as dangerous. '
                     'DDL operations (DROP, TRUNCATE, ALTER, etc.) are not allowed.',
            'columns': [],
            'rows': [],
            'row_count': 0,
        }

    if classification == 'write' and not allow_write:
        return {
            'error': 'BLOCKED: Write query detected but --allow-write not set. '
                     'Use --allow-write to enable DML operations.',
            'columns': [],
            'rows': [],
            'row_count': 0,
        }

    result = {'columns': [], 'rows': [], 'row_count': 0}

    conn = psycopg2.connect(dsn)
    try:
        conn.autocommit = False
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        try:
            cur.execute(sql)

            if cur.description:
                # Query returned results (SELECT or RETURNING clause)
                columns = [desc[0] for desc in cur.description]
                rows = cur.fetchmany(limit)
                total = cur.rowcount

                result['columns'] = columns
                result['rows'] = [dict(row) for row in rows]
                result['row_count'] = total

                if total > limit:
                    result['warning'] = f'Results truncated to {limit} rows (total: {total})'
            else:
                # DML without RETURNING
                result['row_count'] = cur.rowcount
                result['columns'] = []
                result['rows'] = []

            if classification == 'write' and dry_run:
                conn.rollback()
                result['warning'] = (
                    f'DRY RUN: {result["row_count"]} row(s) would be affected. '
                    f'Transaction rolled back. Run without --dry-run to execute.'
                )
            elif classification == 'write':
                conn.commit()
            else:
                conn.commit()

        except Exception as e:
            conn.rollback()
            result['error'] = str(e)
    finally:
        conn.close()

    return result


# ---------------------------------------------------------------------------
# Output Formatting
# ---------------------------------------------------------------------------

def _serialize_value(v):
    """Convert non-JSON-serializable values to strings."""
    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def format_table(result: dict) -> str:
    """Format result as a human-readable table."""
    if 'error' in result:
        return f"ERROR: {result['error']}"

    lines = []

    if result.get('warning'):
        lines.append(f"WARNING: {result['warning']}")

    if not result['columns']:
        lines.append(f"Rows affected: {result['row_count']}")
        return '\n'.join(lines)

    columns = result['columns']
    rows = result['rows']

    # Calculate column widths
    widths = {col: len(col) for col in columns}
    for row in rows:
        for col in columns:
            val = str(row.get(col, ''))
            widths[col] = max(widths[col], min(len(val), 60))

    # Header
    header = ' | '.join(col.ljust(widths[col]) for col in columns)
    separator = '-+-'.join('-' * widths[col] for col in columns)
    lines.append(header)
    lines.append(separator)

    # Rows
    for row in rows:
        line = ' | '.join(
            str(row.get(col, '')).ljust(widths[col])[:60]
            for col in columns
        )
        lines.append(line)

    lines.append(f'\n({result["row_count"]} row(s))')
    return '\n'.join(lines)


def format_json(result: dict) -> str:
    """Format result as JSON."""
    serializable = {
        'columns': result.get('columns', []),
        'rows': [
            {k: _serialize_value(v) for k, v in row.items()}
            for row in result.get('rows', [])
        ],
        'row_count': result.get('row_count', 0),
    }
    if 'error' in result:
        serializable['error'] = result['error']
    if 'warning' in result:
        serializable['warning'] = result['warning']

    return json.dumps(serializable, indent=2, default=str)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Execute SQL against Supabase Postgres',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('sql', help='SQL query to execute')
    parser.add_argument('--allow-write', action='store_true',
                        help='Allow DML statements (INSERT/UPDATE/DELETE)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Wrap write query in ROLLBACK transaction')
    parser.add_argument('--json', action='store_true', dest='json_output',
                        help='Output as JSON instead of table')
    parser.add_argument('--limit', type=int, default=100,
                        help='Max rows to return (default: 100)')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose logging')
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s: %(message)s',
    )

    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        logger.error('DATABASE_URL not set. Add it to .env.local')
        sys.exit(1)

    if args.dry_run and not args.allow_write:
        logger.error('--dry-run requires --allow-write')
        sys.exit(1)

    logger.debug('SQL: %s', args.sql)
    logger.debug('Classification: %s', classify_sql(args.sql))

    result = run_query(
        dsn,
        args.sql,
        allow_write=args.allow_write,
        dry_run=args.dry_run,
        limit=args.limit,
    )

    if args.json_output:
        print(format_json(result))
    else:
        print(format_table(result))

    if 'error' in result:
        sys.exit(1)


if __name__ == '__main__':
    main()
