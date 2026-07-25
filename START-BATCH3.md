# الدفعة الثالثة — تماسك المقياس، العقود، جودة الفهرس

## التشغيل

```powershell
cd E:\IslamicAI_v3_full
& .\.venv\Scripts\Activate.ps1
.\tools\30-install-batch3.ps1 -DryRun
.\tools\30-install-batch3.ps1
```

---

## العطب الذي كشفه القياس

نتيجتك الأولى لاستعلام «الله»:

```json
"score": 1.288811,
"score_explain": { "rrf_base": 0.016129, "signals": 0.018,
                   "exact_raw": 0.02, "fragment_penalty": 0 }
```

المجموع 0.054، والمعروض 1.289. الفرق **1.235** يضيفه `reranker.py`
بعد الترتيب دون أن يظهر في أي مكان.

| المصدر | القيمة | النسبة |
|---|---|---|
| RRF | 0.016 | 1.3% |
| إشارات + مطابقة | 0.038 | 3% |
| **reranker** | **1.235** | **96%** |

فترتيبك الفعلي كان يحكمه `EmbeddingBuilder` — hashing بـ256 بُعداً
تشابهه بين «النبي محمد» و«الرسول الكريم» يساوي **صفراً**.

وأخطر: `filters.py` يقارن بعتبات مطلقة (0.15 / 1.25 / 1.55) معايَرة
على المقياس القديم. نتائجك كانت تنجو **بالصدفة** — الـ boost يرفعها
فوق 1.25 بفارق ضئيل. أي تغيير في وزنه كان سيمسحها كلها.

## الإصلاح

| الملف | التغيير |
|---|---|
| `reranker.py` | مساهمته في حجم RRF (0.010–0.022 لا 1.235)، ووزن الـ embeddings **صفر** حتى يُستبدل بنموذج حقيقي |
| `filters.py` | عتبات **نسبية** إلى أعلى درجة في نفس الاستعلام، تصمد مع أي مقياس مستقبلي |
| كلاهما | كل مساهمة تُسجَّل في `score_explain` — لا تعديل صامت |

إدخال ضجيج بوزن أصغر أسوأ من عدم إدخاله. لهذا الوزن صفر لا 0.01.

---

## العقود (P2)

`packages/schemas/` صارت المصدر الوحيد، **21 عقداً** بدل 6:

`Book` · `Edition` · `Volume` · `Page` · `PageElement` · `BoundingBox` ·
`TextSpan` · `ElementType` · `TextQuality` · `Narrator` · `IsnadLink` ·
`Isnad` · `Hadith` · `Commentary` · `Footnote` · `Source` ·
`RetrievalHit` · `EvidenceBundle` · `VerificationResult` · `FinalAnswer`

عقود تفرض قواعدك:
- `FinalAnswer` **يرفض** إجابة بلا مصدر، ويرفض اعتذاراً بلا سبب
- `PageElement` يفصل `text_raw` / `text_normalized` / `text_display`
- `TextSpan` يربط كل اقتباس بموضعه على الصفحة
- `extra="forbid"` — أي حقل غير معرّف يُرفض

10 اختبارات ✅

---

## جودة الفهرس (P1)

`clean_index_quality.py` يستبعد الفارغ والضجيج والمكرر بضبط
`text_normalized = NULL`. و`fts.py`/`fuzzy.py` يشترطان
`IS NOT NULL` فيخرج تلقائياً.

**لا يُحذف صف ولا يُمس `text_raw`.** التراجع بإعادة تشغيل الملء.

---

## ما لم تشمله هذه الدفعة — بصراحة

| البند | التقدير الواقعي |
|---|---|
| P3 — Layout / OCR / Isnad / Narrator كمحركات | أشهر، ويحتاج بيانات تدريب موسومة منك |
| P3 — Evidence / Verifier / FinalAnswer pipeline | أسابيع، والعقود جاهزة الآن كأساس |
| P4 — Worker / Scheduler / Event bus | أسابيع |
| BGE-M3 بدل الـ hashing | أيام، **لكن بعد** توسيع المجموعة الذهبية |

الترتيب المقترح بعد هذه الدفعة:
1. وسّع `datasets/golden` إلى 30 سؤالاً محكّماً
2. أعد بناء المعجم — الحالي مبني على نص معطوب قبل تصحيح OCR
3. استبدل الـ embeddings بنموذج حقيقي وقِس
4. Layout Engine — بدونه يبقى `element_type="text"` لكل شيء
5. Evidence + Verifier

**لا أستطيع بناء 40 محركاً في دفعة، ولن أدّعي ذلك.**
