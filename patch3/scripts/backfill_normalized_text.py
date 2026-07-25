"""
يملأ text_normalized من text_raw — النسخة الثانية مع تصحيح OCR.

الفرق عن النسخة الأولى: قبل التطبيع، يمرّ النص على مصحح OCR الذي
يزيل التمديد ويلحم الكلمات المتفككة ويصلح الرباطات.

سبب الإضافة: القياس الأساسي أظهر أن النص الممدّد يلوّث النتائج —
"محمّـــــ د بـــــن يعقـــــوب" يتصدّر البحث عن متن حديث، لأن
التطويل يولّد ثلاثيات متكررة ترفع تشابه trigram زوراً.

مبدأ حاكم: **text_raw لا يُمس إطلاقاً.** التصحيح يخص فهرس البحث
فقط، والعرض والاستشهاد يبقيان من الأصل بكل حركاته وهمزاته.

الاستخدام:
    python scripts/backfill_normalized_text.py
    python scripts/backfill_normalized_text.py --no-ocr      # تطبيع فقط
    python scripts/backfill_normalized_text.py --dry-run
    python scripts/backfill_normalized_text.py --force
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import func, select

from packages.database.models import PageElement
from packages.database.session import SessionLocal
from packages.utils.arabic_canonicalizer import CANONICALIZER_VERSION, search_form_text

try:
    from packages.ingestion.ocr_corrector import (
        OCR_CORRECTOR_VERSION,
        Lexicon,
        OcrCorrector,
    )

    HAS_OCR = True
except ImportError:
    HAS_OCR = False
    OCR_CORRECTOR_VERSION = "none"

DICTIONARY_PATH = "storage/learning/dictionary.json"


def main() -> int:
    ap = argparse.ArgumentParser(description="ملء text_normalized بأمان")
    ap.add_argument("--batch-size", type=int, default=1000)
    ap.add_argument("--force", action="store_true", help="أعد معالجة كل الصفوف")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-ocr", action="store_true", help="تخطَّ تصحيح OCR")
    ap.add_argument("--dictionary", default=DICTIONARY_PATH)
    args = ap.parse_args()

    # --- تجهيز المصحح -------------------------------------------------
    corrector = None
    if HAS_OCR and not args.no_ocr:
        lex = Lexicon(args.dictionary)
        corrector = OcrCorrector(lex)
        if lex.loaded:
            print(f"مصحح OCR      : مفعّل، معجم {len(lex):,} كلمة")
        else:
            print(f"مصحح OCR      : مفعّل بلا معجم ({args.dictionary} غير موجود)")
            print("                لحم الكلمات المتفككة معطّل. درّب أولاً لتفعيله.")
    else:
        print("مصحح OCR      : معطّل")

    version_tag = f"{CANONICALIZER_VERSION}+ocr{OCR_CORRECTOR_VERSION}" if corrector \
        else CANONICALIZER_VERSION

    db = SessionLocal()
    started = time.time()

    try:
        total = db.scalar(select(func.count()).select_from(PageElement)) or 0
        if total == 0:
            print("لا توجد عناصر. لا شيء لعمله.")
            return 0

        stmt = select(PageElement)
        if not args.force:
            stmt = stmt.where(
                (PageElement.text_normalized.is_(None))
                | (PageElement.canonicalizer_version.is_distinct_from(version_tag))
            )

        pending = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        print(f"إجمالي العناصر : {total:,}")
        print(f"يحتاج معالجة   : {pending:,}")
        print(f"وسم الإصدار    : {version_tag}")
        print("-" * 58)

        if pending == 0:
            print("كل شيء معالَج بهذا الإصدار.")
            return 0

        if args.dry_run:
            print("\nعيّنة (dry-run):\n")
            for el in db.scalars(stmt.limit(6)).all():
                src = el.text_raw if el.text_raw is not None else (el.text or "")
                fixed = corrector.correct_text(src) if corrector else src
                print(f"  الأصل   : {src[:72]}")
                print(f"  المصحَّح : {fixed[:72]}")
                print(f"  المفهرَس: {search_form_text(fixed)[:72]}")
                print()
            print("لم يُكتب شيء إلى القاعدة.")
            return 0

        processed = changed = blank = 0
        ocr_stretch = ocr_merged = ocr_lig = 0
        offset = 0

        while True:
            batch = db.scalars(
                stmt.order_by(PageElement.id).limit(args.batch_size).offset(offset)
            ).all()
            if not batch:
                break

            for el in batch:
                source = el.text_raw if el.text_raw is not None else (el.text or "")
                if el.text_raw is None:
                    el.text_raw = source          # حفظ الأصل قبل أي شيء

                if not source.strip():
                    el.text_normalized = ""
                    el.canonicalizer_version = version_tag
                    blank += 1
                    processed += 1
                    continue

                if corrector:
                    fixed, st = corrector.correct(source)
                    ocr_stretch += st.stretch_removed
                    ocr_merged += st.words_merged
                    ocr_lig += st.ligatures_fixed
                else:
                    fixed = source

                normalized = search_form_text(fixed)
                if el.text_normalized != normalized:
                    changed += 1
                el.text_normalized = normalized
                el.canonicalizer_version = version_tag
                processed += 1

            db.commit()
            offset += len(batch)
            pct = min(100, round(processed * 100 / max(pending, 1)))
            rate = processed / max(time.time() - started, 0.001)
            print(f"  {processed:,}/{pending:,}  ({pct}%)  — {rate:,.0f} عنصر/ث")

            if args.force and offset >= total:
                break

        print("-" * 58)
        print(f"عولج            : {processed:,}")
        print(f"تغيّر نصه المفهرَس: {changed:,}")
        print(f"فارغ            : {blank:,}")
        if corrector:
            print(f"تمديد أُزيل      : {ocr_stretch:,}")
            print(f"رباطات صُحّحت    : {ocr_lig:,}")
            print(f"كلمات لُحمت      : {ocr_merged:,}")
        print(f"الزمن           : {time.time() - started:,.1f} ثانية")
        print("\ntext_raw لم يُمس. الأصل محفوظ بكل حركاته وهمزاته.")
        return 0

    except Exception as exc:
        db.rollback()
        print(f"\nفشل: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
