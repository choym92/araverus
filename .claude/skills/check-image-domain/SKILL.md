---
name: check-image-domain
description: Check if a domain's og:image should be blocked (UNTRUSTED_IMAGE_DOMAINS)
user-invocable: true
argument-hint: <domain, e.g. "mexc.com" or "mexc">
---

# Check Image Domain

Evaluate whether `$ARGUMENTS` should be added to `UNTRUSTED_IMAGE_DOMAINS` in `scripts/lib/crawl_article.py`.

## Step 1: Current blocklist
Read `scripts/lib/crawl_article.py` and show the current `UNTRUSTED_IMAGE_DOMAINS` set.
Check if the domain is already blocked. If yes, tell the user and stop.

## Step 2: Query DB for articles from this domain
Run via Bash (cd scripts first):
```python
python3 -c "
from domain_utils import get_supabase_client
sb = get_supabase_client()
result = sb.table('wsj_crawl_results').select('id,resolved_domain,top_image,title,crawl_status').or_('resolved_domain.ilike.%<domain>%').execute()
total = len(result.data)
with_image = [r for r in result.data if r.get('top_image')]
unique_images = set(r['top_image'] for r in with_image)
print(f'Total articles: {total}')
print(f'With image: {len(with_image)}')
print(f'Unique images: {len(unique_images)}')
for img in unique_images:
    print(f'  - {img}')
print()
for r in with_image[:10]:
    print(f'[{r[\"crawl_status\"]}] {(r[\"title\"] or \"\")[:70]}')
    print(f'  img: {(r[\"top_image\"] or \"\")[:150]}')
    print()
"
```

## Step 3: Analyze and recommend
Present a summary table:

| Metric | Value |
|--------|-------|
| Total articles from domain | N |
| Articles with image | N |
| Unique image URLs | N |
| Generic/promo banners | N |
| Article-specific images | N |

**Decision criteria:**
- If ALL images are generic banners (same URL or clearly branded promo) -> recommend BLOCK
- If MOST images are generic but some look article-specific -> show examples, ask user
- If images are mostly article-specific -> recommend DO NOT BLOCK

## Step 4: Apply (if approved)
If the user confirms blocking:
1. Add the domain(s) to `UNTRUSTED_IMAGE_DOMAINS` in `scripts/lib/crawl_article.py` (keep alphabetical order)
2. Run `npm run lint:py` to verify
3. Report the change

## Rules
- Match both `.com` and `.co` variants (or other TLDs) if they exist in the data
- Use `ilike` for fuzzy domain matching in the query
- Never auto-apply without user confirmation
- Show actual image URLs so user can visually verify if needed
