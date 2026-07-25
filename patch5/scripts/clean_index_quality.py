"""
يستبعد العناصر الرديئة من فهرس البحث دون حذف أي شيء.

عالج ما رصده فحصك: 772 عنصراً فارغاً، 2487 بمسافات بادئة،
10 مقاطع مكررة، وضجيج OCR.

الآلية: العنصر الرديء يُضبط text_normalized = NULL. و fts.py و
fuzzy.py يشترطان `text_normalized IS NOT NULL`، فيخرج من الفهرس
تلقائياً. **لا يُحذف صف ولا يُمس text_raw** — الأصل يبقى كاملاً
للعرض والاستشهاد، ويمكن التراجع بإعادة تشغيل الملء.

الاستخدام:
    python scripts/clean_index_quality.py --report        # قياس فقط
    python scripts/clean_index_quality.py --apply
    python scripts/clean_index_quality.py --apply --min-words 2
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from collections import Counter

from sqlalchemy import func, select

from packages.database.models import PageElement
from packages.database.session import SessionLocal

# نص يتكوّن من ترقيم وأرقام فقط: لا قيمة بحثية
_ONLY_NOISE_RE = re.compile(r"^[\s\d\u0660-\u0669\u06f0-\u06f9\W_]*$")
_TATWEEL = "\u0640"


def classify(text_raw: str, normalized: str | None, min_words: int) -> str:
    """يرجّع تصنيف الجودة: clean / blank / noise / short."""
    if not text_raw or not text_raw.strip():
        return "blank"
    if normalized is None or not normalized.strip():
        return "blank"
    if _ONLY_NOISE_RE.match(normalized):
        return "noise"
    if len(normalized.split()) < min_words:
        return "short"
    # تمديد كثيف باقٍ رغم التصحيح
    if text_raw.count(_TATWEEL) > len(text_raw) * 0.25:
        return "noise"
    return "clean"


def main() -> int:
    ap = argparse.ArgumentParser(description="استبعاد العناصر الرديئة من الفهرس")
    ap.add_argument("--apply", action="store_true", help="نفّذ التغيير")
    ap.add_argument("--report", action="store_true", help="قياس فقط")
    ap.add_argument("--min-words", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=2000)
    ap.add_argument("--drop-duplicates", action="store_true",
                    help="أبقِ نسخة واحدة من كل نص مكرر حرفياً")
    args = ap.parse_args()

    if not args.apply and not args.report:
        args.report = True

    db = SessionLocal()
    try:
        total = db.scalar(select(func.count()).select_from(PageElement)) or 0
        print(f"إجمالي العناصر : {total:,}")
        print(f"الحد الأدنى للكلمات : {args.min_words}")
        print("-" * 56)

        counts: Counter[str] = Counter()
        seen_hashes: dict[str, int] = {}
        to_exclude: list[int] = []
        duplicates = 0
        offset = 0

        while True:
            batch = db.scalars(
                select(PageElement)
                .order_by(PageElement.id)
                .limit(args.batch_size)
                .offset(offset)
            ).all()
            if not batch:
                break

            for el in batch:
                raw = el.text_raw if el.text_raw is not None else (el.text or "")
                verdict = classify(raw, el.text_normalized, args.min_words)

                if verdict == "clean" and args.drop_duplicates and el.text_normalized:
                    h = hashlib.sha1(el.text_normalized.encode("utf-8")).hexdigest()
                    if h in seen_hashes:
                        verdict = "duplicate"
                        duplicates += 1
                    else:
                        seen_hashes[h] = 1

                counts[verdict] += 1
                if verdict != "clean":
                    to_exclude.append(el.id)
                    if args.apply:
                        el.text_normalized = None

            if args.apply:
                db.commit()
            offset += len(batch)

        print(f"سليم           : {counts['clean']:,}")
        print(f"فارغ           : {counts['blank']:,}")
        print(f"ضجيج           : {counts['noise']:,}")
        print(f"أقصر من الحد   : {counts['short']:,}")
        if args.drop_duplicates:
            print(f"مكرر           : {duplicates:,}")
        print("-" * 56)

        excluded = len(to_exclude)
        pct = (excluded / total * 100) if total else 0
        print(f"سيُستبعد من الفهرس : {excluded:,}  ({pct:.1f}%)")

        if args.apply:
            print("\nطُبِّق. الصفوف لم تُحذف و text_raw لم يُمس.")
            print("للتراجع: python scripts/backfill_normalized_text.py --force")
        else:
            print("\nقياس فقط. للتنفيذ أضف --apply")

        if pct > 40:
            print("\nتحذير: أكثر من 40% مستبعَد. راجع --min-words قبل التطبيق.")

        return 0

    except Exception as exc:
        db.rollback()
        print(f"فشل: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
