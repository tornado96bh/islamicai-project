"""
Eval Harness — قياس جودة البحث ومنع الانحدار الصامت.

سبب وجود هذا الملف: تحسّن المطبّع فتدهور الترتيب، ولم يكتشف أحد ذلك
حتى ظهر في الاستخدام. لا يوجد رقم يمكن مقارنته قبل وبعد.

المقاييس:
  Recall@k   نسبة النتائج الصحيحة الظاهرة في أعلى k
  MRR        متوسط مقلوب رتبة أول نتيجة صحيحة
  P@1        هل النتيجة الأولى صحيحة
  frag_rate  نسبة الشظايا القصيرة في أعلى 10 — مؤشر انهيار الترتيب
  latency    زمن الاستجابة بالمللي ثانية

الاستخدام:
    python scripts/eval_search.py --save baseline.json
    # ... طبّق تغييراً ...
    python scripts/eval_search.py --compare baseline.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = REPO_ROOT / "datasets" / "golden" / "queries.jsonl"

# عنصر بأقل من هذا العدد من الكلمات يُعدّ شظية
FRAGMENT_MAX_WORDS = 3


def load_golden(path: Path = GOLDEN_PATH) -> list[dict]:
    if not path.exists():
        raise SystemExit(f"لم أجد المجموعة الذهبية: {path}")
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("//"):
            rows.append(json.loads(line))
    return rows


def _norm(text: str) -> str:
    """تطبيع خفيف للمقارنة النصية في must_contain."""
    from packages.utils.arabic_canonicalizer import search_form_text

    return search_form_text(text)


def evaluate_one(case: dict, results: list[dict], k: int = 10) -> dict:
    """يقيس حالة واحدة."""
    top = results[:k]
    relevant = set(case.get("relevant_element_ids") or [])

    # --- Recall@k و MRR على المعرّفات المحكَّمة بشرياً ---
    recall = None
    mrr = 0.0
    p_at_1 = None

    if relevant:
        found = {r.get("element_id") for r in top} & relevant
        recall = len(found) / len(relevant)
        for rank, r in enumerate(top, start=1):
            if r.get("element_id") in relevant:
                mrr = 1.0 / rank
                break
        p_at_1 = 1.0 if top and top[0].get("element_id") in relevant else 0.0

    # --- فحص أخف بالكلمات حين لا يوجد تحكيم ---
    must = [_norm(w) for w in (case.get("must_contain") or [])]
    must_not = [_norm(w) for w in (case.get("must_not_contain") or [])]

    contains_hits = 0
    violations = 0
    for r in top:
        text = _norm(r.get("best_text") or r.get("text") or "")
        if must and any(w in text for w in must):
            contains_hits += 1
        if must_not and any(w in text for w in must_not):
            violations += 1

    # --- نسبة الشظايا: مؤشر انهيار الترتيب ---
    fragments = sum(
        1
        for r in top
        if len((r.get("best_text") or r.get("text") or "").split()) < FRAGMENT_MAX_WORDS
    )
    frag_rate = fragments / len(top) if top else 0.0

    return {
        "id": case["id"],
        "query": case["query"],
        "n_results": len(results),
        "recall_at_k": recall,
        "mrr": mrr if relevant else None,
        "p_at_1": p_at_1,
        "must_contain_rate": (contains_hits / len(top)) if (must and top) else None,
        "violations": violations,
        "fragment_rate": round(frag_rate, 3),
        "top1_text": (top[0].get("best_text") or top[0].get("text") or "")[:80] if top else "",
    }


def aggregate(rows: list[dict]) -> dict:
    def mean_of(key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return round(statistics.mean(vals), 4) if vals else None

    return {
        "n_queries": len(rows),
        "recall_at_k": mean_of("recall_at_k"),
        "mrr": mean_of("mrr"),
        "p_at_1": mean_of("p_at_1"),
        "must_contain_rate": mean_of("must_contain_rate"),
        "fragment_rate": mean_of("fragment_rate"),
        "total_violations": sum(r.get("violations", 0) for r in rows),
    }


def run(k: int = 10, limit: int = 20) -> dict:
    from packages.database.session import SessionLocal
    from packages.search.engine import SearchEngine

    cases = load_golden()
    db = SessionLocal()
    rows = []
    latencies = []

    try:
        engine = SearchEngine(db)
        for case in cases:
            t0 = time.perf_counter()
            payload = engine.search(case["query"], limit=limit)
            latencies.append((time.perf_counter() - t0) * 1000)
            rows.append(evaluate_one(case, payload.get("results", []), k=k))
    finally:
        db.close()

    summary = aggregate(rows)
    summary["latency_ms_p50"] = round(statistics.median(latencies), 1) if latencies else None
    summary["latency_ms_max"] = round(max(latencies), 1) if latencies else None

    return {"summary": summary, "per_query": rows}


def print_report(report: dict) -> None:
    s = report["summary"]
    print("\n" + "=" * 62)
    print("  نتيجة القياس")
    print("=" * 62)
    for label, key, fmt in [
        ("عدد الأسئلة", "n_queries", "{}"),
        ("Recall@k", "recall_at_k", "{}"),
        ("MRR", "mrr", "{}"),
        ("P@1", "p_at_1", "{}"),
        ("نسبة تضمّن الكلمة المطلوبة", "must_contain_rate", "{}"),
        ("نسبة الشظايا في أعلى 10", "fragment_rate", "{}"),
        ("مخالفات must_not_contain", "total_violations", "{}"),
        ("زمن الاستجابة الوسيط (مللي)", "latency_ms_p50", "{}"),
        ("أقصى زمن (مللي)", "latency_ms_max", "{}"),
    ]:
        val = s.get(key)
        print(f"  {label:32} {fmt.format('—' if val is None else val)}")

    print("\n  أعلى نتيجة لكل سؤال:")
    for r in report["per_query"]:
        print(f"    [{r['id']}] {r['query'][:24]:26} -> {r['top1_text'][:44]}")
    print()


LAST_RUN_PATH = REPO_ROOT / "_eval" / "last_run.json"


def save_last_run(report: dict) -> None:
    """
    يحفظ نتيجة كل تشغيل تلقائياً.

    سبب الإضافة: المقارنة بالأساس الثابت وحده أخفت انحداراً حقيقياً —
    قفز الزمن من 992 إلى 2506 مللي بينما قال التقرير "لا انحدار" لأن
    الأساس الأصلي كان 6099. الانحدار التدريجي لا يُرى إلا بمقارنة
    التشغيل بسابقه.
    """
    LAST_RUN_PATH.parent.mkdir(parents=True, exist_ok=True)
    LAST_RUN_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def compare_with_last_run(current: dict) -> None:
    """يقارن بالتشغيل السابق لكشف الانحدار التدريجي."""
    if not LAST_RUN_PATH.exists():
        return
    try:
        prev = json.loads(LAST_RUN_PATH.read_text(encoding="utf-8"))
    except Exception:
        return

    cs, ps = current["summary"], prev.get("summary", {})
    print("\n" + "=" * 62)
    print("  المقارنة مع التشغيل السابق  (كشف الانحدار التدريجي)")
    print("=" * 62)

    higher_better = ["recall_at_k", "mrr", "p_at_1", "must_contain_rate"]
    lower_better = ["fragment_rate", "total_violations", "latency_ms_p50"]
    regressed = False

    for key in higher_better + lower_better:
        a, b = ps.get(key), cs.get(key)
        if a is None or b is None:
            continue
        diff = round(b - a, 4)
        if diff == 0:
            continue
        good = (diff > 0) if key in higher_better else (diff < 0)
        if not good:
            regressed = True
        mark = "تحسّن" if good else "انحدار"
        print(f"  {key:28} {a:>10} -> {b:>10}  {diff:+}  {mark}")

    if regressed:
        print("\n  انحدار مقارنةً بالتشغيل السابق، حتى لو بدا الأساس أفضل.")
    else:
        print("\n  لا انحدار مقارنةً بالتشغيل السابق.")


def compare(current: dict, baseline_path: Path) -> int:
    base = json.loads(baseline_path.read_text(encoding="utf-8"))
    cs, bs = current["summary"], base["summary"]

    print("\n" + "=" * 62)
    print("  المقارنة مع الأساس")
    print("=" * 62)
    print(f"  {'المقياس':32} {'أساس':>10} {'الآن':>10}  الفرق")

    regressed = False
    # المقاييس التي ارتفاعها أفضل
    higher_better = ["recall_at_k", "mrr", "p_at_1", "must_contain_rate"]
    lower_better = ["fragment_rate", "total_violations", "latency_ms_p50"]

    for key in higher_better + lower_better:
        b, c = bs.get(key), cs.get(key)
        if b is None or c is None:
            continue
        diff = round(c - b, 4)
        good = (diff >= 0) if key in higher_better else (diff <= 0)
        mark = "تحسّن" if diff and good else ("انحدار" if diff else "بلا تغيير")
        if diff and not good:
            regressed = True
        print(f"  {key:32} {b:>10} {c:>10}  {diff:+}  {mark}")

    print()
    if regressed:
        print("  انحدار مرصود. لا تعتمد هذا التغيير قبل تفسيره.")
        return 1
    print("  لا انحدار.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="قياس جودة البحث")
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--save", type=str, help="احفظ النتيجة كأساس")
    ap.add_argument("--compare", type=str, help="قارن بأساس محفوظ")
    args = ap.parse_args()

    sys.path.insert(0, str(REPO_ROOT))

    try:
        report = run(k=args.k, limit=args.limit)
    except Exception as exc:
        print(f"فشل التشغيل: {exc}", file=sys.stderr)
        print("تأكد أن قاعدة البيانات تعمل وأن .env صحيح.", file=sys.stderr)
        return 2

    print_report(report)
    compare_with_last_run(report)
    save_last_run(report)

    if args.save:
        Path(args.save).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  حُفظ الأساس: {args.save}\n")

    if args.compare:
        p = Path(args.compare)
        if not p.exists():
            print(f"ملف الأساس غير موجود: {p}", file=sys.stderr)
            return 2
        return compare(report, p)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
