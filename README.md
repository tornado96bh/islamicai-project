# IslamicAI Search Final Pack

This pack replaces the search layer with a hybrid retrieval stack:

- Arabic canonicalization with OCR-noise cleanup that preserves meaning.
- Query intent detection.
- In-memory TTL cache.
- Stopword / generic-term filtering.
- Full-text search on PostgreSQL.
- Trigram fuzzy search.
- Semantic page retrieval using Qdrant with local fallback.
- Page-level result fusion and reranking.
- Training helper to refresh embeddings and Qdrant.

## Files

- `packages/learning/dictionary.py`
- `packages/learning/canonicalizer.py`
- `packages/search/*`
- `packages/repositories/search.py`
- `packages/services/search.py`
- `apps/api/app/routers/search.py`
- `packages/ingestion/manager.py`
- `scripts/train_learning.py`
- `scripts/reindex_search.py`
- `apply_upgrade.ps1`

## Apply

1. Extract this zip into the project root.
2. Run `.\apply_upgrade.ps1`.
3. Run `python .\scripts\train_learning.py`.
4. Restart the API:
   `uvicorn apps.api.app.main:app --reload`

## Notes

- The pack keeps the original text untouched for display and only canonicalizes the search form.
- It is designed to reduce OCR noise like `االله` / `عبد االله` while preserving the original text in results.
- The current dataset still contains OCR artifacts, so these search-time canonicalization rules are important.
