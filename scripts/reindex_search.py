from __future__ import annotations

import json
from pathlib import Path

from packages.learning.trainer import LearningTrainer

if __name__ == "__main__":
    trainer = LearningTrainer()
    try:
        summary = trainer.train_all()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    finally:
        trainer.close()
