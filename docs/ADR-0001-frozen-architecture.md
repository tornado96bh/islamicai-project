# ADR 0001: Frozen architecture

## Decision
Use a monorepo with modular architecture and contract-first development.

## Rationale
- Long-term maintainability
- Easier portability
- Easier testing
- Better separation of concerns
- Clear boundaries between build and query pipelines

## Consequences
- Core schemas must be defined before heavy engines.
- Derived layers can be rebuilt from the source of truth.
- New work must fit an existing engine or package.
- Repeated ideas are merged; unique ideas remain.
