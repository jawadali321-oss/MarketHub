#!/usr/bin/env python3
"""
MarketHub Session 2 — MISSING TEST CASES (gap-fill only)
Paste these sections into markethub_s2_test.py after section 11.
Requires: cat_id, product_id, seller_token, seller2_token, buyer_token, admin_token
from the existing shared state.
Run standalone: python3 markethub_s2_missing_tests.py
"""

import requests
import sys
import io
import csv
import time as _time

BASE  = "http://localhost:8000/api/v1"
HEALTH = "http://localhost:8000/api/health/"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

passed = failed = skipped = 0
section_passed = section_failed = 0

def safe_json(r):
    try: return r.json() or {}
    except: return {}

def test(name, condition, info=""):
    global passed, failed, section_passed, section_failed
    if condition:
        print(f"  {GREEN}✅ PASS{RESET} — {name}")
        passed += 1; section_passed += 1
    else:
        print(f"  {RED}❌ FAIL{RESET} — {name} {RED}{info}{RESET}")
        failed += 1; section_failed += 1

def skip(name, reason=""):
    global skipped
    print(f"  {YELLOW}⏭ SKIP{RESET} — {name} {YELLOW}({reason}){RESET}")
    skipped += 1

def section(title):
    global section_passed, section_failed
    section_passed = section_failed = 0
    print(f"\n{BLUE}{BOLD}{'='*58}{RESET}")
    print(f"{BLUE}{BOLD}  {title}{RESET}")
    print(f"{BLUE}{BOLD}{'='*58}{RESET}")

def summary():
    total = passed + failed
    print(f"\n{BOLD}{'='*58}{RESET}")
    print(f"{BOLD}  RESULTS: {passed}/{total} passed ({skipped} skipped){RESET}")
    if failed == 0:
        print(f"  {GREEN}{BOLD}🎉 ALL GAP TESTS PASSED!{RESET}")
    else:
        print(f"  {RED}{BOLD}❌ {failed} test(s) failed — see above{RESET}")
    print(f"{BOLD}{'='*58}{RESET}\n")

# ── shared state ─────────────────────────────────────
_ts = int(_time.time())
BUYER_EMAIL   = f"buyer_{_ts}@test.com"
SELLER_EMAIL  = f"seller_{_ts}@test.com"
SELLER2_EMAIL = f"seller2_{_ts}@test.com"
ADMIN_EMAIL   = f"admin_{_ts}@test.com"
PASSWORD = "TestPass1!"

buyer_token = seller_token = seller2_token = admin_token = ""
cat_id = product_id = None

def h(token): return {"Authorization": f"Bearer {token}"}

def register_and_login(email, role, store_name=None):
    payload = {"email": email, "password": PASSWORD,
               "password_confirm": PASSWORD,
               "first_name": "Test", "last_name": role.capitalize(), "role": role}
    if store_name: payload["store_name"] = store_name
    requests.post(f"{BASE}/auth/register/", json=payload)
    r = requests.post(f"{BASE}/auth/login/", json={"email": email, "password": PASSWORD})
    return r.json().get("data", {}).get("access", "")

def make_csv(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "title", "price", "category_id", "stock", "currency",
        "description", "compare_at_price"
    ])
    writer.writeheader(); writer.writerows(rows)
    return buf.getvalue().encode("utf-8")

# ════════════════════════════════════════════════════
section("0. PRE-FLIGHT & AUTH SETUP")
# ════════════════════════════════════════════════════

try:
    r = requests.get(HEALTH, timeout=5)
    test("Server reachable", r.status_code == 200)
    d = safe_json(r).get("data", {})
    test("DB ok", d.get("db") == "ok")
    test("Redis ok", d.get("redis") == "ok")
except Exception as e:
    print(f"  {RED}❌ Server not reachable: {e}{RESET}")
    sys.exit(1)

buyer_token   = register_and_login(BUYER_EMAIL, "buyer")
seller_token  = register_and_login(SELLER_EMAIL, "seller", "Store One")
seller2_token = register_and_login(SELLER2_EMAIL, "seller", "Store Two")
admin_token   = register_and_login(ADMIN_EMAIL, "admin")

test("Buyer token",   len(buyer_token) > 0)
test("Seller token",  len(seller_token) > 0)
test("Seller2 token", len(seller2_token) > 0)
test("Admin token",   len(admin_token) > 0)

# Admin creates category for tests
r = requests.post(f"{BASE}/categories/", json={
    "name": "Electronics", "slug": f"elec-{_ts}",
    "level": 1, "display_order": 1, "is_active": True, "parent": None
}, headers=h(admin_token))
cat_id = safe_json(r).get("id")
test("Category created for tests", cat_id is not None, f"status {r.status_code}")

# Seller creates product for tests
if cat_id:
    r = requests.post(f"{BASE}/products/", json={
        "title": "Test Phone", "price": "10000.00",
        "currency": "PKR", "stock": 5, "category": cat_id,
        "discount_pct": "10.00",
        "compare_at_price": "12000.00",
    }, headers=h(seller_token))
    product_id = safe_json(r).get("id")
    test("Product created for tests", product_id is not None, f"status {r.status_code}")

# ════════════════════════════════════════════════════
section("12. CATEGORY DELETE (ADMIN ONLY)")
# ════════════════════════════════════════════════════

# Create a throwaway category to delete
r = requests.post(f"{BASE}/categories/", json={
    "name": "ToDelete", "slug": f"to-delete-{_ts}",
    "level": 1, "display_order": 99, "is_active": True
}, headers=h(admin_token))
del_cat_id = safe_json(r).get("id")

if del_cat_id:
    # Buyer cannot delete
    r = requests.delete(f"{BASE}/categories/{del_cat_id}/", headers=h(buyer_token))
    test("Buyer delete category — 403", r.status_code == 403, f"got {r.status_code}")

    # Seller cannot delete
    r = requests.delete(f"{BASE}/categories/{del_cat_id}/", headers=h(seller_token))
    test("Seller delete category — 403", r.status_code == 403, f"got {r.status_code}")

    # No token
    r = requests.delete(f"{BASE}/categories/{del_cat_id}/")
    test("No token delete category — 401/403", r.status_code in (401, 403), f"got {r.status_code}")

    # Admin deletes
    r = requests.delete(f"{BASE}/categories/{del_cat_id}/", headers=h(admin_token))
    test("Admin delete category — 204", r.status_code == 204, f"got {r.status_code}")

    # Verify gone
    r = requests.get(f"{BASE}/categories/{del_cat_id}/")
    test("Deleted category — 404", r.status_code == 404, f"got {r.status_code}")
else:
    skip("Category delete tests", "could not create throwaway category")

# ════════════════════════════════════════════════════
section("13. CATEGORY RETRIEVE BY ID")
# ════════════════════════════════════════════════════

if cat_id:
    r = requests.get(f"{BASE}/categories/{cat_id}/")
    d = safe_json(r)
    test("Retrieve category by id — 200", r.status_code == 200, f"got {r.status_code}")
    test("Retrieve — correct id", d.get("id") == cat_id)
    test("Retrieve — has name", "name" in d)
    test("Retrieve — has slug", "slug" in d)
    test("Retrieve — has level", "level" in d)
    test("Retrieve — has is_active", "is_active" in d)
else:
    skip("Category retrieve", "no cat_id")

# ════════════════════════════════════════════════════
section("14. PRODUCT FULL PUT (UPDATE)")
# ════════════════════════════════════════════════════

if product_id and cat_id:
    # Seller full PUT own product
    r = requests.put(f"{BASE}/products/{product_id}/", json={
        "title": "Test Phone Updated",
        "price": "11000.00",
        "currency": "PKR",
        "stock": 8,
        "category": cat_id,
        "description": "Updated via PUT",
    }, headers=h(seller_token))
    d = safe_json(r)
    test("Seller full PUT own product — 200", r.status_code == 200, f"got {r.status_code}")
    test("PUT — title updated", d.get("title") == "Test Phone Updated")
    test("PUT — price updated", str(d.get("price")) == "11000.00")
    test("PUT — stock updated", d.get("stock") == 8)

    # Seller2 cannot full PUT
    r = requests.put(f"{BASE}/products/{product_id}/", json={
        "title": "Hacked", "price": "1.00", "currency": "PKR",
        "stock": 0, "category": cat_id
    }, headers=h(seller2_token))
    test("Seller2 full PUT — 403/404", r.status_code in (403, 404), f"got {r.status_code}")

    # Buyer cannot full PUT
    r = requests.put(f"{BASE}/products/{product_id}/", json={
        "title": "Hacked", "price": "1.00", "currency": "PKR",
        "stock": 0, "category": cat_id
    }, headers=h(buyer_token))
    test("Buyer full PUT — 403", r.status_code == 403, f"got {r.status_code}")

    # No token
    r = requests.put(f"{BASE}/products/{product_id}/", json={
        "title": "X", "price": "1.00", "currency": "PKR",
        "stock": 0, "category": cat_id
    })
    test("No token full PUT — 401", r.status_code == 401, f"got {r.status_code}")
else:
    skip("Full PUT tests", "no product_id or cat_id")

# ════════════════════════════════════════════════════
section("15. IS_ON_SALE & DISCOUNT LOGIC")
# ════════════════════════════════════════════════════

if cat_id:
    from datetime import datetime, timezone, timedelta

    # Product with discount_pct but no date window → always on sale
    r = requests.post(f"{BASE}/products/", json={
        "title": "Always On Sale", "price": "1000.00",
        "currency": "PKR", "stock": 10, "category": cat_id,
        "discount_pct": "20.00",
    }, headers=h(seller_token))
    d = safe_json(r)
    pid_sale = d.get("id")
    test("Create discounted product — 201", r.status_code == 201, f"got {r.status_code}")

    if pid_sale:
        r = requests.get(f"{BASE}/products/{pid_sale}/")
        d = safe_json(r)
        test("is_on_sale = True (discount, no window)", d.get("is_on_sale") == True)
        test("current_price discounted (800.00)", str(d.get("current_price")) == "800.00")

    # Product with sale window in the past → NOT on sale
    past_start = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
    past_end   = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    r = requests.post(f"{BASE}/products/", json={
        "title": "Expired Sale", "price": "1000.00",
        "currency": "PKR", "stock": 10, "category": cat_id,
        "discount_pct": "20.00",
        "sale_start": past_start, "sale_end": past_end,
    }, headers=h(seller_token))
    d = safe_json(r)
    pid_expired = d.get("id")
    test("Create expired-sale product — 201", r.status_code == 201, f"got {r.status_code}")

    if pid_expired:
        r = requests.get(f"{BASE}/products/{pid_expired}/")
        d = safe_json(r)
        test("is_on_sale = False (past window)", d.get("is_on_sale") == False)
        test("current_price = full price (1000.00)", str(d.get("current_price")) == "1000.00")

    # Product with active sale window → on sale
    now = datetime.now(timezone.utc)
    active_start = (now - timedelta(days=1)).isoformat()
    active_end   = (now + timedelta(days=1)).isoformat()
    r = requests.post(f"{BASE}/products/", json={
        "title": "Active Sale", "price": "1000.00",
        "currency": "PKR", "stock": 10, "category": cat_id,
        "discount_pct": "25.00",
        "sale_start": active_start, "sale_end": active_end,
    }, headers=h(seller_token))
    d = safe_json(r)
    pid_active = d.get("id")
    test("Create active-sale product — 201", r.status_code == 201, f"got {r.status_code}")

    if pid_active:
        r = requests.get(f"{BASE}/products/{pid_active}/")
        d = safe_json(r)
        test("is_on_sale = True (active window)", d.get("is_on_sale") == True)
        test("current_price discounted (750.00)", str(d.get("current_price")) == "750.00")
else:
    skip("Sale logic tests", "no cat_id")

# ════════════════════════════════════════════════════
section("16. IMAGE 10-LIMIT ENFORCEMENT")
# ════════════════════════════════════════════════════

# Minimal valid PNG (1×1 px)
TINY_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
    b'\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18'
    b'\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)

if cat_id:
    # Create a dedicated product for 10-limit test
    r = requests.post(f"{BASE}/products/", json={
        "title": "Image Limit Product", "price": "500.00",
        "currency": "PKR", "stock": 1, "category": cat_id,
    }, headers=h(seller_token))
    limit_pid = safe_json(r).get("id")

    if limit_pid:
        # Upload 10 images
        success_uploads = 0
        for i in range(10):
            r = requests.post(
                f"{BASE}/products/{limit_pid}/images/",
                files={"image": (f"img{i}.png", io.BytesIO(TINY_PNG), "image/png")},
                headers=h(seller_token),
            )
            if r.status_code == 201:
                success_uploads += 1

        test("10 images uploaded successfully", success_uploads == 10, f"only {success_uploads} succeeded")

        # 11th upload must be rejected
        r = requests.post(
            f"{BASE}/products/{limit_pid}/images/",
            files={"image": ("img11.png", io.BytesIO(TINY_PNG), "image/png")},
            headers=h(seller_token),
        )
        d = safe_json(r)
        test("11th image — rejected 400", r.status_code == 400, f"got {r.status_code}")
        test("11th image — limit message", "10" in str(d) or "maximum" in str(d).lower())

        # First uploaded image should be primary
        r = requests.get(f"{BASE}/products/{limit_pid}/")
        images = safe_json(r).get("images", [])
        primary_count = sum(1 for img in images if img.get("is_primary"))
        test("Exactly 1 image is primary", primary_count == 1)
    else:
        skip("Image limit tests", "could not create product")
else:
    skip("Image limit tests", "no cat_id")

# ════════════════════════════════════════════════════
section("17. BULK UPLOAD — REMAINING GAPS")
# ════════════════════════════════════════════════════

# Admin blocked (role != seller)
r = requests.post(f"{BASE}/products/bulk-upload/",
    files={"file": ("x.csv", io.BytesIO(b"title,price,category_id,stock,currency\n"), "text/csv")},
    headers=h(admin_token))
d = safe_json(r)
test("Admin bulk upload — 403", r.status_code == 403, f"got {r.status_code}")
test("Admin bulk — detail mentions seller", "seller" in str(d).lower())

# Empty CSV (header only, 0 data rows)
if cat_id:
    empty_csv = make_csv([])
    r = requests.post(f"{BASE}/products/bulk-upload/",
        files={"file": ("empty.csv", io.BytesIO(empty_csv), "text/csv")},
        headers=h(seller_token))
    d = safe_json(r)
    test("Empty CSV — 201", r.status_code == 201, f"got {r.status_code}")
    test("Empty CSV — success_count=0", d.get("success_count") == 0, f"got {d.get('success_count')}")
    test("Empty CSV — error_count=0", d.get("error_count") == 0, f"got {d.get('error_count')}")

    # Invalid compare_at_price decimal in CSV
    bad_compare_csv = make_csv([{
        "title": "Bad Compare", "price": "500", "category_id": cat_id,
        "stock": "3", "currency": "PKR",
        "description": "", "compare_at_price": "notanumber",
    }])
    r = requests.post(f"{BASE}/products/bulk-upload/",
        files={"file": ("bad_compare.csv", io.BytesIO(bad_compare_csv), "text/csv")},
        headers=h(seller_token))
    d = safe_json(r)
    # Should either be 400 or 201 with error_count=1 (not crash with 500)
    test("Invalid compare_at_price — no 500 crash", r.status_code != 500, f"got {r.status_code}")
    test("Invalid compare_at_price — handled gracefully", r.status_code in (200, 201, 400))
else:
    skip("Bulk upload gap tests", "no cat_id")

# ════════════════════════════════════════════════════
section("18. CURRENCY CHOICES VALIDATION")
# ════════════════════════════════════════════════════

if cat_id:
    # Valid non-PKR currencies
    for currency in ["USD", "EUR", "GBP", "AED", "SAR", "MYR"]:
        r = requests.post(f"{BASE}/products/", json={
            "title": f"Product in {currency}", "price": "100.00",
            "currency": currency, "stock": 1, "category": cat_id,
        }, headers=h(seller_token))
        test(f"Currency {currency} accepted — 201", r.status_code == 201, f"got {r.status_code}")

    # Invalid currency
    r = requests.post(f"{BASE}/products/", json={
        "title": "Bad Currency", "price": "100.00",
        "currency": "XYZ", "stock": 1, "category": cat_id,
    }, headers=h(seller_token))
    test("Invalid currency XYZ — rejected 400", r.status_code == 400, f"got {r.status_code}")
else:
    skip("Currency tests", "no cat_id")

# ════════════════════════════════════════════════════
section("19. CATEGORY unique_together (name + parent)")
# ════════════════════════════════════════════════════

if cat_id:
    # Create child with name "Phones"
    r = requests.post(f"{BASE}/categories/", json={
        "name": "Phones", "slug": f"phones-a-{_ts}",
        "level": 2, "parent": cat_id, "is_active": True
    }, headers=h(admin_token))
    test("Create child 'Phones' — 201", r.status_code == 201, f"got {r.status_code}")

    # Same name + same parent → rejected
    r = requests.post(f"{BASE}/categories/", json={
        "name": "Phones", "slug": f"phones-b-{_ts}",
        "level": 2, "parent": cat_id, "is_active": True
    }, headers=h(admin_token))
    test("Dup name+parent — rejected 400", r.status_code == 400, f"got {r.status_code}")
else:
    skip("unique_together test", "no cat_id")

# ════════════════════════════════════════════════════
summary()
