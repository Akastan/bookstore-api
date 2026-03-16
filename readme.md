# Bookstore API

REST API pro správu knihkupectví. Slouží jako testovací aplikace pro vibe-testing-framework – framework pro automatické generování API testů pomocí LLM.

## O projektu

Jednoduchá CRUD aplikace postavená na FastAPI + SQLite, která spravuje:

- **Autory** – vytváření, editace, mazání (s ochranou proti smazání autora s knihami)
- **Kategorie** – unikátní názvy, ochrana proti smazání s vazbami
- **Knihy** – validace ISBN, cen, roků vydání, stránkování s filtrací
- **Recenze** – hodnocení 1–5, průměrné hodnocení
- **Slevy** – aplikace slev s byznys pravidly (max 50%, jen starší knihy)
- **Správa skladu** – přičítání/odečítání s ochranou proti zápornému stavu

## Technologie

- **Python 3.12**
- **FastAPI** – web framework
- **SQLAlchemy** – ORM
- **SQLite** – databáze (WAL mode pro souběžný přístup)
- **Pydantic v2** – validace dat

## Spuštění

```bash
# Klonování
git clone https://github.com/Akastan/bookstore-api.git
cd bookstore-api

# Virtuální prostředí
python -m venv .venv

# Aktivace (Windows)
.venv\Scripts\Activate.ps1
# Aktivace (Linux/Mac)
source .venv/bin/activate

# Instalace závislostí
pip install -r requirements.txt

# Spuštění serveru
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API běží na `http://localhost:8000`. Interaktivní dokumentace: `http://localhost:8000/docs`

## Struktura

```
bookstore-api/
├── app/
│   ├── __init__.py
│   ├── main.py          # FastAPI routy
│   ├── crud.py          # Business logika
│   ├── models.py        # SQLAlchemy modely
│   ├── schemas.py       # Pydantic schémata
│   └── database.py      # DB konfigurace
├── docs/
│   └── documentation.md # Byznys dokumentace
├── tests/
│   └── test_existing.py # Ukázkové testy
├── db_schema.sql        # SQL schéma pro export
├── export_inputs.py     # Export dat pro vibe-testing-framework
└── requirements.txt
```

## API Endpointy

| Metoda | Endpoint | Popis |
|--------|----------|-------|
| GET | `/health` | Health check |
| POST | `/authors` | Vytvořit autora |
| GET | `/authors` | Seznam autorů |
| GET | `/authors/{id}` | Detail autora |
| PUT | `/authors/{id}` | Upravit autora |
| DELETE | `/authors/{id}` | Smazat autora |
| POST | `/categories` | Vytvořit kategorii |
| GET | `/categories` | Seznam kategorií |
| GET | `/categories/{id}` | Detail kategorie |
| PUT | `/categories/{id}` | Upravit kategorii |
| DELETE | `/categories/{id}` | Smazat kategorii |
| POST | `/books` | Vytvořit knihu |
| GET | `/books` | Seznam knih (stránkování, filtry) |
| GET | `/books/{id}` | Detail knihy |
| PUT | `/books/{id}` | Upravit knihu |
| DELETE | `/books/{id}` | Smazat knihu |
| POST | `/books/{id}/reviews` | Přidat recenzi |
| GET | `/books/{id}/reviews` | Seznam recenzí |
| GET | `/books/{id}/rating` | Průměrné hodnocení |
| POST | `/books/{id}/discount` | Aplikovat slevu |
| PATCH | `/books/{id}/stock` | Upravit sklad |
| POST | `/reset` | Reset databáze (jen pro testování) |

## Použití s Vibe Testing Framework

Toto API slouží jako testovací subjekt. Export vstupních dat pro framework:

```bash
# Server musí běžet
python export_inputs.py
```

Skript exportuje OpenAPI specifikaci, dokumentaci, zdrojový kód, DB schéma a existující testy do `../vibe-testing-framework/inputs/`.

## Licence

Projekt pro diplomovou práci – testování REST API pomocí LLM.