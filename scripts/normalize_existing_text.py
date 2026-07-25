from sqlalchemy import select

from packages.database.session import SessionLocal
from packages.database.models import PageElement
from packages.utils.arabic_normalizer import normalize_for_search

db = SessionLocal()

try:
    elements = db.scalars(select(PageElement)).all()

    total = len(elements)
    changed = 0

    print(f"Found {total} PageElements")

    for i, element in enumerate(elements, start=1):

        original = element.text or ""
        normalized = normalize_for_search(original)

        if original != normalized:
            element.text = normalized
            changed += 1

        if i % 500 == 0:
            print(f"{i}/{total}")

    db.commit()

    print("=" * 60)
    print(f"Finished.")
    print(f"Modified rows : {changed}")
    print(f"Unchanged rows: {total - changed}")

finally:
    db.close()
