from packages.search.query import QueryProcessor

qp = QueryProcessor()

tests = [
    "الله",
    "اﷲ",
    "اللَّه",
    "نهج      البلاغة",
    "  الإمام    علي  ",
]

for q in tests:

    result = qp.process(q)

    print("=" * 60)
    print("Original  :", result.original)
    print("Normalized:", result.normalized)
    print("Tokens    :", result.tokens)
