from fastapi import FastAPI
from apps.api.app.routers.books import router as books_router
from apps.api.app.routers.health import router as health_router
from apps.api.app.routers.search import router as search_router

app = FastAPI(title="IslamicAI", version="3.0.0")

app.include_router(health_router)
app.include_router(books_router, prefix="/books", tags=["books"])
app.include_router(search_router, prefix="/search", tags=["search"])
