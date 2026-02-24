<!-- Updated: 2026-02-24 -->
# Python Pipeline Rules

## Execution Environment

1) **CWD must be `scripts/`**: Pipeline scripts load `.env.local` from CWD. Always `cd scripts/` before running.
2) **MacBook vs Mac Mini**: Mac Mini has full deps (`google-cloud-texttospeech`, `whisper`, `ctc-forced-aligner`, `unidecode`). MacBook `scripts/.venv` may be missing these — install as needed.

## Code Rules

When writing or modifying `scripts/*.py` pipeline scripts:

1) **No unnecessary async**: Sequential HTTP calls with delays → sync `httpx.Client` + `time.sleep`.
2) **Lazy-load heavy deps**: ML models, expensive clients → lazy singleton (`_get_model()` pattern). Never at module level.
3) **argparse only**: No manual `sys.argv` parsing.
4) **One Supabase client**: `domain_utils.require_supabase_client()` (CLI fail-fast) or `get_supabase_client()` (optional, returns None). Never duplicate.
5) **Correct lifecycle names**: `searched` ≠ `processed` ≠ `briefed`. Check `docs/schema.md`.
6) **Separation of concerns**: Each script owns one phase. Don't set downstream state.
7) **Step numbering**: Docstrings use `Phase N · Step M · Name` format.
8) **Kill dead code**: Remove legacy flags, unused params, completed migration fallbacks.
