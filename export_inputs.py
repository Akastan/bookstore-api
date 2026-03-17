"""
Export vstupních dat pro vibe-testing-framework.
Spusť po startu serveru: python export_inputs.py
"""
import os
import shutil
import requests
import yaml

FRAMEWORK_INPUTS = os.path.join("..", "vibe-testing-framework", "inputs")
SERVER_URL = "http://localhost:8000"


def export_openapi():
    """L0: Stáhne OpenAPI spec z běžícího serveru."""
    r = requests.get(f"{SERVER_URL}/openapi.json")
    r.raise_for_status()
    spec = r.json()
    path = os.path.join(FRAMEWORK_INPUTS, "openapi.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(spec, f, allow_unicode=True, sort_keys=False)
    print(f"✅ OpenAPI spec → {path}")


def export_documentation():
    """L1: Kopíruje byznys dokumentaci."""
    src = os.path.join("docs", "documentation.md")
    dst = os.path.join(FRAMEWORK_INPUTS, "documentation.md")
    shutil.copy2(src, dst)
    print(f"✅ Dokumentace → {dst}")


def export_source_code():
    """L2: Spojí zdrojový kód aplikace do jednoho souboru."""
    files = [
        "app/main.py",
        "app/crud.py",
        "app/schemas.py",
        "app/models.py",
    ]
    dst = os.path.join(FRAMEWORK_INPUTS, "source_code.py")
    with open(dst, "w", encoding="utf-8") as out:
        for fpath in files:
            out.write(f"\n# ═══ FILE: {fpath} ═══\n\n")
            with open(fpath, "r", encoding="utf-8") as f:
                out.write(f.read())
            out.write("\n")
    print(f"✅ Zdrojový kód ({len(files)} souborů) → {dst}")


def export_db_schema():
    """L3: Kopíruje DB schéma."""
    src = "db_schema.sql"
    dst = os.path.join(FRAMEWORK_INPUTS, "db_schema.sql")
    shutil.copy2(src, dst)
    print(f"✅ DB schéma → {dst}")


def export_existing_tests():
    """L4: Kopíruje existující testy."""
    src = os.path.join("tests", "test_existing.py")
    dst = os.path.join(FRAMEWORK_INPUTS, "existing_tests.py")
    shutil.copy2(src, dst)
    print(f"✅ Existující testy → {dst}")


if __name__ == "__main__":
    os.makedirs(FRAMEWORK_INPUTS, exist_ok=True)
    export_openapi()
    export_documentation()
    export_source_code()
    export_db_schema()
    export_existing_tests()
    print("\n🎉 Všechny vstupy exportovány!")