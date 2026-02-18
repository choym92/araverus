---
name: browse
description: Browser navigation, screenshots, and UI testing using Playwright MCP.
user-invocable: true
argument-hint: [url] [optional instruction]
context: fork
allowed-tools: mcp__playwright__browser_navigate, mcp__playwright__browser_screenshot, mcp__playwright__browser_click, mcp__playwright__browser_type, mcp__playwright__browser_console_messages, mcp__playwright__browser_close
---

# /browse — Browser Navigation & Testing

Navigate to a URL, take a screenshot, check for errors, and optionally interact.

## Process

1. **Navigate** to the provided URL (default: `http://localhost:3000`)
   - If localhost is not running, suggest `npm run dev` first

2. **Screenshot** the current page
   - Analyze visually for layout issues, broken elements, or errors

3. **Check console** for errors
   - Report JS errors, warnings, or failed network requests

4. **Interact** if the user requested specific actions (click, fill, scroll)
   - Take a follow-up screenshot after interaction

5. **Report** a concise summary:
   - Page title and URL
   - Visual state (OK / broken elements / loading issues)
   - Console errors (if any)

## Rules
- Always take at least one screenshot
- Report console errors even if the page looks fine visually
- Keep the summary short — focus on problems found
