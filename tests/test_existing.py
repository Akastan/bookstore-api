"""
Existující testy Bookstore API.
Ukázka testovacího stylu pro in-context learning (L4).
"""
import pytest
import requests

BASE_URL = "http://localhost:8000"


# ── Helpers ──────────────────────────────────────────────

def create_test_author(name="Test Author", bio=None, born_year=1980):
    """Vytvoří autora a vrátí jeho JSON odpověď."""
    r = requests.post(f"{BASE_URL}/authors", json={
        "name": name, "bio": bio, "born_year": born_year
    })
    assert r.status_code == 201
    return r.json()


def create_test_category(name="Test Category"):
    """Vytvoří kategorii a vrátí její JSON odpověď."""
    r = requests.post(f"{BASE_URL}/categories", json={"name": name})
    assert r.status_code == 201
    return r.json()


def create_test_book(author_id, category_id, title="Test Book",
                     isbn="1234567890", price=29.99, published_year=2020, stock=10):
    """Vytvoří knihu a vrátí její JSON odpověď."""
    r = requests.post(f"{BASE_URL}/books", json={
        "title": title, "isbn": isbn, "price": price,
        "published_year": published_year, "stock": stock,
        "author_id": author_id, "category_id": category_id,
    })
    assert r.status_code == 201
    return r.json()


def create_test_tag(name="test-tag"):
    """Vytvoří tag a vrátí jeho JSON odpověď."""
    r = requests.post(f"{BASE_URL}/tags", json={"name": name})
    assert r.status_code == 201
    return r.json()


def create_test_order(customer_name, customer_email, items):
    """Vytvoří objednávku a vrátí její JSON odpověď."""
    r = requests.post(f"{BASE_URL}/orders", json={
        "customer_name": customer_name,
        "customer_email": customer_email,
        "items": items,
    })
    assert r.status_code == 201
    return r.json()


# ── Health ───────────────────────────────────────────────

def test_health_check():
    r = requests.get(f"{BASE_URL}/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"


# ── Authors CRUD ─────────────────────────────────────────

def test_create_author_happy_path():
    data = create_test_author(name="George Orwell", born_year=1903)
    assert data["name"] == "George Orwell"
    assert data["born_year"] == 1903
    assert "id" in data
    assert "created_at" in data


def test_create_author_missing_name():
    r = requests.post(f"{BASE_URL}/authors", json={"bio": "no name"})
    assert r.status_code == 422


def test_get_author_not_found():
    r = requests.get(f"{BASE_URL}/authors/999999")
    assert r.status_code == 404
    assert "detail" in r.json()


def test_delete_author_with_books_fails():
    author = create_test_author(name="Author With Books")
    cat = create_test_category(name="Cat For Delete Test")
    create_test_book(author["id"], cat["id"], isbn="9999999990")

    r = requests.delete(f"{BASE_URL}/authors/{author['id']}")
    assert r.status_code == 409
    assert "associated book" in r.json()["detail"].lower()


# ── Books – validace ─────────────────────────────────────

def test_create_book_duplicate_isbn():
    author = create_test_author(name="ISBN Test Author")
    cat = create_test_category(name="ISBN Test Cat")
    isbn = "1111111111"
    create_test_book(author["id"], cat["id"], isbn=isbn)

    r = requests.post(f"{BASE_URL}/books", json={
        "title": "Duplicate", "isbn": isbn, "price": 10,
        "published_year": 2020, "stock": 5,
        "author_id": author["id"], "category_id": cat["id"],
    })
    assert r.status_code == 409


def test_create_book_negative_price():
    author = create_test_author(name="Price Test Author")
    cat = create_test_category(name="Price Test Cat")
    r = requests.post(f"{BASE_URL}/books", json={
        "title": "Cheap", "isbn": "0000000001", "price": -5,
        "published_year": 2020, "author_id": author["id"],
        "category_id": cat["id"],
    })
    assert r.status_code == 422


# ── Discount ─────────────────────────────────────────────

def test_discount_old_book():
    author = create_test_author(name="Discount Author")
    cat = create_test_category(name="Discount Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="5555555555", price=100, published_year=2020)

    r = requests.post(f"{BASE_URL}/books/{book['id']}/discount",
                      json={"discount_percent": 25})
    assert r.status_code == 200
    data = r.json()
    assert data["original_price"] == 100
    assert data["discounted_price"] == 75.0
    assert data["discount_percent"] == 25


def test_discount_new_book_rejected():
    author = create_test_author(name="New Book Author")
    cat = create_test_category(name="New Book Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="6666666666", price=50, published_year=2026)

    r = requests.post(f"{BASE_URL}/books/{book['id']}/discount",
                      json={"discount_percent": 10})
    assert r.status_code == 400


# ── Stock ────────────────────────────────────────────────

def test_stock_decrease_below_zero():
    author = create_test_author(name="Stock Author")
    cat = create_test_category(name="Stock Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="7777777777", stock=3)

    r = requests.patch(f"{BASE_URL}/books/{book['id']}/stock", params={"quantity": -10})
    assert r.status_code == 400
    assert "insufficient stock" in r.json()["detail"].lower()


# ── Tags CRUD ────────────────────────────────────────────

def test_create_tag_happy_path():
    data = create_test_tag(name="fiction")
    assert data["name"] == "fiction"
    assert "id" in data
    assert "created_at" in data


def test_create_tag_duplicate_name():
    create_test_tag(name="duplicate-tag")
    r = requests.post(f"{BASE_URL}/tags", json={"name": "duplicate-tag"})
    assert r.status_code == 409


def test_create_tag_empty_name():
    r = requests.post(f"{BASE_URL}/tags", json={"name": ""})
    assert r.status_code == 422


def test_get_tag_not_found():
    r = requests.get(f"{BASE_URL}/tags/999999")
    assert r.status_code == 404


def test_update_tag():
    tag = create_test_tag(name="old-name")
    r = requests.put(f"{BASE_URL}/tags/{tag['id']}", json={"name": "new-name"})
    assert r.status_code == 200
    assert r.json()["name"] == "new-name"


def test_delete_tag_without_books():
    tag = create_test_tag(name="lonely-tag")
    r = requests.delete(f"{BASE_URL}/tags/{tag['id']}")
    assert r.status_code == 204


def test_delete_tag_with_books_fails():
    author = create_test_author(name="Tag Del Author")
    cat = create_test_category(name="Tag Del Cat")
    book = create_test_book(author["id"], cat["id"], isbn="8880000001")
    tag = create_test_tag(name="attached-tag")

    requests.post(f"{BASE_URL}/books/{book['id']}/tags",
                  json={"tag_ids": [tag["id"]]})

    r = requests.delete(f"{BASE_URL}/tags/{tag['id']}")
    assert r.status_code == 409


# ── Book ↔ Tag vazby ─────────────────────────────────────

def test_add_tags_to_book():
    author = create_test_author(name="Tag Book Author")
    cat = create_test_category(name="Tag Book Cat")
    book = create_test_book(author["id"], cat["id"], isbn="8881111111")
    t1 = create_test_tag(name="tag-a")
    t2 = create_test_tag(name="tag-b")

    r = requests.post(f"{BASE_URL}/books/{book['id']}/tags",
                      json={"tag_ids": [t1["id"], t2["id"]]})
    assert r.status_code == 200
    tag_names = [t["name"] for t in r.json()["tags"]]
    assert "tag-a" in tag_names
    assert "tag-b" in tag_names


def test_add_tags_idempotent():
    """Přidání stejného tagu dvakrát nevytvoří duplicitní vazbu."""
    author = create_test_author(name="Idemp Author")
    cat = create_test_category(name="Idemp Cat")
    book = create_test_book(author["id"], cat["id"], isbn="8882222222")
    tag = create_test_tag(name="idemp-tag")

    requests.post(f"{BASE_URL}/books/{book['id']}/tags",
                  json={"tag_ids": [tag["id"]]})
    r = requests.post(f"{BASE_URL}/books/{book['id']}/tags",
                      json={"tag_ids": [tag["id"]]})
    assert r.status_code == 200
    assert len(r.json()["tags"]) == 1


def test_remove_tags_from_book():
    author = create_test_author(name="Rm Tag Author")
    cat = create_test_category(name="Rm Tag Cat")
    book = create_test_book(author["id"], cat["id"], isbn="8883333333")
    tag = create_test_tag(name="removable-tag")

    requests.post(f"{BASE_URL}/books/{book['id']}/tags",
                  json={"tag_ids": [tag["id"]]})
    r = requests.delete(f"{BASE_URL}/books/{book['id']}/tags",
                        json={"tag_ids": [tag["id"]]})
    assert r.status_code == 200
    assert len(r.json()["tags"]) == 0


def test_add_nonexistent_tag_fails():
    author = create_test_author(name="Ghost Tag Author")
    cat = create_test_category(name="Ghost Tag Cat")
    book = create_test_book(author["id"], cat["id"], isbn="8884444444")

    r = requests.post(f"{BASE_URL}/books/{book['id']}/tags",
                      json={"tag_ids": [999999]})
    assert r.status_code == 404


# ── Orders – vytvoření ───────────────────────────────────

def test_create_order_happy_path():
    author = create_test_author(name="Order Author")
    cat = create_test_category(name="Order Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="9990000001", price=50.0, stock=10)

    data = create_test_order(
        customer_name="Jan Novák",
        customer_email="jan@example.com",
        items=[{"book_id": book["id"], "quantity": 2}],
    )
    assert data["status"] == "pending"
    assert data["total_price"] == 100.0
    assert len(data["items"]) == 1
    assert data["items"][0]["unit_price"] == 50.0

    # Ověření odečtení skladu
    r = requests.get(f"{BASE_URL}/books/{book['id']}")
    assert r.json()["stock"] == 8


def test_create_order_insufficient_stock():
    author = create_test_author(name="Low Stock Author")
    cat = create_test_category(name="Low Stock Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="9990000002", price=10.0, stock=2)

    r = requests.post(f"{BASE_URL}/orders", json={
        "customer_name": "Test",
        "customer_email": "test@example.com",
        "items": [{"book_id": book["id"], "quantity": 5}],
    })
    assert r.status_code == 400
    assert "insufficient stock" in r.json()["detail"].lower()


def test_create_order_duplicate_book_ids():
    author = create_test_author(name="Dup Item Author")
    cat = create_test_category(name="Dup Item Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="9990000003", stock=10)

    r = requests.post(f"{BASE_URL}/orders", json={
        "customer_name": "Test",
        "customer_email": "test@example.com",
        "items": [
            {"book_id": book["id"], "quantity": 1},
            {"book_id": book["id"], "quantity": 2},
        ],
    })
    assert r.status_code == 400
    assert "duplicate" in r.json()["detail"].lower()


def test_create_order_empty_items():
    r = requests.post(f"{BASE_URL}/orders", json={
        "customer_name": "Test",
        "customer_email": "test@example.com",
        "items": [],
    })
    assert r.status_code == 422


def test_create_order_nonexistent_book():
    r = requests.post(f"{BASE_URL}/orders", json={
        "customer_name": "Test",
        "customer_email": "test@example.com",
        "items": [{"book_id": 999999, "quantity": 1}],
    })
    assert r.status_code == 404


# ── Orders – stavový automat ─────────────────────────────

def test_order_status_pending_to_confirmed():
    author = create_test_author(name="Status Author")
    cat = create_test_category(name="Status Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="9991111111", stock=10)
    order = create_test_order("Test", "t@t.com",
                              [{"book_id": book["id"], "quantity": 1}])

    r = requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                       json={"status": "confirmed"})
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"


def test_order_status_full_lifecycle():
    """pending → confirmed → shipped → delivered"""
    author = create_test_author(name="Lifecycle Author")
    cat = create_test_category(name="Lifecycle Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="9992222222", stock=10)
    order = create_test_order("Test", "t@t.com",
                              [{"book_id": book["id"], "quantity": 1}])

    for status in ["confirmed", "shipped", "delivered"]:
        r = requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                           json={"status": status})
        assert r.status_code == 200
        assert r.json()["status"] == status


def test_order_status_invalid_transition():
    """pending → shipped by nemělo být povoleno."""
    author = create_test_author(name="Invalid Trans Author")
    cat = create_test_category(name="Invalid Trans Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="9993333333", stock=10)
    order = create_test_order("Test", "t@t.com",
                              [{"book_id": book["id"], "quantity": 1}])

    r = requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                       json={"status": "shipped"})
    assert r.status_code == 400


def test_order_cancel_restores_stock():
    author = create_test_author(name="Cancel Author")
    cat = create_test_category(name="Cancel Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="9994444444", stock=10)
    order = create_test_order("Test", "t@t.com",
                              [{"book_id": book["id"], "quantity": 3}])

    # Sklad by měl být 7
    r = requests.get(f"{BASE_URL}/books/{book['id']}")
    assert r.json()["stock"] == 7

    # Zrušení objednávky
    r = requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                       json={"status": "cancelled"})
    assert r.status_code == 200

    # Sklad by měl být zpět na 10
    r = requests.get(f"{BASE_URL}/books/{book['id']}")
    assert r.json()["stock"] == 10


def test_order_cancelled_is_terminal():
    """Ze stavu cancelled nelze přejít nikam."""
    author = create_test_author(name="Terminal Author")
    cat = create_test_category(name="Terminal Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="9995555555", stock=10)
    order = create_test_order("Test", "t@t.com",
                              [{"book_id": book["id"], "quantity": 1}])

    requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                   json={"status": "cancelled"})
    r = requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                       json={"status": "confirmed"})
    assert r.status_code == 400


# ── Orders – mazání ──────────────────────────────────────

def test_delete_pending_order_restores_stock():
    author = create_test_author(name="Del Pending Author")
    cat = create_test_category(name="Del Pending Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="9996666666", stock=10)
    order = create_test_order("Test", "t@t.com",
                              [{"book_id": book["id"], "quantity": 4}])

    r = requests.delete(f"{BASE_URL}/orders/{order['id']}")
    assert r.status_code == 204

    r = requests.get(f"{BASE_URL}/books/{book['id']}")
    assert r.json()["stock"] == 10


def test_delete_confirmed_order_fails():
    author = create_test_author(name="Del Conf Author")
    cat = create_test_category(name="Del Conf Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="9997777777", stock=10)
    order = create_test_order("Test", "t@t.com",
                              [{"book_id": book["id"], "quantity": 1}])

    requests.patch(f"{BASE_URL}/orders/{order['id']}/status",
                   json={"status": "confirmed"})
    r = requests.delete(f"{BASE_URL}/orders/{order['id']}")
    assert r.status_code == 400


# ── Orders – stránkování a filtry ────────────────────────

def test_list_orders_filter_by_status():
    author = create_test_author(name="Filter Author")
    cat = create_test_category(name="Filter Cat")
    book = create_test_book(author["id"], cat["id"],
                            isbn="9998888888", stock=20)

    o1 = create_test_order("Alice", "a@t.com",
                           [{"book_id": book["id"], "quantity": 1}])
    o2 = create_test_order("Bob", "b@t.com",
                           [{"book_id": book["id"], "quantity": 1}])

    # Potvrdíme jednu objednávku
    requests.patch(f"{BASE_URL}/orders/{o1['id']}/status",
                   json={"status": "confirmed"})

    r = requests.get(f"{BASE_URL}/orders", params={"status": "confirmed"})
    assert r.status_code == 200
    data = r.json()
    statuses = [o["status"] for o in data["items"]]
    assert all(s == "confirmed" for s in statuses)


def test_get_order_not_found():
    r = requests.get(f"{BASE_URL}/orders/999999")
    assert r.status_code == 404