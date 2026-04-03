# Bookstore API – Technická dokumentace

> **Verze:** 3.0.0 · **Poslední aktualizace:** 2026-03-28 · **Autor:** Bc. Martin Chuděj  
> **Stack:** Python 3.12 · FastAPI · SQLAlchemy · SQLite (WAL) · Pydantic v2  
> **Base URL:** `http://localhost:8000` · **Docs:** `http://localhost:8000/docs`

---

## 1. Přehled

REST API pro interní systém knihkupectví. Spravuje katalog (autoři, kategorie, knihy), zákaznické recenze, tagy pro klasifikaci a objednávkový systém se stavovým automatem a správou skladu.

Aplikace běží jako single-instance s SQLite databází. Pro souběžný přístup je nastavený WAL mód (`PRAGMA journal_mode=WAL`) s busy timeout 5 s.

### Entity a relace

```
Author (1) ──→ (N) Book (N) ←── (1) Category
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
pending ──→ confirmed ──→ shipped ──→ delivered (terminální)
   │             │
   └──→ cancelled ←──┘                cancelled (terminální)
```

Povolené přechody:

| Z | Na |
|---|-----|
| `pending` | `confirmed`, `cancelled` |
| `confirmed` | `shipped`, `cancelled` |
| `shipped` | `delivered` |
| `delivered` | *(žádné — terminální stav)* |
| `cancelled` | *(žádné — terminální stav)* |

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

## 3. Chybové kódy — přehled

| Kód | Kdy se vrací                                                                                                                    |
|-----|---------------------------------------------------------------------------------------------------------------------------------|
| **200** | Úspěšný GET, PUT, PATCH                                                                                                         |
| **201** | Úspěšné vytvoření (POST)                                                                                                        |
| **204** | Úspěšné smazání (DELETE) - prázdné tělo, žádný JSON                                                                             |
| **400** | Porušení byznys pravidla: nedostatečný sklad, nepovolený stavový přechod, duplicitní book_id v objednávce, sleva na novou knihu |
| **404** | Entita nenalezena (autor, kniha, kategorie, tag, objednávka)                                                                    |
| **409** | Konflikt: duplicitní ISBN / název kategorie / název tagu, nebo pokus o smazání entity s vazbami                                 |
| **422** | Nevalidní vstupní data (chybějící pole, špatný typ, hodnota mimo rozsah) - Pydantic validace                                    |

**Důležitý rozdíl 404 vs. 422:** Pokud je `author_id` správného typu (integer) ale neexistuje v databázi, API vrátí **404** (business validace). Pokud `author_id` chybí nebo je špatného typu, vrátí **422** (schema validace).

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
- **PATCH `/orders/{id}/status`** -> `cancelled` - vrací sklad zpět
- **DELETE `/orders/{id}`** (pending) - vrací sklad zpět
- **DELETE `/orders/{id}`** (cancelled) - sklad NEvrací (byl vrácen při zrušení)
- **DELETE `/books/{id}`** - kaskádově maže recenze a vazby na tagy

### 4.4 Known Issues

- Stránkování vrací `total_pages: 1` i pro prázdnou databázi (místo 0).
- `author_id=0` ve filtru knih vrací prázdný výsledek místo chyby.
- Validace emailu v objednávkách kontroluje pouze délku (1–200), ne formát - `"xxx"` projde.
- Discount endpoint vrací **200** (ne 201), přestože používá POST - historický důvod, sleva nevytváří nový záznam.