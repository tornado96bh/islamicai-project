# IslamicAI Master Specification (Locked Scope)

This document freezes the agreed scope for the project. Repeated ideas are merged into single categories; unique ideas are preserved.

## 1) Core mission
Build a long-lived Islamic knowledge platform that:
- ingests books and scholarly material,
- understands page structure,
- extracts entities and chains,
- builds evidence packages,
- verifies claims,
- answers with traceable sources,
- learns safely over time,
- stays portable on the external drive.

## 2) Hard rules
- Build pipeline and query pipeline are separate.
- PostgreSQL is the source of truth.
- MinIO stores large files and originals.
- Vector search and graph layers are derived and versioned.
- Every decision must be explainable.
- No silent deletion of referenced data.
- No automatic religious/legal verdicts from the system.
- No hallucinated sources.
- No duplicate storage for identical editions.
- All unique ideas are preserved.

## 3) Fixed architecture
Monorepo with modular architecture:
- apps/
- packages/
- engines/
- datasets/
- docs/
- infra/
- tests/
- data/

## 4) Agreed engines
### Build pipeline engines
- Ingest
- OCR
- Layout
- Normalization
- Isnad parsing
- Narrator resolution
- Entity extraction
- Page structure
- Indexing
- Graph building

### Query pipeline engines
- Question understanding
- Query expansion
- Retrieval (exact/fuzzy/semantic/hybrid)
- Re-ranking
- Evidence bundle building
- Verification
- Self-critique
- Answer synthesis

### Governance / support engines
- Workflow
- Rule engine
- Memory
- Planner
- Semantic cache
- Reviewer workflow
- Export
- Monitoring
- Quality assurance
- Safety governance
- Data lineage
- Audit log
- Disaster recovery

## 5) Fixed features from previous discussions
- Book Structure Engine
- Citation Span Engine
- Variant Comparison Engine
- Scholarly Opinion Engine
- Conflict Resolution Engine
- Evidence Chain Engine
- Arabic Language Intelligence Engine
- Book Edition Relationship Engine
- Source Trust Model
- Plugin Architecture
- Simulation & Sandbox Engine
- Continuous Learning & Optimization Engine
- Safe Learning Governance
- Planning & Decision Engine
- Verification Engine
- Self-Critique Engine
- Memory & Knowledge Memory Engine
- Semantic Caching
- RBAC
- Circuit Breakers
- Token Budgets
- Event-driven updates
- Build/Query separation
- Golden Dataset
- Reviewer roles
- Explainable decisions
- KPI/metrics
- Risk mitigation
- Data retention policy
- API-first mindset

## 6) Data model commitments
- Core contracts are fixed first.
- Pydantic schemas are the source for interface contracts.
- Database migrations are versioned.
- Original files remain traceable.
- Every extracted element stores:
  - source
  - edition
  - volume/page references
  - confidence
  - bounding box when applicable

## 7) Source and evidence policy
- Evidence is always tied to sources.
- Evidence bundles are the unit for model prompting.
- If evidence is insufficient, the system must say so.
- Source trust is calculated and explainable.
- Citations must include exact spans when possible.

## 8) Knowledge and learning policy
- Learn operating behavior, not unverified facts.
- Human-reviewed changes are gold.
- Learning updates must be reversible.
- Cache and memory are invalidated by version changes.
- Updating a narrator or edition can cascade to graph/index derived data.

## 9) Search policy
- Search must understand:
  - exact words
  - approximate spellings
  - meanings
  - intent
  - entity names
  - graph relations
- Search can create multiple hypotheses for a question.
- Results are re-ranked before any answer is generated.

## 10) Reviewer policy
Reviewer roles:
- user: report issues
- researcher: approve OCR/layout corrections
- expert reviewer: resolve narrators/claims and lock gold data

## 11) Quality policy
Minimum evaluation dimensions:
- OCR quality
- layout quality
- narrator resolution
- evidence faithfulness
- retrieval recall
- answer relevance
- latency
- cost
- consistency

## 12) Operational policy
- Docker first.
- External drive for portable storage.
- Backups are mandatory.
- Monitoring is mandatory.
- CI/testing is mandatory.

## 13) Implementation order
1. Freeze scope.
2. Keep repository clean and modular.
3. Build schemas.
4. Build DB layer.
5. Build golden dataset.
6. Build one-page micro-pipeline.
7. Build search.
8. Build verification.
9. Build graph/memory/planner.
10. Harden for production.

## 14) Frozen scope note
This document is the stable reference. Anything added later must map to an existing engine, be measurable, and not break the build/query split.
