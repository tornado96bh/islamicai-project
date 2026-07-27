"""
تجهيز نموذج التمثيل الدلالي وقياسه قبل اعتماده.

لا تعتمد نموذجاً لأن اسمه مشهور. هذا السكربت يحمّله ثم **يختبره على
أزواج عربية معروفة الدلالة**، فترى بعينك هل يفهم متنك أم لا.

    python scripts/setup_embeddings.py --check
    python scripts/setup_embeddings.py --install
    python scripts/setup_embeddings.py --test
    python scripts/setup_embeddings.py --test --model intfloat/multilingual-e5-base
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# أزواج تكشف الفهم الدلالي. الزوجان الأخيران يجب أن يتباعدا،
# وإلا فالنموذج يقيس التشابه الحرفي لا المعنى.
PROBE_PAIRS = [
    ("النبي محمد", "الرسول الكريم", "مرادف دلالي", True),
    ("الوضوء", "الطهارة", "مرتبط فقهياً", True),
    ("قال رسول الله", "حدثنا النبي صلى الله عليه وآله", "صيغتا رواية", True),
    ("الماء يطهر ولا يطهر", "الماء طهور لا ينجسه شيء", "معنى متقارب", True),
    ("زرارة بن أعين", "زر القميص", "لفظ متشابه ومعنى متباعد", False),
    ("كتاب الطهارة", "أحكام البيع والشراء", "بابان مختلفان", False),
]


def check_installed() -> bool:
    try:
        import sentence_transformers  # noqa: F401

        print("  sentence-transformers : مثبَّت")
        return True
    except ImportError:
        print("  sentence-transformers : غير مثبَّت")
        return False


def install() -> int:
    print("  تثبيت sentence-transformers (قد يستغرق دقائق)...")
    return subprocess.run(
        [sys.executable, "-m", "pip", "install", "sentence-transformers"], check=False
    ).returncode


def run_test(model_name: str | None) -> int:
    from packages.learning.embeddings_v2 import DEFAULT_MODEL, build_embedder

    name = model_name or DEFAULT_MODEL
    print(f"  النموذج : {name}")
    print("  التحميل الأول قد يستغرق دقائق ويحتاج إنترنت.")
    print("-" * 66)

    t0 = time.time()
    embedder = build_embedder(name, allow_fallback=False)
    load_s = time.time() - t0

    print(f"  الأبعاد     : {embedder.dimension}")
    print(f"  زمن التحميل : {load_s:.1f} ثانية")
    print(f"  دلالي فعلاً : {getattr(embedder, 'is_semantic', False)}")
    print("-" * 66)

    passed = 0
    for a, b, label, close in PROBE_PAIRS:
        sim = embedder.similarity(
            embedder.vectorize_text(a), embedder.vectorize_text(b)
        )
        ok = (sim >= 0.55) if close else (sim < 0.55)
        passed += ok
        want = "متقارب" if close else "متباعد"
        print(f"  {sim:>7.3f}  {want:>8}  [{'OK' if ok else '!!'}] {label}")
        print(f"           {a}  |  {b}")

    print("-" * 66)
    print(f"  النتيجة : {passed}/{len(PROBE_PAIRS)}")

    t0 = time.time()
    embedder.vectorize_many(["نص تجريبي للقياس"] * 64)
    print(f"  السرعة  : {64 / max(time.time() - t0, 0.001):,.0f} نص/ثانية\n")

    if passed >= 5:
        print("  النموذج يفهم العربية. اعتمده ثم أعد التدريب:")
        print("    python scripts/train_learning.py")
    elif passed >= 3:
        print("  فهم جزئي. جرّب: --model intfloat/multilingual-e5-base")
    else:
        print("  لا يفهم متنك. لا تعتمده. جرّب: --model BAAI/bge-m3")

    return 0 if passed >= 3 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="تجهيز نموذج التمثيل الدلالي")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--model", type=str)
    args = ap.parse_args()

    if not (args.check or args.install or args.test):
        args.check = True

    if args.install:
        code = install()
        if code:
            print("  فشل التثبيت.")
            return code
        print("  تم. الآن: python scripts/setup_embeddings.py --test")
        return 0

    if args.test:
        if not check_installed():
            print("\n  ثبّت أولاً: python scripts/setup_embeddings.py --install")
            return 1
        try:
            return run_test(args.model)
        except Exception as exc:
            print(f"\n  فشل: {exc}", file=sys.stderr)
            return 1

    ok = check_installed()
    if not ok:
        print("\n  للتثبيت: python scripts/setup_embeddings.py --install")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
