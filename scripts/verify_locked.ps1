$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

python -c "import fastapi,sqlalchemy,alembic,torch,transformers,tokenizers,sentence_transformers,qdrant_client,neo4j,fitz,cv2,pytest; print('CORE IMPORTS OK')"

python -c "from packages.database.base import Base; import packages.database.models; print('TABLES:', len(Base.metadata.tables)); print(sorted(Base.metadata.tables.keys()))"

if (Test-Path ".\tests\Wasael-Shia-part01.pdf") {
    python -c "from pathlib import Path; from packages.ingestion.parsers.pdf import PDFParser; r=PDFParser().parse(Path(r'.\tests\Wasael-Shia-part01.pdf')); print('PAGES:', r['page_count']); print('META_TITLE:', r['metadata'].get('title')); print('PAGE1_LEN:', len(r['pages'][0]['text']))"
}

python -m pytest -q
