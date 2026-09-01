---
name: vibecoding
description: >
  Enforce battle-tested testing methodology and bug prevention when building UI features
  with AI. Activates the "seed-first, content-not-structure" workflow that prevents the
  #1 vibecoding failure: green test suites with broken UIs.

  Use when: (1) writing E2E/Playwright/Cypress browser tests, (2) building or modifying
  UI features (templates, pages, dashboards, admin panels), (3) user says /vibecoding,
  (4) debugging "tests pass but UI is broken" situations, (5) reviewing E2E test code.

  Proactively suggest when: the user is about to write E2E tests, building a new page
  or dashboard, or reports that something works in tests but not in the browser.
---

# Vibecoding: Build Systems That Actually Work

Three laws. Follow all three or the UI will ship broken while tests pass green.

## The Three Laws

1. **Test content, not structure.** `int(el.text) >= 1` not `el.count() >= 1`
2. **Test the JS path, not just the server path.** Click the tab, check what renders.
3. **Test combinations, not just singles.** Filter A + Filter B, then reset.

## Workflow: Before Writing Any Code

1. **Create a seed script** that populates realistic data covering all states and domains
2. **Start the dev server**, seed data, open in browser
3. **Click every button and filter combination** -- note what breaks
4. **Then** write tests for what you observed

Never write E2E tests without first manually using the feature.

## Writing Tests That Catch Bugs

### Content Rule
Assert on rendered text values, not DOM element counts:
```python
# BAD
assert page.locator(".stat-item").count() >= 3

# GOOD
text = page.locator("#statPending").inner_text().strip()
assert text.isdigit() and int(text) >= 1, f"Pending shows '{text}'"
```

### Known-Value Rule
Seed a specific item, assert its exact title appears in rendered HTML:
```python
list_text = page.locator("#reviewList").inner_text()
assert "Churn is MRR-based" in list_text, f"Missing: {list_text[:300]}"
```

### Empty-State Rule
Always assert empty-state messages do NOT appear when data exists:
```python
assert "No matching knowledge items found" not in list_text
assert "Error loading" not in review_text
```

### Console-Error Rule
Add a JS error catcher test -- catches 50% of frontend bugs alone:
```python
def test_no_js_errors(page):
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(url)
    page.wait_for_timeout(2000)
    assert not [e for e in errors if "Failed to" in e or "TypeError" in e]
```

### Two-Path Rule
Server-side rendering and client-side JS fetch are separate code paths. Test both:
- Initial page load = server rendering
- Clicking a filter/tab = JS fetch + render
- Both must show the same data

### Cross-Filter Rule
Test filter combinations and resets, not just individual filters:
```python
page.select_option("#domainFilter", "finance")
page.wait_for_timeout(1500)
assert page.locator("#knowledgeList .knowledge-item").count() >= 1
```

## Bug Pattern Catalog

Check for these during code review. See [references/bug_patterns.md](references/bug_patterns.md) for full details with prevention strategies.

| Pattern | Symptom | Quick Check |
|---------|---------|-------------|
| API prefix mismatch | Empty lists, silent 404s | Console-error test |
| Field name divergence | Data exists but UI shows zeros | Known-value assertion |
| Pagination off-by-one | 500 on page load | Page clamp: `max(page, 1)` |
| Hardcoded UI elements | Filters return empty | Dynamic generation from data |
| Template type mismatch | 500 Internal Server Error | Load page with seeded data |
| Cross-filter stacking | Domain filter shows nothing | Reset filters on change |

## 5-Second Smoke Test

Before declaring any UI work complete, verify:
1. Page loads without 500?
2. Stats show nonzero numbers?
3. Lists show actual items?
4. Clicking a filter shows results?
5. Browser console is clean?

If any fail, the feature is not done.
