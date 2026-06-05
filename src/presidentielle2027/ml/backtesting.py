from __future__ import annotations

from pathlib import Path

import pandas as pd

from presidentielle2027.config import get_settings


def run_backtest(historical_dir: Path | None = None) -> dict[str, str | int]:
    directory = historical_dir or get_settings().historical_dir
    files = sorted(directory.glob("*.csv"))
    if not files:
        return {
            "status": "skipped",
            "message": "No historical datasets found. Add 2017/2022 datasets to data/historical/.",
            "file_count": 0,
        }
    frames = [pd.read_csv(path) for path in files]
    row_count = sum(len(frame) for frame in frames)
    return {
        "status": "prepared",
        "message": "Historical data discovered. Extend this module with election-specific evaluation logic.",
        "file_count": len(files),
        "row_count": row_count,
    }

