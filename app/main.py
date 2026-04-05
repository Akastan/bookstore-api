
import os
import time
import uuid
import datetime
from typing import Optional, List
from collections import defaultdict

from fastapi import (
    FastAPI, Depends, Query, Request, Response,
    UploadFile, File, Security, HTTPException,
)
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from .database import engine, get_db, Base
from . import crud, schemas, models

Base.metadata.create_all(bind=engine)

# ── Configuration ────────────────────────────────────────

API_KEY = os.getenv("API_KEY", "test-api-key")
MAX_COVER_SIZE = 2 * 1024 * 1024  # 2 MB
ALLOWED_COVER_TYPES = {"image/jpeg", "image/png"}

# ── In-memory state (cleared on /reset) ─────────────────

maintenance_mode = False
cover_storage: dict[int, dict] = {}        # book_id -> {data, filename, content_type, size}
export_jobs: dict[str, dict] = {}           # job_id -> {status, created_at, complete_after, data}
rate_limit_store: defaultdict = defaultdict(list)  # key -> [timestamps]

# Rate limits: (max_requests, window_seconds)
RATE_LIMITS = {
    "bulk": (3, 30),
    "discount": (5, 10),
}

MAINTENANCE_EXEMPT = {"/health", "/admin/maintenance", "/openapi.json", "/docs", "/redoc"}

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(api_key: str = Security(api_key_header)):
    if not api_key or api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key


# ── App ──────────────────────────────────────────────────

app = FastAPI(
    title="Bookstore API",
    description=(
        "REST API pro správu knihkupectví – knihy, autoři, kategorie, recenze, "
        "tagy a objednávky.\n\n"
        "**Autentizace:** Některé endpointy vyžadují hlavičku `X-API-Key`.\n\n"
        "**Rate limiting:** Endpoint `/books/bulk` (3 req/30s) a `/books/{id}/discount` "
        "(5 req/10s) mají rate limit. Při překročení vrací 429.\n\n"
        "**Maintenance mode:** Při aktivním maintenance režimu vrací neadmin endpointy 503.\n\n"
        "**Soft delete:** `DELETE /books/{id}` provede soft delete. "
        "`GET /books/{id}` na smazanou knihu vrátí 410 Gone.\n\n"
        "**ETags:** Detail endpointy vrací `ETag` header. `If-None-Match` → 304, "
        "`If-Match` na PUT → 412 při neshodě.\n\n"
        "**Nepoužívejte nepodporované HTTP metody** – vrací 405 Method Not Allowed."
    ),
    version="4.0.0",
)


# ── Middleware (registration order: last registered = first executed) ──

def _get_rate_limit_key(method: str, path: str) -> Optional[str]:
    if method == "POST" and path == "/books/bulk":
        return "bulk"
    if method == "POST" and "/discount" in path and path.startswith("/books/"):
        return "discount"
    return None


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    key = _get_rate_limit_key(request.method, request.url.path)
    if key and key in RATE_LIMITS:
        max_req, window = RATE_LIMITS[key]
        client_ip = request.client.host if request.client else "unknown"
        store_key = f"{client_ip}:{key}"
        now = time.time()
        rate_limit_store[store_key] = [t for t in rate_limit_store[store_key] if t > now - window]
        if len(rate_limit_store[store_key]) >= max_req:
            oldest = rate_limit_store[store_key][0]
            retry_after = int(window - (now - oldest)) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded for this endpoint. Try again later."},
                headers={"Retry-After": str(retry_after)},
            )
        rate_limit_store[store_key].append(now)
    return await call_next(request)


@app.middleware("http")
async def maintenance_middleware(request: Request, call_next):
    global maintenance_mode
    if maintenance_mode and request.url.path not in MAINTENANCE_EXEMPT:
        return JSONResponse(
            status_code=503,
            content={"detail": "Service temporarily unavailable for maintenance"},
            headers={"Retry-After": "300"},
        )
    return await call_next(request)


# ── ETag helpers ─────────────────────────────────────────

def _check_etag_get(request: Request, response: Response, updated_at) -> Optional[Response]:
    """For GET: set ETag, return 304 if If-None-Match matches."""
    etag = crud.generate_etag(updated_at)
    response.headers["ETag"] = f'"{etag}"'
    if_none_match = request.headers.get("if-none-match")
    if if_none_match and if_none_match.strip('"') == etag:
        return Response(status_code=304, headers={"ETag": f'"{etag}"'})
    return None


def _check_etag_put(request: Request, updated_at):
    """For PUT: check If-Match, raise 412 if mismatch."""
    if_match = request.headers.get("if-match")
    if if_match:
        current_etag = crud.generate_etag(updated_at)
        if if_match.strip('"') != current_etag:
            raise HTTPException(
                status_code=412,
                detail="Precondition Failed: resource has been modified since last read",
            )


# ── Health ───────────────────────────────────────────────

@app.get("/health", tags=["Health"],
         responses={405: {"description": "Method Not Allowed"}})
def health_check():
    return {"status": "ok"}


# ── Authors ──────────────────────────────────────────────

@app.post("/authors", response_model=schemas.AuthorResponse, status_code=201, tags=["Authors"])
def create_author(author: schemas.AuthorCreate, db: Session = Depends(get_db)):
    return crud.create_author(db, author)


@app.get("/authors", response_model=List[schemas.AuthorResponse], tags=["Authors"])
def list_authors(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_authors(db, skip=skip, limit=limit)


@app.get("/authors/{author_id}", response_model=schemas.AuthorResponse, tags=["Authors"],
         responses={304: {"description": "Not Modified"}, 404: {"description": "Author not found"}})
def get_author(author_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
    author = crud.get_author(db, author_id)
    cached = _check_etag_get(request, response, author.updated_at)
    if cached:
        return cached
    return author


@app.put("/authors/{author_id}", response_model=schemas.AuthorResponse, tags=["Authors"],
         responses={412: {"description": "Precondition Failed – ETag mismatch"}})
def update_author(author_id: int, author: schemas.AuthorUpdate,
                  request: Request, db: Session = Depends(get_db)):
    existing = crud.get_author(db, author_id)
    _check_etag_put(request, existing.updated_at)
    return crud.update_author(db, author_id, author)


@app.delete("/authors/{author_id}", status_code=204, tags=["Authors"])
def delete_author(author_id: int, db: Session = Depends(get_db)):
    crud.delete_author(db, author_id)


@app.get("/authors/{author_id}/books", response_model=schemas.PaginatedBooks, tags=["Authors"])
def list_author_books(
    author_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return crud.get_author_books(db, author_id, page=page, page_size=page_size)


# ── Categories ───────────────────────────────────────────

@app.post("/categories", response_model=schemas.CategoryResponse, status_code=201, tags=["Categories"])
def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    return crud.create_category(db, category)


@app.get("/categories", response_model=List[schemas.CategoryResponse], tags=["Categories"])
def list_categories(db: Session = Depends(get_db)):
    return crud.get_categories(db)


@app.get("/categories/{category_id}", response_model=schemas.CategoryResponse, tags=["Categories"],
         responses={304: {"description": "Not Modified"}})
def get_category(category_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
    cat = crud.get_category(db, category_id)
    cached = _check_etag_get(request, response, cat.updated_at)
    if cached:
        return cached
    return cat


@app.put("/categories/{category_id}", response_model=schemas.CategoryResponse, tags=["Categories"],
         responses={412: {"description": "Precondition Failed – ETag mismatch"}})
def update_category(category_id: int, category: schemas.CategoryUpdate,
                    request: Request, db: Session = Depends(get_db)):
    existing = crud.get_category(db, category_id)
    _check_etag_put(request, existing.updated_at)
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


@app.get("/books/{book_id}", response_model=schemas.BookResponse, tags=["Books"],
         responses={304: {"description": "Not Modified"}, 410: {"description": "Book has been deleted (soft delete)"}})
def get_book(book_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
    book = crud.get_book(db, book_id)
    cached = _check_etag_get(request, response, book.updated_at)
    if cached:
        return cached
    return book


@app.put("/books/{book_id}", response_model=schemas.BookResponse, tags=["Books"],
         responses={412: {"description": "Precondition Failed – ETag mismatch"},
                    410: {"description": "Book has been deleted"}})
def update_book(book_id: int, book: schemas.BookUpdate,
                request: Request, db: Session = Depends(get_db)):
    existing = crud.get_book(db, book_id)
    _check_etag_put(request, existing.updated_at)
    return crud.update_book(db, book_id, book)


@app.delete("/books/{book_id}", status_code=204, tags=["Books"],
            responses={410: {"description": "Book already deleted"}})
def delete_book(book_id: int, db: Session = Depends(get_db)):
    crud.delete_book(db, book_id)


@app.post("/books/{book_id}/restore", response_model=schemas.BookResponse, tags=["Books"],
          responses={400: {"description": "Book is not deleted"}, 404: {"description": "Book not found"}})
def restore_book(book_id: int, db: Session = Depends(get_db)):
    """Restore a soft-deleted book."""
    return crud.restore_book(db, book_id)


# ── Reviews ──────────────────────────────────────────────

@app.post("/books/{book_id}/reviews", response_model=schemas.ReviewResponse,
          status_code=201, tags=["Reviews"],
          responses={410: {"description": "Book has been deleted"}})
def create_review(book_id: int, review: schemas.ReviewCreate, db: Session = Depends(get_db)):
    return crud.create_review(db, book_id, review)


@app.get("/books/{book_id}/reviews", response_model=List[schemas.ReviewResponse], tags=["Reviews"])
def list_reviews(book_id: int, db: Session = Depends(get_db)):
    return crud.get_reviews(db, book_id)


@app.get("/books/{book_id}/rating", tags=["Reviews"])
def get_book_rating(book_id: int, db: Session = Depends(get_db)):
    return crud.get_book_average_rating(db, book_id)


# ── Discount ─────────────────────────────────────────────

@app.post("/books/{book_id}/discount", response_model=schemas.DiscountResponse, tags=["Books"],
          responses={429: {"description": "Rate limit exceeded (5 req/10s)"}})
def apply_discount(book_id: int, discount: schemas.DiscountRequest, db: Session = Depends(get_db)):
    return crud.apply_discount(db, book_id, discount)


# ── Stock ────────────────────────────────────────────────

@app.patch("/books/{book_id}/stock", response_model=schemas.BookResponse, tags=["Books"])
def update_stock(book_id: int, quantity: int = Query(...), db: Session = Depends(get_db)):
    return crud.update_stock(db, book_id, quantity)


# ── Cover Upload ─────────────────────────────────────────

@app.post("/books/{book_id}/cover", response_model=schemas.CoverUploadResponse, tags=["Books"],
          responses={
              413: {"description": "File too large (max 2 MB)"},
              415: {"description": "Unsupported file type (only JPEG, PNG)"},
              410: {"description": "Book has been deleted"},
          })
async def upload_cover(book_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    crud.get_book(db, book_id)
    if file.content_type not in ALLOWED_COVER_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {file.content_type}. Allowed: image/jpeg, image/png",
        )
    data = await file.read()
    if len(data) > MAX_COVER_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {len(data)} bytes. Maximum: {MAX_COVER_SIZE} bytes (2 MB)",
        )
    cover_storage[book_id] = {
        "data": data, "filename": file.filename or "cover",
        "content_type": file.content_type, "size": len(data),
    }
    return schemas.CoverUploadResponse(
        book_id=book_id, filename=file.filename or "cover",
        content_type=file.content_type, size_bytes=len(data),
    )


@app.get("/books/{book_id}/cover", tags=["Books"],
         responses={404: {"description": "No cover uploaded"}, 410: {"description": "Book has been deleted"}})
def get_cover(book_id: int, db: Session = Depends(get_db)):
    crud.get_book(db, book_id)
    if book_id not in cover_storage:
        raise HTTPException(status_code=404, detail="No cover uploaded for this book")
    c = cover_storage[book_id]
    return Response(content=c["data"], media_type=c["content_type"])


@app.delete("/books/{book_id}/cover", status_code=204, tags=["Books"])
def delete_cover(book_id: int, db: Session = Depends(get_db)):
    crud.get_book(db, book_id)
    if book_id not in cover_storage:
        raise HTTPException(status_code=404, detail="No cover uploaded for this book")
    del cover_storage[book_id]


# ── Tags ─────────────────────────────────────────────────

@app.post("/tags", response_model=schemas.TagResponse, status_code=201, tags=["Tags"])
def create_tag(tag: schemas.TagCreate, db: Session = Depends(get_db)):
    return crud.create_tag(db, tag)


@app.get("/tags", response_model=List[schemas.TagResponse], tags=["Tags"])
def list_tags(db: Session = Depends(get_db)):
    return crud.get_tags(db)


@app.get("/tags/{tag_id}", response_model=schemas.TagResponse, tags=["Tags"],
         responses={304: {"description": "Not Modified"}})
def get_tag(tag_id: int, request: Request, response: Response, db: Session = Depends(get_db)):
    tag = crud.get_tag(db, tag_id)
    cached = _check_etag_get(request, response, tag.updated_at)
    if cached:
        return cached
    return tag


@app.put("/tags/{tag_id}", response_model=schemas.TagResponse, tags=["Tags"],
         responses={412: {"description": "Precondition Failed – ETag mismatch"}})
def update_tag(tag_id: int, tag: schemas.TagUpdate,
               request: Request, db: Session = Depends(get_db)):
    existing = crud.get_tag(db, tag_id)
    _check_etag_put(request, existing.updated_at)
    return crud.update_tag(db, tag_id, tag)


@app.delete("/tags/{tag_id}", status_code=204, tags=["Tags"])
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    crud.delete_tag(db, tag_id)


@app.post("/books/{book_id}/tags", response_model=schemas.BookResponse, tags=["Tags"])
def add_tags_to_book(book_id: int, action: schemas.BookTagAction, db: Session = Depends(get_db)):
    return crud.add_tags_to_book(db, book_id, action.tag_ids)


@app.delete("/books/{book_id}/tags", response_model=schemas.BookResponse, tags=["Tags"])
def remove_tags_from_book(book_id: int, action: schemas.BookTagAction, db: Session = Depends(get_db)):
    return crud.remove_tags_from_book(db, book_id, action.tag_ids)


# ── Orders ───────────────────────────────────────────────

@app.post("/orders", response_model=schemas.OrderResponse, status_code=201, tags=["Orders"])
def create_order(order: schemas.OrderCreate, db: Session = Depends(get_db)):
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
    order_id: int, status_update: schemas.OrderStatusUpdate,
    db: Session = Depends(get_db),
):
    o = crud.update_order_status(db, order_id, status_update.status)
    return crud.get_order_response(o)


@app.delete("/orders/{order_id}", status_code=204, tags=["Orders"])
def delete_order(order_id: int, db: Session = Depends(get_db)):
    crud.delete_order(db, order_id)


@app.get("/orders/{order_id}/invoice", response_model=schemas.InvoiceResponse, tags=["Orders"])
def get_invoice(order_id: int, db: Session = Depends(get_db)):
    return crud.generate_invoice(db, order_id)


@app.post("/orders/{order_id}/items", response_model=schemas.OrderResponse,
          status_code=201, tags=["Orders"])
def add_item_to_order(order_id: int, data: schemas.OrderAddItem, db: Session = Depends(get_db)):
    order = crud.add_item_to_order(db, order_id, data)
    return crud.get_order_response(order)


# ── Bulk Create Books ────────────────────────────────────

@app.post("/books/bulk", tags=["Books"],
          responses={
              201: {"description": "All books created"},
              207: {"description": "Partial success"},
              401: {"description": "Invalid or missing API key"},
              422: {"description": "All books failed validation"},
              429: {"description": "Rate limit exceeded (3 req/30s)"},
          })
def bulk_create_books(
    data: schemas.BulkBookCreate,
    db: Session = Depends(get_db),
    _: str = Depends(require_api_key),
):
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
def clone_book(book_id: int, data: schemas.BookCloneRequest, db: Session = Depends(get_db)):
    return crud.clone_book(db, book_id, data)


# ── Async Exports ────────────────────────────────────────

@app.post("/exports/books", status_code=202, tags=["Exports"],
          response_model=schemas.ExportJobCreated,
          responses={401: {"description": "Invalid or missing API key"}})
def create_book_export(db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    """Start async book export. Poll GET /exports/{job_id} for result."""
    job_id = str(uuid.uuid4())
    books = db.query(models.Book).filter(models.Book.is_deleted == False).all()
    data = [
        {"id": b.id, "title": b.title, "isbn": b.isbn, "price": b.price,
         "stock": b.stock, "author_id": b.author_id, "category_id": b.category_id}
        for b in books
    ]
    now = time.time()
    export_jobs[job_id] = {
        "status": "processing",
        "created_at": datetime.now(datetime.timezone.utc).isoformat(),
        "complete_after": now + 2,  # Simulated 2s processing
        "data": data,
        "total": len(data),
    }
    return schemas.ExportJobCreated(
        job_id=job_id, status="processing",
        created_at=export_jobs[job_id]["created_at"],
    )


@app.post("/exports/orders", status_code=202, tags=["Exports"],
          response_model=schemas.ExportJobCreated,
          responses={401: {"description": "Invalid or missing API key"}})
def create_order_export(db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    """Start async order export. Poll GET /exports/{job_id} for result."""
    job_id = str(uuid.uuid4())
    orders = db.query(models.Order).all()
    data = [
        {"id": o.id, "customer_name": o.customer_name, "status": o.status,
         "total_price": round(sum(i.unit_price * i.quantity for i in o.items), 2),
         "item_count": len(o.items), "created_at": o.created_at.isoformat()}
        for o in orders
    ]
    now = time.time()
    export_jobs[job_id] = {
        "status": "processing",
        "created_at": datetime.now(datetime.timezone.utc).isoformat(),
        "complete_after": now + 2,
        "data": data,
        "total": len(data),
    }
    return schemas.ExportJobCreated(
        job_id=job_id, status="processing",
        created_at=export_jobs[job_id]["created_at"],
    )


@app.get("/exports/{job_id}", tags=["Exports"],
         responses={
             200: {"description": "Export completed", "model": schemas.ExportJobResult},
             202: {"description": "Export still processing"},
             404: {"description": "Export job not found"},
         })
def get_export_job(job_id: str):
    job = export_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Export job {job_id} not found")

    if time.time() < job["complete_after"]:
        return JSONResponse(
            status_code=202,
            content={"job_id": job_id, "status": "processing", "created_at": job["created_at"]},
        )
    return schemas.ExportJobResult(
        job_id=job_id, status="completed", created_at=job["created_at"],
        completed_at=datetime.now(datetime.timezone.utc).isoformat(),
        total=job["total"], data=job["data"],
    )


# ── Admin ────────────────────────────────────────────────

@app.post("/admin/maintenance", response_model=schemas.MaintenanceStatus, tags=["Admin"],
          responses={401: {"description": "Invalid or missing API key"}})
def toggle_maintenance(data: schemas.MaintenanceToggle, _: str = Depends(require_api_key)):
    global maintenance_mode
    maintenance_mode = data.enabled
    msg = "Maintenance mode activated" if data.enabled else "Maintenance mode deactivated"
    return schemas.MaintenanceStatus(maintenance_mode=maintenance_mode, message=msg)


@app.get("/admin/maintenance", response_model=schemas.MaintenanceStatus, tags=["Admin"])
def get_maintenance_status():
    return schemas.MaintenanceStatus(
        maintenance_mode=maintenance_mode,
        message="Maintenance mode is active" if maintenance_mode else "System operational",
    )


# ── Statistics (protected) ───────────────────────────────

@app.get("/statistics/summary", response_model=schemas.StatisticsSummary, tags=["Statistics"],
         responses={401: {"description": "Invalid or missing API key"}})
def get_statistics(db: Session = Depends(get_db), _: str = Depends(require_api_key)):
    return crud.get_statistics(db)


# ── Deprecated Redirect ──────────────────────────────────

@app.get("/catalog", tags=["Deprecated"],
         responses={301: {"description": "Moved Permanently to /books"}},
         status_code=301)
def deprecated_catalog():
    """Deprecated: use GET /books instead."""
    return RedirectResponse(url="/books", status_code=301)


# ── Reset ────────────────────────────────────────────────

@app.post("/reset", tags=["Testing"])
def reset_database(db: Session = Depends(get_db)):
    """Reset all data (DB + in-memory state). For testing only."""
    global maintenance_mode
    db.execute(models.Review.__table__.delete())
    db.execute(models.OrderItem.__table__.delete())
    db.execute(models.Order.__table__.delete())
    db.execute(models.book_tags.delete())
    db.execute(models.Book.__table__.delete())
    db.execute(models.Tag.__table__.delete())
    db.execute(models.Category.__table__.delete())
    db.execute(models.Author.__table__.delete())
    db.commit()
    # Clear in-memory state
    maintenance_mode = False
    cover_storage.clear()
    export_jobs.clear()
    rate_limit_store.clear()
    return {"status": "ok", "message": "Database and state reset complete"}