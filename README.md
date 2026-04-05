
# Bookstore API

REST API pro správu knihkupectví. Slouží jako testovací aplikace pro [vibe-testing-framework](https://github.com/Akastan/vibe-testing-framework) - framework pro automatické generování API testů pomocí LLM.

## O projektu

CRUD aplikace postavená na FastAPI + SQLite s **50 endpointy** a **20 různými HTTP status kódy**. Spravuje:

- **Autory** – CRUD, ochrana proti smazání autora s knihami (409), sub-resource listing knih
- **Kategorie** – CRUD, unikátní názvy, ochrana proti smazání s vazbami (409)
- **Knihy** – CRUD, soft delete (410 Gone) + restore, validace ISBN (10–13 znaků), stránkování s filtrací, hromadné vytváření (207 Multi-Status), klonování, nahrávání obálek (413/415)
- **Recenze** – hodnocení 1–5, průměrné hodnocení per kniha
- **Slevy** – aplikace slev s byznys pravidly (max 50 %, jen starší knihy), rate limit (429)
- **Správa skladu** – delta přičítání/odečítání přes query parametr, ochrana proti zápornému stavu
- **Tagy** – many-to-many vazba na knihy, idempotentní přidávání, ochrana při mazání
- **Objednávky** – stavový automat (pending -> confirmed -> shipped -> delivered / cancelled), zachycení cen, automatická správa skladu, přidávání položek, fakturace (403 pro nesprávný stav)
- **Exporty** – asynchronní export knih/objednávek s polling (202 Accepted)
- **Statistiky** – agregované metriky (obrat, průměrné hodnocení, stav skladu), chráněno API klíčem (401)
- **Autentizace** – API key auth pro admin endpointy (401 Unauthorized)
- **ETags** – podmíněné requesty (304 Not Modified, 412 Precondition Failed)
- **Rate limiting** – ochrana proti nadměrnému volání (429 Too Many Requests)
- **Maintenance mode** – globální režim údržby (503 Service Unavailable)
- **Deprecated redirect** – zpětná kompatibilita (301 Moved Permanently)

## Technologie

**Python 3.12** · **FastAPI** · **SQLAlchemy** · **SQLite** (WAL mode) · **Pydantic v2** · **Docker**

## Spuštění

### Docker (doporučeno)

```bash
git clone https://github.com/Akastan/bookstore-api.git
cd bookstore-api
docker compose up --build -d
```

API běží na `http://localhost:8000`. Dokumentace: `http://localhost:8000/docs`

```bash
docker compose down --volumes   # čistý restart
```

### Lokální

```bash
git clone https://github.com/Akastan/bookstore-api.git
cd bookstore-api
python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows
# source .venv/bin/activate     # Linux/Mac
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Testy

```bash
# Server musí běžet
curl -X POST http://localhost:8000/reset
pytest tests/test_existing.py -v
```

## Autentizace

Některé endpointy vyžadují API key v hlavičce `X-API-Key`.

| Parametr | Hodnota |
|----------|---------|
| Header | `X-API-Key` |
| Testovací klíč | `test-api-key` |

Chráněné endpointy: `/books/bulk`, `/exports/*`, `/statistics/summary`, `/admin/maintenance`.

## API Endpointy (50)

### Authors (6)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/authors` | 201 | Vytvořit autora |
| GET | `/authors` | 200 | Seznam autorů |
| GET | `/authors/{id}` | 200/304 | Detail autora (ETag) |
| PUT | `/authors/{id}` | 200/412 | Upravit autora (If-Match) |
| DELETE | `/authors/{id}` | 204 | Smazat autora (409 pokud má knihy) |
| GET | `/authors/{id}/books` | 200 | Knihy autora (stránkování) |

### Categories (5)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/categories` | 201 | Vytvořit kategorii |
| GET | `/categories` | 200 | Seznam kategorií |
| GET | `/categories/{id}` | 200/304 | Detail kategorie (ETag) |
| PUT | `/categories/{id}` | 200/412 | Upravit kategorii (If-Match) |
| DELETE | `/categories/{id}` | 204 | Smazat kategorii (409 pokud má knihy) |

### Books (13)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books` | 201 | Vytvořit knihu |
| GET | `/books` | 200 | Seznam knih (stránkování, filtry, search) |
| GET | `/books/{id}` | 200/304/410 | Detail knihy (ETag, soft delete) |
| PUT | `/books/{id}` | 200/412 | Upravit knihu (If-Match) |
| DELETE | `/books/{id}` | 204 | Soft delete knihy |
| POST | `/books/{id}/restore` | 200 | Obnovit soft-deleted knihu |
| POST | `/books/{id}/discount` | 200 | Aplikovat slevu (429 rate limit) |
| PATCH | `/books/{id}/stock` | 200 | Upravit sklad (query param) |
| POST | `/books/bulk` | 201/207/422 | Hromadné vytvoření (🔒 API key, 429 rate limit) |
| POST | `/books/{id}/clone` | 201 | Klonovat knihu |
| POST | `/books/{id}/tags` | 200 | Přidat tagy ke knize |
| POST | `/books/{id}/cover` | 200 | Nahrát obálku (413/415) |
| GET | `/books/{id}/cover` | 200 | Stáhnout obálku |
| DELETE | `/books/{id}/cover` | 204 | Smazat obálku |

### Reviews (3)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books/{id}/reviews` | 201 | Přidat recenzi |
| GET | `/books/{id}/reviews` | 200 | Seznam recenzí knihy |
| GET | `/books/{id}/rating` | 200 | Průměrné hodnocení |

### Tags (6)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/tags` | 201 | Vytvořit tag |
| GET | `/tags` | 200 | Seznam tagů |
| GET | `/tags/{id}` | 200/304 | Detail tagu (ETag) |
| PUT | `/tags/{id}` | 200/412 | Upravit tag (If-Match) |
| DELETE | `/tags/{id}` | 204 | Smazat tag (409 pokud přiřazen) |
| DELETE | `/books/{id}/tags` | 200 | Odebrat tagy z knihy |

### Orders (7)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/orders` | 201 | Vytvořit objednávku (odečte sklad) |
| GET | `/orders` | 200 | Seznam objednávek (stránkování, filtry) |
| GET | `/orders/{id}` | 200 | Detail objednávky |
| PATCH | `/orders/{id}/status` | 200 | Změnit stav (stavový automat) |
| DELETE | `/orders/{id}` | 204 | Smazat (jen pending/cancelled) |
| POST | `/orders/{id}/items` | 201 | Přidat položku (jen pending, 403/409) |
| GET | `/orders/{id}/invoice` | 200 | Faktura (jen confirmed+, 403) |

### Exports (3)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/exports/books` | 202 | Spustit export knih (🔒 API key) |
| POST | `/exports/orders` | 202 | Spustit export objednávek (🔒 API key) |
| GET | `/exports/{job_id}` | 200/202 | Polling stavu exportu |

### Admin (2)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/admin/maintenance` | 200 | Přepnout maintenance mode (🔒 API key) |
| GET | `/admin/maintenance` | 200 | Stav maintenance mode |

### Ostatní (4)

| Metoda | Endpoint | Status | Popis                              |
|--------|----------|--------|------------------------------------|
| GET | `/health` | 200 | Health check                       |
| GET | `/statistics/summary` | 200 | Souhrnné statistiky (🔒 API key)   |
| POST | `/reset` | 200 | Reset databáze + in-memory stav    |
| GET | `/catalog` | 301 | Deprecated -> redirect na `/books` |

### Status kódy (20)

| Kód | Význam                                            |
|-----|---------------------------------------------------|
| 200 | Úspěšný GET / PUT / PATCH                         |
| 201 | Úspěšné vytvoření                                 |
| 202 | Přijato ke zpracování (async export)              |
| 204 | Úspěšné smazání (prázdné tělo)                    |
| 207 | Multi-Status - hromadné operace s partial success |
| 301 | Moved Permanently - deprecated redirect           |
| 304 | Not Modified - ETag match                         |
| 400 | Porušení byznys pravidla                          |
| 401 | Unauthorized - chybějící/neplatný API key         |
| 403 | Operace nedostupná v aktuálním stavu              |
| 404 | Entita nenalezena                                 |
| 405 | Method Not Allowed                                |
| 409 | Konflikt (duplicita, závislosti)                  |
| 410 | Gone - soft-deleted resource                      |
| 412 | Precondition Failed - ETag mismatch               |
| 413 | Content Too Large - soubor > 2 MB                 |
| 415 | Unsupported Media Type - nepovolený typ souboru   |
| 422 | Nevalidní vstupní data (Pydantic)                 |
| 429 | Too Many Requests - rate limit                    |
| 503 | Service Unavailable - maintenance mode            |

## Stavový automat objednávek

```
pending ──-> confirmed ──-> shipped ──-> delivered (terminální)
   │             │
   └──-> cancelled ←──┘                cancelled (terminální)
```

## Struktura

```
bookstore-api/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI routy (50 endpointů) + middleware
│   ├── crud.py          # Business logika
│   ├── models.py        # SQLAlchemy modely
│   ├── schemas.py       # Pydantic schémata
│   └── database.py      # DB konfigurace (SQLite + WAL)
├── docs/
│   └── documentation.md # Technická dokumentace
├── tests/
│   └── test_existing.py # Integrační testy (50 testů, 20 status kódů)
├── Dockerfile
├── docker-compose.yml
├── db_schema.sql        # SQL schéma export
├── requirements.txt
└── README.md
```

## Export pro Vibe Testing Framework

```bash
# V adresáři vibe-testing-framework (bookstore musí běžet na :8000):
python export_inputs.py bookstore
```

Exportuje OpenAPI spec, dokumentaci, zdrojový kód, DB schéma a existující testy do `inputs/api1_bookstore/`.

## Licence

Projekt pro diplomovou práci - Vibe Testing: využití vibe codingu pro automatizované generování testů softwaru.