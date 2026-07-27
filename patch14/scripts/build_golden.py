"""
بناء المجموعة الذهبية — بحكمك أنت، بأقل جهد ممكن.

لماذا هذه الأداة
----------------
مرّتان في هذا المشروع خدعنا القياسُ:

  * انحدار زمن خفي، لأن المقارنة كانت بالأساس الأصلي لا بالتشغيل السابق.
  * تدهور في جودة النتائج رفع `must_contain_rate` إلى 0.875، لأن كل
    عبارة نمطية تحوي كلمة الاستعلام.

السبب واحد: خمسة أسئلة، ومقياس ضعيف. و`Recall@k` و`MRR` معطَّلان لأن
`relevant_element_ids` فارغة — ولا يستطيع أحد ملأها غيرك.

هذه الأداة تقلّل عملك إلى: انظر عشر نتائج، اكتب أرقام الصحيحة، اضغط
Enter. عشرون سؤالاً تستغرق نحو ساعة.

الاستخدام:
    python scripts/build_golden.py --suggest 30      # اقتراح أسئلة من متنك
    python scripts/build_golden.py                   # جلسة تحكيم تفاعلية
    python scripts/build_golden.py --query "زرارة بن أعين"
    python scripts/build_golden.py --status
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = REPO_ROOT / "datasets" / "golden" / "queries.jsonl"

INTENTS = ("entity", "hadith", "bibliography", "ruling", "general")


# ---------------------------------------------------------------------------
# التخزين
# ---------------------------------------------------------------------------

def load_golden() -> list[dict]:
    if not GOLDEN_PATH.exists():
        return []
    rows = []
    for line in GOLDEN_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def save_golden(rows: list[dict]) -> None:
    GOLDEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)
    GOLDEN_PATH.write_text(body + "\n", encoding="utf-8")


def next_id(rows: list[dict]) -> str:
    used = {r.get("id", "") for r in rows}
    n = 1
    while f"q{n:03d}" in used:
        n += 1
    return f"q{n:03d}"


# ---------------------------------------------------------------------------
# اقتراح الأسئلة من متنك
# ---------------------------------------------------------------------------

def _clean_enough(text: str) -> bool:
    """يستبعد النص المعطوب أو الفهرسي قبل أن يصير سؤالاً."""
    t = (text or "").strip()
    if not t or "...." in t or ".. ." in t:
        return False
    tokens = t.split()
    if not (6 <= len(tokens) <= 22):
        return False
    digits = sum(1 for ch in t if ch.isdigit() or "\u0660" <= ch <= "\u0669")
    if digits > len(t) * 0.08:
        return False
    # شظايا الحرف والحرفين علامة تفكك
    fragments = sum(1 for tok in tokens if len(tok) <= 2 and tok.isalpha())
    return fragments <= len(tokens) * 0.25


# كلمات نمطية لا تميّز نصاً عن آخر
_LOW_VALUE = {
    "الله", "عليه", "عليهم", "السلام", "صلي", "واله", "رسول", "النبي",
    "قال", "عن", "في", "من", "الي", "علي", "ان", "انه", "له", "به",
    "هو", "هي", "ما", "لا", "ثم", "وقد", "قد", "كان", "عز", "وجل",
    "بن", "ابن", "ابي", "ابو", "الذي", "التي", "هذا", "هذه",
}


def _distinctive_phrase(text: str, n: int = 5) -> str:
    """
    يختار النافذة **الأكثر إفادة** من النص، لا الوسطى عمياء.

    اقتطاع الوسط أنتج أسئلة مثل "الله عليه واله الما يطهر" — نصفها
    صيغة صلاة نمطية. النافذة المختارة هنا هي الأقل احتواءً على
    الكلمات النمطية، فتشبه ما يكتبه باحث فعلاً.
    """
    tokens = [t for t in (text or "").split() if len(t) > 1 and t.isalpha()]
    if len(tokens) <= n:
        return " ".join(tokens)

    best_start, best_value = 0, -1
    for start in range(len(tokens) - n + 1):
        window = tokens[start : start + n]
        value = sum(1 for t in window if t not in _LOW_VALUE)
        if value > best_value:
            best_value, best_start = value, start

    return " ".join(tokens[best_start : best_start + n])


def suggest_from_corpus(db, limit: int = 25) -> list[tuple[str, str]]:
    """
    يبني الأسئلة من قاعدة البيانات مباشرة، لا من ملفات التعلّم.

    سبب التغيير: النسخة السابقة قرأت entities.json، وهو مخزَّن بلا
    ترشيح، فأنتجت أسئلة فاسدة مثل
        "................ ....... ابن بابويه القمي"
        "الشيخ المساله الاخيره باسناده عن"
    وهي شظايا لا أسئلة.

    الآن: عيّنات من المتون النظيفة والعناوين الحقيقية، مصنَّفة بمحرك
    التخطيط. فتكون الأسئلة قابلة للإجابة فعلاً.
    """
    import random

    from sqlalchemy import func, select

    from packages.database.models import PageElement

    random.seed(11)
    out: list[tuple[str, str]] = []

    # (أ) عناوين حقيقية — أسئلة ببليوغرافية طبيعية
    headings = db.scalars(
        select(PageElement.text_normalized)
        .where(PageElement.element_type == "heading")
        .where(PageElement.text_normalized.isnot(None))
        .order_by(func.random())
        .limit(limit * 3)
    ).all()
    for h in headings:
        t = (h or "").strip()
        if _clean_enough(t):
            out.append((t[:60], "bibliography"))
        if len(out) >= limit // 3:
            break

    # (ب) متون نظيفة — أسئلة عن نص حديث
    matns = db.scalars(
        select(PageElement.text_normalized)
        .where(PageElement.element_type == "matn")
        .where(PageElement.text_normalized.isnot(None))
        .order_by(func.random())
        .limit(limit * 6)
    ).all()
    added = 0
    for m in matns:
        if not _clean_enough(m or ""):
            continue
        phrase = _distinctive_phrase(m, n=5)
        if len(phrase.split()) >= 4:
            out.append((phrase, "hadith"))
            added += 1
        if added >= limit // 2:
            break

    # (ج) أسماء رواة من الأسانيد، مرشَّحة بالفلتر البنيوي
    try:
        from packages.learning.entity_filter import EntityKind, classify_entity
    except ImportError:
        classify_entity = None  # type: ignore[assignment]

    if classify_entity is not None:
        sanads = db.scalars(
            select(PageElement.text_normalized)
            .where(PageElement.element_type == "sanad")
            .where(PageElement.text_normalized.isnot(None))
            .order_by(func.random())
            .limit(limit * 4)
        ).all()
        names: set[str] = set()
        for line in sanads:
            tokens = (line or "").split()
            for i, tok in enumerate(tokens):
                if tok in {"بن", "ابن"} and 0 < i < len(tokens) - 1:
                    cand = " ".join(tokens[max(0, i - 1) : i + 2])
                    v = classify_entity(cand)
                    if v.accepted and v.kind is EntityKind.PERSON:
                        names.add(v.cleaned_label or cand)
        for name in sorted(names)[: limit // 4]:
            out.append((name, "entity"))

    seen: set[str] = set()
    unique: list[tuple[str, str]] = []
    for q, kind in out:
        key = q.strip()
        if key and key not in seen:
            seen.add(key)
            unique.append((key, kind))
    random.shuffle(unique)
    return unique[:limit]


# ---------------------------------------------------------------------------
# جلسة التحكيم
# ---------------------------------------------------------------------------

def judge_query(engine, query: str, intent: str, top_n: int = 10) -> dict | None:
    payload = engine.search(query, limit=top_n)
    results = payload.get("results", [])[:top_n]

    if not results:
        print("  لا نتائج. تُسجَّل كسؤال بلا إجابة صحيحة معروفة.")
        return {
            "id": "",
            "query": query,
            "intent": intent,
            "relevant_element_ids": [],
            "must_contain": [],
            "must_not_contain": [],
            "note": "لم يرجّع النظام نتائج",
        }

    print(f"\n{'='*74}")
    print(f"  السؤال: {query}    [{intent}]")
    print("=" * 74)
    for i, r in enumerate(results, start=1):
        text = (r.get("search_text") or r.get("best_text") or "")[:96]
        page = r.get("page_number")
        kind = r.get("best_element_type") or r.get("element_type") or "-"
        print(f"  {i:>2}. [ص{page} {kind}] {text}")

    print()
    print("  اكتب أرقام النتائج الصحيحة مفصولة بمسافة.")
    print("  Enter وحدها = لا شيء منها صحيح  |  s = تخطَّ  |  q = إنهاء وحفظ")
    answer = input("  > ").strip().lower()

    if answer == "q":
        return "QUIT"  # type: ignore[return-value]
    if answer == "s":
        return None

    chosen: list[str] = []
    for token in answer.split():
        if token.isdigit():
            idx = int(token) - 1
            if 0 <= idx < len(results):
                eid = results[idx].get("element_id")
                if eid:
                    chosen.append(str(eid))

    note = input("  ملاحظة (اختياري): ").strip()

    return {
        "id": "",
        "query": query,
        "intent": intent,
        "relevant_element_ids": chosen,
        "must_contain": [],
        "must_not_contain": [],
        "note": note or f"حُكم عليه يدوياً، {len(chosen)} نتيجة صحيحة من {len(results)}",
    }


def print_status(rows: list[dict]) -> None:
    judged = [r for r in rows if r.get("relevant_element_ids")]
    print(f"\n  أسئلة مسجَّلة   : {len(rows)}")
    print(f"  محكَّمة بمعرّفات : {len(judged)}")
    print(f"  بلا تحكيم      : {len(rows) - len(judged)}")

    by_intent: dict[str, int] = {}
    for r in rows:
        by_intent[r.get("intent", "?")] = by_intent.get(r.get("intent", "?"), 0) + 1
    if by_intent:
        print("\n  التوزيع على أنواع النية:")
        for kind, n in sorted(by_intent.items(), key=lambda x: -x[1]):
            print(f"    {kind:16} {n}")

    print()
    if len(judged) < 20:
        print(f"  ينقصك {20 - len(judged)} سؤالاً محكَّماً ليصير القياس ذا معنى.")
        print("  دون ذلك تبقى Recall@k و MRR معطَّلة، والقياس يعتمد على")
        print("  must_contain_rate وحده — وقد خدعنا مرتين.")
    else:
        print("  المجموعة كافية لقياس Recall@k و MRR.")
        print("  شغّل: python scripts/eval_search.py --save _eval/golden_baseline.json")


def main() -> int:
    ap = argparse.ArgumentParser(description="بناء المجموعة الذهبية")
    ap.add_argument("--suggest", type=int, default=0,
                    help="اقترح N سؤالاً من متنك وابدأ التحكيم")
    ap.add_argument("--query", type=str, help="حكّم على سؤال واحد")
    ap.add_argument("--intent", type=str, default="general", choices=INTENTS)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    sys.path.insert(0, str(REPO_ROOT))
    rows = load_golden()

    if args.status:
        print_status(rows)
        return 0

    from packages.database.session import SessionLocal
    from packages.search.engine import SearchEngine

    db = SessionLocal()
    try:
        engine = SearchEngine(db)
        existing = {r.get("query") for r in rows}

        if args.query:
            todo = [(args.query, args.intent)]
        else:
            n = args.suggest or 20
            todo = [(q, k) for q, k in suggest_from_corpus(db, n) if q not in existing]
            if not todo:
                print("  كل الأسئلة المقترحة مسجَّلة. استعمل --query لإضافة سؤالك.")
                print_status(rows)
                return 0
            print(f"\n  {len(todo)} سؤالاً مقترحاً من متنك.")
            print("  انظر النتائج واحكم عليها. الحكم لك وحدك.\n")

        added = 0
        for query, intent in todo:
            verdict = judge_query(engine, query, intent, top_n=args.top)
            if verdict == "QUIT":
                break
            if verdict is None:
                continue
            verdict["id"] = next_id(rows)
            rows.append(verdict)
            added += 1
            save_golden(rows)  # حفظ بعد كل حكم: لا يضيع العمل

        print(f"\n  أُضيف {added} سؤالاً. المجموع {len(rows)}.")
        print(f"  حُفظ في: {GOLDEN_PATH}")
        print_status(rows)
        return 0

    except KeyboardInterrupt:
        save_golden(rows)
        print("\n  أُوقف. ما حُكم عليه محفوظ.")
        return 0
    except Exception as exc:
        print(f"فشل: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
