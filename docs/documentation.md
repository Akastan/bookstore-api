# Bookstore API – Technická dokumentace

> **Verze:** 3.0.2 · **Poslední aktualizace:** 2026-04-03 · **Autor:** Bc. Martin Chuděj  
> **Stack:** Python 3.12 · FastAPI · SQLAlchemy · SQLite (WAL) · Pydantic v2  
> **Base URL:** `http://localhost:8000` · **Docs:** `http://localhost:8000/docs`

---

## 1. Přehled

REST API pro interní systém knihkupectví. Spravuje katalog (autoři, kategorie, knihy), zákaznické recenze, tagy pro klasifikaci a objednávkový systém se stavovým automatem a správou skladu.

Aplikace běží jako single-instance s SQLite databází. Pro souběžný přístup je nastavený WAL mód (`PRAGMA journal_mode=WAL`) s busy timeout 5 s.

### Entity a relace

```
Author (1) ──-> (N) Book (N) ←── (1) Category
                     │
          ┌──────────┼──────────┐
          ↓          ↓          ↓
     Review (N)   Tag (M:N)   OrderItem (N)
                                   │
                                   ↓
                              Order (1)
```

- **Author** -> 0..N knih. Nelze smazat autora s existujícími knihami.
- **Category** -> 0..N knih. Nelze smazat kategorii s existujícími knihami.
- **Book** -> patří 1 autorovi a 1 kategorii. Má 0..N recenzí, 0..N tagů (M:N přes `book_tags`). Smazání knihy kaskádově odstraní recenze a vazby na tagy.
- **Review** -> patří 1 knize. Kaskádové mazání při smazání knihy.
- **Tag** -> 0..N knih (M:N). Nelze smazat tag přiřazený ke knize.
- **Order** -> 1..N položek (OrderItem). Stavový automat řídí lifecycle.
- **OrderItem** -> patří 1 objednávce, odkazuje na 1 knihu. Cena se zachytí v momentě vytvoření.

---

## 2. Endpointy a byznys pravidla

### 2.1 Autoři (`/authors`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/authors` | 201 | Vytvoření autora |
| GET | `/authors` | 200 | Seznam (skip, limit) |
| GET | `/authors/{id}` | 200 | Detail |
| PUT | `/authors/{id}` | 200 | Aktualizace |
| DELETE | `/authors/{id}` | 204 | Smazání |

**Pravidla:**
- `name` je povinné, 1–100 znaků. Chybějící nebo prázdné -> 422.
- `born_year` je volitelné, rozsah 0–2026.
- DELETE autora s přiřazenými knihami -> **409 Conflict** (ne 204). Napřed je nutné smazat nebo přeřadit knihy.

### 2.2 Kategorie (`/categories`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/categories` | 201 | Vytvoření |
| GET | `/categories` | 200 | Seznam |
| GET | `/categories/{id}` | 200 | Detail |
| PUT | `/categories/{id}` | 200 | Aktualizace |
| DELETE | `/categories/{id}` | 204 | Smazání |

**Pravidla:**
- `name` musí být unikátní (case-sensitive), 1–50 znaků.
- Duplicitní název při vytvoření i aktualizaci -> **409 Conflict**.
- DELETE kategorie s knihami -> **409 Conflict**.

### 2.3 Knihy (`/books`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books` | 201 | Vytvoření |
| GET | `/books` | 200 | Stránkovaný seznam s filtry |
| GET | `/books/{id}` | 200 | Detail (včetně autora, kategorie, tagů) |
| PUT | `/books/{id}` | 200 | Aktualizace |
| DELETE | `/books/{id}` | 204 | Smazání (kaskádové) |

**Pravidla při vytváření (POST):**
- `title`: povinné, 1–200 znaků.
- `isbn`: povinné, **10–13 znaků**, unikátní. Duplicitní ISBN -> **409 Conflict**. Validace přes Pydantic (`min_length=10, max_length=13`) - řetězec mimo rozsah nebo s neplatnými znaky vrátí 422.
- `price`: povinné, >= 0. Záporná cena -> 422.
- `published_year`: povinné, rozsah 1000–2026.
- `stock`: volitelné, **výchozí hodnota 0**, >= 0.
- `author_id`, `category_id`: povinné. Neexistující autor/kategorie -> **404** (ne 422 - server validuje existenci na úrovni business logiky, ne schématu).

**Stránkování a filtry (GET `/books`):**

| Parametr | Typ | Default | Popis |
|----------|-----|---------|-------|
| `page` | int | 1 | Stránka (min 1) |
| `page_size` | int | 10 | Položek na stránku (1–100) |
| `search` | string | – | Fulltextové hledání v `title` a `isbn` (case-insensitive LIKE) |
| `author_id` | int | – | Filtr dle autora |
| `category_id` | int | – | Filtr dle kategorie |
| `min_price` | float | – | Minimální cena (inclusive) |
| `max_price` | float | – | Maximální cena (inclusive) |

Odpověď: `{ "items": [...], "total": N, "page": P, "page_size": S, "total_pages": T }`

### 2.4 Slevy (`/books/{id}/discount`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books/{id}/discount` | 200 | Výpočet zlevněné ceny |

**Pravidla:**
- `discount_percent`: povinné, rozsah **(0, 50]** - striktně větší než 0, max 50 %. Hodnota mimo rozsah -> 422.
- **Sleva je povolena pouze u knih vydaných před více než 1 rokem** (`current_year - published_year >= 1`). Novější kniha -> **400 Bad Request**.
- Sleva **nemění cenu v databázi**. Vrací jen vypočítanou `discounted_price`.
- Odpověď: `{ "book_id", "title", "original_price", "discount_percent", "discounted_price" }`

### 2.5 Správa skladu (`/books/{id}/stock`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| PATCH | `/books/{id}/stock?quantity=N` | 200 | Úprava skladu |

**Pravidla:**
- Parametr `quantity` se předává jako **query parametr** (`?quantity=5`), ne jako JSON body.
- Quantity je **delta** - přičte se ke stávajícímu skladu. Kladná hodnota = naskladnění, záporná = vyskladnění.
- Příklad: aktuální stock = 10, `quantity=5` -> nový stock = 15. `quantity=-3` -> nový stock = 7.
- Pokud by výsledný sklad byl záporný -> **400 Bad Request** (`"Insufficient stock"`).
- Odpověď: kompletní BookResponse s aktualizovaným stavem.

### 2.6 Recenze (`/books/{id}/reviews`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books/{id}/reviews` | 201 | Přidání recenze |
| GET | `/books/{id}/reviews` | 200 | Seznam recenzí knihy |
| GET | `/books/{id}/rating` | 200 | Průměrné hodnocení |

**Pravidla:**
- `rating`: povinné, celé číslo **1–5**.
- `reviewer_name`: povinné, 1–100 znaků.
- `comment`: volitelné.
- Endpoint `/rating` vrací `{ "book_id", "average_rating", "review_count" }`. Bez recenzí: `average_rating` = `null`, `review_count` = 0.

### 2.7 Tagy (`/tags`, `/books/{id}/tags`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/tags` | 201 | Vytvoření tagu |
| GET | `/tags` | 200 | Seznam tagů |
| GET | `/tags/{id}` | 200 | Detail |
| PUT | `/tags/{id}` | 200 | Aktualizace |
| DELETE | `/tags/{id}` | 204 | Smazání |
| POST | `/books/{id}/tags` | 200 | Přidání tagů ke knize |
| DELETE | `/books/{id}/tags` | 200 | Odebrání tagů z knihy |

**Pravidla:**
- `name`: unikátní (case-sensitive), 1–30 znaků. Duplicita -> 409.
- DELETE tagu přiřazeného ke knize -> **409 Conflict**.
- Přidání tagů: POST s **JSON body** `{"tag_ids": [1, 2, 3]}`. Již přiřazený tag se ignoruje (idempotentní). Neexistující `tag_id` -> 404.
- Odebrání tagů: DELETE s **JSON body** `{"tag_ids": [1, 2]}`. Nepřiřazený tag se ignoruje.
- Odpověď obou tag operací: kompletní BookResponse (včetně aktualizovaného pole `tags`).

### 2.8 Objednávky (`/orders`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/orders` | 201 | Vytvoření objednávky |
| GET | `/orders` | 200 | Stránkovaný seznam |
| GET | `/orders/{id}` | 200 | Detail |
| PATCH | `/orders/{id}/status` | 200 | Změna stavu |
| DELETE | `/orders/{id}` | 204 | Smazání |

**Vytvoření objednávky (POST):**
- `customer_name`: povinné, 1–100 znaků.
- `customer_email`: povinné, 1–200 znaků (validuje se pouze délka, ne formát).
- `items`: pole s min. 1 položkou. Každá: `{ "book_id": int, "quantity": int >= 1 }`.
- **Duplicitní `book_id`** v jedné objednávce -> **400 Bad Request**.
- Neexistující kniha -> **404**.
- **Nedostatečný sklad** -> **400 Bad Request**.
- Při úspěchu se automaticky **odečte objednané množství ze skladu**.
- `unit_price` se zachytí z aktuální ceny knihy v momentě objednávky.
- Odpověď obsahuje vypočítaný `total_price` (∑ `unit_price × quantity`).

**Stavový automat:**

```
pending ──-> confirmed ──-> shipped ──-> delivered (terminální)
   │             │
   └──-> cancelled ←──┘                cancelled (terminální)
```

Povolené přechody:

| Z | Na                          |
|---|-----------------------------|
| `pending` | `confirmed`, `cancelled`    |
| `confirmed` | `shipped`, `cancelled`      |
| `shipped` | `delivered`                 |
| `delivered` | *(žádné - terminální stav)* |
| `cancelled` | *(žádné - terminální stav)* |

- Nepovolený přechod -> **400 Bad Request**.
- **Při zrušení (`cancelled`)** se automaticky **vrátí sklad** - množství z každé položky se přičte zpět.

**Mazání objednávek:**
- Smazat lze pouze objednávky ve stavu `pending` nebo `cancelled`. Jiný stav -> 400.
- Smazání `pending` objednávky -> **vrátí sklad**.
- Smazání `cancelled` objednávky -> sklad se **nevrací** (byl vrácen při zrušení).

**Stránkování a filtry (GET `/orders`):**

| Parametr | Popis |
|----------|-------|
| `page`, `page_size` | Stránkování (stejné jako u knih) |
| `status` | Filtr dle stavu (exact match) |
| `customer_name` | Case-insensitive LIKE |

Řazení: od nejnovější po nejstarší (`created_at DESC`).

---

## 3. Chybové kódy - přehled

| Kód | Kdy se vrací                                                                                                                    |
|-----|---------------------------------------------------------------------------------------------------------------------------------|
| **200** | Úspěšný GET, PUT, PATCH                                                                                                         |
| **201** | Úspěšné vytvoření (POST)                                                                                                        |
| **204** | Úspěšné smazání (DELETE) - prázdné tělo, žádný JSON                                                                             |
| **400** | Porušení byznys pravidla: nedostatečný sklad, nepovolený stavový přechod, duplicitní book_id v objednávce, sleva na novou knihu |
| **404** | Entita nenalezena (autor, kniha, kategorie, tag, objednávka)                                                                    |
| **409** | Konflikt: duplicitní ISBN / název kategorie / název tagu, nebo pokus o smazání entity s vazbami                                 |
| **422** | Nevalidní vstupní data (chybějící pole, špatný typ, hodnota mimo rozsah) - Pydantic validace                                    |

**Důležitý rozdíl 404 vs 422:** Pokud je `author_id` správného typu (integer) ale neexistuje v databázi, API vrátí **404** (business validace). Pokud `author_id` chybí nebo je špatného typu, vrátí **422** (schema validace).

---

### 2.9 Hromadné operace (`/books/bulk`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books/bulk` | 201 / **207** / 422 | Hromadné vytvoření knih |

**Pravidla:**
- Body: `{"books": [{ BookCreate }, ...]}`, max 20 knih v jednom requestu.
- Každá kniha se validuje samostatně - úspěšné se uloží, neúspěšné vrátí chybu.
- **201** - všechny knihy vytvořeny úspěšně.
- **207 Multi-Status** - některé vytvořeny, některé selhaly (partial success).
- **422** - všechny selhaly.
- Odpověď: `{ "total", "created", "failed", "results": [{ "index", "status", "book"|"error" }] }`

### 2.10 Klonování knihy (`/books/{id}/clone`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books/{id}/clone` | 201 | Vytvoření kopie knihy |

**Pravidla:**
- Body: `{"new_isbn": "...", "new_title": "..." (volitelné), "stock": 0}`
- Zkopíruje cenu, rok vydání, autora, kategorii ze zdrojové knihy.
- **Stock se nekopíruje** - vždy se nastaví z requestu (default 0).
- Tagy a recenze se nekopírují.
- Duplicitní `new_isbn` -> **409 Conflict**.
- Neexistující zdrojová kniha -> **404**.
- Pokud `new_title` není zadán, použije se `"{original_title} (copy)"`.

### 2.11 Knihy autora (`/authors/{id}/books`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| GET | `/authors/{id}/books` | 200 | Stránkovaný seznam knih autora |

- Stránkování: `page`, `page_size` (stejné jako `/books`).
- Neexistující autor -> **404**.
- Odpověď: standardní `PaginatedBooks`.

### 2.12 Faktura objednávky (`/orders/{id}/invoice`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| GET | `/orders/{id}/invoice` | 200 | Vygenerování faktury |

**Pravidla:**
- Faktura je dostupná **pouze pro objednávky ve stavu `confirmed`, `shipped` nebo `delivered`**.
- Objednávka ve stavu `pending` nebo `cancelled` -> **403 Forbidden** (ne 400 - klient nemá oprávnění k této operaci v daném stavu).
- Neexistující objednávka -> **404**.
- Odpověď: `{ "invoice_number": "INV-000001", "order_id", "customer_name", "customer_email", "status", "issued_at", "items": [{ "book_title", "isbn", "quantity", "unit_price", "line_total" }], "subtotal", "item_count" }`

### 2.13 Přidání položky do objednávky (`/orders/{id}/items`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/orders/{id}/items` | 201 | Přidání knihy do objednávky |

**Pravidla:**
- Body: `{"book_id": int, "quantity": int >= 1}`
- Pouze **pending** objednávky lze modifikovat. Jiný stav -> **403 Forbidden**.
- Kniha, která už je v objednávce -> **409 Conflict** (duplicitní book_id).
- Neexistující kniha -> **404**.
- Nedostatečný sklad -> **400 Bad Request**.
- Při úspěchu se odečte sklad a aktualizuje `updated_at`.
- Odpověď: kompletní `OrderResponse` s aktualizovanými položkami a `total_price`.

### 2.14 Statistiky (`/statistics/summary`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| GET | `/statistics/summary` | 200 | Souhrnné statistiky |

- Odpověď: `{ "total_authors", "total_categories", "total_books", "total_tags", "total_orders", "total_reviews", "books_in_stock", "books_out_of_stock", "total_revenue", "average_book_price", "average_rating", "orders_by_status": {"pending": N, ...} }`
- `total_revenue` se počítá **pouze z delivered objednávek**.
- `average_book_price` a `average_rating` jsou `null` pokud nejsou žádné knihy/recenze.

---

## 3. Chybové kódy - přehled

| Kód | Kdy se vrací                                                                                                                      |
|-----|-----------------------------------------------------------------------------------------------------------------------------------|
| **200** | Úspěšný GET, PUT, PATCH                                                                                                           |
| **201** | Úspěšné vytvoření (POST), přidání položky do objednávky                                                                           |
| **204** | Úspěšné smazání (DELETE) - prázdné tělo, žádný JSON                                                                               |
| **207** | **Multi-Status** - hromadné operace s částečným úspěchem (`/books/bulk`)                                                          |
| **400** | Porušení byznys pravidla: nedostatečný sklad, nepovolený stavový přechod, duplicitní book_id v objednávce, sleva na novou knihu   |
| **403** | **Forbidden** - operace nedostupná v aktuálním stavu: faktura pro pending/cancelled objednávku, modifikace non-pending objednávky |
| **404** | Entita nenalezena                                                                                                                 |
| **409** | Konflikt: duplicitní ISBN / název, pokus o smazání entity s vazbami, duplicitní kniha v objednávce                                |
| **422** | Nevalidní vstupní data (Pydantic validace)                                                                                        |

**Důležité rozdíly:**
- **400 vs 403:** 400 = porušení byznys pravidla (špatný vstup). 403 = operace není v daném kontextu povolena (stavová prerekvizita).
- **404 vs 422:** Pokud je `author_id` správného typu ale neexistuje -> **404**. Pokud chybí nebo je špatného typu -> **422**.
- **207 vs 201 vs 422:** Bulk endpoint vrací 201 (vše OK), 207 (mix), 422 (vše selhalo).

---

## 4. Poznámky pro integraci a testování

### 4.1 Výchozí hodnoty a prerekvizity

- **Stock defaultuje na 0.** Pokud při vytváření knihy nenastavíte `"stock": N`, kniha bude mít nulový sklad. Jakýkoli pokus o objednávku takové knihy selže s 400 (`insufficient stock`).
- ISBN musí mít **10–13 znaků** a projít Pydantic validací. Řetězce s podtržítky, mezerami nebo speciálními znaky budou odmítnuty s 422.
- Pro testování discountu na **novou knihu** (mladší 1 roku) je potřeba vytvořit knihu s `published_year` nastaveným na aktuální rok. Starší knihy (např. `published_year: 2020`) projdou discount validací.

### 4.2 Nestandardní formáty requestů

- `PATCH /books/{id}/stock` - quantity je **query parametr**, ne JSON: `?quantity=5`
- `DELETE /books/{id}/tags` - tag_ids se předávají jako **JSON request body**: `{"tag_ids": [1, 2]}`
- `DELETE /authors/{id}`, `DELETE /books/{id}` atd. - vracejí **204 s prázdným tělem** (ne JSON)

### 4.3 Side effects

- **POST `/orders`** - odečítá sklad (book.stock -= quantity)
- **POST `/orders/{id}/items`** - odečítá sklad pro nově přidanou položku
- **PATCH `/orders/{id}/status`** -> `cancelled` - vrací sklad zpět
- **DELETE `/orders/{id}`** (pending) - vrací sklad zpět
- **DELETE `/orders/{id}`** (cancelled) - sklad NEvrací (byl vrácen při zrušení)
- **DELETE `/books/{id}`** - kaskádově maže recenze a vazby na tagy
- **POST `/books/{id}/clone`** - vytvoří novou knihu, stock se nekopíruje (vždy z requestu)
- **POST `/books/bulk`** - při partial success (207) se uloží jen úspěšné knihy

### 4.4 Stavové prerekvizity (403 Forbidden)

Některé operace vyžadují specifický stav objednávky:
- `GET /orders/{id}/invoice` - vyžaduje `confirmed`, `shipped` nebo `delivered`. Pending/cancelled -> 403.
- `POST /orders/{id}/items` - vyžaduje `pending`. Jakýkoli jiný stav -> 403.

### 4.5 Known Issues

- Stránkování vrací `total_pages: 1` i pro prázdnou databázi (místo 0).
- `author_id=0` ve filtru knih vrací prázdný výsledek místo chyby.
- Validace emailu v objednávkách kontroluje pouze délku (1–200), ne formát - `"xxx"` projde.
- Discount endpoint vrací **200** (ne 201), přestože používá POST - historický důvod, sleva nevytváří nový záznam.