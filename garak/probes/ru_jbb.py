import json
import os
from pathlib import Path

import pandas as pd
from garak.data import path as data_path
from garak.probes.base import Probe


class RuJBB(Probe):
    """
    Минимальная probe: загружает промпты из CSV/JSONL/JSON и отдаёт их garak.
    Buffs будут применены автоматически на уровне Probe.probe() -> _buff_hook().
    """

    tags = ["ru", "dataset", "jbb"]

    DEFAULT_PARAMS = Probe.DEFAULT_PARAMS | {
        "path": None,
        "prompt_field": "prompt_ru",
        "limit": None,
    }

    def __init__(self, config_root=None):
        super().__init__(config_root=config_root)

        path = self.path or os.getenv("RU_JBB_PATH")
        if not path:
            path = data_path / "ru_jbb" / "ru-jbb.csv"

        prompt_field = os.getenv("RU_JBB_PROMPT_FIELD", self.prompt_field)

        limit = self.limit
        limit_env = os.getenv("RU_JBB_LIMIT")
        if limit_env:
            try:
                limit = int(limit_env)
            except ValueError as exc:
                raise ValueError("RU_JBB_LIMIT must be an integer") from exc

        self.prompts = self._load_prompts(path, prompt_field, limit)

    def _load_prompts(self, path: str, prompt_field: str, limit: int | None):
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(p)

        if p.suffix.lower() == ".csv":
            df = pd.read_csv(p)
            if prompt_field not in df.columns:
                raise ValueError(
                    f"CSV does not contain prompt field '{prompt_field}': {p}"
                )
            if limit:
                df = df.head(limit)
            return [row[prompt_field] for _, row in df.iterrows()]

        if p.suffix.lower() == ".jsonl":
            prompts = []
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    if prompt_field not in obj:
                        raise ValueError(
                            f"JSONL entry missing '{prompt_field}' field"
                        )
                    prompts.append(obj[prompt_field])
                    if limit and len(prompts) >= limit:
                        break
            return prompts

        if p.suffix.lower() == ".json":
            obj = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(obj, dict) and "prompts" in obj:
                prompts = list(obj["prompts"])
            elif isinstance(obj, list):
                prompts = [x[prompt_field] for x in obj]
            else:
                raise ValueError("Unsupported JSON structure")
            return prompts[:limit] if limit else prompts

        raise ValueError("Unsupported file type. Use .csv, .jsonl or .json")
