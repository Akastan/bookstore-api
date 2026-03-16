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