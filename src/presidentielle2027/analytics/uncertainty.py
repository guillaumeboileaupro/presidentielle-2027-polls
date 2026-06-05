from __future__ import annotations

import math


def approximate_margin_of_error(sample_size: int | float | None, proportion_percent: float = 50.0) -> float | None:
    if sample_size is None or sample_size <= 0:
        return None
    p = min(max(proportion_percent / 100, 0.0), 1.0)
    return 1.96 * math.sqrt((p * (1 - p)) / float(sample_size)) * 100

