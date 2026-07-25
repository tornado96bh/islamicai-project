from __future__ import annotations

import unicodedata


def normalize_for_search(text: str | None) -> str:
    if not text:
        return ""

    # تحويل Arabic Presentation Forms إلى Unicode القياسي
    text = unicodedata.normalize("NFKC", text)

    # توحيد نهاية الأسطر
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # إزالة المسافات المكررة فقط
    text = " ".join(text.split())

    return text
