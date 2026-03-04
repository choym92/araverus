<!-- Created: 2026-03-02 -->
# News Legal Compliance — Copyright & Content Risk Mitigation

## Problem

Current news pipeline (WSJ → AI summary → araverus.com) has legal risks:
- **Headlines**: identical to WSJ originals
- **Images**: crawled from source articles (AP/Reuters/Getty risk)
- **Summaries**: AI-generated but derivative of copyrighted articles
- **Scale**: systematic, automated collection of hundreds of articles

---

## Risk Assessment

### Headlines — Medium Risk
- Individual headlines generally not copyrightable
- But **systematic bulk extraction** triggers "hot news" doctrine (AP vs. INS, 1918)
- WSJ could argue unfair competition if headlines are copied verbatim at scale

### AI Summaries — Low-Medium Risk
- Facts are not copyrightable — reporting factual content is OK
- But reproducing the **structure, analysis, or unique expression** of the original = derivative work
- **NYT vs OpenAI (2023-ongoing)** lawsuit is testing exactly this boundary
- Current legal landscape: unsettled, but trending toward stricter enforcement

### Crawled Images — HIGH Risk
- Wire service images (AP, Reuters, Getty) are **aggressively enforced**
- Using `top_image` from crawled articles = almost certainly copyrighted
- DMCA takedown notices are automated and common
- Statutory damages: $750–$30,000 per image (up to $150,000 if willful)

### Scale Factor
- Automated, systematic collection increases all risks
- Looks more like a "news aggregator competing with the source" than fair use
- Google may also penalize as duplicate content (SEO risk)

---

## Current vs. Target State

| Element | Current | Target | Priority |
|---------|---------|--------|----------|
| **Headlines** | WSJ verbatim | AI-rewritten | High |
| **Images** | Crawled `top_image` | Remove or replace | **Critical** |
| **Summaries** | AI-generated from full text | Keep, add attribution | Medium |
| **Source attribution** | Link to original | "Based on reporting by [source]" + link | Medium |
| **robots.txt** | Not checked | Respect per-site robots.txt | Medium |

---

## Action Items

### 1. AI Headline Rewrite (High Priority)
- LLM pipeline already summarizes articles → add headline rewrite step
- Prompt: generate a factual, neutral headline that conveys the same news without copying phrasing
- Store both `original_title` (internal reference) and `display_title` (shown to users)
- Pipeline location: `scripts/` LLM analysis phase

### 2. Remove Crawled Images (Critical Priority)
- Stop using `top_image` from `wsj_crawl_results` on the frontend
- Options for replacement:
  - **No image**: Typography-focused card design (cleanest legally)
  - **Sector icons**: Generic icons per sector/category (Tech, Finance, etc.)
  - **AI-generated**: Use DALL-E/Stable Diffusion to generate abstract illustrations per category
  - **Stock photos**: Unsplash/Pexels (free, requires attribution for some)
  - **OG image generation**: Auto-generate branded cards with headline text (Vercel OG)
- Recommendation: **No image + sector icons** (zero legal risk, minimal effort)

### 3. Source Attribution (Medium Priority)
- Add visible attribution: "Based on reporting by [source_name]"
- Keep link to original article
- Add footer disclaimer: "araverus.com aggregates and summarizes publicly reported news. All original reporting belongs to the respective publishers."

### 4. robots.txt Compliance (Medium Priority)
- Check robots.txt of crawled domains before fetching
- Respect `Disallow` directives
- Add `crawl-delay` if specified
- Log compliance status per domain

---

## Legal References

| Case / Doctrine | Relevance |
|----------------|-----------|
| **AP v. INS (1918)** | "Hot news" doctrine — systematic copying of breaking news = unfair competition |
| **NYT v. OpenAI (2023)** | AI summarization of copyrighted articles — ongoing, will set precedent |
| **Google v. Oracle (2021)** | Fair use of functional elements (APIs) — may support factual summarization |
| **DMCA Safe Harbor** | Respond promptly to takedown notices to limit liability |
| **Fair Use (17 U.S.C. § 107)** | Transformative use + small portion + non-commercial + no market harm = stronger defense |

### Fair Use Factors for Our Case
1. **Purpose**: Informational/educational — somewhat favorable
2. **Nature of original**: Factual reporting — favorable (facts aren't copyrightable)
3. **Amount used**: AI summary (not full text) — favorable
4. **Market effect**: Could reduce need to visit WSJ — unfavorable

---

## Realistic Risk Level

- **Individual blogger / low traffic**: WSJ unlikely to sue → but DMCA takedowns possible
- **Images**: Most likely trigger for enforcement (automated detection by Getty/AP)
- **SEO**: Google may deprioritize if content looks duplicative

**Bottom line**: Fix images first (highest risk, easiest to fix), then headlines (medium effort), then attribution (low effort).

---

## Implementation Notes

- Headline rewrite can be added to existing LLM analysis step (minimal pipeline change)
- Image removal is a frontend-only change (stop rendering `top_image`)
- Attribution is a frontend-only change (add text to article detail page)
- robots.txt check goes into crawl scripts
