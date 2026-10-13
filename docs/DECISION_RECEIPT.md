# Engineering Decision Receipt — Menu-item price representation and validation

**Milestone:** M1 — First Vertical Slice  
**Status:** Implemented in the application; receipt awaiting teammate review  
**Decision recorded:** 2026-10-13 (documents the previously adopted rule)  
**Related work:** [Decision task #41](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/41), [documentation task #64](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/64), [API contract #30](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/issues/30), and [merged PR #55](https://github.com/gwan-kib/COSC-310-Lab-Food4Thought/pull/55)

## Problem

Food4Thought needs menu-item prices that are predictable to validate, save, and return through the API. Ordinary floating-point numbers can introduce small rounding errors, while accepting arbitrary input makes stored prices inconsistent. We also need to handle invalid prices without modifying saved data.

## Decision

Use **JSON strings** for prices and Python's **`Decimal`** to validate them. Accept only nonnegative values with at most two decimal places, normalize valid prices to exactly two places, and enforce an inclusive **999.00** maximum. Apply the same rules to created items, updated items, and prices read from JSON.

The 999.00 cap is a **team-chosen limit**, confirmed for both input and stored data on 2026-10-12. It is **not an instructor-mandated price** or a documented stakeholder requirement. This receipt records an already adopted rule; it does not introduce a new one.

## Why this approach

- Decimal strings and `Decimal` avoid binary floating-point representation problems for money-like values.
- A consistent two-decimal format keeps API responses and JSON data predictable.
- One shared price rule catches bad inputs and invalid stored records in the same way.
- A finite upper limit rejects prices outside the range we agreed to support in M1. **999.00 is a practical team choice, not a mathematically required threshold.**

## Alternatives and trade-offs

| Option | Advantage | Trade-off |
| --- | --- | --- |
| **Chosen: decimal strings + `Decimal` + 999.00 cap** | Exact decimal representation, consistent formatting and validation | Clients must send a string; the cap may reject a legitimate expensive item |
| JSON numbers / binary floating point | Convenient for many clients | Potential precision and rounding problems |
| Integer cents | Exact representation | Clients must convert values and agree on units |
| No upper price cap | More flexible for unusual items | No agreed ceiling to catch out-of-range entries |

These are reasonable **comparison alternatives**, not a claim that the team formally evaluated each one before adopting the rule.

## What the code actually does

- [`app/schemas/restaurant.py`](../app/schemas/restaurant.py) defines `MAX_MENU_ITEM_PRICE`, `WritePrice`, and `normalize_price()`. The model accepts a price string matching `^[0-9]+(\.[0-9]{1,2})?$`; it converts through `Decimal` and returns a string with two decimal places.
- [`app/api/routes/restaurants.py`](../app/api/routes/restaurants.py) applies this schema to **POST** `/restaurants/{restaurant_id}/menu/items` and **PATCH** `/restaurants/{restaurant_id}/menu/items/{item_id}`. Invalid request prices return **422**.
- [`app/repositories/restaurant.py`](../app/repositories/restaurant.py) validates complete records when loading and before saving. An invalid price in stored JSON causes a **generic 500**, rather than silently correcting or rewriting the file.
- [`tests/test_menu_price_limit.py`](../tests/test_menu_price_limit.py) checks both write operations, boundary prices, rejected inputs without writes, invalid stored records, and API error behavior.

| Input / situation | Result |
| --- | --- |
| `"12.5"` | Saved and returned as `"12.50"` |
| `"999"` | Saved and returned as `"999.00"` |
| `"999.01"` submitted through create/update | **422**; saved data unchanged |
| JSON number `12.5` or string `"1.234"` | **422**; invalid input |
| `"999.01"` already present in stored JSON | **500** (generic storage error); file unchanged |

## Consequences and limits

A future requirement for items over 999.00 would require revisiting the cap, schemas, stored-data policy, and tests. The current design does not define tax, currency conversion, payments, or an order-total calculation. It validates *menu-item prices*, not entire transactions.
