# Bookstore API – Technická dokumentace

> **Verze:** 4.0.0 · **Poslední aktualizace:** 2026-04-05 · **Autor:** Bc. Martin Chuděj
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

- **Author** -> 0..N knih. Nelze smazat autora s existujícími (nesmazanými) knihami.
- **Category** -> 0..N knih. Nelze smazat kategorii s existujícími (nesmazanými) knihami.
- **Book** -> patří 1 autorovi a 1 kategorii. Má 0..N recenzí, 0..N tagů (M:N přes `book_tags`). Smazání knihy je soft delete (nastaví `is_deleted=True`). Recenze a tagy zůstávají, ale kniha je nedostupná.
- **Review** -> patří 1 knize. Nedostupná pokud je kniha soft-deleted.
- **Tag** -> 0..N knih (M:N). Nelze smazat tag přiřazený ke knize.
- **Order** -> 1..N položek (OrderItem). Stavový automat řídí lifecycle.
- **OrderItem** -> patří 1 objednávce, odkazuje na 1 knihu. Cena se zachytí v momentě vytvoření.

---

## 2. Autentizace

API používá API key autentizaci přes HTTP hlavičku `X-API-Key`.

| Parametr | Hodnota |
|----------|---------|
| Hlavička | `X-API-Key` |
| Testovací klíč | `test-api-key` (výchozí, konfigurovatelné přes env `API_KEY`) |

### Chráněné endpointy

| Endpoint | Důvod |
|----------|-------|
| `POST /books/bulk` | Admin operace – hromadné vytváření |
| `POST /exports/books` | Export dat |
| `POST /exports/orders` | Export dat |
| `GET /statistics/summary` | Citlivá agregovaná data |
| `POST /admin/maintenance` | Správa systému |

Chybějící nebo neplatný klíč -> **401 Unauthorized**.

Nechráněné endpointy (včetně `POST /reset`) nevyžadují autentizaci.

---

## 3. Rate Limiting

Některé endpointy mají omezení počtu requestů:

| Endpoint | Limit | Okno |
|----------|-------|------|
| `POST /books/bulk` | 3 requesty | 30 sekund |
| `POST /books/{id}/discount` | 5 requestů | 10 sekund |

Při překročení limitu -> **429 Too Many Requests** s hlavičkou `Retry-After` (počet sekund do resetování okna).

Limity se počítají per IP adresa. Reset databáze (`POST /reset`) vymaže i čítače rate limitu.

---

## 4. ETags a podmíněné requesty

Detail endpointy (`GET /books/{id}`, `GET /authors/{id}`, `GET /categories/{id}`, `GET /tags/{id}`) vrací hlavičku `ETag` obsahující hash z `updated_at` timestamp.

### Podmíněný GET (304 Not Modified)

Klient pošle `If-None-Match: "<etag>"`. Pokud se data nezměnila -> **304 Not Modified** (prázdné tělo, úspora bandwidthu).

### Optimistic Locking na PUT (412 Precondition Failed)

PUT endpointy (`PUT /books/{id}`, `PUT /authors/{id}`, `PUT /categories/{id}`, `PUT /tags/{id}`) podporují hlavičku `If-Match: "<etag>"`. Pokud se data od posledního čtení změnila (ETag nesouhlasí) -> **412 Precondition Failed**. Hlavička `If-Match` je volitelná – bez ní se update provede vždy.

---

## 5. Maintenance Mode

Globální přepínač pro údržbu systému.

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/admin/maintenance` | 200 | Aktivace/deaktivace (vyžaduje API key) |
| GET | `/admin/maintenance` | 200 | Aktuální stav |

Aktivace: `POST /admin/maintenance` s tělem `{"enabled": true}`.

Když je maintenance mode aktivní, **všechny endpointy kromě** `/health`, `/admin/maintenance`, `/docs`, `/openapi.json` vrací **503 Service Unavailable** s hlavičkou `Retry-After: 300`.

Reset databáze (`POST /reset`) automaticky deaktivuje maintenance mode.

---

## 6. Endpointy a byznys pravidla

### 6.1 Autoři (`/authors`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/authors` | 201 | Vytvoření autora |
| GET | `/authors` | 200 | Seznam (skip, limit) |
| GET | `/authors/{id}` | 200 / 304 | Detail (ETag) |
| PUT | `/authors/{id}` | 200 / 412 | Aktualizace (If-Match) |
| DELETE | `/authors/{id}` | 204 | Smazání |
| GET | `/authors/{id}/books` | 200 | Knihy autora (stránkování) |

**Pravidla:**
- `name` je povinné, 1–100 znaků. Chybějící nebo prázdné -> 422.
- `born_year` je volitelné, rozsah 0–2026.
- DELETE autora s přiřazenými (nesmazanými) knihami -> **409 Conflict**. Napřed je nutné smazat nebo přeřadit knihy.
- Neexistující autor -> **404**.
- GET detail vrací `ETag` hlavičku. S `If-None-Match` -> **304** pokud nezměněno.
- PUT s `If-Match` -> **412** pokud ETag nesouhlasí.

### 6.2 Kategorie (`/categories`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/categories` | 201 | Vytvoření |
| GET | `/categories` | 200 | Seznam |
| GET | `/categories/{id}` | 200 / 304 | Detail (ETag) |
| PUT | `/categories/{id}` | 200 / 412 | Aktualizace (If-Match) |
| DELETE | `/categories/{id}` | 204 | Smazání |

**Pravidla:**
- `name` musí být unikátní (case-sensitive), 1–50 znaků.
- Duplicitní název při vytvoření i aktualizaci -> **409 Conflict**.
- DELETE kategorie s (nesmazanými) knihami -> **409 Conflict**.

### 6.3 Knihy (`/books`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books` | 201 | Vytvoření |
| GET | `/books` | 200 | Stránkovaný seznam s filtry |
| GET | `/books/{id}` | 200 / 304 / 410 | Detail (ETag, soft delete) |
| PUT | `/books/{id}` | 200 / 410 / 412 | Aktualizace |
| DELETE | `/books/{id}` | 204 / 410 | Soft delete |
| POST | `/books/{id}/restore` | 200 | Obnovení smazané knihy |

**Pravidla při vytváření (POST):**
- `title`: povinné, 1–200 znaků.
- `isbn`: povinné, **10–13 znaků**, unikátní. Duplicitní ISBN -> **409 Conflict**. Validace přes Pydantic (`min_length=10, max_length=13`) – řetězec mimo rozsah vrátí 422.
- `price`: povinné, >= 0. Záporná cena -> 422.
- `published_year`: povinné, rozsah 1000–2026.
- `stock`: volitelné, **výchozí hodnota 0**, >= 0.
- `author_id`, `category_id`: povinné. Neexistující autor/kategorie -> **404** (ne 422 – server validuje existenci na úrovni business logiky, ne schématu).

**Soft delete:**
- `DELETE /books/{id}` neprovede fyzické smazání – nastaví `is_deleted=True` a `deleted_at`.
- `GET /books/{id}` na soft-deleted knihu -> **410 Gone**.
- `GET /books` (seznam) automaticky vyfiltruje soft-deleted knihy.
- Recenze a tagy zůstávají přiřazené, ale nejsou dostupné (book endpoint vrací 410).
- `POST /books/{id}/restore` obnoví smazanou knihu. Pokud kniha není smazaná -> **400**. Neexistující ID -> **404**.

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

### 6.4 Slevy (`/books/{id}/discount`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books/{id}/discount` | 200 | Výpočet zlevněné ceny |

**Pravidla:**
- `discount_percent`: povinné, rozsah **(0, 50]** – striktně větší než 0, max 50 %. Hodnota mimo rozsah -> 422.
- **Sleva je povolena pouze u knih vydaných před více než 1 rokem** (`current_year - published_year >= 1`). Novější kniha -> **400 Bad Request**.
- Sleva **nemění cenu v databázi**. Vrací jen vypočítanou `discounted_price`.
- Odpověď: `{ "book_id", "title", "original_price", "discount_percent", "discounted_price" }`
- **Rate limit:** 5 requestů za 10 sekund. Překročení -> **429 Too Many Requests**.

### 6.5 Správa skladu (`/books/{id}/stock`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| PATCH | `/books/{id}/stock?quantity=N` | 200 | Úprava skladu |

**Pravidla:**
- Parametr `quantity` se předává jako **query parametr** (`?quantity=5`), ne jako JSON body.
- Quantity je **delta** – přičte se ke stávajícímu skladu. Kladná hodnota = naskladnění, záporná = vyskladnění.
- Příklad: aktuální stock = 10, `quantity=5` -> nový stock = 15. `quantity=-3` -> nový stock = 7.
- Pokud by výsledný sklad byl záporný -> **400 Bad Request** (`"Insufficient stock"`).
- Odpověď: kompletní BookResponse s aktualizovaným stavem.

### 6.6 Obálka knihy (`/books/{id}/cover`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books/{id}/cover` | 200 | Nahrání obálky (multipart upload) |
| GET | `/books/{id}/cover` | 200 | Stažení obálky (raw image) |
| DELETE | `/books/{id}/cover` | 204 | Smazání obálky |

**Pravidla:**
- Upload: multipart/form-data s polem `file`.
- Povolené typy: pouze `image/jpeg` a `image/png`. Jiný typ -> **415 Unsupported Media Type**.
- Maximální velikost: **2 MB** (2 097 152 bytes). Větší soubor -> **413 Content Too Large**.
- GET vrací raw binární data s odpovídajícím `Content-Type`.
- GET/POST/DELETE na soft-deleted knihu -> **410 Gone**.
- GET/DELETE obálky pokud nebyla nahrána -> **404**.
- Obálky se ukládají v paměti – `POST /reset` je vymaže.

### 6.7 Recenze (`/books/{id}/reviews`)

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
- Operace na soft-deleted knize -> **410 Gone**.

### 6.8 Tagy (`/tags`, `/books/{id}/tags`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/tags` | 201 | Vytvoření tagu |
| GET | `/tags` | 200 | Seznam tagů |
| GET | `/tags/{id}` | 200 / 304 | Detail (ETag) |
| PUT | `/tags/{id}` | 200 / 412 | Aktualizace (If-Match) |
| DELETE | `/tags/{id}` | 204 | Smazání |
| POST | `/books/{id}/tags` | 200 | Přidání tagů ke knize |
| DELETE | `/books/{id}/tags` | 200 | Odebrání tagů z knihy |

**Pravidla:**
- `name`: unikátní (case-sensitive), 1–30 znaků. Duplicita -> 409.
- DELETE tagu přiřazeného ke knize -> **409 Conflict**.
- Přidání tagů: POST s **JSON body** `{"tag_ids": [1, 2, 3]}`. Již přiřazený tag se ignoruje (idempotentní). Neexistující `tag_id` -> 404.
- Odebrání tagů: DELETE s **JSON body** `{"tag_ids": [1, 2]}`. Nepřiřazený tag se ignoruje.
- Odpověď obou tag operací: kompletní BookResponse (včetně aktualizovaného pole `tags`).

### 6.9 Objednávky (`/orders`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/orders` | 201 | Vytvoření objednávky |
| GET | `/orders` | 200 | Stránkovaný seznam |
| GET | `/orders/{id}` | 200 | Detail |
| PATCH | `/orders/{id}/status` | 200 | Změna stavu |
| DELETE | `/orders/{id}` | 204 | Smazání |
| POST | `/orders/{id}/items` | 201 | Přidání položky |
| GET | `/orders/{id}/invoice` | 200 | Faktura |

**Vytvoření objednávky (POST):**
- `customer_name`: povinné, 1–100 znaků.
- `customer_email`: povinné, 1–200 znaků (validuje se pouze délka, ne formát).
- `items`: pole s min. 1 položkou. Každá: `{ "book_id": int, "quantity": int >= 1 }`.
- **Duplicitní `book_id`** v jedné objednávce -> **400 Bad Request**.
- Neexistující kniha -> **404**. Soft-deleted kniha -> **410**.
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

| Z | Na |
|---|----|
| `pending` | `confirmed`, `cancelled` |
| `confirmed` | `shipped`, `cancelled` |
| `shipped` | `delivered` |
| `delivered` | *(žádné – terminální stav)* |
| `cancelled` | *(žádné – terminální stav)* |

- Nepovolený přechod -> **400 Bad Request**.
- **Při zrušení (`cancelled`)** se automaticky **vrátí sklad**.

**Mazání objednávek:**
- Smazat lze pouze objednávky ve stavu `pending` nebo `cancelled`. Jiný stav -> 400.
- Smazání `pending` objednávky -> **vrátí sklad**.
- Smazání `cancelled` objednávky -> sklad se **nevrací** (byl vrácen při zrušení).

**Přidání položky (`POST /orders/{id}/items`):**
- Body: `{"book_id": int, "quantity": int >= 1}`
- Pouze **pending** objednávky -> jiný stav -> **403 Forbidden**.
- Kniha už v objednávce -> **409 Conflict**.
- Neexistující/smazaná kniha -> **404**/**410**.
- Nedostatečný sklad -> **400**.

**Faktura (`GET /orders/{id}/invoice`):**
- Dostupná pouze pro `confirmed`, `shipped`, `delivered`.
- Pending/cancelled -> **403 Forbidden**.
- Odpověď: `{ "invoice_number": "INV-000001", "order_id", "customer_name", "customer_email", "status", "issued_at", "items": [...], "subtotal", "item_count" }`

**Stránkování a filtry (GET `/orders`):**

| Parametr | Popis |
|----------|-------|
| `page`, `page_size` | Stránkování (stejné jako u knih) |
| `status` | Filtr dle stavu (exact match) |
| `customer_name` | Case-insensitive LIKE |

Řazení: od nejnovější po nejstarší (`created_at DESC`).

### 6.10 Hromadné operace (`/books/bulk`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books/bulk` | 201 / 207 / 422 | Hromadné vytvoření knih |

**Pravidla:**
- **Vyžaduje API key** (`X-API-Key` hlavička). Bez klíče -> **401**.
- Body: `{"books": [{ BookCreate }, ...]}`, max 20 knih v jednom requestu.
- Každá kniha se validuje samostatně – úspěšné se uloží, neúspěšné vrátí chybu.
- **201** – všechny knihy vytvořeny úspěšně.
- **207 Multi-Status** – některé vytvořeny, některé selhaly (partial success).
- **422** – všechny selhaly.
- **Rate limit:** 3 requesty za 30 sekund. Překročení -> **429**.
- Odpověď: `{ "total", "created", "failed", "results": [{ "index", "status", "book"|"error" }] }`

### 6.11 Klonování knihy (`/books/{id}/clone`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books/{id}/clone` | 201 | Vytvoření kopie knihy |

**Pravidla:**
- Body: `{"new_isbn": "...", "new_title": "..." (volitelné), "stock": 0}`
- Zkopíruje cenu, rok vydání, autora, kategorii ze zdrojové knihy.
- **Stock se nekopíruje** – vždy se nastaví z requestu (default 0).
- Tagy a recenze se nekopírují.
- Duplicitní `new_isbn` -> **409 Conflict**.
- Neexistující/smazaná zdrojová kniha -> **404**/**410**.
- Pokud `new_title` není zadán, použije se `"{original_title} (copy)"`.

### 6.12 Asynchronní exporty (`/exports`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/exports/books` | 202 | Spuštění exportu knih |
| POST | `/exports/orders` | 202 | Spuštění exportu objednávek |
| GET | `/exports/{job_id}` | 200 / 202 | Polling stavu exportu |

**Pravidla:**
- **Vyžaduje API key** na POST endpointech. Bez klíče -> **401**.
- POST vrací **202 Accepted** s `{ "job_id", "status": "processing", "created_at" }`.
- Export se zpracovává asynchronně (simulovaná prodleva ~2 sekundy).
- GET na `job_id` vrací:
  - **202** – export stále probíhá (`"status": "processing"`).
  - **200** – export dokončen (`"status": "completed"`, obsahuje `data` a `total`).
- Neexistující `job_id` -> **404**.
- Export jobs se ukládají v paměti – `POST /reset` je vymaže.

### 6.13 Statistiky (`/statistics/summary`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| GET | `/statistics/summary` | 200 | Souhrnné statistiky |

- **Vyžaduje API key.** Bez klíče -> **401**.
- Odpověď: `{ "total_authors", "total_categories", "total_books", "total_tags", "total_orders", "total_reviews", "books_in_stock", "books_out_of_stock", "total_revenue", "average_book_price", "average_rating", "orders_by_status": {...} }`
- `total_revenue` se počítá **pouze z delivered objednávek**.
- `total_books` počítá pouze nesmazané knihy.
- `average_book_price` a `average_rating` jsou `null` pokud nejsou žádné knihy/recenze.

### 6.14 Deprecated redirect (`/catalog`)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| GET | `/catalog` | 301 | Přesměrování na `/books` |

- **301 Moved Permanently** – klient by měl následovat `Location` hlavičku.
- Tento endpoint je deprecated – slouží pro zpětnou kompatibilitu.

### 6.15 Ostatní

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| GET | `/health` | 200 | Health check |
| POST | `/reset` | 200 | Reset databáze + in-memory stav |

- `POST /reset` vymaže všechna data z databáze, vyčistí cover storage, export jobs, rate limit čítače a deaktivuje maintenance mode.
- Použití nepodporované HTTP metody na libovolný endpoint -> **405 Method Not Allowed** (automatická odpověď FastAPI).

---

## 7. Chybové kódy – přehled (20)

| Kód | Význam | Příklady                                                                                                          |
|-----|--------|-------------------------------------------------------------------------------------------------------------------|
| **200** | Úspěšný GET / PUT / PATCH | Detail, aktualizace, sklad, slevy                                                                                 |
| **201** | Úspěšné vytvoření (POST) | Autor, kniha, objednávka, recenze                                                                                 |
| **202** | Přijato ke zpracování | Async export (`POST /exports/*`, polling `GET /exports/{id}`)                                                     |
| **204** | Úspěšné smazání (DELETE) | Smazání autora, knihy, tagu, objednávky, obálky                                                                   |
| **207** | Multi-Status – částečný úspěch | Hromadné vytvoření knih (`POST /books/bulk`)                                                                      |
| **301** | Moved Permanently | `GET /catalog` -> `/books`                                                                                        |
| **304** | Not Modified | Podmíněný GET s `If-None-Match` (ETag match)                                                                      |
| **400** | Porušení byznys pravidla | Nedostatečný sklad, nepovolený stavový přechod, sleva na novou knihu, duplicitní book_id, restore nesmazané knihy |
| **401** | Unauthorized | Chybějící/neplatný API key na chráněných endpointech                                                              |
| **403** | Forbidden – stavová prerekvizita | Faktura pro pending/cancelled, modifikace non-pending objednávky                                                  |
| **404** | Entita nenalezena | Neexistující autor, kniha, kategorie, tag, objednávka, export job, obálka                                         |
| **405** | Method Not Allowed | Nepodporovaná HTTP metoda (např. PUT /health)                                                                     |
| **409** | Konflikt | Duplicitní ISBN/název, smazání entity s vazbami, duplicitní kniha v objednávce                                    |
| **410** | Gone – soft-deleted | GET/PUT/DELETE na soft-deleted knihu, operace na smazané knize                                                    |
| **412** | Precondition Failed | ETag nesouhlasí při PUT s `If-Match`                                                                              |
| **413** | Content Too Large | Obálka > 2 MB                                                                                                     |
| **415** | Unsupported Media Type | Obálka jiného typu než JPEG/PNG                                                                                   |
| **422** | Nevalidní vstupní data | Pydantic validace – chybějící pole, špatný typ, hodnota mimo rozsah                                               |
| **429** | Too Many Requests | Překročení rate limitu (bulk: 3/30s, discount: 5/10s)                                                             |
| **503** | Service Unavailable | Maintenance mode aktivní                                                                                          |

**Důležité rozdíly:**
- **400 vs 403:** 400 = porušení byznys pravidla (špatný vstup). 403 = operace není v daném kontextu povolena (stavová prerekvizita).
- **404 vs 410:** 404 = entita nikdy neexistovala. 410 = entita existovala, ale byla smazána (soft delete).
- **404 vs 422:** Pokud je `author_id` správného typu ale neexistuje -> **404**. Pokud chybí nebo je špatného typu -> **422**.
- **401 vs 403:** 401 = chybějící/neplatná autentizace. 403 = autentizace OK, ale operace není v daném stavu povolena.
- **412 vs 409:** 412 = optimistic locking selhání (data se změnila). 409 = business conflict (duplicita, vazby).

---

## 8. Poznámky pro integraci a testování

### 8.1 Výchozí hodnoty a prerekvizity

- **Stock defaultuje na 0.** Pokud při vytváření knihy nenastavíte `"stock": N`, kniha bude mít nulový sklad. Jakýkoli pokus o objednávku takové knihy selže s 400 (`insufficient stock`).
- ISBN musí mít **10–13 znaků** a projít Pydantic validací.
- Pro testování discountu na **novou knihu** (mladší 1 roku) je potřeba vytvořit knihu s `published_year` nastaveným na aktuální rok. Starší knihy (např. `published_year: 2020`) projdou discount validací.
- Pro testování **API key autentizace** je třeba posílat hlavičku `X-API-Key: test-api-key` na chráněné endpointy.

### 8.2 Nestandardní formáty requestů

- `PATCH /books/{id}/stock` – quantity je **query parametr**, ne JSON: `?quantity=5`
- `DELETE /books/{id}/tags` – tag_ids se předávají jako **JSON request body**: `{"tag_ids": [1, 2]}`
- `DELETE /authors/{id}`, `DELETE /books/{id}` atd. – vracejí **204 s prázdným tělem** (ne JSON)
- `POST /books/{id}/cover` – **multipart/form-data**, ne JSON
- `GET /books/{id}/cover` – vrací **raw binární data** (image), ne JSON

### 8.3 Side effects

- **POST `/orders`** – odečítá sklad
- **POST `/orders/{id}/items`** – odečítá sklad pro nově přidanou položku
- **PATCH `/orders/{id}/status`** -> `cancelled` – vrací sklad zpět
- **DELETE `/orders/{id}`** (pending) – vrací sklad zpět
- **DELETE `/orders/{id}`** (cancelled) – sklad NEvrací
- **DELETE `/books/{id}`** – soft delete (nastaví is_deleted, recenze a tagy zůstávají)
- **POST `/books/{id}/restore`** – obnoví soft-deleted knihu
- **POST `/books/{id}/clone`** – vytvoří novou knihu, stock se nekopíruje
- **POST `/books/bulk`** – při partial success (207) se uloží jen úspěšné knihy
- **POST `/admin/maintenance`** – ovlivňuje dostupnost VŠECH endpointů

### 8.4 Stavové prerekvizity (403 Forbidden)

- `GET /orders/{id}/invoice` – vyžaduje `confirmed`, `shipped` nebo `delivered`. Pending/cancelled -> 403.
- `POST /orders/{id}/items` – vyžaduje `pending`. Jakýkoli jiný stav -> 403.

### 8.5 ETag workflow

1. `GET /books/1` -> response obsahuje `ETag: "abc123"`
2. `GET /books/1` s `If-None-Match: "abc123"` -> **304** (data nezměněna)
3. `PUT /books/1` s `If-Match: "abc123"` + nová data -> **200** (update OK)
4. `PUT /books/1` s `If-Match: "stary-etag"` -> **412** (data se mezitím změnila)

### 8.6 Known Issues

- Stránkování vrací `total_pages: 1` i pro prázdnou databázi (místo 0).
- `author_id=0` ve filtru knih vrací prázdný výsledek místo chyby.
- Validace emailu v objednávkách kontroluje pouze délku (1–200), ne formát – `"xxx"` projde.
- Discount endpoint vrací **200** (ne 201), přestože používá POST – sleva nevytváří nový záznam.
- Async export prodleva je simulovaná (~2 sekundy) – v produkci by se použila task queue.
