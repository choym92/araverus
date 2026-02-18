<!-- Updated: 2026-02-16 -->
# Security / A11y / Testing

### Secrets
Live only in `.env*`; never commit. Mask in logs/errors.

```typescript
// GOOD: Use env variable, mask in logs
const key = process.env.SUPABASE_SERVICE_KEY!;
console.log('Key loaded:', key ? '***' : 'MISSING');

// BAD: Hardcoded or logged secret
const key = 'sbp_abc123...';
console.log('Using key:', key);
```

### Accessibility
ARIA labels, focus management, color contrast. Never use `alert()` — use accessible error UI.

### Testing
For new/changed logic, provide at least **1 happy + 1 edge** unit test. E2E optional.
Test runner: `npm run test` (vitest).

```typescript
// Test structure: 1 happy path + 1 edge case
describe('formatDate', () => {
  it('formats a valid date', () => {
    expect(formatDate('2026-01-15')).toBe('January 15, 2026');
  });

  it('returns fallback for invalid input', () => {
    expect(formatDate('')).toBe('Unknown date');
  });
});
```
