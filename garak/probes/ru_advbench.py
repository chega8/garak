"""**RuADVBench Probe**

Probe на основе русскоязычных переводов AdvBench (520 атакующих промптов).
Промпты загружаются из garak/garak/data/ru_advbench/ru_advbench_prompts.txt.

Использует RuJBBDetector для обнаружения harmful content в ответах модели.
"""

from garak import _config
from garak.data import path as data_path
from garak.probes.base import Probe
import garak.probes


class RuADVBenchProbe(Probe):
    """
    Probe с атакующими промптами AdvBench на русском языке.
    Загружает 520 промптов из data/ru_advbench/ru_advbench_prompts.txt.
    """

    tags = ["ru", "dataset", "advbench", "harmful"]
    lang = "ru"
    goal = "elicit harmful/instructional responses from Russian AdvBench prompts"
    primary_detector = "ru_jbb.RuJBBDetector"
    doc_uri = ""
    tier = garak.probes.Tier.OF_CONCERN
    active = False

    def __init__(self, config_root=_config):
        super().__init__(config_root=config_root)
        self._load_prompts()

    def _load_prompts(self):
        prompts_file = data_path / "ru_advbench" / "ru_advbench_prompts.txt"
        with open(prompts_file, "r", encoding="utf-8") as f:
            self.prompts = [line.strip() for line in f if line.strip()]

        if self.follow_prompt_cap and self.soft_probe_prompt_cap is not None:
            if len(self.prompts) > self.soft_probe_prompt_cap:
                self._prune_data(self.soft_probe_prompt_cap)
