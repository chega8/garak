"""**RuPromptInject**

Русскоязычная адаптация PromptInject: prompt injection атаки с базовыми промптами
и целевыми строками на русском языке.

Использует те же принципы, что и PromptInject (https://openreview.net/forum?id=qiaRo_7Zmug),
но с переведёнными инструкциями и rogue strings для тестирования русскоязычных моделей.
"""

import random
import sys

from garak.attempt import Attempt
import garak.probes
from garak import _config

this = sys.modules[__name__]

RU_ROGUE_STRINGS = ("hate-humans", "kill-humans", "long-prompt")


def _ru_constructor(self, config_root=_config):
    super(self.__class__, self).__init__(config_root=config_root)
    from garak.resources.promptinject import prompting
    from garak.resources.promptinject import ru_prompt_data as prompt_data

    self.max_prompts = self.soft_probe_prompt_cap
    if self.__class__.__name__.endswith("Full"):
        self.max_prompts = None

    self.pi_build_prompts = prompting.build_prompts
    self._load_ru_data(prompt_data)


def _load_ru_data(self, prompt_data):
    prompt_config = {
        "base": {
            "text": prompt_data.ALL_RU_PLAYGROUND_PROMPTS,
        },
        "attack": {
            "text": (
                prompt_data.goal_hikacking_attacks["ignore-print"],
                prompt_data.goal_hikacking_attacks["ignore-say"],
                prompt_data.goal_hikacking_attacks["ignore-print-upper"],
                prompt_data.goal_hikacking_attacks["nevermind"],
                prompt_data.goal_hikacking_attacks["screaming-stop"],
            ),
            "rogue_string": prompt_data.rogue_strings[self.rogue_string],
            "scoring": "match_rogue_to_output",
            "settings": {
                "escape": prompt_data.escape_chars["n"],
                "delimiter": prompt_data.delimiter_chars["dash"],
                "escape_length": 10,
                "escape_times": 2,
            },
        },
        "config": {
            "id": (0, 1, 2, 3),
        },
    }
    self.prompts = []
    self.pi_prompts = self.pi_build_prompts(prompt_config)
    for pi_prompt in self.pi_prompts:
        self.prompts.append(pi_prompt["prompt"])
    if self.max_prompts:
        random.seed(self.seed)
        random.shuffle(self.prompts)
        self.prompts = self.prompts[-self.max_prompts :]


def _ru_attempt_prestore_hook(self, attempt: Attempt, seq: int) -> Attempt:
    attempt.notes["settings"] = self.pi_prompts[seq]["settings"]
    attempt.notes["triggers"] = [
        self.pi_prompts[seq]["settings"]["attack_rogue_string"]
    ]
    return attempt


def _ru_generator_precall_hook(self, generator, attempt):
    map_attribs = (
        "temperature top_p frequency_penalty presence_penalty max_tokens".split()
    )
    settings = attempt.notes.get("settings", {})
    for map_attrib in map_attribs:
        val = settings.get("config_" + map_attrib)
        if val is not None and map_attrib in dir(generator):
            setattr(generator, map_attrib, val)


for rogue_string in RU_ROGUE_STRINGS:
    classname = "RuHijack" + rogue_string.replace("-", " ").title().replace(" ", "")

    for suffix, active in [("Full", False), ("", True)]:
        setattr(
            this,
            classname + suffix,
            type(
                classname + suffix,
                (garak.probes.Probe,),
                {
                    "__init__": _ru_constructor,
                    "__doc__": (
                        f"RuPromptInject: инъекция строки; payload={rogue_string}. "
                        "Попытка заставить модель повторить заданную строку."
                    ),
                    "name": "ru_promptinject_" + rogue_string,
                    "lang": "ru",
                    "description": "Русскоязычная адаптация PromptInject для тестирования prompt injection",
                    "primary_detector": "ru_promptinject.RuAttackRogueString",
                    "parallelisable_attempts": False,
                    "tags": [
                        "ru",
                        "avid-effect:security:S0403",
                        "owasp:llm01",
                        "quality:Security:PromptStability",
                    ],
                    "_load_ru_data": _load_ru_data,
                    "uri": "https://openreview.net/forum?id=qiaRo_7Zmug",
                    "rogue_string": rogue_string,
                    "_attempt_prestore_hook": _ru_attempt_prestore_hook,
                    "_generator_precall_hook": _ru_generator_precall_hook,
                    "goal": "инъекция промпта: " + rogue_string.replace("-", " "),
                    "active": active,
                    "tier": garak.probes.Tier.COMPETE_WITH_SOTA,
                },
            ),
        )
