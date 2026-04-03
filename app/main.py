from typing import Optional, List

from fastapi import FastAPI, Depends, Query
from sqlalchemy.orm import Session

from .database import engine, get_db, Base
from . import crud, schemas
from . import models

from fastapi.responses import JSONResponse

# Vytvoření tabulek při startu
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Bookstore API",
    description="REST API pro správu knihkupectví – knihy, autoři, kategorie, recenze, tagy a objednávky.",
    version="2.0.0",
)


# ── Health ───────────────────────────────────────────────

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok"}


# ── Authors ──────────────────────────────────────────────

@app.post("/authors", response_model=schemas.AuthorResponse, status_code=201, tags=["Authors"])
def create_author(author: schemas.AuthorCreate, db: Session = Depends(get_db)):
    return crud.create_author(db, author)


@app.get("/authors", response_model=List[schemas.AuthorResponse], tags=["Authors"])
def list_authors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_authors(db, skip=skip, limit=limit)


@app.get("/authors/{author_id}", response_model=schemas.AuthorResponse, tags=["Authors"])
def get_author(author_id: int, db: Session = Depends(get_db)):
    return crud.get_author(db, author_id)


@app.put("/authors/{author_id}", response_model=schemas.AuthorResponse, tags=["Authors"])
def update_author(author_id: int, author: schemas.AuthorUpdate, db: Session = Depends(get_db)):
    return crud.update_author(db, author_id, author)


@app.delete("/authors/{author_id}", status_code=204, tags=["Authors"])
def delete_author(author_id: int, db: Session = Depends(get_db)):
    crud.delete_author(db, author_id)


# ── Categories ───────────────────────────────────────────

@app.post("/categories", response_model=schemas.CategoryResponse, status_code=201, tags=["Categories"])
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    return crud.create_category(db, category)


@app.get("/categories", response_model=List[schemas.CategoryResponse], tags=["Categories"])
def list_categories(db: Session = Depends(get_db)):
    return crud.get_categories(db)


@app.get("/categories/{category_id}", response_model=schemas.CategoryResponse, tags=["Categories"])
def get_category(category_id: int, db: Session = Depends(get_db)):
    return crud.get_category(db, category_id)


@app.put("/categories/{category_id}", response_model=schemas.CategoryResponse, tags=["Categories"])
def update_category(category_id: int, category: schemas.CategoryUpdate, db: Session = Depends(get_db)):
    return crud.update_category(db, category_id, category)


@app.delete("/categories/{category_id}", status_code=204, tags=["Categories"])
def delete_category(category_id: int, db: Session = Depends(get_db)):
    crud.delete_category(db, category_id)


# ── Books ────────────────────────────────────────────────

@app.post("/books", response_model=schemas.BookResponse, status_code=201, tags=["Books"])
def create_book(book: schemas.BookCreate, db: Session = Depends(get_db)):
    return crud.create_book(db, book)


@app.get("/books", response_model=schemas.PaginatedBooks, tags=["Books"])
def list_books(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    author_id: Optional[int] = None,
    category_id: Optional[int] = None,
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    db: Session = Depends(get_db),
):
    return crud.get_books(
        db, page=page, page_size=page_size, search=search,
        author_id=author_id, category_id=category_id,
        min_price=min_price, max_price=max_price,
    )


@app.get("/books/{book_id}", response_model=schemas.BookResponse, tags=["Books"])
def get_book(book_id: int, db: Session = Depends(get_db)):
    return crud.get_book(db, book_id)


@app.put("/books/{book_id}", response_model=schemas.BookResponse, tags=["Books"])
def update_book(book_id: int, book: schemas.BookUpdate, db: Session = Depends(get_db)):
    return crud.update_book(db, book_id, book)


@app.delete("/books/{book_id}", status_code=204, tags=["Books"])
def delete_book(book_id: int, db: Session = Depends(get_db)):
    crud.delete_book(db, book_id)


# ── Reviews ──────────────────────────────────────────────

@app.post("/books/{book_id}/reviews", response_model=schemas.ReviewResponse, status_code=201, tags=["Reviews"])
def create_review(book_id: int, review: schemas.ReviewCreate, db: Session = Depends(get_db)):
    return crud.create_review(db, book_id, review)


@app.get("/books/{book_id}/reviews", response_model=List[schemas.ReviewResponse], tags=["Reviews"])
def list_reviews(book_id: int, db: Session = Depends(get_db)):
    return crud.get_reviews(db, book_id)


@app.get("/books/{book_id}/rating", tags=["Reviews"])
def get_book_rating(book_id: int, db: Session = Depends(get_db)):
    return crud.get_book_average_rating(db, book_id)


# ── Discount ─────────────────────────────────────────────

@app.post("/books/{book_id}/discount", response_model=schemas.DiscountResponse, tags=["Books"])
def apply_discount(book_id: int, discount: schemas.DiscountRequest, db: Session = Depends(get_db)):
    return crud.apply_discount(db, book_id, discount)


# ── Stock ────────────────────────────────────────────────

@app.patch("/books/{book_id}/stock", response_model=schemas.BookResponse, tags=["Books"])
def update_stock(book_id: int, quantity: int = Query(...), db: Session = Depends(get_db)):
    return crud.update_stock(db, book_id, quantity)


# ── Tags ─────────────────────────────────────────────────

@app.post("/tags", response_model=schemas.TagResponse, status_code=201, tags=["Tags"])
def create_tag(tag: schemas.TagCreate, db: Session = Depends(get_db)):
    return crud.create_tag(db, tag)


@app.get("/tags", response_model=List[schemas.TagResponse], tags=["Tags"])
def list_tags(db: Session = Depends(get_db)):
    return crud.get_tags(db)


@app.get("/tags/{tag_id}", response_model=schemas.TagResponse, tags=["Tags"])
def get_tag(tag_id: int, db: Session = Depends(get_db)):
    return crud.get_tag(db, tag_id)


@app.put("/tags/{tag_id}", response_model=schemas.TagResponse, tags=["Tags"])
def update_tag(tag_id: int, tag: schemas.TagUpdate, db: Session = Depends(get_db)):
    return crud.update_tag(db, tag_id, tag)


@app.delete("/tags/{tag_id}", status_code=204, tags=["Tags"])
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    crud.delete_tag(db, tag_id)


@app.post("/books/{book_id}/tags", response_model=schemas.BookResponse, tags=["Tags"])
def add_tags_to_book(book_id: int, action: schemas.BookTagAction, db: Session = Depends(get_db)):
    """Přidá tagy ke knize. Již existující vazby se ignorují."""
    return crud.add_tags_to_book(db, book_id, action.tag_ids)


@app.delete("/books/{book_id}/tags", response_model=schemas.BookResponse, tags=["Tags"])
def remove_tags_from_book(book_id: int, action: schemas.BookTagAction, db: Session = Depends(get_db)):
    """Odebere tagy z knihy."""
    return crud.remove_tags_from_book(db, book_id, action.tag_ids)


# ── Orders ───────────────────────────────────────────────

@app.post("/orders", response_model=schemas.OrderResponse, status_code=201, tags=["Orders"])
def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
    """Vytvoří objednávku, odečte sklad a zachytí aktuální ceny."""
    o = crud.create_order(db, order)
    return crud.get_order_response(o)


@app.get("/orders", response_model=schemas.PaginatedOrders, tags=["Orders"])
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    customer_name: Optional[str] = None,
    db: Session = Depends(get_db),
):
    return crud.get_orders(db, page=page, page_size=page_size,
                           status=status, customer_name=customer_name)


@app.get("/orders/{order_id}", response_model=schemas.OrderResponse, tags=["Orders"])
def get_order(order_id: int, db: Session = Depends(get_db)):
    o = crud.get_order(db, order_id)
    return crud.get_order_response(o)


@app.patch("/orders/{order_id}/status", response_model=schemas.OrderResponse, tags=["Orders"])
def update_order_status(
    order_id: int,
    status_update: schemas.OrderStatusUpdate,
    db: Session = Depends(get_db),
):
    """Změní stav objednávky dle povolených přechodů. Při zrušení vrátí sklad."""
    o = crud.update_order_status(db, order_id, status_update.status)
    return crud.get_order_response(o)


@app.delete("/orders/{order_id}", status_code=204, tags=["Orders"])
def delete_order(order_id: int, db: Session = Depends(get_db)):
    """Smaže objednávku. Lze smazat pouze pending nebo cancelled objednávky."""
    crud.delete_order(db, order_id)


# ── Reset (pro testovací framework) ──────────────────────

@app.post("/reset", tags=["Testing"])
def reset_database(db: Session = Depends(get_db)):
    """Smaže všechna data z databáze. Pouze pro testovací účely."""
    db.execute(models.Review.__table__.delete())
    db.execute(models.OrderItem.__table__.delete())
    db.execute(models.Order.__table__.delete())
    db.execute(models.book_tags.delete())
    db.execute(models.Book.__table__.delete())
    db.execute(models.Tag.__table__.delete())
    db.execute(models.Category.__table__.delete())
    db.execute(models.Author.__table__.delete())
    db.commit()
    return {"status": "ok", "message": "Database reset complete"}


# ── Author's Books ───────────────────────────────────────

@app.get("/authors/{author_id}/books", response_model=schemas.PaginatedBooks,
         tags=["Authors"])
def list_author_books(
    author_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Seznam knih daného autora s stránkováním."""
    return crud.get_author_books(db, author_id, page=page, page_size=page_size)


# ── Bulk Create Books ────────────────────────────────────

@app.post("/books/bulk", tags=["Books"])
def bulk_create_books(
    data: schemas.BulkBookCreate, db: Session = Depends(get_db),
):
    """
    Hromadné vytvoření knih. Každá kniha se validuje samostatně.
    Vrací 201 pokud všechny uspěly, 207 pokud některé selhaly,
    422 pokud všechny selhaly.
    """
    result = crud.bulk_create_books(db, data)

    if result.failed == 0:
        return JSONResponse(status_code=201, content=result.model_dump())
    elif result.created == 0:
        return JSONResponse(status_code=422, content=result.model_dump())
    else:
        return JSONResponse(status_code=207, content=result.model_dump())


# ── Clone Book ───────────────────────────────────────────

@app.post("/books/{book_id}/clone", response_model=schemas.BookResponse,
          status_code=201, tags=["Books"])
def clone_book(
    book_id: int, data: schemas.BookCloneRequest,
    db: Session = Depends(get_db),
):
    """Vytvoří kopii knihy s novým ISBN. Stock se nekopíruje."""
    return crud.clone_book(db, book_id, data)


# ── Invoice ──────────────────────────────────────────────

@app.get("/orders/{order_id}/invoice", response_model=schemas.InvoiceResponse,
         tags=["Orders"])
def get_invoice(order_id: int, db: Session = Depends(get_db)):
    """
    Vygeneruje fakturu pro objednávku.
    Dostupné pouze pro objednávky ve stavu confirmed, shipped nebo delivered.
    Pending a cancelled → 403.
    """
    return crud.generate_invoice(db, order_id)


# ── Add Item to Order ────────────────────────────────────

@app.post("/orders/{order_id}/items", response_model=schemas.OrderResponse,
          status_code=201, tags=["Orders"])
def add_item_to_order(
    order_id: int, data: schemas.OrderAddItem,
    db: Session = Depends(get_db),
):
    """
    Přidá položku do existující objednávky.
    Pouze pending objednávky lze modifikovat (jinak 403).
    Duplicitní book_id v objednávce → 409.
    """
    order = crud.add_item_to_order(db, order_id, data)
    return crud.get_order_response(order)


# ── Statistics ───────────────────────────────────────────

@app.get("/statistics/summary", response_model=schemas.StatisticsSummary,
         tags=["Statistics"])
def get_statistics(db: Session = Depends(get_db)):
    """Souhrnné statistiky knihkupectví. Obrat se počítá jen z delivered objednávek."""
    return crud.get_statistics(db)