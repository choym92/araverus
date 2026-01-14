#!/usr/bin/env python3
"""
Test crawl success rate for different domains.

Reads resolved URLs from wsj_google_news_results.jsonl and tests crawling.
Run resolve_urls.py first to populate resolved_url fields.

Usage:
    python scripts/test_domain_crawl.py [--limit N]
"""
import asyncio
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Import from local modules
sys.path.insert(0, str(Path(__file__).parent))
from crawl_article import crawl_article, get_domain


# Paywall/bot detection signals
PAYWALL_SIGNALS = [
    "subscribe", "sign in", "log in to continue", "you've reached",
    "to continue reading", "start your subscription", "premium content",
    "members only", "unlock this article", "create an account",
    "free trial", "already a subscriber", "subscription required",
]

BOT_SIGNALS = [
    "please verify", "are you a robot", "captcha", "access denied",
    "403 forbidden", "enable javascript", "browser check",
]


def validate_content(text: str, title: str = "") -> tuple[bool, str, dict]:
    """Validate crawled content quality."""
    metrics = {
        "length": len(text) if text else 0,
        "word_count": len(text.split()) if text else 0,
        "has_paywall_signal": False,
        "has_bot_signal": False,
    }

    if not text:
        return False, "empty", metrics

    if len(text) < 200:
        return False, "too_short", metrics

    lower = text.lower()

    for signal in PAYWALL_SIGNALS:
        if signal in lower:
            metrics["has_paywall_signal"] = True
            if signal in lower[:500]:
                return False, f"paywall_signal:{signal}", metrics

    for signal in BOT_SIGNALS:
        if signal in lower:
            metrics["has_bot_signal"] = True
            return False, f"bot_signal:{signal}", metrics

    if metrics["word_count"] < 50:
        return False, "too_few_words", metrics

    if title:
        title_words = set(title.lower().split()[:5])
        content_words = set(lower.split()[:200])
        if len(title_words & content_words) < 2:
            return False, "title_not_in_content", metrics

    return True, "ok", metrics


async def test_single_url(url: str, title: str = "") -> dict:
    """Test crawling a single resolved URL."""
    result = {
        "url": url,
        "domain": get_domain(url),
        "title": title,
        "success": False,
        "status_code": 0,
        "content_length": 0,
        "word_count": 0,
        "validation": "not_tested",
        "fail_reason": None,
        "sample_content": "",
    }

    try:
        crawl_result = await crawl_article(
            url,
            mode="undetected",
            skip_blocked=False,
            log_result=False,
        )

        result["status_code"] = crawl_result.get("status_code", 0)
        content = crawl_result.get("markdown", "")
        result["content_length"] = len(content) if content else 0

        is_valid, reason, metrics = validate_content(content, title)
        result["word_count"] = metrics["word_count"]
        result["validation"] = reason
        result["success"] = is_valid

        if not is_valid:
            result["fail_reason"] = reason

        if content:
            result["sample_content"] = content[:500].replace("\n", " ")

    except Exception as e:
        result["fail_reason"] = f"crawl_error:{str(e)[:80]}"

    return result


async def main():
    # Parse arguments
    limit = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1])

    # Load Google News results with resolved URLs
    input_path = Path(__file__).parent / "output" / "wsj_google_news_results.jsonl"
    if not input_path.exists():
        print(f"Error: Run wsj_to_google_news.py first")
        return

    # Collect unique domains with resolved URLs
    domain_articles = defaultdict(list)

    with open(input_path) as f:
        for line in f:
            data = json.loads(line)
            for article in data.get("google_news", []):
                domain = article.get("source_domain", "")
                resolved_url = article.get("resolved_url")
                if domain and resolved_url:
                    domain_articles[domain].append({
                        "resolved_url": resolved_url,
                        "title": article.get("title", ""),
                        "source": article.get("source", ""),
                    })

    if not domain_articles:
        print("Error: No resolved URLs found. Run resolve_urls.py first.")
        return

    total_domains = len(domain_articles)
    test_domains = list(sorted(domain_articles.items()))
    if limit:
        test_domains = test_domains[:limit]

    print(f"Found {total_domains} domains with resolved URLs")
    print(f"Testing {len(test_domains)} domains" + (f" (limit={limit})" if limit else ""))
    print("=" * 80)

    # Test one URL per domain
    results = []

    for i, (domain, articles) in enumerate(test_domains):
        sample = articles[0]
        print(f"[{i+1}/{len(test_domains)}] Testing: {domain}")
        print(f"    URL: {sample['resolved_url'][:70]}...")

        result = await test_single_url(sample["resolved_url"], sample["title"])
        result["source_name"] = sample["source"]
        result["expected_domain"] = domain
        results.append(result)

        status = "✓" if result["success"] else "✗"
        print(f"    {status} Status={result['status_code']}, "
              f"Words={result['word_count']}, "
              f"Validation={result['validation']}")

        # Rate limit
        await asyncio.sleep(2)

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    success = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"\nTotal domains tested: {len(results)}")
    print(f"Success: {len(success)}")
    print(f"Failed: {len(failed)}")

    print("\n" + "=" * 80)
    print("TIER RECOMMENDATION")
    print("=" * 80)

    print("\n🟢 TIER A (Crawl successful):")
    for r in success:
        print(f"  - {r['domain']} ({r['source_name']})")
        print(f"      Words: {r['word_count']}, Status: {r['status_code']}")

    print("\n🔴 TIER C (Crawl failed):")
    for r in failed:
        print(f"  - {r['domain']} ({r['source_name']})")
        print(f"      Reason: {r['fail_reason']}")

    # Save results
    output_dir = Path(__file__).parent / "output"

    json_path = output_dir / "domain_crawl_test.json"
    with open(json_path, "w") as f:
        json.dump({
            "tested_at": datetime.now().isoformat(),
            "total": len(results),
            "success_count": len(success),
            "failed_count": len(failed),
            "results": results,
        }, f, indent=2, ensure_ascii=False)

    txt_path = output_dir / "domain_crawl_test.txt"
    with open(txt_path, "w") as f:
        f.write(f"Domain Crawl Test Results\n")
        f.write(f"Tested at: {datetime.now().isoformat()}\n")
        f.write(f"{'=' * 80}\n\n")
        f.write(f"Total: {len(results)}, Success: {len(success)}, Failed: {len(failed)}\n\n")

        f.write(f"{'=' * 80}\n")
        f.write(f"TIER A - CRAWL SUCCESSFUL\n")
        f.write(f"{'=' * 80}\n\n")
        for r in success:
            f.write(f"Domain: {r['domain']}\n")
            f.write(f"Source: {r['source_name']}\n")
            f.write(f"Status: {r['status_code']}, Words: {r['word_count']}\n")
            f.write(f"URL: {r['url']}\n")
            if r['sample_content']:
                f.write(f"Sample: {r['sample_content'][:200]}...\n")
            f.write(f"\n")

        f.write(f"{'=' * 80}\n")
        f.write(f"TIER C - CRAWL FAILED\n")
        f.write(f"{'=' * 80}\n\n")
        for r in failed:
            f.write(f"Domain: {r['domain']}\n")
            f.write(f"Source: {r['source_name']}\n")
            f.write(f"Reason: {r['fail_reason']}\n")
            f.write(f"URL: {r['url']}\n")
            f.write(f"\n")

    print(f"\nResults saved to:")
    print(f"  {json_path}")
    print(f"  {txt_path}")


if __name__ == "__main__":
    asyncio.run(main())
