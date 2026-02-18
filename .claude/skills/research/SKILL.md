---
name: research
description: Research a topic using web search and codebase analysis without modifying any files. Use for investigating best practices, libraries, APIs, or understanding existing code.
user-invocable: true
argument-hint: [topic or question]
context: fork
model: sonnet
allowed-tools: Read, Glob, Grep, WebSearch, WebFetch, mcp__context7__resolve-library-id, mcp__context7__query-docs
---

# Research

Investigate `$ARGUMENTS` thoroughly without modifying any files.

## Process

1. **Understand the Question:**
   - What specifically needs to be researched?
   - Is this about the codebase, an external technology, or both?

2. **Codebase Analysis (if relevant):**
   - Search for related code, patterns, and implementations
   - Understand existing architecture and conventions
   - Map dependencies and relationships

3. **Web Research (if relevant):**
   - Search for best practices, documentation, tutorials
   - Use Context7 for library-specific docs
   - Compare different approaches with trade-offs

4. **Synthesize Findings:**

```markdown
# Research: [Topic]

## Summary
One paragraph overview of findings.

## Key Findings
1. Finding with explanation
2. Finding with explanation

## Codebase Context
- What exists in our codebase related to this
- Current patterns and conventions

## Recommendations
- Recommended approach with reasoning
- Alternatives considered and why not chosen

## Sources
- Links to relevant docs, articles, repos
```

## Rules
- **DO NOT** create, edit, or write any files
- **DO NOT** run any commands that modify state
- Focus on gathering and synthesizing information
- Be specific with source attribution
