"""فصل text_raw/text_normalized وإصلاح فهارس البحث

الغرض:
  1. فصل النص الأصلي عن الصيغة البحثية، تنفيذاً لعقد PageElement
     الذي يوجب text_raw و text_normalized (والذي كان مهجوراً).
  2. إصلاح فهرس FTS: الفهرس القديم كان على
        to_tsvector('simple', coalesce(text,''))
     بينما الاستعلام في packages/search/fts.py يستخدم
        to_tsvector('simple', translate(coalesce(text,''), <حركات>, ''))
     وPostgreSQL يطابق فهارس التعابير حرفياً، فلم يكن يُستعمل أبداً
     وكان كل بحث مسحاً تسلسلياً للجدول.
  3. إضافة فهرس trigram على page_elements — لم يكن موجوداً إطلاقاً،
     رغم أن FuzzySearcher يعتمد على similarity().
  4. إضافة أعمدة الثقة والإصدار المطلوبة في الماستر §2 و §6.

بعد هذه الهجرة شغّل:
    python scripts/backfill_normalized_text.py

Revision ID: a1b2c3d4e5f6
Revises: 08af36dbc5dc
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "08af36dbc5dc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- الامتدادات ------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # -- الأعمدة الجديدة -------------------------------------------
    op.add_column("page_elements", sa.Column("text_raw", sa.Text(), nullable=True))
    op.add_column("page_elements", sa.Column("text_normalized", sa.Text(), nullable=True))
    op.add_column(
        "page_elements",
        sa.Column("canonicalizer_version", sa.String(length=20), nullable=True),
    )
    op.add_column("page_elements", sa.Column("ocr_confidence", sa.Float(), nullable=True))
    op.add_column("page_elements", sa.Column("layout_confidence", sa.Float(), nullable=True))

    # -- حفظ النص الأصلي قبل أن يمسّه أي تطبيع ----------------------
    # الحالي في عمود text قد يكون تعرّض لـ normalize_existing_text.py
    # سابقاً، لكنه أفضل ما لدينا كنقطة انطلاق.
    op.execute("UPDATE page_elements SET text_raw = text WHERE text_raw IS NULL")

    # -- إزالة الفهرس القديم غير المستخدَم -------------------------
    op.execute("DROP INDEX IF EXISTS ix_page_elements_text_fts")

    # -- فهرس FTS على العمود المطبّع مباشرة ------------------------
    # الآن التعبير في الفهرس يطابق تماماً ما سيستعمله الاستعلام.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_page_elements_norm_fts
        ON page_elements
        USING GIN (to_tsvector('simple', coalesce(text_normalized, '')))
        """
    )

    # -- فهرس trigram للبحث التقريبي --------------------------------
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_page_elements_norm_trgm
        ON page_elements
        USING GIN (text_normalized gin_trgm_ops)
        """
    )

    # -- فهرس مركب لترتيب النتائج داخل الصفحة -----------------------
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_page_elements_page_order
        ON page_elements (page_id, element_order)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_page_elements_page_order")
    op.execute("DROP INDEX IF EXISTS ix_page_elements_norm_trgm")
    op.execute("DROP INDEX IF EXISTS ix_page_elements_norm_fts")

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_page_elements_text_fts
        ON page_elements
        USING GIN (to_tsvector('simple', coalesce(text, '')))
        """
    )

    op.drop_column("page_elements", "layout_confidence")
    op.drop_column("page_elements", "ocr_confidence")
    op.drop_column("page_elements", "canonicalizer_version")
    op.drop_column("page_elements", "text_normalized")
    op.drop_column("page_elements", "text_raw")
