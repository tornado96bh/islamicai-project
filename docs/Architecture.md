# Architecture

## Core Rules
- Source of truth is PostgreSQL.
- Build pipeline and query pipeline are separated.
- Every decision must be explainable.
- No duplicate storage for identical editions.
- All unique ideas are preserved, repeated ideas are merged.

## Main Pipelines
### Build
Ingestion -> OCR -> Layout -> Normalization -> Extraction -> Graph/Index -> Storage

### Query
Question Understanding -> Retrieval -> Evidence Bundle -> Verification -> Answer Generation -> Self-Critique
