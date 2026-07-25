"""
ينشئ المجلدات التشغيلية الناقصة التي رصدها production_audit.

عالج تحذيرات: storage / logs / uploads مفقودة.
آمن للتكرار: لا يمس ما هو موجود.
"""

from __future__ import annotations

from pathlib import Path

REQUIRED = [
    "storage",
    "storage/learning",
    "storage/exports",
    "logs",
    "uploads",
    "data/tmp",
    "data/cache",
    "_eval",
]


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    created = 0
    for rel in REQUIRED:
        p = root / rel
        if p.exists():
            print(f"  موجود : {rel}")
            continue
        p.mkdir(parents=True, exist_ok=True)
        (p / ".gitkeep").write_text("", encoding="utf-8")
        print(f"  أُنشئ  : {rel}")
        created += 1
    print(f"\nأُنشئ {created} مجلداً من أصل {len(REQUIRED)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
