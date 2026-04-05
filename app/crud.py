
import math
import hashlib
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models, schemas


# ═══ ETag helper ═════════════════════════════════════════

def generate_etag(updated_at) -> str:
    return hashlib.md5(str(updated_at).encode()).hexdigest()


# ═══ Authors ═════════════════════════════════════════════

def create_author(db: Session, data: schemas.AuthorCreate) -> models.Author:
    author = models.Author(**data.model_dump())
    db.add(author)
    db.commit()
    db.refresh(author)
    return author


def get_author(db: Session, author_id: int) -> models.Author:
    author = db.query(models.Author).filter(models.Author.id == author_id).first()
    if not author:
        raise HTTPException(status_code=404, detail=f"Author with id {author_id} not found")
    return author


def get_authors(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Author).offset(skip).limit(limit).all()


def update_author(db: Session, author_id: int, data: schemas.AuthorUpdate):
    author = get_author(db, author_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(author, k, v)
    author.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(author)
    return author


def delete_author(db: Session, author_id: int):
    author = get_author(db, author_id)
    book_count = db.query(models.Book).filter(
        models.Book.author_id == author_id,
        models.Book.is_deleted == False,
    ).count()
    if book_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete author with {book_count} associated book(s). Remove books first."
        )
    db.delete(author)
    db.commit()


# ═══ Categories ══════════════════════════════════════════

def create_category(db: Session, data: schemas.CategoryCreate) -> models.Category:
    if db.query(models.Category).filter(models.Category.name == data.name).first():
        raise HTTPException(status_code=409, detail=f"Category '{data.name}' already exists")
    cat = models.Category(**data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


def get_category(db: Session, category_id: int) -> models.Category:
    cat = db.query(models.Category).filter(models.Category.id == category_id).first()
    if not cat:
        raise HTTPException(status_code=404, detail=f"Category with id {category_id} not found")
    return cat


def get_categories(db: Session):
    return db.query(models.Category).all()


def update_category(db: Session, category_id: int, data: schemas.CategoryUpdate):
    cat = get_category(db, category_id)
    update = data.model_dump(exclude_unset=True)
    if "name" in update:
        dup = db.query(models.Category).filter(
            models.Category.name == update["name"],
            models.Category.id != category_id
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"Category '{update['name']}' already exists")
    for k, v in update.items():
        setattr(cat, k, v)
    cat.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cat)
    return cat


def delete_category(db: Session, category_id: int):
    cat = get_category(db, category_id)
    book_count = db.query(models.Book).filter(
        models.Book.category_id == category_id,
        models.Book.is_deleted == False,
    ).count()
    if book_count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete category with {book_count} associated book(s). Remove books first."
        )
    db.delete(cat)
    db.commit()


# ═══ Books ═══════════════════════════════════════════════

def get_book(db: Session, book_id: int) -> models.Book:
    """Returns 404 if not found, 410 if soft-deleted."""
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail=f"Book with id {book_id} not found")
    if book.is_deleted:
        raise HTTPException(status_code=410, detail=f"Book with id {book_id} has been deleted")
    return book


def get_book_include_deleted(db: Session, book_id: int) -> models.Book:
    """Internal: returns book regardless of soft-delete status. 404 only."""
    book = db.query(models.Book).filter(models.Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail=f"Book with id {book_id} not found")
    return book


def create_book(db: Session, data: schemas.BookCreate) -> models.Book:
    get_author(db, data.author_id)
    get_category(db, data.category_id)
    if db.query(models.Book).filter(models.Book.isbn == data.isbn).first():
        raise HTTPException(status_code=409, detail=f"Book with ISBN '{data.isbn}' already exists")
    book = models.Book(**data.model_dump())
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def get_books(
    db: Session, page: int = 1, page_size: int = 10,
    search: str = None, author_id: int = None,
    category_id: int = None, min_price: float = None,
    max_price: float = None,
) -> schemas.PaginatedBooks:
    q = db.query(models.Book).filter(models.Book.is_deleted == False)
    if search:
        q = q.filter(or_(
            models.Book.title.ilike(f"%{search}%"),
            models.Book.isbn.ilike(f"%{search}%"),
        ))
    if author_id:
        q = q.filter(models.Book.author_id == author_id)
    if category_id:
        q = q.filter(models.Book.category_id == category_id)
    if min_price is not None:
        q = q.filter(models.Book.price >= min_price)
    if max_price is not None:
        q = q.filter(models.Book.price <= max_price)

    total = q.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return schemas.PaginatedBooks(
        items=items, total=total, page=page,
        page_size=page_size, total_pages=total_pages,
    )


def update_book(db: Session, book_id: int, data: schemas.BookUpdate):
    book = get_book(db, book_id)
    update = data.model_dump(exclude_unset=True)
    if "author_id" in update:
        get_author(db, update["author_id"])
    if "category_id" in update:
        get_category(db, update["category_id"])
    if "isbn" in update:
        dup = db.query(models.Book).filter(
            models.Book.isbn == update["isbn"],
            models.Book.id != book_id,
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"Book with ISBN '{update['isbn']}' already exists")
    for k, v in update.items():
        setattr(book, k, v)
    book.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(book)
    return book


def delete_book(db: Session, book_id: int):
    """Soft delete — sets is_deleted=True, preserves reviews and tags."""
    book = get_book(db, book_id)
    book.is_deleted = True
    book.deleted_at = datetime.now(timezone.utc)
    book.updated_at = datetime.now(timezone.utc)
    db.commit()


def restore_book(db: Session, book_id: int) -> models.Book:
    """Restore a soft-deleted book. 404 if not found, 400 if not deleted."""
    book = get_book_include_deleted(db, book_id)
    if not book.is_deleted:
        raise HTTPException(status_code=400, detail=f"Book with id {book_id} is not deleted")
    book.is_deleted = False
    book.deleted_at = None
    book.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(book)
    return book


# ═══ Reviews ═════════════════════════════════════════════

def create_review(db: Session, book_id: int, data: schemas.ReviewCreate):
    get_book(db, book_id)  # 404/410 check
    review = models.Review(book_id=book_id, **data.model_dump())
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def get_reviews(db: Session, book_id: int):
    get_book(db, book_id)
    return db.query(models.Review).filter(models.Review.book_id == book_id).all()


def get_book_average_rating(db: Session, book_id: int) -> dict:
    get_book(db, book_id)
    reviews = db.query(models.Review).filter(models.Review.book_id == book_id).all()
    if not reviews:
        return {"book_id": book_id, "average_rating": None, "review_count": 0}
    avg = sum(r.rating for r in reviews) / len(reviews)
    return {"book_id": book_id, "average_rating": round(avg, 2), "review_count": len(reviews)}


# ═══ Discount ════════════════════════════════════════════

def apply_discount(db: Session, book_id: int, data: schemas.DiscountRequest):
    book = get_book(db, book_id)
    current_year = datetime.now(timezone.utc).year
    if current_year - book.published_year < 1:
        raise HTTPException(
            status_code=400,
            detail="Discount can only be applied to books published more than 1 year ago",
        )
    discounted = round(book.price * (1 - data.discount_percent / 100), 2)
    return schemas.DiscountResponse(
        book_id=book.id, title=book.title,
        original_price=book.price,
        discount_percent=data.discount_percent,
        discounted_price=discounted,
    )


# ═══ Stock ═══════════════════════════════════════════════

def update_stock(db: Session, book_id: int, quantity: int):
    book = get_book(db, book_id)
    new_stock = book.stock + quantity
    if new_stock < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock. Current: {book.stock}, requested change: {quantity}",
        )
    book.stock = new_stock
    book.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(book)
    return book


# ═══ Tags ════════════════════════════════════════════════

def create_tag(db: Session, data: schemas.TagCreate) -> models.Tag:
    if db.query(models.Tag).filter(models.Tag.name == data.name).first():
        raise HTTPException(status_code=409, detail=f"Tag '{data.name}' already exists")
    tag = models.Tag(**data.model_dump())
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag


def get_tag(db: Session, tag_id: int) -> models.Tag:
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=404, detail=f"Tag with id {tag_id} not found")
    return tag


def get_tags(db: Session):
    return db.query(models.Tag).all()


def update_tag(db: Session, tag_id: int, data: schemas.TagUpdate):
    tag = get_tag(db, tag_id)
    update = data.model_dump(exclude_unset=True)
    if "name" in update:
        dup = db.query(models.Tag).filter(
            models.Tag.name == update["name"],
            models.Tag.id != tag_id,
        ).first()
        if dup:
            raise HTTPException(status_code=409, detail=f"Tag '{update['name']}' already exists")
    for k, v in update.items():
        setattr(tag, k, v)
    tag.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tag)
    return tag


def delete_tag(db: Session, tag_id: int):
    tag = get_tag(db, tag_id)
    if len(tag.books) > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete tag with {len(tag.books)} associated book(s). Remove tag from books first.",
        )
    db.delete(tag)
    db.commit()


def add_tags_to_book(db: Session, book_id: int, tag_ids: list[int]):
    book = get_book(db, book_id)
    for tid in tag_ids:
        tag = get_tag(db, tid)
        if tag not in book.tags:
            book.tags.append(tag)
    db.commit()
    db.refresh(book)
    return book


def remove_tags_from_book(db: Session, book_id: int, tag_ids: list[int]):
    book = get_book(db, book_id)
    for tid in tag_ids:
        tag = get_tag(db, tid)
        if tag in book.tags:
            book.tags.remove(tag)
    db.commit()
    db.refresh(book)
    return book


# ═══ Orders ══════════════════════════════════════════════

VALID_STATUS_TRANSITIONS = {
    "pending": ["confirmed", "cancelled"],
    "confirmed": ["shipped", "cancelled"],
    "shipped": ["delivered"],
    "delivered": [],
    "cancelled": [],
}


def create_order(db: Session, data: schemas.OrderCreate) -> models.Order:
    book_ids = [item.book_id for item in data.items]
    if len(book_ids) != len(set(book_ids)):
        raise HTTPException(status_code=400, detail="Duplicate book_id in order items")

    order_items = []
    for item in data.items:
        book = get_book(db, item.book_id)
        if book.stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for book '{book.title}'. "
                       f"Available: {book.stock}, requested: {item.quantity}",
            )
        order_items.append((book, item))

    order = models.Order(
        customer_name=data.customer_name,
        customer_email=data.customer_email,
        status="pending",
    )
    db.add(order)
    db.flush()

    for book, item in order_items:
        oi = models.OrderItem(
            order_id=order.id, book_id=item.book_id,
            quantity=item.quantity, unit_price=book.price,
        )
        db.add(oi)
        book.stock -= item.quantity

    db.commit()
    db.refresh(order)
    return order


def get_order(db: Session, order_id: int) -> models.Order:
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail=f"Order with id {order_id} not found")
    return order


def get_orders(
    db: Session, page: int = 1, page_size: int = 10,
    status: str = None, customer_name: str = None,
) -> schemas.PaginatedOrders:
    q = db.query(models.Order)
    if status:
        q = q.filter(models.Order.status == status)
    if customer_name:
        q = q.filter(models.Order.customer_name.ilike(f"%{customer_name}%"))

    total = q.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    orders = q.order_by(models.Order.created_at.desc()) \
              .offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for o in orders:
        total_price = sum(i.unit_price * i.quantity for i in o.items)
        items.append(schemas.OrderListResponse(
            id=o.id, customer_name=o.customer_name,
            customer_email=o.customer_email, status=o.status,
            total_price=round(total_price, 2), created_at=o.created_at,
        ))
    return schemas.PaginatedOrders(
        items=items, total=total, page=page,
        page_size=page_size, total_pages=total_pages,
    )


def update_order_status(db: Session, order_id: int, new_status: str) -> models.Order:
    order = get_order(db, order_id)
    allowed = VALID_STATUS_TRANSITIONS.get(order.status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from '{order.status}' to '{new_status}'. "
                   f"Allowed transitions: {allowed if allowed else 'none (terminal state)'}",
        )
    if new_status == "cancelled":
        for item in order.items:
            book = db.query(models.Book).filter(models.Book.id == item.book_id).first()
            if book:
                book.stock += item.quantity
    order.status = new_status
    order.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(order)
    return order


def delete_order(db: Session, order_id: int):
    order = get_order(db, order_id)
    if order.status not in ("pending", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete order in '{order.status}' state. "
                   f"Only pending or cancelled orders can be deleted.",
        )
    if order.status == "pending":
        for item in order.items:
            book = db.query(models.Book).filter(models.Book.id == item.book_id).first()
            if book:
                book.stock += item.quantity
    db.delete(order)
    db.commit()


def get_order_response(order: models.Order) -> dict:
    total_price = sum(i.unit_price * i.quantity for i in order.items)
    return {
        "id": order.id,
        "customer_name": order.customer_name,
        "customer_email": order.customer_email,
        "status": order.status,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "items": order.items,
        "total_price": round(total_price, 2),
    }


# ── Author's Books ───────────────────────────────────────

def get_author_books(db: Session, author_id: int, page: int = 1, page_size: int = 10):
    get_author(db, author_id)
    q = db.query(models.Book).filter(
        models.Book.author_id == author_id,
        models.Book.is_deleted == False,
    )
    total = q.count()
    total_pages = math.ceil(total / page_size) if total > 0 else 1
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return schemas.PaginatedBooks(
        items=items, total=total, page=page,
        page_size=page_size, total_pages=total_pages,
    )


# ── Bulk Create Books ────────────────────────────────────

def bulk_create_books(db: Session, data: schemas.BulkBookCreate) -> schemas.BulkCreateResponse:
    results = []
    created_count = 0
    failed_count = 0

    for i, book_data in enumerate(data.books):
        try:
            author = db.query(models.Author).filter(models.Author.id == book_data.author_id).first()
            if not author:
                raise ValueError(f"Author with id {book_data.author_id} not found")
            cat = db.query(models.Category).filter(models.Category.id == book_data.category_id).first()
            if not cat:
                raise ValueError(f"Category with id {book_data.category_id} not found")
            if db.query(models.Book).filter(models.Book.isbn == book_data.isbn).first():
                raise ValueError(f"Book with ISBN '{book_data.isbn}' already exists")

            book = models.Book(**book_data.model_dump())
            db.add(book)
            db.flush()
            db.refresh(book)
            results.append(schemas.BulkResultItem(index=i, status="created", book=book))
            created_count += 1
        except (ValueError, Exception) as e:
            results.append(schemas.BulkResultItem(index=i, status="error", error=str(e)))
            failed_count += 1

    if created_count > 0:
        db.commit()
    else:
        db.rollback()

    return schemas.BulkCreateResponse(
        total=len(data.books), created=created_count,
        failed=failed_count, results=results,
    )


# ── Clone Book ───────────────────────────────────────────

def clone_book(db: Session, book_id: int, data: schemas.BookCloneRequest) -> models.Book:
    source = get_book(db, book_id)
    if db.query(models.Book).filter(models.Book.isbn == data.new_isbn).first():
        raise HTTPException(status_code=409, detail=f"Book with ISBN '{data.new_isbn}' already exists")
    clone = models.Book(
        title=data.new_title or f"{source.title} (copy)",
        isbn=data.new_isbn, price=source.price,
        published_year=source.published_year, stock=data.stock,
        author_id=source.author_id, category_id=source.category_id,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return clone


# ── Invoice ──────────────────────────────────────────────

def generate_invoice(db: Session, order_id: int) -> schemas.InvoiceResponse:
    order = get_order(db, order_id)
    if order.status in ("pending", "cancelled"):
        raise HTTPException(
            status_code=403,
            detail=f"Cannot generate invoice for order in '{order.status}' state. "
                   f"Order must be confirmed, shipped, or delivered.",
        )
    items = []
    subtotal = 0.0
    for oi in order.items:
        book = db.query(models.Book).filter(models.Book.id == oi.book_id).first()
        line_total = round(oi.unit_price * oi.quantity, 2)
        items.append(schemas.InvoiceItem(
            book_title=book.title if book else "Unknown",
            isbn=book.isbn if book else "N/A",
            quantity=oi.quantity, unit_price=oi.unit_price, line_total=line_total,
        ))
        subtotal += line_total
    return schemas.InvoiceResponse(
        invoice_number=f"INV-{order.id:06d}", order_id=order.id,
        customer_name=order.customer_name, customer_email=order.customer_email,
        status=order.status, issued_at=datetime.now(timezone.utc).isoformat(),
        items=items, subtotal=round(subtotal, 2), item_count=len(items),
    )


# ── Add Item to Pending Order ────────────────────────────

def add_item_to_order(db: Session, order_id: int, data: schemas.OrderAddItem) -> models.Order:
    order = get_order(db, order_id)
    if order.status != "pending":
        raise HTTPException(
            status_code=403,
            detail=f"Cannot modify order in '{order.status}' state. Only pending orders can be modified.",
        )
    existing_book_ids = {oi.book_id for oi in order.items}
    if data.book_id in existing_book_ids:
        raise HTTPException(
            status_code=409,
            detail=f"Book {data.book_id} is already in this order.",
        )
    book = get_book(db, data.book_id)
    if book.stock < data.quantity:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient stock for book '{book.title}'. "
                   f"Available: {book.stock}, requested: {data.quantity}",
        )
    oi = models.OrderItem(
        order_id=order.id, book_id=data.book_id,
        quantity=data.quantity, unit_price=book.price,
    )
    db.add(oi)
    book.stock -= data.quantity
    order.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(order)
    return order


# ── Statistics ───────────────────────────────────────────

def get_statistics(db: Session) -> schemas.StatisticsSummary:
    total_books = db.query(models.Book).filter(models.Book.is_deleted == False).count()
    in_stock = db.query(models.Book).filter(
        models.Book.stock > 0, models.Book.is_deleted == False,
    ).count()

    delivered = db.query(models.Order).filter(models.Order.status == "delivered").all()
    revenue = sum(
        sum(i.unit_price * i.quantity for i in order.items)
        for order in delivered
    )

    avg_price = None
    if total_books > 0:
        prices = [b.price for b in db.query(models.Book).filter(models.Book.is_deleted == False).all()]
        avg_price = round(sum(prices) / len(prices), 2)

    avg_rating = None
    reviews = db.query(models.Review).all()
    if reviews:
        avg_rating = round(sum(r.rating for r in reviews) / len(reviews), 2)

    status_counts = {}
    for status in ["pending", "confirmed", "shipped", "delivered", "cancelled"]:
        status_counts[status] = db.query(models.Order).filter(models.Order.status == status).count()

    return schemas.StatisticsSummary(
        total_authors=db.query(models.Author).count(),
        total_categories=db.query(models.Category).count(),
        total_books=total_books,
        total_tags=db.query(models.Tag).count(),
        total_orders=db.query(models.Order).count(),
        total_reviews=len(reviews),
        books_in_stock=in_stock,
        books_out_of_stock=total_books - in_stock,
        total_revenue=round(revenue, 2),
        average_book_price=avg_price,
        average_rating=avg_rating,
        orders_by_status=status_counts,
    )