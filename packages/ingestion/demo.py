from pathlib import Path

from .manager import IngestionManager

manager = IngestionManager()

result = manager.parse(
    str(
        Path("sample.pdf")
    )
)

print(result["metadata"])
print(result["toc"])
print(len(result["pages"]))
print(len(result["text"]))
print(len(result["blocks"]))
print(len(result["words"]))
print(len(result["links"]))
print(len(result["drawings"]))
print(len(result["images"]))
