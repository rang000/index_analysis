from pathlib import Path
from typing import Optional, Union

import yaml


def load_settings(path: Optional[Union[str, Path]] = None) -> dict:
    if path is None:
        path = Path("config/setting.yml")
    else:
        path = Path(path)

    with path.open("r", encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    return settings
