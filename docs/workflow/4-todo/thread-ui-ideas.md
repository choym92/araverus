<!-- Created: 2026-03-05 -->
# Thread/Stories UI Ideas

## Current Implementations
1. **ArticleCard carousel** — card footer `◀ 3/7 ▶ Thread Title` slide
2. **StoriesTab** — `/news?tab=stories` accordion (thread → articles)
3. **TimelineSection** — `/news/[slug]` article detail page vertical timeline

---

## Ideas

### A. Today Tab — Thread Group Headers
Group threaded articles under thread headers instead of flat list:
```
── Fed Rate Decision (5 articles) ──────
  [Featured card]  [Standard] [Standard]
── US-Iran Tensions (8 articles) ───────
  [Featured card]  [Standard] [Standard]
── Standalone articles ─────────────────
  [Card] [Card] [Card] ...
```

### B. Today Tab — "Trending Threads" Banner
Horizontal scroll pill bar at top of Today tab:
```
🔥 Fed Rate Decision (5)  |  US-Iran (8)  |  Epstein Files (4)  |  →
```
Click → jump to thread detail or filter articles by that thread.

### C. Article Detail — Thread Context Card
Above TimelineSection, add a summary card:
```
┌─────────────────────────────────┐
│ 📰 Part of: Fed Rate Decision   │
│ 29 articles · Feb 1 – Mar 5     │
│ This story is about...          │
│ [View Full Thread →]            │
└─────────────────────────────────┘
```

### D. Article Detail — Related Threads
Below RelatedSection, recommend threads by embedding similarity:
```
Related Stories
├── Gold Price Surge (12 articles, ●●●)
├── Commodity Markets (8 articles, ●●)
└── Mining Industry (4 articles, ●)
```

### E. Stories Tab — Thread Card Redesign
Replace text-only accordion with visual cards:
```
┌──────────────────────────────────┐
│ Fed Rate Decision          ●●●  │
│ 29 articles · Feb 1 – Mar 5     │
│ ┌────┐ ┌────┐ ┌────┐            │
│ │img1│ │img2│ │img3│  ← recent  │
│ └────┘ └────┘ └────┘            │
│ Latest: "Fed holds at 4.5%..."  │
└──────────────────────────────────┘
```

### F. Thread Detail Page `/news/thread/[id]`
Dedicated page for each thread:
- Thread title + summary
- Full timeline (expanded TimelineSection)
- Related threads
- All articles with images
- Heat/activity visualization

### G. ArticleCard Carousel — Thread Title Link
Make thread title in carousel clickable → navigates to thread detail page or Stories tab.

---

## Priority

| Rank | Idea | Effort | Impact | Notes |
|------|------|--------|--------|-------|
| 1 | **F. Thread detail page** | Med | High | Landing destination for the new tab |
| 2 | **E. Stories card redesign** | Med | High | Current accordion is plain |
| 3 | **B. Trending Threads banner** | Low | Med | Thread discovery on Today tab |
| 4 | **C. Thread context card** | Low | Med | Adds context to article detail |
| 5 | **A. Thread group headers** | Med | High | Today tab structure overhaul, more complex |
| 6 | **G. Carousel link** | Low | Low | Small QoL improvement |
| 7 | **D. Related threads** | Med | Med | Cross-thread discovery, later phase |
