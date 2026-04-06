import sqlite3

conn = sqlite3.connect("bookstore.db")
cursor = conn.cursor()
cursor.execute(
    "SELECT sql FROM sqlite_master WHERE type IN ('table','index') AND sql IS NOT NULL ORDER BY type, name"
)
with open("db_schema.sql", "w", encoding="utf-8") as f:
    for row in cursor.fetchall():
        f.write(row[0] + ";\n\n")
conn.close()
print("Done:", open("db_schema.sql", encoding="utf-8").read()[:300])