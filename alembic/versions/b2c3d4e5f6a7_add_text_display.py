"""إضافة text_display: الصيغة المقروءة بكل الحركات

المشكلة التي تحلها
------------------
كان عندنا صيغتان فقط:

    text_raw        الأصل، بحركاته وهمزاته — لكنه ممدّد ومفكّك
                    "قــــــال رســــــول االله ) صــــــلى االله عليــــــه"
    text_normalized الصيغة البحثية — نظيفة لكنها **بلا حركات ولا همزات**
                    "قال رسول الله ) صلي الله عليه"

فالمستخدم إما يرى نصاً معطوباً أو نصاً منزوع الحركات. والصيغة الثالثة
المطلوبة كانت تُحسب في المسار ثم تُرمى: ناتج تصحيح OCR **قبل** التطبيع.

    text_display    "قال رسول اللّه ) صلى اللّه عليه"
                    بلا تمديد، بلا تفكّك، **بكل الحركات والهمزات والنقاط**

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("page_elements", sa.Column("text_display", sa.Text(), nullable=True))
    op.add_column(
        "page_elements",
        sa.Column("hadith_number", sa.String(length=40), nullable=True),
    )
    op.add_column("page_elements", sa.Column("isnad_text", sa.Text(), nullable=True))
    op.add_column("page_elements", sa.Column("matn_text", sa.Text(), nullable=True))
    op.add_column(
        "page_elements", sa.Column("split_confidence", sa.Float(), nullable=True)
    )

    # البداية: نسخة من الأصل حتى يملأها السكربت
    op.execute("UPDATE page_elements SET text_display = text_raw WHERE text_display IS NULL")

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_page_elements_hadith_number
        ON page_elements (hadith_number)
        WHERE hadith_number IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_page_elements_hadith_number")
    op.drop_column("page_elements", "split_confidence")
    op.drop_column("page_elements", "matn_text")
    op.drop_column("page_elements", "isnad_text")
    op.drop_column("page_elements", "hadith_number")
    op.drop_column("page_elements", "text_display")
