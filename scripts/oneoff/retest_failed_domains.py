#!/usr/bin/env python3
"""
Retest failed popular domains with improved crawler settings.

Usage:
    python scripts/retest_failed_domains.py
"""
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from crawl_article import crawl_article
from test_domain_crawl import validate_content

# Popular failed domains to retest (excluding paywall sites)
FAILED_DOMAINS_TO_TEST = {
    # Major News
    "cnn.com": "https://www.cnn.com/2026/01/07/business/character-ai-google-settle-teen-suicide-lawsuit",
    "forbes.com": "https://www.forbes.com/sites/tylerroush/2026/01/07/anthropic-seeks-10-billion-raised-on-350-billion-valuation-report-says/",
    "engadget.com": "https://www.engadget.com/ai/characterai-and-google-settle-with-families-in-teen-suicide-and-self-harm-lawsuits-201059912.html",
    "euronews.com": "https://www.euronews.com/next/2026/01/08/google-and-chatbot-start-up-characterai-to-settle-lawsuits-over-teen-suicides",
    "scmp.com": "https://www.scmp.com/tech/article/3339008/beijing-mulls-intervention-metas-deal-buy-manus-amid-ai-brain-drain-fears",
    "straitstimes.com": "https://www.straitstimes.com/business/companies-markets/nvidia-says-its-revenue-forecast-has-only-grown-more-bullish",
    "channelnewsasia.com": "https://www.channelnewsasia.com/business/anthropic-plans-raise-10-billion-350-billion-valuation-wsj-reports-5837126",
    # Finance/Trading
    "benzinga.com": "https://www.benzinga.com/markets/tech/26/01/49746474/metas-2-billion-manus-acquisition-under-chinese-scrutiny-for-possible-export-control-violations-report",
    "finviz.com": "https://finviz.com/news/269139/how-samsungs-ai-drive-helps-alphabets-googl-gemini-ambitions",
    "tipranks.com": "https://www.tipranks.com/news/private-companies/anthropic-targets-10-billion-raise-at-350-billion-valuation-as-ipo-looms",
    "thestreet.com": "https://www.thestreet.com/investing/what-nvidia-just-did-could-rewire-the-ai-race",
    "msn.com": "https://www.msn.com/en-in/news/world/anthropic-said-to-be-in-talks-to-raise-funding-at-a-350-billion-valuation/ar-AA1TMyjB",
    # Tech News
    "tomshardware.com": "https://www.tomshardware.com/pc-components/gpus/nvidia-says-h200-demand-in-china-is-very-high-as-export-licenses-near-completion",
    "semafor.com": "https://www.semafor.com/article/01/06/2026/nvidia-speeds-up-chip-release-as-ai-competition-intensifies",
    "dataconomy.com": "https://dataconomy.com/2026/01/08/anthropic-to-raise-10-billion-at-350-billion-valuation/",
    "the-decoder.com": "https://the-decoder.com/claude-creator-anthropic-reportedly-hits-350-billion-valuation-as-it-raises-another-10-billion/",
    # Regional (India)
    "livemint.com": "https://www.livemint.com/global/china-warns-ai-startups-seeking-to-emulate-meta-deal-not-so-fast-11767874471237.html",
    "hindustantimes.com": "https://www.hindustantimes.com/world-news/us-news/why-did-b-la-fleck-withdraw-from-kennedy-center-show-musician-makes-major-announcement-performing-there-has-become-101767773254451.html",
    "ndtvprofit.com": "https://www.ndtvprofit.com/amp/business/anthropic-is-raising-10-billion-at-a-350-billion-valuation",
}


async def test_single_url(domain: str, url: str) -> dict:
    """Test crawling a single URL with improved settings."""
    result = {
        "domain": domain,
        "url": url,
        "success": False,
        "status_code": 0,
        "content_length": 0,
        "word_count": 0,
        "validation": "not_tested",
        "fail_reason": None,
        "sample_content": "",
    }

    try:
        print("  Crawling with improved settings...")
        crawl_result = await crawl_article(
            url,
            mode="undetected",
            skip_blocked=False,
            log_result=False,
        )

        result["status_code"] = crawl_result.get("status_code", 0)
        content = crawl_result.get("markdown", "")
        result["content_length"] = len(content) if content else 0

        # Get title for validation
        title = crawl_result.get("title", "")

        is_valid, reason, metrics = validate_content(content, title)
        result["word_count"] = metrics["word_count"]
        result["validation"] = reason
        result["success"] = is_valid

        if not is_valid:
            result["fail_reason"] = reason

        if content:
            result["sample_content"] = content[:300].replace("\n", " ")

    except Exception as e:
        result["fail_reason"] = f"crawl_error:{str(e)[:80]}"

    return result


async def main():
    print("=" * 80)
    print("RETEST FAILED POPULAR DOMAINS")
    print("With improved crawler settings:")
    print("  - wait_until: networkidle")
    print("  - scan_full_page: True")
    print("  - magic: True")
    print("  - simulate_user: True")
    print("  - wait_for_images: True")
    print("  - process_iframes: True")
    print("=" * 80)
    print()

    results = []
    total = len(FAILED_DOMAINS_TO_TEST)

    for i, (domain, url) in enumerate(FAILED_DOMAINS_TO_TEST.items()):
        print(f"[{i+1}/{total}] Testing: {domain}")
        print(f"  URL: {url[:70]}...")

        result = await test_single_url(domain, url)
        results.append(result)

        status = "✓ FIXED" if result["success"] else "✗ STILL FAILED"
        print(f"  {status} | Status={result['status_code']}, Words={result['word_count']}, Reason={result['validation']}")

        if result["sample_content"]:
            print(f"  Sample: {result['sample_content'][:100]}...")
        print()

        # Rate limit
        await asyncio.sleep(3)

    # Summary
    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)

    fixed = [r for r in results if r["success"]]
    still_failed = [r for r in results if not r["success"]]

    print(f"\nTotal tested: {len(results)}")
    print(f"✓ Fixed: {len(fixed)}")
    print(f"✗ Still failed: {len(still_failed)}")

    if fixed:
        print("\n🟢 FIXED DOMAINS:")
        for r in fixed:
            print(f"  - {r['domain']}: {r['word_count']} words")

    if still_failed:
        print("\n🔴 STILL FAILING:")
        for r in still_failed:
            print(f"  - {r['domain']}: {r['fail_reason']}")

    # Save results
    output_dir = Path(__file__).parent / "output"
    output_path = output_dir / "retest_results.json"

    with open(output_path, "w") as f:
        json.dump({
            "tested_at": datetime.now().isoformat(),
            "total": len(results),
            "fixed_count": len(fixed),
            "still_failed_count": len(still_failed),
            "results": results,
        }, f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
