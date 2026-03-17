-- Bookstore API – Databázové schéma (SQLite)
-- Export pro účely white-box testování (L3)

CREATE TABLE authors (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    name     VARCHAR(100) NOT NULL,
    bio      TEXT,
    born_year INTEGER,
    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        VARCHAR(50) NOT NULL UNIQUE,
    description TEXT
);

CREATE TABLE books (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          VARCHAR(200) NOT NULL,
    isbn           VARCHAR(13)  NOT NULL UNIQUE,
    price          REAL         NOT NULL CHECK (price >= 0),
    published_year INTEGER      NOT NULL,
    stock          INTEGER      NOT NULL DEFAULT 0 CHECK (stock >= 0),
    author_id      INTEGER      NOT NULL REFERENCES authors(id),
    category_id    INTEGER      NOT NULL REFERENCES categories(id),
    created_at     DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE reviews (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id       INTEGER      NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    rating        INTEGER      NOT NULL CHECK (rating >= 1 AND rating <= 5),
    comment       TEXT,
    reviewer_name VARCHAR(100) NOT NULL,
    created_at    DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE tags (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       VARCHAR(30) NOT NULL UNIQUE,
    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE book_tags (
    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    PRIMARY KEY (book_id, tag_id)
);

CREATE TABLE orders (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name  VARCHAR(100) NOT NULL,
    customer_email VARCHAR(200) NOT NULL,
    status         VARCHAR(20)  NOT NULL DEFAULT 'pending',
    created_at     DATETIME DEFAULT (datetime('now')),
    updated_at     DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE order_items (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id   INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    book_id    INTEGER NOT NULL REFERENCES books(id),
    quantity   INTEGER NOT NULL CHECK (quantity >= 1),
    unit_price REAL    NOT NULL
);

-- Indexy pro časté dotazy
CREATE INDEX idx_books_author    ON books(author_id);
CREATE INDEX idx_books_category  ON books(category_id);
CREATE INDEX idx_books_isbn      ON books(isbn);
CREATE INDEX idx_reviews_book    ON reviews(book_id);
CREATE INDEX idx_book_tags_book  ON book_tags(book_id);
CREATE INDEX idx_book_tags_tag   ON book_tags(tag_id);
CREATE INDEX idx_orders_status   ON orders(status);
CREATE INDEX idx_order_items_order ON order_items(order_id);