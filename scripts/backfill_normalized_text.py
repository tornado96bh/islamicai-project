"""
يملأ text_normalized من text_raw باستخدام المطبّع الجديد.

بديل آمن لـ scripts/normalize_existing_text.py المعطَّل:
  - لا يكتب فوق النص الأصلي إطلاقاً
  - يعمل على دفعات مع commit دوري (يتحمل الانقطاع)
  - قابل للاستئناف: يتخطى ما طُبِّع بنفس إصدار المطبّع
  - يبلّغ عن التقدم والإحصاءات

الاستخدام:
    python scripts/backfill_normalized_text.py
    python scripts/backfill_normalized_text.py --batch-size 2000
    python scripts/backfill_normalized_text.py --force   # يعيد تطبيع الكل
    python scripts/backfill_normalized_text.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import func, select, update

from packages.database.models import PageElement
from packages.database.session import SessionLocal
from packages.utils.arabic_canonicalizer import (
    CANONICALIZER_VERSION,
    normalize_surface_text,
    search_form_text,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="ملء text_normalized بأمان")
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--force", action="store_true", help="أعد تطبيع كل الصفوف")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db = SessionLocal()
    started = time.time()

    try:
        total = db.scalar(select(func.count()).select_from(PageElement)) or 0
        if total == 0:
            print("لا توجد عناصر في page_elements. لا شيء لعمله.")
            return 0

        stmt = select(PageElement)
        if not args.force:
            stmt = stmt.where(
                (PageElement.text_normalized.is_(None))
                | (PageElement.canonicalizer_version.is_distinct_from(CANONICALIZER_VERSION))
            )

        pending = db.scalar(
            select(func.count()).select_from(stmt.subquery())
        ) or 0

        print(f"إجمالي العناصر     : {total:,}")
        print(f"يحتاج معالجة       : {pending:,}")
        print(f"إصدار المطبّع       : {CANONICALIZER_VERSION}")
        print(f"حجم الدفعة         : {args.batch_size:,}")
        print("-" * 55)

        if pending == 0:
            print("كل شيء مُطبَّع بالفعل بهذا الإصدار.")
            return 0

        if args.dry_run:
            sample = db.scalars(stmt.limit(5)).all()
            print("\nعيّنة (dry-run):\n")
            for el in sample:
                src = el.text_raw or el.text or ""
                print(f"  الأصل   : {src[:70]}")
                print(f"  المطبّع  : {search_form_text(src)[:70]}")
                print()
            print("لم يُكتب شيء إلى القاعدة (--dry-run).")
            return 0

        processed = 0
        changed = 0
        blank = 0
        offset = 0

        while True:
            batch = db.scalars(
                stmt.order_by(PageElement.id).limit(args.batch_size).offset(offset)
            ).all()
            if not batch:
                break

            for el in batch:
                # مصدر التطبيع: text_raw إن وُجد، وإلا text
                source = el.text_raw if el.text_raw is not None else (el.text or "")

                if el.text_raw is None:
                    el.text_raw = source

                if not source.strip():
                    el.text_normalized = ""
                    el.canonicalizer_version = CANONICALIZER_VERSION
                    blank += 1
                    processed += 1
                    continue

                normalized = search_form_text(source)
                if el.text_normalized != normalized:
                    changed += 1
                el.text_normalized = normalized
                el.canonicalizer_version = CANONICALIZER_VERSION
                processed += 1

            db.commit()
            offset += len(batch)
            pct = min(100, round(processed * 100 / max(pending, 1)))
            elapsed = time.time() - started
            rate = processed / elapsed if elapsed > 0 else 0
            print(f"  {processed:,}/{pending:,}  ({pct}%)  — {rate:,.0f} عنصر/ث")

            if args.force and offset >= total:
                break

        print("-" * 55)
        print(f"عولج            : {processed:,}")
        print(f"تغيّر نصه المطبّع : {changed:,}")
        print(f"فارغ            : {blank:,}")
        print(f"الزمن           : {time.time() - started:,.1f} ثانية")
        print("\nالنص الأصلي في text_raw لم يُمس.")
        return 0

    except Exception as exc:
        db.rollback()
        print(f"\nفشل: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
