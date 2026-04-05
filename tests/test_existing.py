
"""
Referenční testy Bookstore API v4.0.
Pokrývá všech 20 HTTP status kódů a klíčové byznys pravidla.
Spuštění: curl -X POST http://localhost:8000/reset && pytest tests/test_existing.py -v
"""
import time
import pytest
import requests

BASE_URL = "http://localhost:8000"
API_KEY = "test-api-key"
AUTH = {"X-API-Key": API_KEY}


# ── Helpers ──────────────────────────────────────────────

def reset_db():
    r = requests.post(f"{BASE_URL}/reset")
    assert r.status_code == 200


def create_author(name="Test Author", bio=None, born_year=1980):
    r = requests.post(f"{BASE_URL}/authors", json={
        "name": name, "bio": bio, "born_year": born_year,
    })
    assert r.status_code == 201
    return r.json()


def create_category(name="Test Category"):
    r = requests.post(f"{BASE_URL}/categories", json={"name": name})
    assert r.status_code == 201
    return r.json()


def create_book(author_id, category_id, title="Test Book",
                isbn="1234567890", price=29.99, published_year=2020, stock=10):
    r = requests.post(f"{BASE_URL}/books", json={
        "title": title, "isbn": isbn, "price": price,
        "published_year": published_year, "stock": stock,
        "author_id": author_id, "category_id": category_id,
    })
    assert r.status_code == 201
    return r.json()


def create_tag(name="test-tag"):
    r = requests.post(f"{BASE_URL}/tags", json={"name": name})
    assert r.status_code == 201
    return r.json()


def create_order(customer_name, customer_email, items):
    r = requests.post(f"{BASE_URL}/orders", json={
        "customer_name": customer_name,
        "customer_email": customer_email,
        "items": items,
    })
    assert r.status_code == 201
    return r.json()


def setup_book_with_deps(isbn="1234567890", stock=10, price=29.99,
                          published_year=2020, author_name=None, cat_name=None):
    """Helper: vytvoří autora + kategorii + knihu, vrátí (author, category, book)."""
    a = create_author(name=author_name or f"Author-{isbn}")
    c = create_category(name=cat_name or f"Cat-{isbn}")
    b = create_book(a["id"], c["id"], isbn=isbn, stock=stock,
                    price=price, published_year=published_year)
    return a, c, b


# ══════════════════════════════════════════════════════════
# 200 · Health
# ══════════════════════════════════════════════════════════

def test_health_check():
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ══════════════════════════════════════════════════════════
# 201 · Authors CRUD
# ══════════════════════════════════════════════════════════

def test_create_author_happy_path():
    data = create_author(name="George Orwell", born_year=1903)
    assert data["name"] == "George Orwell"
    assert data["born_year"] == 1903
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


def test_get_author_not_found():
    r = requests.get(f"{BASE_URL}/authors/999999")
    assert r.status_code == 404


def test_update_author():
    a = create_author(name="Old Name")
    r = requests.put(f"{BASE_URL}/authors/{a['id']}", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_delete_author_with_books_fails_409():
    a, c, b = setup_book_with_deps(isbn="9999999990")
    r = requests.delete(f"{BASE_URL}/authors/{a['id']}")
    assert r.status_code == 409


# ══════════════════════════════════════════════════════════
# Categories
# ══════════════════════════════════════════════════════════

def test_create_category_duplicate_409():
    create_category(name="Unique Cat")
    r = requests.post(f"{BASE_URL}/categories", json={"name": "Unique Cat"})
    assert r.status_code == 409


def test_delete_category_with_books_fails_409():
    a, c, b = setup_book_with_deps(isbn="8888888880")
    r = requests.delete(f"{BASE_URL}/categories/{c['id']}")
    assert r.status_code == 409


# ══════════════════════════════════════════════════════════
# 422 · Validation errors
# ══════════════════════════════════════════════════════════

def test_create_author_missing_name_422():
    r = requests.post(f"{BASE_URL}/authors", json={"bio": "no name"})
    assert r.status_code == 422


def test_create_book_negative_price_422():
    a = create_author(name="Price Author")
    c = create_category(name="Price Cat")
    r = requests.post(f"{BASE_URL}/books", json={
        "title": "Cheap", "isbn": "0000000001", "price": -5,
        "published_year": 2020, "author_id": a["id"], "category_id": c["id"],
    })
    assert r.status_code == 422


# ══════════════════════════════════════════════════════════
# 409 · Duplicate ISBN
# ══════════════════════════════════════════════════════════

def test_create_book_duplicate_isbn_409():
    a, c, _ = setup_book_with_deps(isbn="1111111111")
    r = requests.post(f"{BASE_URL}/books", json={
        "title": "Dup", "isbn": "1111111111", "price": 10,
        "published_year": 2020, "stock": 5,
        "author_id": a["id"], "category_id": c["id"],
    })
    assert r.status_code == 409


# ══════════════════════════════════════════════════════════
# 410 · Soft delete + restore
# ══════════════════════════════════════════════════════════

def test_soft_delete_book_then_get_returns_410():
    _, _, b = setup_book_with_deps(isbn="4100000001")
    r = requests.delete(f"{BASE_URL}/books/{b['id']}")
    assert r.status_code == 204
    r = requests.get(f"{BASE_URL}/books/{b['id']}")
    assert r.status_code == 410


def test_soft_deleted_book_excluded_from_list():
    _, _, b = setup_book_with_deps(isbn="4100000002")
    requests.delete(f"{BASE_URL}/books/{b['id']}")
    r = requests.get(f"{BASE_URL}/books", params={"search": "4100000002"})
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_restore_soft_deleted_book():
    _, _, b = setup_book_with_deps(isbn="4100000003")
    requests.delete(f"{BASE_URL}/books/{b['id']}")
    r = requests.post(f"{BASE_URL}/books/{b['id']}/restore")
    assert r.status_code == 200
    assert r.json()["id"] == b["id"]
    r = requests.get(f"{BASE_URL}/books/{b['id']}")
    assert r.status_code == 200


def test_restore_non_deleted_book_fails_400():
    _, _, b = setup_book_with_deps(isbn="4100000004")
    r = requests.post(f"{BASE_URL}/books/{b['id']}/restore")
    assert r.status_code == 400


# ══════════════════════════════════════════════════════════
# Discount (200 + 400)
# ══════════════════════════════════════════════════════════

def test_discount_old_book():
    _, _, b = setup_book_with_deps(isbn="5555555555", price=100, published_year=2020)
    r = requests.post(f"{BASE_URL}/books/{b['id']}/discount",
                      json={"discount_percent": 25})
    assert r.status_code == 200
    assert r.json()["discounted_price"] == 75.0


def test_discount_new_book_rejected_400():
    _, _, b = setup_book_with_deps(isbn="6666666666", price=50, published_year=2026)
    r = requests.post(f"{BASE_URL}/books/{b['id']}/discount",
                      json={"discount_percent": 10})
    assert r.status_code == 400


# ══════════════════════════════════════════════════════════
# Stock (400)
# ══════════════════════════════════════════════════════════

def test_stock_increase():
    _, _, b = setup_book_with_deps(isbn="7770000001", stock=5)
    r = requests.patch(f"{BASE_URL}/books/{b['id']}/stock", params={"quantity": 10})
    assert r.status_code == 200
    assert r.json()["stock"] == 15


def test_stock_decrease_below_zero_400():
    _, _, b = setup_book_with_deps(isbn="7777777777", stock=3)
    r = requests.patch(f"{BASE_URL}/books/{b['id']}/stock", params={"quantity": -10})
    assert r.status_code == 400


# ══════════════════════════════════════════════════════════
# Reviews
# ══════════════════════════════════════════════════════════

def test_create_review_and_get_rating():
    _, _, b = setup_book_with_deps(isbn="REV0000001")
    requests.post(f"{BASE_URL}/books/{b['id']}/reviews",
                  json={"rating": 5, "reviewer_name": "Alice"})
    requests.post(f"{BASE_URL}/books/{b['id']}/reviews",
                  json={"rating": 3, "reviewer_name": "Bob"})
    r = requests.get(f"{BASE_URL}/books/{b['id']}/rating")
    assert r.status_code == 200
    assert r.json()["average_rating"] == 4.0
    assert r.json()["review_count"] == 2


def test_review_on_soft_deleted_book_410():
    _, _, b = setup_book_with_deps(isbn="REV0000002")
    requests.delete(f"{BASE_URL}/books/{b['id']}")
    r = requests.post(f"{BASE_URL}/books/{b['id']}/reviews",
                      json={"rating": 5, "reviewer_name": "Eve"})
    assert r.status_code == 410


# ══════════════════════════════════════════════════════════
# Tags
# ══════════════════════════════════════════════════════════

def test_create_tag_and_duplicate_409():
    create_tag(name="unique-t")
    r = requests.post(f"{BASE_URL}/tags", json={"name": "unique-t"})
    assert r.status_code == 409


def test_add_tags_to_book_idempotent():
    _, _, b = setup_book_with_deps(isbn="TAG0000001")
    t = create_tag(name="idmp-tag")
    requests.post(f"{BASE_URL}/books/{b['id']}/tags", json={"tag_ids": [t["id"]]})
    r = requests.post(f"{BASE_URL}/books/{b['id']}/tags", json={"tag_ids": [t["id"]]})
    assert r.status_code == 200
    assert len(r.json()["tags"]) == 1


def test_remove_tags_from_book():
    _, _, b = setup_book_with_deps(isbn="TAG0000002")
    t = create_tag(name="rm-tag")
    requests.post(f"{BASE_URL}/books/{b['id']}/tags", json={"tag_ids": [t["id"]]})
    r = requests.delete(f"{BASE_URL}/books/{b['id']}/tags", json={"tag_ids": [t["id"]]})
    assert r.status_code == 200
    assert len(r.json()["tags"]) == 0


def test_delete_tag_with_books_409():
    _, _, b = setup_book_with_deps(isbn="TAG0000003")
    t = create_tag(name="attached-t")
    requests.post(f"{BASE_URL}/books/{b['id']}/tags", json={"tag_ids": [t["id"]]})
    r = requests.delete(f"{BASE_URL}/tags/{t['id']}")
    assert r.status_code == 409


def test_add_nonexistent_tag_404():
    _, _, b = setup_book_with_deps(isbn="TAG0000004")
    r = requests.post(f"{BASE_URL}/books/{b['id']}/tags", json={"tag_ids": [999999]})
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════
# Orders – vytvoření + stavy
# ══════════════════════════════════════════════════════════

def test_create_order_happy_path():
    _, _, b = setup_book_with_deps(isbn="ORD0000001", price=50, stock=10)
    data = create_order("Jan", "jan@test.com",
                        [{"book_id": b["id"], "quantity": 2}])
    assert data["status"] == "pending"
    assert data["total_price"] == 100.0
    r = requests.get(f"{BASE_URL}/books/{b['id']}")
    assert r.json()["stock"] == 8


def test_create_order_insufficient_stock_400():
    _, _, b = setup_book_with_deps(isbn="ORD0000002", stock=2)
    r = requests.post(f"{BASE_URL}/orders", json={
        "customer_name": "X", "customer_email": "x@t.com",
        "items": [{"book_id": b["id"], "quantity": 5}],
    })
    assert r.status_code == 400


def test_create_order_duplicate_book_400():
    _, _, b = setup_book_with_deps(isbn="ORD0000003", stock=10)
    r = requests.post(f"{BASE_URL}/orders", json={
        "customer_name": "X", "customer_email": "x@t.com",
        "items": [
            {"book_id": b["id"], "quantity": 1},
            {"book_id": b["id"], "quantity": 2},
        ],
    })
    assert r.status_code == 400


def test_create_order_empty_items_422():
    r = requests.post(f"{BASE_URL}/orders", json={
        "customer_name": "X", "customer_email": "x@t.com", "items": [],
    })
    assert r.status_code == 422


def test_order_full_lifecycle():
    """pending → confirmed → shipped → delivered"""
    _, _, b = setup_book_with_deps(isbn="ORD0000004", stock=10)
    order = create_order("Test", "t@t.com",
                         [{"book_id": b["id"], "quantity": 1}])
    for status in ["confirmed", "shipped", "delivered"]:
        r = requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                           json={"status": status})
        assert r.status_code == 200
        assert r.json()["status"] == status


def test_order_invalid_transition_400():
    _, _, b = setup_book_with_deps(isbn="ORD0000005", stock=10)
    order = create_order("Test", "t@t.com",
                         [{"book_id": b["id"], "quantity": 1}])
    r = requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                       json={"status": "shipped"})
    assert r.status_code == 400


def test_order_cancel_restores_stock():
    _, _, b = setup_book_with_deps(isbn="ORD0000006", stock=10)
    order = create_order("Test", "t@t.com",
                         [{"book_id": b["id"], "quantity": 3}])
    assert requests.get(f"{BASE_URL}/books/{b['id']}").json()["stock"] == 7
    requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                   json={"status": "cancelled"})
    assert requests.get(f"{BASE_URL}/books/{b['id']}").json()["stock"] == 10


def test_delete_pending_order_restores_stock():
    _, _, b = setup_book_with_deps(isbn="ORD0000007", stock=10)
    order = create_order("Test", "t@t.com",
                         [{"book_id": b["id"], "quantity": 4}])
    r = requests.delete(f"{BASE_URL}/orders/{order['id']}")
    assert r.status_code == 204
    assert requests.get(f"{BASE_URL}/books/{b['id']}").json()["stock"] == 10


def test_delete_confirmed_order_fails_400():
    _, _, b = setup_book_with_deps(isbn="ORD0000008", stock=10)
    order = create_order("Test", "t@t.com",
                         [{"book_id": b["id"], "quantity": 1}])
    requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                   json={"status": "confirmed"})
    r = requests.delete(f"{BASE_URL}/orders/{order['id']}")
    assert r.status_code == 400


# ══════════════════════════════════════════════════════════
# 403 · Invoice + Add Item
# ══════════════════════════════════════════════════════════

def test_invoice_confirmed_order():
    _, _, b = setup_book_with_deps(isbn="INV0000001", stock=10, price=50)
    order = create_order("Test", "t@t.com",
                         [{"book_id": b["id"], "quantity": 2}])
    requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                   json={"status": "confirmed"})
    r = requests.get(f"{BASE_URL}/orders/{order['id']}/invoice")
    assert r.status_code == 200
    assert r.json()["subtotal"] == 100.0
    assert r.json()["invoice_number"].startswith("INV-")


def test_invoice_pending_order_403():
    _, _, b = setup_book_with_deps(isbn="INV0000002", stock=10)
    order = create_order("Test", "t@t.com",
                         [{"book_id": b["id"], "quantity": 1}])
    r = requests.get(f"{BASE_URL}/orders/{order['id']}/invoice")
    assert r.status_code == 403


def test_add_item_to_non_pending_order_403():
    _, _, b = setup_book_with_deps(isbn="ITEM000001", stock=10)
    a2 = create_author(name="Item Author 2")
    c2 = create_category(name="Item Cat 2")
    b2 = create_book(a2["id"], c2["id"], isbn="ITEM000002", stock=10)
    order = create_order("Test", "t@t.com",
                         [{"book_id": b["id"], "quantity": 1}])
    requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                   json={"status": "confirmed"})
    r = requests.post(f"{BASE_URL}/orders/{order['id']}/items",
                      json={"book_id": b2["id"], "quantity": 1})
    assert r.status_code == 403


def test_add_duplicate_item_to_order_409():
    _, _, b = setup_book_with_deps(isbn="ITEM000003", stock=10)
    order = create_order("Test", "t@t.com",
                         [{"book_id": b["id"], "quantity": 1}])
    r = requests.post(f"{BASE_URL}/orders/{order['id']}/items",
                      json={"book_id": b["id"], "quantity": 1})
    assert r.status_code == 409


# ══════════════════════════════════════════════════════════
# 207 · Bulk create
# ══════════════════════════════════════════════════════════

def test_bulk_create_all_success_201():
    a = create_author(name="Bulk Author")
    c = create_category(name="Bulk Cat")
    r = requests.post(f"{BASE_URL}/books/bulk", headers=AUTH, json={"books": [
        {"title": "B1", "isbn": "BULK000001", "price": 10,
         "published_year": 2020, "author_id": a["id"], "category_id": c["id"]},
        {"title": "B2", "isbn": "BULK000002", "price": 20,
         "published_year": 2020, "author_id": a["id"], "category_id": c["id"]},
    ]})
    assert r.status_code == 201
    assert r.json()["created"] == 2
    assert r.json()["failed"] == 0


def test_bulk_create_partial_207():
    a = create_author(name="Bulk207 Author")
    c = create_category(name="Bulk207 Cat")
    r = requests.post(f"{BASE_URL}/books/bulk", headers=AUTH, json={"books": [
        {"title": "OK", "isbn": "BULK207001", "price": 10,
         "published_year": 2020, "author_id": a["id"], "category_id": c["id"]},
        {"title": "Fail", "isbn": "BULK207001", "price": 10,
         "published_year": 2020, "author_id": a["id"], "category_id": c["id"]},
    ]})
    assert r.status_code == 207
    assert r.json()["created"] == 1
    assert r.json()["failed"] == 1


# ══════════════════════════════════════════════════════════
# Clone
# ══════════════════════════════════════════════════════════

def test_clone_book():
    _, _, b = setup_book_with_deps(isbn="CLON000001", price=100, stock=50)
    r = requests.post(f"{BASE_URL}/books/{b['id']}/clone",
                      json={"new_isbn": "CLON000002"})
    assert r.status_code == 201
    clone = r.json()
    assert clone["price"] == 100
    assert clone["stock"] == 0  # stock se nekopíruje
    assert "(copy)" in clone["title"]


def test_clone_duplicate_isbn_409():
    _, _, b = setup_book_with_deps(isbn="CLON000003")
    r = requests.post(f"{BASE_URL}/books/{b['id']}/clone",
                      json={"new_isbn": "CLON000003"})
    assert r.status_code == 409


# ══════════════════════════════════════════════════════════
# 401 · Autentizace
# ══════════════════════════════════════════════════════════

def test_bulk_without_api_key_401():
    r = requests.post(f"{BASE_URL}/books/bulk", json={"books": []})
    assert r.status_code == 401


def test_statistics_without_api_key_401():
    r = requests.get(f"{BASE_URL}/statistics/summary")
    assert r.status_code == 401


def test_statistics_with_api_key_200():
    r = requests.get(f"{BASE_URL}/statistics/summary", headers=AUTH)
    assert r.status_code == 200
    data = r.json()
    assert "total_books" in data
    assert "orders_by_status" in data


def test_export_without_api_key_401():
    r = requests.post(f"{BASE_URL}/exports/books")
    assert r.status_code == 401


# ══════════════════════════════════════════════════════════
# 304 + 412 · ETags
# ══════════════════════════════════════════════════════════

def test_etag_304_not_modified():
    a = create_author(name="ETag Author")
    r = requests.get(f"{BASE_URL}/authors/{a['id']}")
    assert r.status_code == 200
    etag = r.headers.get("ETag")
    assert etag is not None

    r2 = requests.get(f"{BASE_URL}/authors/{a['id']}",
                      headers={"If-None-Match": etag})
    assert r2.status_code == 304


def test_etag_changes_after_update():
    _, _, b = setup_book_with_deps(isbn="ETAG000001")
    r1 = requests.get(f"{BASE_URL}/books/{b['id']}")
    etag1 = r1.headers["ETag"]

    requests.put(f"{BASE_URL}/books/{b['id']}", json={"title": "Updated Title"})
    r2 = requests.get(f"{BASE_URL}/books/{b['id']}")
    etag2 = r2.headers["ETag"]
    assert etag1 != etag2


def test_etag_412_precondition_failed():
    _, _, b = setup_book_with_deps(isbn="ETAG000002")
    r1 = requests.get(f"{BASE_URL}/books/{b['id']}")
    old_etag = r1.headers["ETag"]

    # Update book → ETag changes
    requests.put(f"{BASE_URL}/books/{b['id']}", json={"title": "Changed"})

    # Try PUT with old ETag → 412
    r2 = requests.put(f"{BASE_URL}/books/{b['id']}",
                      json={"title": "Stale Update"},
                      headers={"If-Match": old_etag})
    assert r2.status_code == 412


# ══════════════════════════════════════════════════════════
# 413 + 415 · Cover upload
# ══════════════════════════════════════════════════════════

def test_cover_upload_wrong_type_415():
    _, _, b = setup_book_with_deps(isbn="COV0000001")
    r = requests.post(
        f"{BASE_URL}/books/{b['id']}/cover",
        files={"file": ("doc.txt", b"hello world", "text/plain")},
    )
    assert r.status_code == 415


def test_cover_upload_too_large_413():
    _, _, b = setup_book_with_deps(isbn="COV0000002")
    big_data = b"\x00" * (2 * 1024 * 1024 + 1)  # 2 MB + 1 byte
    r = requests.post(
        f"{BASE_URL}/books/{b['id']}/cover",
        files={"file": ("big.jpg", big_data, "image/jpeg")},
    )
    assert r.status_code == 413


def test_cover_upload_and_get():
    _, _, b = setup_book_with_deps(isbn="COV0000003")
    img = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # Fake PNG header
    r = requests.post(
        f"{BASE_URL}/books/{b['id']}/cover",
        files={"file": ("cover.png", img, "image/png")},
    )
    assert r.status_code == 200
    assert r.json()["content_type"] == "image/png"

    r2 = requests.get(f"{BASE_URL}/books/{b['id']}/cover")
    assert r2.status_code == 200
    assert r2.headers["content-type"] == "image/png"


def test_get_cover_not_uploaded_404():
    _, _, b = setup_book_with_deps(isbn="COV0000004")
    r = requests.get(f"{BASE_URL}/books/{b['id']}/cover")
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════
# 429 · Rate limiting
# ══════════════════════════════════════════════════════════

def test_discount_rate_limit_429():
    reset_db()  # Clear rate limit counters from previous discount tests
    _, _, b = setup_book_with_deps(isbn="RATE000001", published_year=2020, price=100)
    # Discount rate limit: 5 per 10s
    for _ in range(5):
        r = requests.post(f"{BASE_URL}/books/{b['id']}/discount",
                          json={"discount_percent": 10})
        assert r.status_code == 200
    # 6th request should be rate limited
    r = requests.post(f"{BASE_URL}/books/{b['id']}/discount",
                      json={"discount_percent": 10})
    assert r.status_code == 429
    assert "Retry-After" in r.headers


# ══════════════════════════════════════════════════════════
# 503 · Maintenance mode
# ══════════════════════════════════════════════════════════

def test_maintenance_mode_503():
    # Activate maintenance
    r = requests.post(f"{BASE_URL}/admin/maintenance", headers=AUTH,
                      json={"enabled": True})
    assert r.status_code == 200
    assert r.json()["maintenance_mode"] is True

    # Regular endpoint → 503
    r = requests.get(f"{BASE_URL}/authors")
    assert r.status_code == 503
    assert "Retry-After" in r.headers

    # Health is exempt
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200

    # Deactivate
    r = requests.post(f"{BASE_URL}/admin/maintenance", headers=AUTH,
                      json={"enabled": False})
    assert r.status_code == 200

    # Regular endpoint works again
    r = requests.get(f"{BASE_URL}/authors")
    assert r.status_code == 200


# ══════════════════════════════════════════════════════════
# 301 · Deprecated redirect
# ══════════════════════════════════════════════════════════

def test_catalog_redirect_301():
    r = requests.get(f"{BASE_URL}/catalog", allow_redirects=False)
    assert r.status_code == 301
    assert "/books" in r.headers.get("location", "")


# ══════════════════════════════════════════════════════════
# 405 · Method Not Allowed
# ══════════════════════════════════════════════════════════

def test_method_not_allowed_405():
    r = requests.put(f"{BASE_URL}/health")
    assert r.status_code == 405


# ══════════════════════════════════════════════════════════
# 202 · Async export
# ══════════════════════════════════════════════════════════

def test_export_books_async_202_then_200():
    _, _, _ = setup_book_with_deps(isbn="EXP0000001")
    # Start export → 202
    r = requests.post(f"{BASE_URL}/exports/books", headers=AUTH)
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    assert r.json()["status"] == "processing"

    # Immediate poll might be 202
    r2 = requests.get(f"{BASE_URL}/exports/{job_id}")
    assert r2.status_code in (200, 202)

    # Wait for completion (2s simulated delay)
    time.sleep(2.5)
    r3 = requests.get(f"{BASE_URL}/exports/{job_id}")
    assert r3.status_code == 200
    assert r3.json()["status"] == "completed"
    assert r3.json()["total"] >= 1



def test_export_nonexistent_job_404():
    r = requests.get(f"{BASE_URL}/exports/nonexistent-job-id")
    assert r.status_code == 404


# ══════════════════════════════════════════════════════════
# Order filters
# ══════════════════════════════════════════════════════════

def test_list_orders_filter_by_status():
    _, _, b = setup_book_with_deps(isbn="FILT000001", stock=20)
    o1 = create_order("Alice", "a@t.com",
                      [{"book_id": b["id"], "quantity": 1}])
    create_order("Bob", "b@t.com",
                 [{"book_id": b["id"], "quantity": 1}])
    requests.patch(f"{BASE_URL}/orders/{o1['id']}/status",
                   json={"status": "confirmed"})
    r = requests.get(f"{BASE_URL}/orders", params={"status": "confirmed"})
    assert r.status_code == 200
    assert all(o["status"] == "confirmed" for o in r.json()["items"])


# ══════════════════════════════════════════════════════════
# Author books sub-resource
# ══════════════════════════════════════════════════════════

def test_author_books_sub_resource():
    a, c, b = setup_book_with_deps(isbn="ASUB000001")
    r = requests.get(f"{BASE_URL}/authors/{a['id']}/books")
    assert r.status_code == 200
    assert r.json()["total"] >= 1