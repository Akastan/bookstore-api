# Bookstore API

REST API pro správu knihkupectví. Slouží jako testovací aplikace pro [vibe-testing-framework](https://github.com/Akastan/vibe-testing-framework) — framework pro automatické generování API testů pomocí LLM.

## O projektu

CRUD aplikace postavená na FastAPI + SQLite se 40 endpointy a 10 různými HTTP status kódy. Spravuje:

- **Autory** – CRUD, ochrana proti smazání autora s knihami (409), sub-resource listing knih
- **Kategorie** – CRUD, unikátní názvy, ochrana proti smazání s vazbami (409)
- **Knihy** – CRUD, validace ISBN (10–13 znaků), stránkování s filtrací, hromadné vytváření (207 Multi-Status), klonování
- **Recenze** – hodnocení 1–5, průměrné hodnocení per kniha
- **Slevy** – aplikace slev s byznys pravidly (max 50 %, jen starší knihy)
- **Správa skladu** – delta přičítání/odečítání přes query parametr, ochrana proti zápornému stavu
- **Tagy** – many-to-many vazba na knihy, idempotentní přidávání, ochrana při mazání
- **Objednávky** – stavový automat (pending → confirmed → shipped → delivered / cancelled), zachycení cen, automatická správa skladu, přidávání položek, fakturace
- **Statistiky** – agregované metriky (obrat, průměrné hodnocení, stav skladu)

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

## API Endpointy (40)

### Authors (6)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/authors` | 201 | Vytvořit autora |
| GET | `/authors` | 200 | Seznam autorů |
| GET | `/authors/{id}` | 200 | Detail autora |
| PUT | `/authors/{id}` | 200 | Upravit autora |
| DELETE | `/authors/{id}` | 204 | Smazat autora (409 pokud má knihy) |
| GET | `/authors/{id}/books` | 200 | Knihy autora (stránkování) |

### Categories (5)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/categories` | 201 | Vytvořit kategorii |
| GET | `/categories` | 200 | Seznam kategorií |
| GET | `/categories/{id}` | 200 | Detail kategorie |
| PUT | `/categories/{id}` | 200 | Upravit kategorii |
| DELETE | `/categories/{id}` | 204 | Smazat kategorii (409 pokud má knihy) |

### Books (10)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| POST | `/books` | 201 | Vytvořit knihu |
| GET | `/books` | 200 | Seznam knih (stránkování, filtry, search) |
| GET | `/books/{id}` | 200 | Detail knihy (+ autor, kategorie, tagy) |
| PUT | `/books/{id}` | 200 | Upravit knihu |
| DELETE | `/books/{id}` | 204 | Smazat knihu (kaskádové mazání recenzí + tagů) |
| POST | `/books/{id}/discount` | 200 | Aplikovat slevu (400 pro nové knihy) |
| PATCH | `/books/{id}/stock` | 200 | Upravit sklad (query param `?quantity=N`) |
| POST | `/books/bulk` | 201/207/422 | Hromadné vytvoření knih |
| POST | `/books/{id}/clone` | 201 | Klonovat knihu s novým ISBN |
| POST | `/books/{id}/tags` | 200 | Přidat tagy ke knize |

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
| GET | `/tags/{id}` | 200 | Detail tagu |
| PUT | `/tags/{id}` | 200 | Upravit tag |
| DELETE | `/tags/{id}` | 204 | Smazat tag (409 pokud je přiřazen) |
| DELETE | `/books/{id}/tags` | 200 | Odebrat tagy z knihy (JSON body) |

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

### Ostatní (3)

| Metoda | Endpoint | Status | Popis |
|--------|----------|--------|-------|
| GET | `/health` | 200 | Health check |
| GET | `/statistics/summary` | 200 | Souhrnné statistiky |
| POST | `/reset` | 200 | Reset databáze (jen testování) |

### Status kódy (10)

| Kód | Význam |
|-----|--------|
| 200 | Úspěšný GET / PUT / PATCH |
| 201 | Úspěšné vytvoření |
| 204 | Úspěšné smazání (prázdné tělo) |
| 207 | Multi-Status — hromadné operace s partial success |
| 400 | Porušení byznys pravidla |
| 403 | Operace nedostupná v aktuálním stavu |
| 404 | Entita nenalezena |
| 409 | Konflikt (duplicita, závislosti) |
| 422 | Nevalidní vstupní data (Pydantic) |

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
│   ├── main.py          # FastAPI routy (40 endpointů)
│   ├── crud.py          # Business logika
│   ├── models.py        # SQLAlchemy modely
│   ├── schemas.py       # Pydantic schémata
│   └── database.py      # DB konfigurace (SQLite + WAL)
├── docs/
│   └── documentation.md # Technická dokumentace
├── tests/
│   └── test_existing.py # Integrační testy (referenční)
├── Dockerfile
├── docker-compose.yml
├── db_schema.sql        # SQL schéma export
├── requirements.txt
└── readme.md
```

## Export pro Vibe Testing Framework

Export vstupních dat se provádí centrálně z [vibe-testing-framework](https://github.com/Akastan/vibe-testing-framework):

```bash
# V adresáři vibe-testing-framework (bookstore musí běžet na :8000):
python export_inputs.py bookstore
```

Exportuje OpenAPI spec, dokumentaci, zdrojový kód, DB schéma a existující testy do `inputs/api1_bookstore/`.

## Licence

Projekt pro diplomovou práci — Vibe Testing: využití vibe codingu pro automatizované generování testů softwaru.