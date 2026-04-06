CREATE INDEX ix_authors_id ON authors (id);

CREATE INDEX ix_books_id ON books (id);

CREATE INDEX ix_categories_id ON categories (id);

CREATE INDEX ix_order_items_id ON order_items (id);

CREATE INDEX ix_orders_id ON orders (id);

CREATE INDEX ix_reviews_id ON reviews (id);

CREATE INDEX ix_tags_id ON tags (id);

CREATE TABLE authors (
	id INTEGER NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	bio TEXT, 
	born_year INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE book_tags (
	book_id INTEGER NOT NULL, 
	tag_id INTEGER NOT NULL, 
	PRIMARY KEY (book_id, tag_id), 
	FOREIGN KEY(book_id) REFERENCES books (id) ON DELETE CASCADE, 
	FOREIGN KEY(tag_id) REFERENCES tags (id) ON DELETE CASCADE
);

CREATE TABLE books (
	id INTEGER NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	isbn VARCHAR(13) NOT NULL, 
	price FLOAT NOT NULL, 
	published_year INTEGER NOT NULL, 
	stock INTEGER NOT NULL, 
	author_id INTEGER NOT NULL, 
	category_id INTEGER NOT NULL, 
	created_at DATETIME, 
	updated_at DATETIME, 
	is_deleted BOOLEAN NOT NULL, 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT check_price_positive CHECK (price >= 0), 
	CONSTRAINT check_stock_positive CHECK (stock >= 0), 
	UNIQUE (isbn), 
	FOREIGN KEY(author_id) REFERENCES authors (id), 
	FOREIGN KEY(category_id) REFERENCES categories (id)
);

CREATE TABLE categories (
	id INTEGER NOT NULL, 
	name VARCHAR(50) NOT NULL, 
	description TEXT, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

CREATE TABLE order_items (
	id INTEGER NOT NULL, 
	order_id INTEGER NOT NULL, 
	book_id INTEGER NOT NULL, 
	quantity INTEGER NOT NULL, 
	unit_price FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT check_quantity_positive CHECK (quantity >= 1), 
	FOREIGN KEY(order_id) REFERENCES orders (id), 
	FOREIGN KEY(book_id) REFERENCES books (id)
);

CREATE TABLE orders (
	id INTEGER NOT NULL, 
	customer_name VARCHAR(100) NOT NULL, 
	customer_email VARCHAR(200) NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id)
);

CREATE TABLE reviews (
	id INTEGER NOT NULL, 
	book_id INTEGER NOT NULL, 
	rating INTEGER NOT NULL, 
	comment TEXT, 
	reviewer_name VARCHAR(100) NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT check_rating_range CHECK (rating >= 1 AND rating <= 5), 
	FOREIGN KEY(book_id) REFERENCES books (id)
);

CREATE TABLE tags (
	id INTEGER NOT NULL, 
	name VARCHAR(30) NOT NULL, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (name)
);

