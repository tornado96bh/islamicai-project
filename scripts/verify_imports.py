"""
فحص سلامة الاستيراد — حارس ضد عطب متكرر.

سبب وجوده
---------
سُلّمت حزمة تحوي ملفات `__init__.py` **فارغة** كعلامات حزم، فمحا
مثبِّتُها ملفاتِ الاستيراد الكسول الحقيقية، فانهار الخادم بـ

    ImportError: cannot import name 'BookImportResult'

العطب صامت: الملف الفارغ صحيح نحوياً، ولا يظهر إلا عند الإقلاع.

هذا السكربت يفحص كل ما يستورده المشروع فعلاً، ويُرجع رمز خروج غير
صفري عند أي فشل — فيصلح لبوابة قبل النشر.

    python scripts/verify_imports.py
    python scripts/verify_imports.py --strict   # يفشل حتى لو نقصت تبعية
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# ما يستورده المشروع فعلاً، بحسب ما تحتاجه الراوترات والسكربتات
REQUIRED = [
    ("packages.ingestion", ["BookImportResult", "IngestionManager",
                            "PDFParser", "BookImportService", "PDFBookImporter"]),
    ("packages.search", ["SearchEngine", "RankingEngine", "FullTextSearcher",
                         "FuzzySearcher", "SemanticSearcher", "IntentDetector"]),
    ("packages.learning", ["LearningTrainer", "EntityLearner",
                           "normalize_surface_text", "search_form_text"]),
    ("packages.database.session", ["SessionLocal", "get_db"]),
]

# محركات اختيارية: غيابها ينبّه ولا يُفشل
OPTIONAL = [
    ("engines.evidence.bundle", ["EvidenceBuilder"]),
    ("engines.evidence.verifier", ["Verifier", "compose"]),
    ("engines.narrator.gazetteer", ["NarratorGazetteer"]),
    ("engines.planner.planner", ["Planner"]),
    ("engines.memory.memory", ["MemoryEngine"]),
    ("engines.pipeline.orchestrator", ["Pipeline"]),
    ("engines.report.builder", ["ReportBuilder"]),
    ("packages.governance.audit", ["AuditLog", "Role"]),
]

# ملفات __init__ التي **يجب** ألا تكون فارغة
MUST_NOT_BE_EMPTY = [
    "packages/ingestion/__init__.py",
    "packages/search/__init__.py",
    "packages/learning/__init__.py",
]


def check_empty_inits() -> list[str]:
    """
    الملف الفارغ هنا عطب صامت: صحيح نحوياً، قاتل عند الإقلاع.
    """
    bad = []
    for rel in MUST_NOT_BE_EMPTY:
        p = REPO_ROOT / rel
        if not p.exists():
            bad.append(f"{rel}: مفقود")
        elif p.stat().st_size < 50:
            bad.append(f"{rel}: فارغ أو شبه فارغ ({p.stat().st_size} بايت)")
    return bad


def check_group(group, label: str, fatal: bool) -> tuple[int, int, list[str]]:
    ok = failed = 0
    problems: list[str] = []
    print(f"\n{label}")
    print("-" * 62)
    for module_name, names in group:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            failed += len(names)
            msg = f"{module_name}: {type(exc).__name__}: {exc}"
            problems.append(msg)
            print(f"  [!] {module_name}")
            print(f"      {str(exc)[:110]}")
            continue

        # hasattr لا يبتلع ImportError، وهو ما يرفعه الاستيراد الكسول
        # عند نقص تبعية. فنمسك كل استثناء لنفرّق بين "الاسم مفقود"
        # و"تبعية ناقصة" — والثاني ليس عطباً في الكود.
        missing: list[str] = []
        dependency_errors: list[str] = []
        for n in names:
            try:
                getattr(module, n)
            except ImportError as exc:
                dependency_errors.append(f"{n}: {str(exc)[:80]}")
            except AttributeError:
                missing.append(n)

        if dependency_errors:
            failed += len(dependency_errors)
            problems.append(f"{module_name}: تبعيات ناقصة")
            print(f"  [!] {module_name} — تبعية ناقصة")
            for d in dependency_errors[:2]:
                print(f"      {d}")
            continue

        if missing:
            failed += len(missing)
            problems.append(f"{module_name}: ينقصه {', '.join(missing)}")
            print(f"  [!] {module_name} — ينقصه: {', '.join(missing)}")
        else:
            ok += len(names)
            print(f"  [ok] {module_name} ({len(names)} اسماً)")
    return ok, failed, problems


def main() -> int:
    ap = argparse.ArgumentParser(description="فحص سلامة الاستيراد")
    ap.add_argument("--strict", action="store_true",
                    help="يفشل حتى على المحركات الاختيارية")
    args = ap.parse_args()

    print("فحص سلامة الاستيراد")
    print("=" * 62)

    empty = check_empty_inits()
    if empty:
        print("\nملفات __init__ معطوبة:")
        for e in empty:
            print(f"  [!] {e}")
        print("\n  هذا هو العطب الذي أسقط الخادم سابقاً: ملف فارغ يمحو")
        print("  الاستيراد الكسول، فتفشل الراوترات عند الإقلاع.")
        return 1
    print("\n[ok] ملفات __init__ سليمة")

    ok1, bad1, p1 = check_group(REQUIRED, "الاستيرادات الإلزامية", True)
    ok2, bad2, p2 = check_group(OPTIONAL, "المحركات (اختيارية)", False)

    print("\n" + "=" * 62)
    print(f"  إلزامية : {ok1} ناجحة، {bad1} فاشلة")
    print(f"  محركات  : {ok2} ناجحة، {bad2} فاشلة")

    if bad1:
        print("\n  فشل إلزامي — الخادم لن يقلع:")
        for p in p1:
            print(f"    - {p[:100]}")
        return 1

    if bad2:
        print("\n  المحركات غير متاحة. مسارات /pipeline لن تعمل.")
        print("  الأرجح أن الحزمة تحتاج: pip install -e .")
        for p in p2[:3]:
            print(f"    - {p[:100]}")
        return 1 if args.strict else 0

    print("\n  كل شيء سليم.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
