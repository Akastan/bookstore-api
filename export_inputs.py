"""
Export vstupních dat pro vibe-testing-framework.

Spusť po startu serveru:
    python export_inputs.py

Exportuje 5 souborů odpovídajících kontextovým úrovním L0–L4:
  L0: openapi.yaml       ← staženo z /openapi.json
  L1: documentation.md   ← docs/documentation.md
  L2: source_code.py     ← spojené soubory z app/
  L3: db_schema.sql      ← db_schema.sql
  L4: existing_tests.py  ← tests/test_existing.py
"""
import os
import shutil
import requests
import yaml

FRAMEWORK_INPUTS = os.path.join("..", "vibe-testing-framework", "inputs")
SERVER_URL = "http://localhost:8000"

# Soubory pro L2 export — pořadí záleží na čitelnosti
SOURCE_FILES = [
    "app/main.py",
    "app/crud.py",
    "app/schemas.py",
    "app/models.py",
]


def export_openapi():
    """L0: Stáhne OpenAPI spec z běžícího serveru a uloží jako YAML."""
    r = requests.get(f"{SERVER_URL}/openapi.json")
    r.raise_for_status()
    spec = r.json()

    # Validace — měl by mít paths
    path_count = len(spec.get("paths", {}))
    if path_count < 30:
        print(f"  ⚠️  Jen {path_count} cest — očekáváno ~40. Běží server s novými endpointy?")

    path = os.path.join(FRAMEWORK_INPUTS, "openapi.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(spec, f, allow_unicode=True, sort_keys=False)
    print(f"  ✅ OpenAPI spec ({path_count} cest) → {path}")


def export_documentation():
    """L1: Kopíruje technickou dokumentaci."""
    src = os.path.join("docs", "documentation.md")
    dst = os.path.join(FRAMEWORK_INPUTS, "documentation.md")
    shutil.copy2(src, dst)

    # Info o velikosti
    size = os.path.getsize(dst)
    print(f"  ✅ Dokumentace ({size:,} B) → {dst}")


def export_source_code():
    """L2: Spojí zdrojový kód aplikace do jednoho souboru."""
    dst = os.path.join(FRAMEWORK_INPUTS, "source_code.py")
    total_lines = 0

    with open(dst, "w", encoding="utf-8") as out:
        for fpath in SOURCE_FILES:
            if not os.path.exists(fpath):
                print(f"  ⚠️  {fpath} neexistuje — přeskakuji")
                continue
            out.write(f"\n# ═══ FILE: {fpath} ═══\n\n")
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
                out.write(content)
                total_lines += content.count("\n")
            out.write("\n")

    print(f"  ✅ Zdrojový kód ({len(SOURCE_FILES)} souborů, ~{total_lines} řádků) → {dst}")


def export_db_schema():
    """L3: Kopíruje DB schéma."""
    src = "db_schema.sql"
    dst = os.path.join(FRAMEWORK_INPUTS, "db_schema.sql")
    shutil.copy2(src, dst)
    print(f"  ✅ DB schéma → {dst}")


def export_existing_tests():
    """L4: Kopíruje existující referenční testy."""
    src = os.path.join("tests", "test_existing.py")
    dst = os.path.join(FRAMEWORK_INPUTS, "existing_tests.py")
    shutil.copy2(src, dst)

    # Spočítej testy
    with open(src, "r", encoding="utf-8") as f:
        test_count = sum(1 for line in f if line.strip().startswith("def test_"))
    print(f"  ✅ Existující testy ({test_count} testů) → {dst}")


if __name__ == "__main__":
    os.makedirs(FRAMEWORK_INPUTS, exist_ok=True)

    print(f"\n📦 Export vstupů do {os.path.abspath(FRAMEWORK_INPUTS)}\n")

    export_openapi()
    export_documentation()
    export_source_code()
    export_db_schema()
    export_existing_tests()

    print(f"\n🎉 Všech 5 vstupů exportováno (L0–L4).")
    print(f"   Cíl: {os.path.abspath(FRAMEWORK_INPUTS)}")