"""
يملأ text_display وتفكيك الرواية.

    text_display   الصيغة المقروءة: بلا تمديد ولا تفكّك، **بكل الحركات
                   والهمزات والنقاط**. هذا ما يُعرض للقارئ.
    hadith_number  رقم الرواية بين القوسين
    isnad_text     السند
    matn_text      المتن

مبدأ صارم: **text_raw لا يُمس**، وكل جزء مقتطع حرفياً من الأصل، فيمكن
دائماً إعادة تركيبه كاملاً.

    python scripts/backfill_display_and_split.py --dry-run
    python scripts/backfill_display_and_split.py --apply
    python scripts/backfill_display_and_split.py --apply --min-confidence 0.7
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import func, select

from packages.database.models import PageElement
from packages.database.session import SessionLocal
from packages.ingestion.ocr_corrector import Lexicon, OcrCorrector
from packages.layout.hadith_splitter import HadithSplitter

DICTIONARY_PATH = "storage/learning/dictionary.json"

# أنواع تُفكَّك: السند والمتن وترقيم الحديث
SPLITTABLE = {"sanad", "matn", "hadith_number", "unknown"}


def main() -> int:
    ap = argparse.ArgumentParser(description="ملء الصيغة المقروءة وتفكيك الرواية")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--batch-size", type=int, default=1000)
    ap.add_argument("--min-confidence", type=float, default=0.5)
    ap.add_argument("--dictionary", default=DICTIONARY_PATH)
    args = ap.parse_args()
    if not (args.apply or args.dry_run):
        args.dry_run = True

    lex = Lexicon(args.dictionary)
    corrector = OcrCorrector(lex)
    splitter = HadithSplitter(min_confidence=args.min_confidence)

    print(f"مصحح OCR   : {'معجم ' + format(len(lex), ',') + ' كلمة' if lex.loaded else 'بلا معجم'}")
    print(f"عتبة التقسيم: {args.min_confidence}")
    print("-" * 60)

    db = SessionLocal()
    started = time.time()
    try:
        total = db.scalar(select(func.count()).select_from(PageElement)) or 0
        print(f"إجمالي العناصر : {total:,}")

        if args.dry_run:
            rows = db.scalars(
                select(PageElement)
                .where(PageElement.element_type.in_(("sanad", "matn")))
                .limit(4)
            ).all()
            print("\nعيّنة (dry-run):\n")
            for el in rows:
                raw = el.text_raw or el.text or ""
                display = corrector.correct_text(raw)
                parts = splitter.split(display)
                print(f"  الأصل    : {raw[:78]}")
                print(f"  المقروء  : {display[:78]}")
                if parts.number:
                    print(f"  الرقم    : {parts.number}")
                if parts.isnad:
                    print(f"  السند    : {parts.isnad[:78]}")
                if parts.matn:
                    print(f"  المتن    : {parts.matn[:78]}")
                print()
            print("لم يُكتب شيء.")
            return 0

        processed = displayed = split_ok = 0
        offset = 0
        while True:
            batch = db.scalars(
                select(PageElement).order_by(PageElement.id)
                .limit(args.batch_size).offset(offset)
            ).all()
            if not batch:
                break

            for el in batch:
                raw = el.text_raw if el.text_raw is not None else (el.text or "")
                if el.text_raw is None:
                    el.text_raw = raw

                # الصيغة المقروءة: تصحيح OCR بلا تطبيع
                display = corrector.correct_text(raw)
                el.text_display = display
                displayed += 1

                kind = (el.element_type or "").lower()
                if kind in SPLITTABLE and display.strip():
                    parts = splitter.split(display)
                    el.hadith_number = (parts.number or None) or None
                    el.isnad_text = (parts.isnad or None) or None
                    el.matn_text = (parts.matn or None) or None
                    el.split_confidence = round(parts.confidence, 4)
                    if parts.is_complete():
                        split_ok += 1

                processed += 1

            db.commit()
            offset += len(batch)
            rate = processed / max(time.time() - started, 0.001)
            print(f"  {processed:,}/{total:,}  — {rate:,.0f} عنصر/ث")

        print("-" * 60)
        print(f"عولج               : {processed:,}")
        print(f"صيغة مقروءة        : {displayed:,}")
        print(f"فُكِّك إلى سند ومتن  : {split_ok:,}")
        print(f"الزمن              : {time.time() - started:,.1f} ثانية")
        print("\ntext_raw لم يُمس. كل جزء مقتطع حرفياً من الأصل.")
        return 0

    except Exception as exc:
        db.rollback()
        print(f"\nفشل: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
