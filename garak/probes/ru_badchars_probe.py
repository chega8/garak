import json
import logging
import random
from pathlib import Path
from dataclasses import dataclass
from typing import Iterator, List, Sequence, Tuple

import garak.attempt
from garak.probes import Probe
from garak.exception import PluginConfigurationError
from garak.data import path as data_path

# -----------------------
# Constants (from BadChars)
# -----------------------

DEFAULT_INVISIBLE = ("\u200b", "\u200c", "\u200d")  # ZWSP, ZWNJ, ZWJ

BIDI_CONTROLS = {
    "PDF": "\u202c",
    "LRO": "\u202d",
    "RLO": "\u202e",
    "LRI": "\u2066",
    "RLI": "\u2067",
    "PDI": "\u2069",
}

ASCII_PRINTABLE = tuple(chr(i) for i in range(0x20, 0x7F))


@dataclass(frozen=True)
class _Swap:
    first: str
    second: str


# -----------------------
# Helpers
# -----------------------

def _render_swaps(elements: Sequence) -> str:
    rendered = []
    for el in elements:
        if isinstance(el, _Swap):
            rendered.append(
                BIDI_CONTROLS["LRO"]
                + BIDI_CONTROLS["LRI"]
                + BIDI_CONTROLS["RLO"]
                + BIDI_CONTROLS["LRI"]
                + el.first
                + BIDI_CONTROLS["PDI"]
                + BIDI_CONTROLS["LRI"]
                + el.second
                + BIDI_CONTROLS["PDI"]
                + BIDI_CONTROLS["PDF"]
                + BIDI_CONTROLS["PDI"]
                + BIDI_CONTROLS["PDF"]
            )
        else:
            rendered.append(el)
    return "".join(rendered)


def _load_homoglyph_map() -> dict[str, List[str]]:
    """Parse intentional.txt into a source -> targets dictionary."""
    mapping: dict[str, set[str]] = {}
    intent_path = data_path / "badchars" / "intentional.txt"
    try:
        with open(intent_path, "r", encoding="utf-8") as infile:
            for raw_line in infile:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                left, remainder = line.split(";", maxsplit=1)
                remainder = remainder.split("#", maxsplit=1)[0].strip()
                if not remainder:
                    continue
                codepoints = remainder.split()
                if not codepoints:
                    continue
                source = chr(int(left.strip(), 16))
                target = "".join(chr(int(cp, 16)) for cp in codepoints)
                if source == target:
                    continue
                mapping.setdefault(source, set()).add(target)
    except FileNotFoundError as exc:
        msg = (
            "Unable to load intentional.txt for homoglyph perturbations. "
            "Get data from https://www.unicode.org/Public/security/latest/intentional.txt"
        )
        logging.error(msg)
        raise PluginConfigurationError(msg) from exc

    return {key: sorted(values) for key, values in mapping.items()}


def _select_positions(length: int, cap: int, include_endpoint: bool = True) -> List[int]:
    """Select up to cap positions from 0..length (or 0..length-1 if not include_endpoint)."""
    positions = list(range(length + (1 if include_endpoint else 0)))
    if cap is None or cap <= 0 or len(positions) <= cap:
        return positions

    if cap == 1:
        return [positions[0]]

    step = (len(positions) - 1) / (cap - 1) if len(positions) > 1 else 0
    selected = []
    seen = set()
    for idx in range(cap):
        pick = round(idx * step)
        value = positions[min(pick, len(positions) - 1)]
        if value in seen:
            continue
        selected.append(value)
        seen.add(value)
    for value in positions:
        if len(selected) >= cap:
            break
        if value not in seen:
            selected.append(value)
            seen.add(value)
    selected.sort()
    return selected


# =======================
# RuJBBBadCharsProbe
# =======================

class RuJBBBadCharsProbe(Probe):
    """
    Applies Bad Characters perturbations to a RU corpus of harmful prompts.
    Loads prompts from garak/data/ru_jbb/ru-jbb.csv (or custom path via config).
    """

    tags = ["ru", "badchars", "jailbreak"]
    goal = "apply imperceptible unicode perturbations to RU prompts"

    DEFAULT_PARAMS = Probe.DEFAULT_PARAMS | {
        "path": None,
        "max_seeds": 5,
        "perturbation_budget": 1,
        "enabled_categories": ["invisible", "homoglyph", "reordering", "deletion"],
        "max_position_candidates": 16,
        "max_reorder_candidates": 16,
        "follow_prompt_cap": True,
    }

    def __init__(self, config_root=None):
        super().__init__(config_root=config_root)

        if self.perturbation_budget <= 0:
            raise PluginConfigurationError(
                "perturbation_budget must be a positive integer"
            )

        self._homoglyph_map = _load_homoglyph_map()

        path = self.path
        if path is None:
            path = data_path / "ru_jbb" / "ru-jbb.csv"
        path = Path(path) if not isinstance(path, Path) else path
        self._load_prompts(path)

        categories = self.enabled_categories
        if isinstance(categories, str):
            categories = [categories]
        self._enabled_categories = {
            cat.lower() for cat in categories if isinstance(cat, str)
        }
        if not self._enabled_categories:
            raise PluginConfigurationError(
                "enabled_categories must include at least one entry"
            )

        self._generators = {
            "invisible": self._gen_invisible,
            "homoglyph": self._gen_homoglyph,
            "reordering": self._gen_reordering,
            "deletion": self._gen_deletion,
        }
        unknown = self._enabled_categories - set(self._generators)
        if unknown:
            logging.warning("Unknown RuJBBBadCharsProbe categories %s; skipping", sorted(unknown))
            self._enabled_categories &= set(self._generators)

        self.prompts = []
        seen = set()

        max_seeds = getattr(self, "max_seeds", 5) or len(self._seeds)
        seeds = self._seeds[:max_seeds]

        for idx, seed in enumerate(seeds[:5]):
            for cat in self._enabled_categories:
                gen = self._generators.get(cat)
                if not gen:
                    continue
                for text, meta in gen(seed):
                    if text in seen:
                        continue
                    seen.add(text)
                    self.prompts.append(
                        garak.attempt.Conversation(
                            [
                                garak.attempt.Turn(
                                    "user",
                                    garak.attempt.Message(text=text, lang="ru"),
                                )
                            ],
                            notes={
                                "category": cat,
                                "source_index": idx,
                                "source_excerpt": seed[:80],
                                **meta,
                            },
                        )
                    )

        if not self.prompts:
            raise PluginConfigurationError(
                "RuJBBBadCharsProbe generated zero prompts"
            )

        if (
            self.follow_prompt_cap
            and self.soft_probe_prompt_cap is not None
            and len(self.prompts) > self.soft_probe_prompt_cap
        ):
            self._prune_data(self.soft_probe_prompt_cap)

    # -----------------------
    # Load corpus
    # -----------------------

    def _load_prompts(self, path: Path):
        self._seeds = []

        if path.suffix.lower() == ".jsonl":
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._seeds.append(json.loads(line)["prompt_ru"])
        elif path.suffix.lower() == ".csv":
            import csv

            with open(path, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    self._seeds.append(row["prompt_ru"])
        else:
            raise PluginConfigurationError(
                "Unsupported corpus format. Use .csv or .jsonl with prompt_ru column."
            )

        if not self._seeds:
            raise PluginConfigurationError(
                f"No prompts loaded from {path}"
            )

    # -----------------------
    # Perturbation generators
    # -----------------------

    def _gen_invisible(self, payload: str) -> Iterator[Tuple[str, dict]]:
        positions = _select_positions(
            len(payload), self.max_position_candidates, include_endpoint=True
        )
        for pos in positions:
            text = (
                payload[:pos]
                + random.choice(DEFAULT_INVISIBLE)
                + payload[pos:]
            )
            yield text, {"op": "invisible", "pos": pos}

    def _gen_homoglyph(self, payload: str) -> Iterator[Tuple[str, dict]]:
        candidate_positions = [
            idx for idx, ch in enumerate(payload) if ch in self._homoglyph_map
        ]
        if not candidate_positions:
            return

        indices = _select_positions(
            len(candidate_positions),
            self.max_position_candidates,
            include_endpoint=False,
        )
        capped = [candidate_positions[i] for i in indices if i < len(candidate_positions)]

        for pos in capped:
            ch = payload[pos]
            for rep in self._homoglyph_map[ch]:
                yield (
                    payload[:pos] + rep + payload[pos + 1 :],
                    {"op": "homoglyph", "pos": pos},
                )

    def _gen_reordering(self, payload: str) -> Iterator[Tuple[str, dict]]:
        if len(payload) < 2:
            return

        reorder_indices = _select_positions(
            len(payload) - 1, self.max_reorder_candidates, include_endpoint=False
        )

        for idx in reorder_indices:
            if idx >= len(payload) - 1:
                continue
            swapped = list(payload)
            swapped[idx : idx + 2] = [_Swap(payload[idx + 1], payload[idx])]
            yield (
                _render_swaps(swapped),
                {"op": "bidi_swap", "pos": idx},
            )

    def _gen_deletion(self, payload: str) -> Iterator[Tuple[str, dict]]:
        positions = _select_positions(
            len(payload), self.max_position_candidates, include_endpoint=True
        )
        for pos in positions:
            ch = random.choice(ASCII_PRINTABLE)
            yield (
                payload[:pos] + ch + "\b" + payload[pos:],
                {"op": "deletion", "pos": pos},
            )
