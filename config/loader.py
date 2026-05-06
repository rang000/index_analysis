from pathlib import Path
from typing import Union

import yaml


def load_settings(path: Union[str, Path] = "config/setting.yml") -> dict:
    path = Path(path)

    with path.open("r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    return settings
