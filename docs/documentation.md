# Bookstore API – Technická a byznys dokumentace

## Přehled
REST API pro správu knihkupectví. Entity: autoři, kategorie, knihy, recenze, tagy, objednávky.
Base URL: `http://localhost:8000`

## Entity a relace
- **Author** → má 0..N knih
- **Category** → má 0..N knih
- **Book** → patří 1 autorovi a 1 kategorii, má 0..N recenzí, má 0..N tagů (many-to-many)
- **Review** → patří 1 knize
- **Tag** → má 0..N knih (many-to-many přes `book_tags`)
- **Order** → má 1..N položek (OrderItem)
- **OrderItem** → patří 1 objednávce, odkazuje na 1 knihu

## Byznys pravidla

### Autoři
- Jméno je povinné (1–100 znaků).
- Rok narození musí být v rozsahu 0–2026 (pokud je uveden).
- **Smazání autora je zakázáno, pokud má přiřazené knihy.** Server vrátí 409 Conflict.

### Kategorie
- Název kategorie musí být unikátní (case-sensitive).
- Smazání kategorie je zakázáno, pokud má přiřazené knihy (409 Conflict).
- Duplicitní název při vytvoření i úpravě vrací 409 Conflict.

### Knihy
- ISBN musí být unikátní (10–13 znaků). Duplicitní ISBN vrací 409 Conflict.
- Cena musí být >= 0.
- Rok vydání musí být v rozsahu 1000–2026.
- Sklad (stock) musí být >= 0.
- Při vytvoření se validuje existence autora i kategorie (404 pokud neexistují).
- Smazání knihy kaskádově smaže její recenze a odstraní vazby na tagy.

### Recenze
- Hodnocení (rating) musí být celé číslo 1–5.
- Jméno recenzenta je povinné.
- Endpoint `/books/{id}/rating` vrací průměrné hodnocení a počet recenzí.
  Pokud kniha nemá recenze, `average_rating` je `null`.

### Slevy (Discount)
- Sleva se aplikuje přes POST `/books/{id}/discount`.
- **Maximální povolená sleva je 50 %** (validováno na úrovni schématu, `gt=0, le=50`).
- **Sleva je povolena pouze u knih vydaných před více než 1 rokem.**
  Pokud je kniha novější, server vrátí 400 Bad Request.
- Sleva NEMĚNÍ cenu v databázi – vrací jen vypočítanou zlevněnou cenu.

### Správa skladu
- PATCH `/books/{id}/stock?quantity=N` přičte N ke stávajícímu skladu.
- Záporná hodnota quantity = odečtení ze skladu.
- Pokud by výsledný sklad byl záporný, server vrátí 400 Bad Request.

### Tagy
- Název tagu musí být unikátní (case-sensitive, max 30 znaků).
- Duplicitní název při vytvoření i úpravě vrací 409 Conflict.
- **Smazání tagu je zakázáno, pokud je přiřazen k alespoň jedné knize** (409 Conflict).
- Přidání tagů ke knize: POST `/books/{id}/tags` s tělem `{"tag_ids": [1, 2, 3]}`.
  Pokud je tag již přiřazen, vazba se ignoruje (idempotentní).
- Odebrání tagů z knihy: DELETE `/books/{id}/tags` s tělem `{"tag_ids": [1, 2]}`.
  Pokud tag není přiřazen, ignoruje se.
- Při dotazu na detail knihy (`GET /books/{id}`) se v odpovědi vrací pole `tags`.
- Neexistující tag_id v požadavku vrací 404.

### Objednávky (Orders)
- Objednávka musí mít alespoň jednu položku.
- **Duplicitní book_id v jedné objednávce není povolen** (400 Bad Request).
- Při vytvoření se validuje existence knih a dostatek skladu.
  Nedostatečný sklad vrací 400 Bad Request.
- **Cena se zachytí v momentě vytvoření objednávky** (`unit_price` v OrderItem).
  Pozdější změna ceny knihy neovlivní existující objednávky.
- Vytvoření objednávky automaticky odečte objednané množství ze skladu.
- Odpověď obsahuje vypočítané pole `total_price` (suma `unit_price × quantity`).

#### Stavový automat objednávky
```
pending → confirmed → shipped → delivered
   ↓          ↓
cancelled  cancelled
```
- Nová objednávka začíná ve stavu `pending`.
- Povolené přechody:
  - `pending` → `confirmed`, `cancelled`
  - `confirmed` → `shipped`, `cancelled`
  - `shipped` → `delivered`
  - `delivered` → (terminální stav, žádné přechody)
  - `cancelled` → (terminální stav, žádné přechody)
- Nepovolený přechod vrací 400 Bad Request s popisem povolených přechodů.
- **Při zrušení objednávky (`cancelled`) se vrátí sklad** – množství z každé položky se přičte zpět.

#### Mazání objednávek
- Smazat lze pouze objednávky ve stavu `pending` nebo `cancelled`.
- Pokus o smazání objednávky v jiném stavu vrací 400 Bad Request.
- Při smazání `pending` objednávky se vrátí sklad.
- Při smazání `cancelled` objednávky se sklad nevrací (byl vrácen při zrušení).

#### Filtrování a stránkování objednávek
- GET `/orders` podporuje stránkování (`page`, `page_size`) a filtry (`status`, `customer_name`).
- Filtr `customer_name` je case-insensitive (LIKE).
- Objednávky se řadí od nejnovější po nejstarší.

## Stránkování (GET /books, GET /orders)
- Query parametry: `page` (min 1), `page_size` (1–100, default 10).
- Pro knihy: vyhledávání `search` hledá v title a isbn (case-insensitive LIKE).
- Pro knihy: filtrace `author_id`, `category_id`, `min_price`, `max_price`.
- Pro objednávky: filtrace `status`, `customer_name`.
- Odpověď obsahuje: `items`, `total`, `page`, `page_size`, `total_pages`.

## Chybové kódy
| Kód | Význam |
|-----|--------|
| 201 | Úspěšné vytvoření |
| 204 | Úspěšné smazání (prázdné tělo) |
| 400 | Validační chyba nebo porušení byznys pravidla |
| 404 | Entita nenalezena |
| 409 | Konflikt (duplicita, nebo nelze smazat kvůli závislostem) |
| 422 | Nevalidní vstupní data (Pydantic validace) |

## Known Issues
- Stránkování vrací `total_pages: 1` i když je databáze prázdná (ne 0).
- DELETE endpointy vracejí 204 s prázdným tělem (žádný JSON).
- Filtr `author_id=0` vrací prázdný výsledek místo chyby.
- Validace emailu v objednávkách kontroluje pouze délku (1–200), ne formát.