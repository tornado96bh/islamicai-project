"""
يصنّف عناصر الصفحات إلى متن / سند / هامش / ترويسة / عنوان.

يكتب النتيجة في element_type (كان "text" لكل شيء) و layout_confidence.
لا يمس text_raw ولا text_normalized.

تحذير منهجي مهم
---------------
هذا مصنّف قواعد لا نموذج مدرَّب. نجح على 17 عيّنة انتُقيت من متنك،
وهذا **لا يساوي** دقته على 13,916 عنصراً. شغّل --review أولاً وراجع
عيّنة عشوائية بنفسك قبل التطبيق. أنت المتخصص، والقواعد بحاجة إلى
حكمك لا إلى حدسي.

الاستخدام:
    python scripts/classify_layout.py --review 40      # عيّنة للمراجعة
    python scripts/classify_layout.py --report         # توزيع الأنواع
    python scripts/classify_layout.py --apply
    python scripts/classify_layout.py --apply --min-confidence 0.7
"""

from __future__ import annotations

import argparse
import random
import sys
from collections import Counter

from sqlalchemy import func, select

from packages.database.models import Page, PageElement
from packages.database.session import SessionLocal
from packages.layout.classifier import LayoutClassifier, LayoutType


def _page_element_counts(db) -> dict:
    rows = db.execute(
        select(PageElement.page_id, func.count()).group_by(PageElement.page_id)
    ).all()
    return {r[0]: r[1] for r in rows}


def main() -> int:
    ap = argparse.ArgumentParser(description="تصنيف تخطيط عناصر الصفحة")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--review", type=int, default=0,
                    help="اعرض N عيّنة عشوائية للمراجعة البشرية")
    ap.add_argument("--min-confidence", type=float, default=0.55)
    ap.add_argument("--batch-size", type=int, default=2000)
    args = ap.parse_args()

    if not (args.apply or args.report or args.review):
        args.report = True

    clf = LayoutClassifier(min_confidence=args.min_confidence)
    db = SessionLocal()

    try:
        total = db.scalar(select(func.count()).select_from(PageElement)) or 0
        print(f"إجمالي العناصر    : {total:,}")
        print(f"عتبة الثقة        : {args.min_confidence}")
        print(f"إصدار المصنّف      : {clf.version}")
        print("-" * 60)

        page_counts = _page_element_counts(db)

        counts: Counter[str] = Counter()
        conf_sum: Counter[str] = Counter()
        review_pool: list[tuple[str, str, float, list[str]]] = []
        offset = 0

        while True:
            batch = db.scalars(
                select(PageElement).order_by(PageElement.id)
                .limit(args.batch_size).offset(offset)
            ).all()
            if not batch:
                break

            for el in batch:
                text = el.text_raw if el.text_raw is not None else (el.text or "")
                verdict = clf.classify(
                    text,
                    element_order=el.element_order or 0,
                    elements_on_page=page_counts.get(el.page_id, 0),
                )
                name = verdict.layout_type.value
                counts[name] += 1
                conf_sum[name] += verdict.confidence

                if args.review and len(review_pool) < args.review * 6:
                    review_pool.append((text, name, verdict.confidence, verdict.reasons))

                if args.apply:
                    el.element_type = name
                    el.layout_confidence = round(verdict.confidence, 4)

            if args.apply:
                db.commit()
            offset += len(batch)

        # -- التوزيع ------------------------------------------------
        print(f"{'النوع':16} {'العدد':>8} {'النسبة':>8}  متوسط الثقة")
        print("-" * 60)
        for name, n in counts.most_common():
            pct = n / total * 100 if total else 0
            avg = conf_sum[name] / n if n else 0
            print(f"{name:16} {n:>8,} {pct:>7.1f}%  {avg:.2f}")
        print("-" * 60)

        unknown_pct = counts.get("unknown", 0) / total * 100 if total else 0
        matn_pct = counts.get("matn", 0) / total * 100 if total else 0

        if unknown_pct > 35:
            print(f"تحذير: {unknown_pct:.0f}% بلا تصنيف. اخفض --min-confidence أو")
            print("       أرسل لي عيّنة من غير المصنَّف لأوسّع القواعد.")
        if matn_pct > 85:
            print(f"تحذير: {matn_pct:.0f}% صُنّف متناً. هذا مرتفع — قد يكون")
            print("       الاحتياطي النثري يبتلع أنواعاً أخرى.")

        # -- عيّنة المراجعة ------------------------------------------
        if args.review and review_pool:
            print(f"\n{'='*60}\n  عيّنة عشوائية للمراجعة — احكم عليها بنفسك\n{'='*60}")
            random.seed(42)
            for text, name, conf, reasons in random.sample(
                review_pool, min(args.review, len(review_pool))
            ):
                print(f"\n  [{name}]  ثقة {conf:.2f}")
                print(f"  السبب : {'; '.join(reasons[:2])}")
                print(f"  النص  : {text[:100]}")
            print(f"\n{'='*60}")
            print("  إن رأيت أخطاء، أرسلها لي مع التصنيف الصحيح.")

        if args.apply:
            print("\nطُبِّق. element_type و layout_confidence حُدِّثا.")
            print("text_raw و text_normalized لم يُمسّا.")
        elif not args.review:
            print("\nقياس فقط. للتنفيذ أضف --apply")

        return 0

    except Exception as exc:
        db.rollback()
        print(f"فشل: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
