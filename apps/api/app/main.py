from fastapi import FastAPI
from apps.api.app.routers.books import router as books_router
from apps.api.app.routers.health import router as health_router
from apps.api.app.routers.search import router as search_router

app = FastAPI(title="IslamicAI", version="3.0.0")

app.include_router(health_router)
app.include_router(books_router, prefix="/books", tags=["books"])
app.include_router(search_router, prefix="/search", tags=["search"])

# خط الأنابيب الموثَّق. يُسجَّل بجانب /search لا بدلاً منه: البحث
# الخام يبقى متاحاً لمن يريده، والإجابة الموثَّقة تُضاف بمسار مستقل.
try:
    from apps.api.app.routers.pipeline import router as pipeline_router

    app.include_router(pipeline_router, prefix="/pipeline", tags=["pipeline"])
except ImportError:  # pragma: no cover - engines غير مثبَّتة
    pass
