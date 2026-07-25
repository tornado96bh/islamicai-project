"""
معطَّل عمداً — لا تشغّله.

كان هذا السكربت ينفّذ:
    element.text = normalize_for_search(element.text)
    db.commit()

أي أنه يكتب فوق النص الأصلي في مصدر الحقيقة بلا نسخة، ويؤدي إلى:

  1. فقدان التشكيل والهمزات الأصلية إلى الأبد، والاستشهاد العلمي
     يتطلب نقل النص كما هو في الطبعة.
  2. كسر ربط النص بموضعه على الصفحة (bbox)، لأن التطبيع يغيّر
     أطوال السلاسل ولا خريطة إزاحة تعوّض ذلك.
  3. مخالفة الماستر §2 (PostgreSQL مصدر الحقيقة) وعقد PageElement
     الذي يفصل text_raw عن text_normalized.

البديل الصحيح:
    python scripts/backfill_normalized_text.py
وهو يملأ عمود text_normalized الجديد دون المساس بالنص الأصلي.
"""

import sys

sys.exit(
    "DISABLED: this script destroys original text. "
    "Use scripts/backfill_normalized_text.py instead."
)
