# Bookstore API

REST API pro správu knihkupectví. Slouží jako testovací aplikace pro vibe-testing-framework – framework pro automatické generování API testů pomocí LLM.

## O projektu

CRUD aplikace postavená na FastAPI + SQLite, která spravuje:

- **Autory** – vytváření, editace, mazání (s ochranou proti smazání autora s knihami)
- **Kategorie** – unikátní názvy, ochrana proti smazání s vazbami
- **Knihy** – validace ISBN, cen, roků vydání, stránkování s filtrací
- **Recenze** – hodnocení 1–5, průměrné hodnocení
- **Slevy** – aplikace slev s byznys pravidly (max 50 %, jen starší knihy)
- **Správa skladu** – přičítání/odečítání s ochranou proti zápornému stavu
- **Tagy** – many-to-many vazba na knihy, unikátní názvy, ochrana při mazání
- **Objednávky** – stavový automat (pending → confirmed → shipped → delivered / cancelled), zachycení cen, automatická správa skladu

## Technologie

- **Python 3.12**
- **FastAPI** – web framework
- **SQLAlchemy** – ORM
- **SQLite** – databáze (WAL mode pro souběžný přístup)
- **Pydantic v2** – validace dat
- **pytest + requests** – integrační testy
- **Docker** – kontejnerizace pro izolované spouštění

## Spuštění

### Varianta 1: Docker (doporučeno)

Docker zajistí izolované prostředí s čistou databází při každém startu. Testovací framework (`vibe-testing-framework`) umí Docker kontejner spouštět a zastavovat automaticky.

```bash
# Klonování
git clone https://github.com/Akastan/bookstore-api.git
cd bookstore-api

# Sestavení a spuštění
docker compose up --build

# Nebo na pozadí (detached mode)
docker compose up --build -d
```

API běží na `http://localhost:8000`. Při každém `docker compose down` + `docker compose up` se vytvoří čistá databáze.

```bash
# Zastavení a smazání kontejneru (včetně databáze)
docker compose down

# Zastavení s odstraněním volumes (úplně čistý stav)
docker compose down --volumes
```

### Varianta 2: Lokální spuštění

```bash
# Klonování
git clone https://github.com/Akastan/bookstore-api.git
cd bookstore-api

# Virtuální prostředí
python -m venv .venv

# Aktivace (Windows PowerShell)
.venv\Scripts\Activate.ps1
# Aktivace (Windows CMD)
.venv\Scripts\activate.bat
# Aktivace (Linux/Mac)
source .venv/bin/activate

# Instalace závislostí
pip install -r requirements.txt

# Smazání staré databáze (pokud existuje)
# Windows:
del bookstore.db
# Linux/Mac:
rm -f bookstore.db

# Spuštění serveru
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API běží na `http://localhost:8000`. Interaktivní dokumentace: `http://localhost:8000/docs`

## Spuštění testů

Testy jsou integrační – volají HTTP endpointy běžícího serveru. Server musí běžet na `localhost:8000` (buď přes Docker, nebo lokálně).

```bash
# 1. Spustit server (Docker nebo lokálně)
docker compose up -d
# nebo: python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. Resetovat DB a spustit testy
curl -X POST http://localhost:8000/reset
pytest tests/test_existing.py -v
```

Na Windows bez curl lze reset udělat přes PowerShell:
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/reset
pytest tests/test_existing.py -v
```

> **Důležité:** Před každým spuštěním testů zavolejte `POST /reset`, aby se smazala data z předchozího běhu. Testy vytvářejí entity s unikátními názvy, které by jinak kolidovaly.

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
│   └── test_existing.py # Integrační testy
├── Dockerfile           # Docker image definice
├── docker-compose.yml   # Docker Compose konfigurace
├── db_schema.sql        # SQL schéma pro export
├── export_inputs.py     # Export dat pro vibe-testing-framework
├── requirements.txt
└── readme.md
```

## API Endpointy

### Authors
| Metoda | Endpoint | Popis |
|--------|----------|-------|
| POST | `/authors` | Vytvořit autora |
| GET | `/authors` | Seznam autorů |
| GET | `/authors/{id}` | Detail autora |
| PUT | `/authors/{id}` | Upravit autora |
| DELETE | `/authors/{id}` | Smazat autora |

### Categories
| Metoda | Endpoint | Popis |
|--------|----------|-------|
| POST | `/categories` | Vytvořit kategorii |
| GET | `/categories` | Seznam kategorií |
| GET | `/categories/{id}` | Detail kategorie |
| PUT | `/categories/{id}` | Upravit kategorii |
| DELETE | `/categories/{id}` | Smazat kategorii |

### Books
| Metoda | Endpoint | Popis |
|--------|----------|-------|
| POST | `/books` | Vytvořit knihu |
| GET | `/books` | Seznam knih (stránkování, filtry) |
| GET | `/books/{id}` | Detail knihy |
| PUT | `/books/{id}` | Upravit knihu |
| DELETE | `/books/{id}` | Smazat knihu |
| POST | `/books/{id}/discount` | Aplikovat slevu |
| PATCH | `/books/{id}/stock` | Upravit sklad |

### Reviews
| Metoda | Endpoint | Popis |
|--------|----------|-------|
| POST | `/books/{id}/reviews` | Přidat recenzi |
| GET | `/books/{id}/reviews` | Seznam recenzí |
| GET | `/books/{id}/rating` | Průměrné hodnocení |

### Tags
| Metoda | Endpoint | Popis |
|--------|----------|-------|
| POST | `/tags` | Vytvořit tag |
| GET | `/tags` | Seznam tagů |
| GET | `/tags/{id}` | Detail tagu |
| PUT | `/tags/{id}` | Upravit tag |
| DELETE | `/tags/{id}` | Smazat tag |
| POST | `/books/{id}/tags` | Přidat tagy ke knize |
| DELETE | `/books/{id}/tags` | Odebrat tagy z knihy |

### Orders
| Metoda | Endpoint | Popis |
|--------|----------|-------|
| POST | `/orders` | Vytvořit objednávku |
| GET | `/orders` | Seznam objednávek (stránkování, filtry) |
| GET | `/orders/{id}` | Detail objednávky |
| PATCH | `/orders/{id}/status` | Změnit stav objednávky |
| DELETE | `/orders/{id}` | Smazat objednávku |

### Ostatní
| Metoda | Endpoint | Popis |
|--------|----------|-------|
| GET | `/health` | Health check |
| POST | `/reset` | Reset databáze (jen pro testování) |

## Použití s Vibe Testing Framework

Toto API slouží jako testovací subjekt. Testovací framework umí API spouštět automaticky ve dvou režimech:

**Docker režim** (`docker: true` v `experiment.yaml`): Framework spustí `docker compose up --build -d`, testuje přes HTTP, a po dokončení zavolá `docker compose down --volumes`. Každý run začíná s čistou databází.

**Lokální režim** (výchozí): Framework spustí Python subprocess z `.venv` projektu. Databáze se čistí voláním `POST /reset`.

Export vstupních dat pro framework:

```bash
# Server musí běžet
python export_inputs.py
```

Skript exportuje OpenAPI specifikaci, dokumentaci, zdrojový kód, DB schéma a existující testy do `../vibe-testing-framework/inputs/`.

## Licence

Projekt pro diplomovou práci – testování REST API pomocí LLM.