# Bookstore API – Technická a byznys dokumentace

## Přehled
REST API pro správu knihkupectví. Entity: autoři, kategorie, knihy, recenze.
Base URL: `http://localhost:8000`

## Entity a relace
- **Author** → má 0..N knih
- **Category** → má 0..N knih
- **Book** → patří 1 autorovi a 1 kategorii, má 0..N recenzí
- **Review** → patří 1 knize

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
- Smazání knihy kaskádově smaže její recenze.

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

## Stránkování (GET /books)
- Query parametry: `page` (min 1), `page_size` (1–100, default 10).
- Vyhledávání: `search` hledá v title a isbn (case-insensitive LIKE).
- Filtrace: `author_id`, `category_id`, `min_price`, `max_price`.
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