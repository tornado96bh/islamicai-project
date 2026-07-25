from sqlalchemy import text
from packages.database.session import SessionLocal

db = SessionLocal()

print("=" * 80)
print("COUNTS")
print("=" * 80)

queries = [
    ("Pages", "SELECT COUNT(*) FROM pages"),
    ("PageElements", "SELECT COUNT(*) FROM page_elements"),
    ("PageElements with text", "SELECT COUNT(*) FROM page_elements WHERE text IS NOT NULL"),
    ("PageElements with non-empty text", "SELECT COUNT(*) FROM page_elements WHERE trim(coalesce(text,'')) <> ''")
]

for name, sql in queries:
    value = db.execute(text(sql)).scalar()
    print(f"{name}: {value}")

print()
print("=" * 80)
print("FIRST 20 TEXT BLOCKS")
print("=" * 80)

rows = db.execute(text("""
SELECT page_id,
       length(text),
       left(text,200)
FROM page_elements
WHERE text IS NOT NULL
LIMIT 20
""")).fetchall()

for r in rows:
    print("-" * 80)
    print("Page :", r[0])
    print("Len  :", r[1])
    print("Text :", repr(r[2]))

db.close()
