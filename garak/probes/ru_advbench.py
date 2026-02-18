"""**RuADVBench Probe**

Probe на основе русскоязычных переводов AdvBench.
Промпты по умолчанию загружаются из garak/garak/data/ru_advbench/ru_advbench_prompts.txt,
но путь можно переопределить через config/env.
"""

import os
from pathlib import Path

import garak.probes
import pandas as pd
from garak import _config
from garak.data import path as data_path
from garak.probes.base import Probe


class RuADVBenchProbe(Probe):
    """
    Probe с атакующими промптами AdvBench на русском языке.
    """

    tags = ["ru", "dataset", "advbench", "harmful"]
    lang = "ru"
    goal = "elicit harmful/instructional responses from Russian AdvBench prompts"
    primary_detector = "ru_jbb.RuJBBDetector"
    doc_uri = ""
    tier = garak.probes.Tier.OF_CONCERN
    active = False

    DEFAULT_PARAMS = Probe.DEFAULT_PARAMS | {
        "path": None,
        "prompt_field": "prompt_ru",
        "limit": None,
    }

    def __init__(self, config_root=_config):
        super().__init__(config_root=config_root)
        self._load_prompts()

    def _load_prompts(self):
        path = self.path or os.getenv("RU_ADVBENCH_PATH")
        if not path:
            path = data_path / "ru_advbench" / "ru_advbench_prompts.txt"

        prompt_field = os.getenv("RU_ADVBENCH_PROMPT_FIELD", self.prompt_field)

        limit = self.limit
        limit_env = os.getenv("RU_ADVBENCH_LIMIT")
        if limit_env:
            try:
                limit = int(limit_env)
            except ValueError as exc:
                raise ValueError("RU_ADVBENCH_LIMIT must be an integer") from exc

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(p)

        if p.suffix.lower() == ".txt":
            with p.open("r", encoding="utf-8") as f:
                prompts = [line.strip() for line in f if line.strip()]
            self.prompts = prompts[:limit] if limit else prompts
        elif p.suffix.lower() == ".csv":
            df = pd.read_csv(p)
            if prompt_field not in df.columns:
                raise ValueError(
                    f"CSV does not contain prompt field '{prompt_field}': {p}"
                )
            if limit:
                df = df.head(limit)
            self.prompts = [row[prompt_field] for _, row in df.iterrows()]
        else:
            raise ValueError("Unsupported file type. Use .txt or .csv")

        if self.follow_prompt_cap and self.soft_probe_prompt_cap is not None:
            if len(self.prompts) > self.soft_probe_prompt_cap:
                self._prune_data(self.soft_probe_prompt_cap)
