from functools import lru_cache
from pathlib import Path

import yaml

PROMPTS_DIR = Path(__file__).parent


@lru_cache(maxsize=None)
def _load_file(name: str) -> dict:
    with (PROMPTS_DIR / f"{name}.yml").open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=None)
def get_system_prompt(name: str, section: str | None = None) -> str:
    node = _load_file(name)[section] if section else _load_file(name)
    return node["system_prompt"] if isinstance(node, dict) else node
