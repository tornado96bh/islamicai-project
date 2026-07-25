from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent

def write(path: str, text: str):
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text.strip() + "\n", encoding="utf-8")
    print("[OK]", path)

def sprint2():

    write(
        "packages/database/models/publisher.py",
        """
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from packages.database.base import BaseModel

class Publisher(BaseModel):
    __tablename__ = "publishers"

    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
"""
    )

    write(
        "packages/database/models/author.py",
        """
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from packages.database.base import BaseModel

class Author(BaseModel):
    __tablename__ = "authors"

    full_name: Mapped[str] = mapped_column(String(255), index=True)
"""
    )

    write(
        "packages/database/models/book.py",
        """
from sqlalchemy import ForeignKey,String,Text
from sqlalchemy.orm import Mapped,mapped_column

from packages.database.base import BaseModel

class Book(BaseModel):

    __tablename__="books"

    title_ar:Mapped[str]=mapped_column(String(500),index=True)
    title_en:Mapped[str]=mapped_column(String(500),default="")
    short_title:Mapped[str]=mapped_column(String(255),default="")
    description:Mapped[str]=mapped_column(Text(),default="")

    author_id= mapped_column(ForeignKey("authors.id"))
    publisher_id= mapped_column(ForeignKey("publishers.id"))
"""
    )

    write(
        "packages/database/models/__init__.py",
        """
from .author import Author
from .publisher import Publisher
from .book import Book
"""
    )

    print()
    print("="*60)
    print("SPRINT 2 COMPLETED")
    print("="*60)

if __name__=="__main__":

    if len(sys.argv)<2:
        print("Usage: python scripts/build.py sprint2")
        raise SystemExit

    cmd=sys.argv[1].lower()

    if cmd=="sprint2":
        sprint2()
    else:
        print("Unknown command")
