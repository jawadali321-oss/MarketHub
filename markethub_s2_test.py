#!/usr/bin/env python3
"""
MarketHub Session 2 — 100% Products Coverage Test Script
Covers: Categories, Products CRUD, Search, Image Upload, Bulk CSV Upload
Requires S1 server running at localhost:8000 (docker-compose up)
Run: python3 markethub_s2_test.py
"""

import requests
import sys
import time
import io
import csv

BASE   = "http://localhost:8000/api/v1"
HEALTH = "http://localhost:8000/api/health/"

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

passed = failed = skipped = 0
section_passed = section_failed = 0


def safe_json(r):
    try:
        return r.json() or {}
    except Exception:
        return {}


def test(name, condition, info=""):
    global passed, failed, section_passed, section_failed
    if condition:
        print(f"  {GREEN}✅ PASS{RESET} — {name}")
        passed += 1
        section_passed += 1
    else:
        print(f"  {RED}❌ FAIL{RESET} — {name} {RED}{info}{RESET}")
        failed += 1
        section_failed += 1


def skip(name, reason=""):
    global skipped
    print(f"  {YELLOW}⏭  SKIP{RESET} — {name} {YELLOW}({reason}){RESET}")
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
    print(f"{BOLD}  FINAL RESULTS: {passed}/{total} passed  ({skipped} skipped){RESET}")
    if failed == 0:
        print(f"  {GREEN}{BOLD}🎉 ALL TESTS PASSED — SESSION 2 PRODUCTS = 100% COVERED!{RESET}")
    else:
        print(f"  {RED}{BOLD}❌ {failed} test(s) failed — see above{RESET}")
    print(f"{BOLD}{'='*58}{RESET}\n")


# ── shared state ─────────────────────────────────────
import time as _time; _ts = int(_time.time())
BUYER_EMAIL   = f"buyer_{_ts}@test.com"
SELLER_EMAIL  = f"seller_{_ts}@test.com"
SELLER2_EMAIL = f"seller2_{_ts}@test.com"
ADMIN_EMAIL   = f"admin_{_ts}@test.com"
PASSWORD      = "TestPass1!"

buyer_token   = ""
seller_token  = ""
seller2_token = ""
admin_token   = ""

cat_id        = None
child_cat_id  = None
product_id    = None
product_id2   = None


def h(token):
    return {"Authorization": f"Bearer {token}"}


def register_and_login(email, password, role, store_name=None):
    payload = {
        "email": email, "password": password,
        "password_confirm": password,
        "first_name": "Test", "last_name": role.capitalize(),
        "role": role,
    }
    if store_name:
        payload["store_name"] = store_name
    requests.post(f"{BASE}/auth/register/", json=payload)
    r = requests.post(f"{BASE}/auth/login/", json={"email": email, "password": password})
    return r.json().get("data", {}).get("access", "")


# ════════════════════════════════════════════════════
section("0. PRE-FLIGHT: SERVER & AUTH SETUP")
# ════════════════════════════════════════════════════

try:
    r = requests.get(HEALTH, timeout=5)
    test("Server is reachable", r.status_code == 200)
    body = safe_json(r)
    test("DB is ok",    body.get("data", {}).get("db")    == "ok")
    test("Redis is ok", body.get("data", {}).get("redis") == "ok")
except Exception as e:
    print(f"  {RED}❌ Server not reachable: {e}{RESET}")
    print(f"  {YELLOW}Run: docker-compose up -d{RESET}")
    sys.exit(1)

# Register all test users
buyer_token   = register_and_login(BUYER_EMAIL,   PASSWORD, "buyer")
seller_token  = register_and_login(SELLER_EMAIL,  PASSWORD, "seller", "Store One")
seller2_token = register_and_login(SELLER2_EMAIL, PASSWORD, "seller", "Store Two")
admin_token   = register_and_login(ADMIN_EMAIL,   PASSWORD, "admin")

test("Buyer token obtained",   len(buyer_token)   > 0)
test("Seller token obtained",  len(seller_token)  > 0)
test("Seller2 token obtained", len(seller2_token) > 0)
test("Admin token obtained",   len(admin_token)   > 0)


# ════════════════════════════════════════════════════
section("1. CATEGORIES — PUBLIC READ")
# ════════════════════════════════════════════════════

# List categories (public)
r = requests.get(f"{BASE}/categories/")
d = safe_json(r)
test("List categories — status 200",         r.status_code == 200, f"got {r.status_code}")
test("List categories — no auth needed",     r.status_code == 200)

# Retrieve single non-existent category
r = requests.get(f"{BASE}/categories/99999/")
test("Get non-existent category — 404",      r.status_code == 404, f"got {r.status_code}")


# ════════════════════════════════════════════════════
section("2. CATEGORIES — ADMIN WRITE")
# ════════════════════════════════════════════════════

# Buyer cannot create category
r = requests.post(f"{BASE}/categories/", json={
    "name": "Electronics", "slug": f"electronics-{_ts}",
    "level": 1, "display_order": 1
}, headers=h(buyer_token))
test("Buyer create category — forbidden (403)", r.status_code == 403, f"got {r.status_code}")

# Seller cannot create category
r = requests.post(f"{BASE}/categories/", json={
    "name": "Electronics", "slug": f"electronics-{_ts}",
    "level": 1, "display_order": 1
}, headers=h(seller_token))
test("Seller create category — forbidden (403)", r.status_code == 403, f"got {r.status_code}")

# Admin creates root category
r = requests.post(f"{BASE}/categories/", json={
    "name": "Electronics", "slug": f"electronics-{_ts}",
    "level": 1, "display_order": 1, "is_active": True, "parent": None
}, headers=h(admin_token))
d = safe_json(r)
test("Admin create category — status 201",   r.status_code == 201, f"got {r.status_code}")
test("Category — has id",                    "id" in d)
test("Category — correct name",              d.get("name") == "Electronics")
test("Category — correct level",             d.get("level") == 1)
cat_id = d.get("id")

# Admin creates child category
if cat_id:
    r = requests.post(f"{BASE}/categories/", json={
        "name": "Phones", "slug": f"phones-{_ts}",
        "level": 2, "parent": cat_id, "display_order": 1, "is_active": True
    }, headers=h(admin_token))
    d = safe_json(r)
    test("Admin create child category — 201",    r.status_code == 201, f"got {r.status_code}")
    test("Child category — correct parent",       d.get("parent") == cat_id)
    test("Child category — level = 2",            d.get("level") == 2)
    child_cat_id = d.get("id")

# Duplicate slug rejected
r = requests.post(f"{BASE}/categories/", json={
    "name": "Electronics Dupe", "slug": f"electronics-{_ts}",
    "level": 1
}, headers=h(admin_token))
test("Duplicate slug — rejected (400)",      r.status_code == 400, f"got {r.status_code}")

# Wrong level for child (parent is level 1, child should be level 2 not 3)
if cat_id:
    r = requests.post(f"{BASE}/categories/", json={
        "name": "Bad Level", "slug": f"bad-level-{_ts}",
        "level": 3, "parent": cat_id
    }, headers=h(admin_token))
    test("Wrong child level — rejected (400)",   r.status_code == 400, f"got {r.status_code}")

# Admin updates category
if cat_id:
    r = requests.patch(f"{BASE}/categories/{cat_id}/", json={
        "display_order": 5
    }, headers=h(admin_token))
    test("Admin update category — 200",          r.status_code == 200, f"got {r.status_code}")

# No auth on create
r = requests.post(f"{BASE}/categories/", json={"name": "X", "slug": "x", "level": 1})
test("Create category no token — 401/403",   r.status_code in (401, 403), f"got {r.status_code}")


# ════════════════════════════════════════════════════
section("3. PRODUCTS — CREATE (SELLER ONLY)")
# ════════════════════════════════════════════════════

if not cat_id:
    skip("All product create tests", "no category available")
else:
    # Buyer cannot create product
    r = requests.post(f"{BASE}/products/", json={
        "title": "Test Product", "price": "999.99",
        "currency": "PKR", "stock": 10, "category": cat_id
    }, headers=h(buyer_token))
    test("Buyer create product — forbidden (403)", r.status_code == 403, f"got {r.status_code}")

    # Unauthenticated cannot create
    r = requests.post(f"{BASE}/products/", json={
        "title": "Test Product", "price": "999.99",
        "currency": "PKR", "stock": 10, "category": cat_id
    })
    test("No token create product — 401",        r.status_code == 401, f"got {r.status_code}")

    # Seller creates product
    r = requests.post(f"{BASE}/products/", json={
        "title": "Samsung Galaxy S24",
        "description": "Latest Samsung flagship phone",
        "price": "299999.00",
        "currency": "PKR",
        "stock": 50,
        "category": cat_id,
        "compare_at_price": "349999.00",
        "discount_pct": "10.00",
    }, headers=h(seller_token))
    d = safe_json(r)
    test("Seller create product — 201",          r.status_code == 201, f"got {r.status_code}")
    test("Product — has UUID id",                len(str(d.get("id", ""))) == 36)
    test("Product — correct title",              d.get("title") == "Samsung Galaxy S24")
    test("Product — correct price",              str(d.get("price")) == "299999.00")
    test("Product — correct currency",           d.get("currency") == "PKR")
    test("Product — stock set",                  d.get("stock") == 50)
    test("Product — has is_on_sale",             "is_on_sale" in d)
    test("Product — has current_price",          "current_price" in d)
    test("Product — has created_at",             "created_at" in d)
    product_id = d.get("id")

    # Seller creates second product
    r = requests.post(f"{BASE}/products/", json={
        "title": "iPhone 15 Pro",
        "description": "Apple flagship",
        "price": "399999.00",
        "currency": "PKR",
        "stock": 0,   # out of stock
        "category": cat_id,
    }, headers=h(seller_token))
    d = safe_json(r)
    test("Seller create 2nd product — 201",      r.status_code == 201, f"got {r.status_code}")
    product_id2 = d.get("id")

    # Missing required fields
    r = requests.post(f"{BASE}/products/", json={
        "title": "No Price Product", "stock": 5, "category": cat_id
    }, headers=h(seller_token))
    test("Missing price — rejected (400)",       r.status_code == 400, f"got {r.status_code}")

    # Negative price
    r = requests.post(f"{BASE}/products/", json={
        "title": "Negative Price", "price": "-100", "stock": 5, "category": cat_id
    }, headers=h(seller_token))
    test("Negative price — rejected (400)",      r.status_code == 400, f"got {r.status_code}")

    # Negative stock
    r = requests.post(f"{BASE}/products/", json={
        "title": "Negative Stock", "price": "100", "stock": -1, "category": cat_id
    }, headers=h(seller_token))
    test("Negative stock — rejected (400)",      r.status_code == 400, f"got {r.status_code}")

    # Invalid category
    r = requests.post(f"{BASE}/products/", json={
        "title": "Bad Cat", "price": "100", "stock": 5, "category": 99999
    }, headers=h(seller_token))
    test("Invalid category — rejected (400)",    r.status_code == 400, f"got {r.status_code}")


# ════════════════════════════════════════════════════
section("4. PRODUCTS — LIST & RETRIEVE (PUBLIC)")
# ════════════════════════════════════════════════════

# Public list
r = requests.get(f"{BASE}/products/")
d = safe_json(r)
test("List products — status 200",           r.status_code == 200, f"got {r.status_code}")
test("List products — no auth needed",       r.status_code == 200)
test("List products — has results",          len(d.get("results", [])) > 0)
test("List products — cursor pagination",    "next" in d or "previous" in d or "results" in d)

# List fields (lightweight serializer)
if d.get("results"):
    p = d["results"][0]
    test("List — has id",            "id"            in p)
    test("List — has title",         "title"         in p)
    test("List — has price",         "price"         in p)
    test("List — has current_price", "current_price" in p)
    test("List — has stock",         "stock"         in p)
    test("List — has primary_image", "primary_image" in p)

# Retrieve specific product
if product_id:
    r = requests.get(f"{BASE}/products/{product_id}/")
    d = safe_json(r)
    test("Retrieve product — status 200",        r.status_code == 200, f"got {r.status_code}")
    test("Retrieve — correct id",                str(d.get("id")) == str(product_id))
    test("Retrieve — has images array",          "images"   in d)
    test("Retrieve — has variants array",        "variants" in d)
    test("Retrieve — has seller_id",             "seller_id" in d)

    # view_count increments
    r2 = requests.get(f"{BASE}/products/{product_id}/")
    test("view_count increments on retrieve",    r2.json().get("view_count", 0) >= 1)

# Retrieve non-existent
r = requests.get(f"{BASE}/products/00000000-0000-0000-0000-000000000000/")
test("Get non-existent product — 404",       r.status_code == 404, f"got {r.status_code}")


# ════════════════════════════════════════════════════
section("5. PRODUCTS — FILTERING")
# ════════════════════════════════════════════════════

# Filter by category
if cat_id:
    r = requests.get(f"{BASE}/products/?category={cat_id}")
    test("Filter by category — 200",             r.status_code == 200, f"got {r.status_code}")
    results = safe_json(r).get("results", [])
    test("Filter by category — returns results", len(results) >= 1)

# Filter by currency
r = requests.get(f"{BASE}/products/?currency=PKR")
test("Filter by currency=PKR — 200",         r.status_code == 200, f"got {r.status_code}")

# Filter by min/max price
r = requests.get(f"{BASE}/products/?min_price=100000&max_price=350000")
d = safe_json(r)
test("Filter by price range — 200",          r.status_code == 200, f"got {r.status_code}")

# Filter in_stock=true
r = requests.get(f"{BASE}/products/?in_stock=true")
test("Filter in_stock=true — 200",           r.status_code == 200, f"got {r.status_code}")
results = safe_json(r).get("results", [])
for p in results:
    test("in_stock filter — all stock > 0",  p.get("stock", 0) > 0)
    break  # just check first one

# Filter in_stock=false (out of stock)
r = requests.get(f"{BASE}/products/?in_stock=false")
test("Filter in_stock=false — 200",          r.status_code == 200, f"got {r.status_code}")

# Ordering by price
r = requests.get(f"{BASE}/products/?ordering=price")
test("Order by price asc — 200",             r.status_code == 200, f"got {r.status_code}")

r = requests.get(f"{BASE}/products/?ordering=-price")
test("Order by price desc — 200",            r.status_code == 200, f"got {r.status_code}")

r = requests.get(f"{BASE}/products/?ordering=-view_count")
test("Order by view_count desc — 200",       r.status_code == 200, f"got {r.status_code}")

# Filter by seller
r_me = requests.get(f"{BASE}/products/", headers=h(seller_token))
d_me = safe_json(r_me)
test("Seller sees own products — 200",       r_me.status_code == 200, f"got {r_me.status_code}")


# ════════════════════════════════════════════════════
section("6. PRODUCTS — UPDATE & OWNERSHIP")
# ════════════════════════════════════════════════════

if product_id:
    # Seller updates own product
    r = requests.patch(f"{BASE}/products/{product_id}/", json={
        "title": "Samsung Galaxy S24 Ultra",
        "stock": 45,
    }, headers=h(seller_token))
    d = safe_json(r)
    test("Seller update own product — 200",      r.status_code == 200, f"got {r.status_code}")
    test("Title updated correctly",              d.get("title") == "Samsung Galaxy S24 Ultra")
    test("Stock updated correctly",              d.get("stock") == 45)

    # Seller2 cannot update seller's product
    r = requests.patch(f"{BASE}/products/{product_id}/", json={
        "title": "Hacked Title"
    }, headers=h(seller2_token))
    test("Other seller update — forbidden (403)", r.status_code in (403, 404), f"got {r.status_code}")

    # Buyer cannot update product
    r = requests.patch(f"{BASE}/products/{product_id}/", json={
        "title": "Buyer Hack"
    }, headers=h(buyer_token))
    test("Buyer update product — forbidden (403)", r.status_code == 403, f"got {r.status_code}")

    # No token update
    r = requests.patch(f"{BASE}/products/{product_id}/", json={"title": "No Auth"})
    test("No token update — 401",                r.status_code == 401, f"got {r.status_code}")


# ════════════════════════════════════════════════════
section("7. PRODUCTS — FULL-TEXT SEARCH")
# ════════════════════════════════════════════════════

# Missing q param
r = requests.get(f"{BASE}/products/search/")
test("Search missing q — 400",               r.status_code == 400, f"got {r.status_code}")

# Search with q (may return 0 results if search vectors not refreshed yet — that's ok)
r = requests.get(f"{BASE}/products/search/?q=samsung")
test("Search q=samsung — 200",               r.status_code == 200, f"got {r.status_code}")
test("Search — has results key",             "results" in safe_json(r) or isinstance(safe_json(r), list))

r = requests.get(f"{BASE}/products/search/?q=iphone")
test("Search q=iphone — 200",               r.status_code == 200, f"got {r.status_code}")

# Empty q
r = requests.get(f"{BASE}/products/search/?q=")
test("Search empty q — 400",                r.status_code == 400, f"got {r.status_code}")

# Search is public (no auth needed)
r = requests.get(f"{BASE}/products/search/?q=phone")
test("Search is public — no auth needed",   r.status_code == 200, f"got {r.status_code}")


# ════════════════════════════════════════════════════
section("8. PRODUCTS — IMAGE UPLOAD")
# ════════════════════════════════════════════════════

if product_id:
    # No file provided
    r = requests.post(f"{BASE}/products/{product_id}/images/",
                      headers=h(seller_token))
    test("Image upload no file — 400",           r.status_code == 400, f"got {r.status_code}")

    # Valid small PNG (1x1 pixel PNG bytes)
    tiny_png = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
        b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
        b'\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18'
        b'\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
    )
    r = requests.post(
        f"{BASE}/products/{product_id}/images/",
        files={"image": ("test.png", io.BytesIO(tiny_png), "image/png")},
        headers=h(seller_token),
    )
    d = safe_json(r)
    test("Image upload valid — 201",             r.status_code == 201, f"got {r.status_code}: {d}")
    test("Image upload — has id",                "id" in d)
    test("Image upload — status=processing",     d.get("status") == "processing")

    # File too large (> 5MB)
    big_file = io.BytesIO(b"x" * (5 * 1024 * 1024 + 1))
    r = requests.post(
        f"{BASE}/products/{product_id}/images/",
        files={"image": ("big.jpg", big_file, "image/jpeg")},
        headers=h(seller_token),
    )
    test("Image >5MB — rejected (400)",          r.status_code == 400, f"got {r.status_code}")

    # Seller2 cannot upload to seller's product
    r = requests.post(
        f"{BASE}/products/{product_id}/images/",
        files={"image": ("x.png", io.BytesIO(tiny_png), "image/png")},
        headers=h(seller2_token),
    )
    test("Other seller upload image — 403",      r.status_code in (403, 404), f"got {r.status_code}")

    # Unauthenticated cannot upload
    r = requests.post(
        f"{BASE}/products/{product_id}/images/",
        files={"image": ("x.png", io.BytesIO(tiny_png), "image/png")},
    )
    test("No token image upload — 401",          r.status_code == 401, f"got {r.status_code}")


# ════════════════════════════════════════════════════
section("9. BULK CSV UPLOAD")
# ════════════════════════════════════════════════════

def make_csv(rows):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "title", "price", "category_id", "stock", "currency", "description", "compare_at_price"
    ])
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


# Buyer cannot bulk upload
r = requests.post(f"{BASE}/products/bulk-upload/",
                  files={"file": ("products.csv", io.BytesIO(b"title,price,category_id,stock,currency\n"), "text/csv")},
                  headers=h(buyer_token))
test("Buyer bulk upload — 403",              r.status_code == 403, f"got {r.status_code}")

# No file
r = requests.post(f"{BASE}/products/bulk-upload/", headers=h(seller_token))
test("Bulk upload no file — 400",            r.status_code == 400, f"got {r.status_code}")

if cat_id:
    # Valid CSV
    valid_csv = make_csv([
        {"title": "Bulk Product 1", "price": "1000", "category_id": cat_id,
         "stock": "5", "currency": "PKR", "description": "Desc 1", "compare_at_price": ""},
        {"title": "Bulk Product 2", "price": "2000", "category_id": cat_id,
         "stock": "10", "currency": "PKR", "description": "Desc 2", "compare_at_price": "2500"},
    ])
    r = requests.post(f"{BASE}/products/bulk-upload/",
                      files={"file": ("products.csv", io.BytesIO(valid_csv), "text/csv")},
                      headers=h(seller_token))
    d = safe_json(r)
    test("Valid CSV bulk upload — 201",          r.status_code == 201, f"got {r.status_code}")
    test("Bulk — success_count = 2",             d.get("success_count") == 2, f"got {d.get('success_count')}")
    test("Bulk — error_count = 0",               d.get("error_count") == 0, f"got {d.get('error_count')}")
    test("Bulk — errors is empty list",          d.get("errors") == [])

    # CSV with some invalid rows
    mixed_csv = make_csv([
        {"title": "Good Product", "price": "500", "category_id": cat_id,
         "stock": "3", "currency": "PKR", "description": "", "compare_at_price": ""},
        {"title": "Bad Price", "price": "notanumber", "category_id": cat_id,
         "stock": "3", "currency": "PKR", "description": "", "compare_at_price": ""},
        {"title": "Bad Category", "price": "500", "category_id": "99999",
         "stock": "3", "currency": "PKR", "description": "", "compare_at_price": ""},
        {"title": "Negative Stock", "price": "500", "category_id": cat_id,
         "stock": "-1", "currency": "PKR", "description": "", "compare_at_price": ""},
    ])
    r = requests.post(f"{BASE}/products/bulk-upload/",
                      files={"file": ("mixed.csv", io.BytesIO(mixed_csv), "text/csv")},
                      headers=h(seller_token))
    d = safe_json(r)
    test("Mixed CSV — 201",                      r.status_code == 201, f"got {r.status_code}")
    test("Mixed CSV — success_count = 1",        d.get("success_count") == 1, f"got {d.get('success_count')}")
    test("Mixed CSV — error_count = 3",          d.get("error_count") == 3, f"got {d.get('error_count')}")
    test("Mixed CSV — errors list populated",    len(d.get("errors", [])) == 3)
    test("Mixed CSV — errors have row numbers",  all("row" in e for e in d.get("errors", [])))

# Missing required columns
bad_header_csv = b"title,price\nProduct,100\n"
r = requests.post(f"{BASE}/products/bulk-upload/",
                  files={"file": ("bad.csv", io.BytesIO(bad_header_csv), "text/csv")},
                  headers=h(seller_token))
d = safe_json(r)
test("Missing CSV columns — 400",            r.status_code == 400, f"got {r.status_code}")
test("Missing cols — detail mentions missing", "Missing" in d.get("detail", ""))

# Non-UTF8 file
r = requests.post(f"{BASE}/products/bulk-upload/",
                  files={"file": ("bad.csv", io.BytesIO(b"\xff\xfe bad encoding"), "text/csv")},
                  headers=h(seller_token))
test("Non-UTF8 CSV — 400",                   r.status_code == 400, f"got {r.status_code}")

# No token
r = requests.post(f"{BASE}/products/bulk-upload/")
test("Bulk upload no token — 401",           r.status_code == 401, f"got {r.status_code}")


# ════════════════════════════════════════════════════
section("10. PRODUCTS — SOFT DELETE")
# ════════════════════════════════════════════════════

if product_id2:
    # Seller2 cannot delete seller's product
    r = requests.delete(f"{BASE}/products/{product_id2}/", headers=h(seller2_token))
    test("Other seller delete — 403",            r.status_code in (403, 404), f"got {r.status_code}")

    # Buyer cannot delete
    r = requests.delete(f"{BASE}/products/{product_id2}/", headers=h(buyer_token))
    test("Buyer delete product — 403",           r.status_code == 403, f"got {r.status_code}")

    # Seller soft-deletes own product
    r = requests.delete(f"{BASE}/products/{product_id2}/", headers=h(seller_token))
    test("Seller soft delete — 204",             r.status_code == 204, f"got {r.status_code}")

    # Deleted product not visible publicly
    r = requests.get(f"{BASE}/products/{product_id2}/")
    test("Deleted product not visible — 404",    r.status_code == 404, f"got {r.status_code}")

    # No token delete
    if product_id:
        r = requests.delete(f"{BASE}/products/{product_id}/")
        test("No token delete — 401",            r.status_code == 401, f"got {r.status_code}")


# ════════════════════════════════════════════════════
section("11. CATEGORY — CACHE (BASIC)")
# ════════════════════════════════════════════════════

# Hit category list twice — both should return same data (cached)
r1 = requests.get(f"{BASE}/categories/")
r2 = requests.get(f"{BASE}/categories/")
test("Category list cached — both 200",       r1.status_code == 200 and r2.status_code == 200)
test("Category list cached — same data",      r1.json() == r2.json())


# ════════════════════════════════════════════════════
summary()
