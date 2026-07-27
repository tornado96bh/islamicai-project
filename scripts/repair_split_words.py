"""
إصلاح الكلمات المشقوقة — تكراري وذاتي التغذية.

المشكلة التي يحلها
------------------
مصحح OCR يحتاج الكلمةَ الصحيحة موجودةً في المعجم ليجرؤ على لحم
شظيتين. والمعجم مبني من النص نفسه الذي فيه الكلمة مشقوقة. دورة
مغلقة:

    "حمّ ، اد"  لا تُلحم لأن "حماد" تردده 44 فقط
    و"حماد" تردده منخفض لأن أكثر مواضعه مشقوقة

الحل
----
التكرار. كل تمريرة تلحم ما تستطيع، فترتفع ترددات الكلمات الصحيحة،
فتصير التمريرة التالية أجرأ. يتوقف عند التقارب.

ولا يعتمد هذا السكربت على ملفات التعلّم إطلاقاً: يبني معجمه من
`text_normalized` مباشرة في كل تمريرة. فهو مستقل عن أي تلوّث سابق.

مبدأ حاكم: **text_raw لا يُمس.** الإصلاح على العمود المفهرَس وحده.

الاستخدام:
    python scripts/repair_split_words.py --report
    python scripts/repair_split_words.py --apply
    python scripts/repair_split_words.py --apply --iterations 4
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter

from sqlalchemy import func, select

from packages.database.models import PageElement
from packages.database.session import SessionLocal

# حروف عربية خالصة فقط تُلحم — لا أرقام ولا ترقيم
_ARABIC_RE = re.compile(r"^[\u0621-\u064a]+$")

# علامة ترقيم مفردة قد تقع داخل الكلمة المشقوقة
_LONE_PUNCT = {"،", ",", ".", ":", ";", "؛", "-"}

# كلمات لا تُلحم أبداً مهما كان الناتج
PROTECTED = {
    "عن", "في", "من", "الي", "علي", "او", "ثم", "قد", "لا", "ما", "بن",
    "ابن", "ابي", "ابو", "اب", "ام", "اذا", "ان", "انه", "به", "له",
    "هو", "هي", "هم", "كل", "بل", "لم", "لن", "يا", "قال", "عند", "بعد",
    "قبل", "غير", "بين", "حتي", "لو", "اي", "كم", "مع", "عليه", "الله",
    "عنه", "عنها", "عنهم", "التي", "الذي", "هذا", "هذه", "ذلك",
}

MAX_FRAGMENT_LEN = 3
MIN_TARGET_FREQ = 3
MIN_TARGET_LEN = 4


def build_vocabulary(db) -> Counter:
    """معجم الكلمات المفردة كما هي الآن في العمود المفهرَس."""
    vocab: Counter = Counter()
    offset = 0
    while True:
        rows = db.execute(
            select(PageElement.text_normalized)
            .where(PageElement.text_normalized.isnot(None))
            .order_by(PageElement.id)
            .limit(5000)
            .offset(offset)
        ).all()
        if not rows:
            break
        for (text,) in rows:
            for token in (text or "").split():
                if _ARABIC_RE.match(token):
                    vocab[token] += 1
        offset += len(rows)
    return vocab


def repair_line(text: str, vocab: Counter, stats: Counter) -> str:
    """يلحم الشظايا في سطر واحد بحسب المعجم الحالي."""
    tokens = text.split()
    if len(tokens) < 2:
        return text

    out: list[str] = []
    i = 0
    n = len(tokens)

    def joinable(a: str, b: str) -> str | None:
        if not (_ARABIC_RE.match(a) and _ARABIC_RE.match(b)):
            return None
        if a in PROTECTED or b in PROTECTED:
            return None
        if min(len(a), len(b)) > MAX_FRAGMENT_LEN:
            return None
        cand = a + b
        if len(cand) < MIN_TARGET_LEN:
            return None
        if vocab.get(cand, 0) < MIN_TARGET_FREQ:
            return None
        # الناتج يجب أن يكون أوضح من الشظية الأقصر منفردة، وإلا فالشظية
        # كلمة قائمة بذاتها لا جزءاً مبتوراً
        short = a if len(a) <= len(b) else b
        if len(short) >= 2 and vocab.get(short, 0) > vocab[cand] * 20:
            # الشظية أشيع بعشرين ضعفاً: مؤشر تلوّث لا كلمة مستقلة،
            # فنسمح باللحم رغم ذلك حين يكون الناتج معروفاً بوضوح
            return cand if vocab[cand] >= MIN_TARGET_FREQ * 3 else None
        return cand

    while i < n:
        a = tokens[i]
        # (أ) شظيتان متجاورتان
        if i + 1 < n:
            merged = joinable(a, tokens[i + 1])
            if merged:
                out.append(merged)
                stats[f"{a} {tokens[i+1]} -> {merged}"] += 1
                i += 2
                continue
        # (ب) شظيتان تفصلهما علامة ترقيم مفردة
        if i + 2 < n and tokens[i + 1] in _LONE_PUNCT:
            merged = joinable(a, tokens[i + 2])
            if merged:
                out.append(merged)
                stats[f"{a} {tokens[i+1]} {tokens[i+2]} -> {merged}"] += 1
                i += 3
                continue
        out.append(a)
        i += 1

    return " ".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="إصلاح تكراري للكلمات المشقوقة")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--iterations", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=2000)
    args = ap.parse_args()
    if not (args.apply or args.report):
        args.report = True

    db = SessionLocal()
    try:
        total = db.scalar(select(func.count()).select_from(PageElement)) or 0
        print(f"إجمالي العناصر : {total:,}")
        print(f"عدد التمريرات  : {args.iterations}")
        print("-" * 58)

        grand_total = 0
        for iteration in range(1, args.iterations + 1):
            vocab = build_vocabulary(db)
            print(f"\nالتمريرة {iteration}: معجم مشتق من العمود المفهرَس "
                  f"({len(vocab):,} كلمة)")

            stats: Counter = Counter()
            changed = 0
            offset = 0

            while True:
                batch = db.scalars(
                    select(PageElement)
                    .where(PageElement.text_normalized.isnot(None))
                    .order_by(PageElement.id)
                    .limit(args.batch_size)
                    .offset(offset)
                ).all()
                if not batch:
                    break
                for el in batch:
                    fixed = repair_line(el.text_normalized or "", vocab, stats)
                    if fixed != el.text_normalized:
                        changed += 1
                        if args.apply:
                            el.text_normalized = fixed
                if args.apply:
                    db.commit()
                offset += len(batch)

            merges = sum(stats.values())
            grand_total += merges
            print(f"  عناصر تغيّرت : {changed:,}")
            print(f"  عمليات لحم   : {merges:,}")
            if stats:
                print("  أشيع اللحمات:")
                for pattern, count in stats.most_common(8):
                    print(f"    {count:>5} x  {pattern}")

            if merges == 0:
                print("  تقارب — لا مزيد من اللحم الممكن.")
                break
            if not args.apply:
                print("  (قياس فقط: التمريرات التالية ستعطي نفس النتيجة)")
                break

        print("-" * 58)
        print(f"إجمالي عمليات اللحم: {grand_total:,}")
        if args.apply:
            print("\nطُبِّق. text_raw لم يُمس.")
            print("الخطوة التالية: python scripts/train_learning.py")
        else:
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
