from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

import requests

from presidentielle2027.config import get_settings


def download_pdf(url: str, destination_dir: Path | None = None, timeout: int = 30) -> Path:
    target_dir = destination_dir or get_settings().raw_dir / "pdfs"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = Path(urlparse(url).path).name or "source.pdf"
    output_path = target_dir / filename
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    output_path.write_bytes(response.content)
    return output_path

