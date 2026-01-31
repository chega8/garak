import json
from pathlib import Path
from garak.probes.base import Probe
import pandas as pd

class RuJBB(Probe):
    """
    Минимальная probe: загружает промпты из JSONL/JSON и отдаёт их garak.
    Buffs будут применены автоматически на уровне Probe.probe() -> _buff_hook().
    """

    # (опционально) теги для фильтрации/отчёта
    tags = ["ru", "dataset", "jbb"]

    # (опционально) детектор по умолчанию можно определить позже
    # primary_detector = "judge.Refusal"  # пример, если захочешь

    def __init__(self, config_root=None):
        super().__init__(config_root=config_root)

        # путь задаём через --probe_options / --probe_option_file
        # path = getattr(self, "path", None)
        # if not path:
        #     raise ValueError("RuJBB requires probe option 'path' (JSONL/JSON with prompts)")

        path = '/Users/aleksandrfida/Desktop/code/guardrails/data/ru_jbb/ru-jbb.csv'
        self.prompts = self._load_prompts(path)[:5]

    def _load_prompts(self, path: str):
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(p)
        
        df = pd.read_csv(path).head(5)
        prompts = []
        for i, row in df.iterrows():
            prompts.append(row['prompt_ru'])
        return prompts

        if p.suffix.lower() == ".jsonl":
            prompts = []
            with p.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    prompts.append(obj["prompt"])
            return prompts

        if p.suffix.lower() == ".json":
            obj = json.loads(p.read_text(encoding="utf-8"))
            # поддержим варианты: {"prompts":[...]} или [{"prompt":"..."}, ...]
            if isinstance(obj, dict) and "prompts" in obj:
                return list(obj["prompts"])
            if isinstance(obj, list):
                return [x["prompt"] for x in obj]
            raise ValueError("Unsupported JSON structure")

        raise ValueError("Unsupported file type. Use .jsonl or .json")
