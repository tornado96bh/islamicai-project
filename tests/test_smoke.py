def test_smoke_imports():
    from packages.config.settings import settings
    from packages.database.base import Base
    from packages.repositories import BookRepository
    from packages.services import BookService
    from packages.ingestion import IngestionManager
    assert settings.database_url
    assert Base.metadata.tables
    assert BookRepository is not None
    assert BookService is not None
    assert IngestionManager is not None
