#!/usr/bin/env python3
"""
Backfill embeddings and thread assignments for all historical articles.

Usage:
    python scripts/backfill_embeddings.py
    python scripts/backfill_embeddings.py --embed-only
    python scripts/backfill_embeddings.py --dry-run
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from embed_and_thread import main

if __name__ == "__main__":
    # This is a convenience wrapper around embed_and_thread.py
    # The main script already handles unembedded + unthreaded articles
    print("=== BACKFILL MODE ===")
    print("Running embed_and_thread.py for all historical articles...")
    print("This may take several minutes for large datasets.\n")
    main()
