# Bug Pattern Catalog

Six patterns that cause "green tests, broken UI." Check for each during code review.

## 1. API Prefix Mismatch

**Symptom:** JS fetch returns 404, empty-state messages appear, no console errors (caught silently in try/catch)
**Cause:** Template JS hardcodes one URL prefix (`/api/corporate-memory/`), API router uses another (`/api/memory/`)
**Test:** Console-error-catcher test + content assertion on JS-rendered sections
**Prevention:** Define the API prefix as a JS constant from the server:
```javascript
const API_PREFIX = '{{ api_prefix }}';
// Then: fetch(`${API_PREFIX}/admin/pending?${params}`)
```

## 2. Field Name Divergence

**Symptom:** Data exists in API response but UI shows nothing or zeros
**Cause:** JS reads `entry.admin`, API returns `user_id`. JS does `item.tags.map()`, API returns a JSON string `"[\"a\",\"b\"]"`.
**Test:** Assert specific known values appear in rendered HTML
**Prevention:** Parse defensively:
```javascript
function parseJsonField(val) {
    if (Array.isArray(val)) return val;
    if (typeof val === 'string') { try { return JSON.parse(val); } catch { return []; } }
    return [];
}
```

## 3. Pagination Off-By-One

**Symptom:** 500 errors on initial page load, works after clicking "next page"
**Cause:** JS initializes `page = 0`, API expects `page >= 1`, offset becomes negative (`(0-1)*50 = -50`)
**Test:** Check that initial page load doesn't produce errors
**Prevention:** API must always clamp: `page = max(page, 1)`. JS must initialize page variables to 1.

## 4. Hardcoded UI vs Dynamic Data

**Symptom:** Filter buttons exist but clicking any of them returns empty results
**Cause:** Button labels hardcoded ("Performance", "API") but actual data has different categories ("business_logic", "metric_definition")
**Test:** Assert that clicking a filter button returns results (not empty state)
**Prevention:** Generate UI elements from actual data:
```jinja
{% for cat in categories %}
<button data-category="{{ cat }}">{{ cat|replace('_', ' ')|title }}</button>
{% endfor %}
```

## 5. Jinja/Template Type Mismatch

**Symptom:** 500 Internal Server Error on page load
**Cause:** Template does `c.detected_at[:10]` on a datetime object (not a string). Or `GROUPS.map()` on a dict `{}` instead of an array.
**Test:** Simply loading the page with seeded data catches this immediately
**Prevention:**
- Always use `|string` filter before slicing: `{{ (c.detected_at|string)[:10] }}`
- Always convert dicts to lists in the router before passing to JS: `list(groups.values())`

## 6. Silent Cross-Filter Empty Results

**Symptom:** User selects a domain, sees nothing, thinks the filter is broken
**Cause:** A category filter was still active from a previous click. Category "technical_spec" + domain "product" = 0 results (correct but confusing).
**Test:** Test filter combinations and resets
**Prevention:** Reset other filters when one changes:
```javascript
function onDomainChange() {
    // Reset category to "All" when domain changes
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    document.querySelector('.filter-btn[data-category=""]').classList.add('active');
    currentCategory = '';
    applyFilters();
}
```
