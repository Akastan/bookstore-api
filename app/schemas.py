
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── Authors ──────────────────────────────────────────────

class AuthorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    bio: Optional[str] = None
    born_year: Optional[int] = Field(None, ge=0, le=2026)


class AuthorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    bio: Optional[str] = None
    born_year: Optional[int] = Field(None, ge=0, le=2026)


class AuthorResponse(BaseModel):
    id: int
    name: str
    bio: Optional[str]
    born_year: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Categories ───────────────────────────────────────────

class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    description: Optional[str] = None


class CategoryResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    updated_at: datetime

    class Config:
        from_attributes = True


# ── Tags ─────────────────────────────────────────────────

class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=30)


class TagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=30)


class TagResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BookTagAction(BaseModel):
    tag_ids: List[int] = Field(..., min_length=1)


# ── Books ────────────────────────────────────────────────

class BookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    isbn: str = Field(..., min_length=10, max_length=13)
    price: float = Field(..., ge=0)
    published_year: int = Field(..., ge=1000, le=2026)
    stock: int = Field(0, ge=0)
    author_id: int
    category_id: int


class BookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    isbn: Optional[str] = Field(None, min_length=10, max_length=13)
    price: Optional[float] = Field(None, ge=0)
    published_year: Optional[int] = Field(None, ge=1000, le=2026)
    stock: Optional[int] = Field(None, ge=0)
    author_id: Optional[int] = None
    category_id: Optional[int] = None


class BookResponse(BaseModel):
    id: int
    title: str
    isbn: str
    price: float
    published_year: int
    stock: int
    author_id: int
    category_id: int
    created_at: datetime
    updated_at: datetime
    author: AuthorResponse
    category: CategoryResponse
    tags: List[TagResponse] = Field(default_factory=list)

    class Config:
        from_attributes = True


class BookListResponse(BaseModel):
    id: int
    title: str
    isbn: str
    price: float
    published_year: int
    stock: int
    author_id: int
    category_id: int

    class Config:
        from_attributes = True


# ── Reviews ──────────────────────────────────────────────

class ReviewCreate(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None
    reviewer_name: str = Field(..., min_length=1, max_length=100)


class ReviewResponse(BaseModel):
    id: int
    book_id: int
    rating: int
    comment: Optional[str]
    reviewer_name: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Discount ─────────────────────────────────────────────

class DiscountRequest(BaseModel):
    discount_percent: float = Field(..., gt=0, le=50)


class DiscountResponse(BaseModel):
    book_id: int
    title: str
    original_price: float
    discount_percent: float
    discounted_price: float


# ── Pagination ───────────────────────────────────────────

class PaginatedBooks(BaseModel):
    items: List[BookListResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Orders ───────────────────────────────────────────────

class OrderItemCreate(BaseModel):
    book_id: int
    quantity: int = Field(..., ge=1)


class OrderItemResponse(BaseModel):
    id: int
    book_id: int
    quantity: int
    unit_price: float

    class Config:
        from_attributes = True


class OrderCreate(BaseModel):
    customer_name: str = Field(..., min_length=1, max_length=100)
    customer_email: str = Field(..., min_length=1, max_length=200)
    items: List[OrderItemCreate] = Field(..., min_length=1)


class OrderStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(confirmed|shipped|delivered|cancelled)$")


class OrderResponse(BaseModel):
    id: int
    customer_name: str
    customer_email: str
    status: str
    created_at: datetime
    updated_at: datetime
    items: List[OrderItemResponse]
    total_price: float

    class Config:
        from_attributes = True


class OrderListResponse(BaseModel):
    id: int
    customer_name: str
    customer_email: str
    status: str
    total_price: float
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedOrders(BaseModel):
    items: List[OrderListResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ── Bulk Create ──────────────────────────────────────────

class BulkBookItem(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    isbn: str = Field(..., min_length=10, max_length=13)
    price: float = Field(..., ge=0)
    published_year: int = Field(..., ge=1000, le=2026)
    stock: int = Field(0, ge=0)
    author_id: int
    category_id: int


class BulkBookCreate(BaseModel):
    books: List[BulkBookItem] = Field(..., min_length=1, max_length=20)


class BulkResultItem(BaseModel):
    index: int
    status: str
    book: Optional[BookResponse] = None
    error: Optional[str] = None


class BulkCreateResponse(BaseModel):
    total: int
    created: int
    failed: int
    results: List[BulkResultItem]


# ── Clone ────────────────────────────────────────────────

class BookCloneRequest(BaseModel):
    new_isbn: str = Field(..., min_length=10, max_length=13)
    new_title: Optional[str] = None
    stock: int = Field(0, ge=0)


# ── Invoice ──────────────────────────────────────────────

class InvoiceItem(BaseModel):
    book_title: str
    isbn: str
    quantity: int
    unit_price: float
    line_total: float


class InvoiceResponse(BaseModel):
    invoice_number: str
    order_id: int
    customer_name: str
    customer_email: str
    status: str
    issued_at: str
    items: List[InvoiceItem]
    subtotal: float
    item_count: int


# ── Add Item to Order ────────────────────────────────────

class OrderAddItem(BaseModel):
    book_id: int
    quantity: int = Field(..., ge=1)


# ── Statistics ───────────────────────────────────────────

class StatisticsSummary(BaseModel):
    total_authors: int
    total_categories: int
    total_books: int
    total_tags: int
    total_orders: int
    total_reviews: int
    books_in_stock: int
    books_out_of_stock: int
    total_revenue: float
    average_book_price: Optional[float]
    average_rating: Optional[float]
    orders_by_status: dict


# ── Cover Upload ─────────────────────────────────────────

class CoverUploadResponse(BaseModel):
    book_id: int
    filename: str
    content_type: str
    size_bytes: int


# ── Export Jobs ──────────────────────────────────────────

class ExportJobCreated(BaseModel):
    job_id: str
    status: str
    created_at: str


class ExportJobResult(BaseModel):
    job_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    total: Optional[int] = None
    data: Optional[list] = None


# ── Maintenance ──────────────────────────────────────────

class MaintenanceToggle(BaseModel):
    enabled: bool


class MaintenanceStatus(BaseModel):
    maintenance_mode: bool
    message: str
