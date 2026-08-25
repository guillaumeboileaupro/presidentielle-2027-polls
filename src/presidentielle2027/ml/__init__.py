"""Experimental ML helpers for poll-bias correction.

This package intentionally avoids importing scikit-learn at module import time.
Import concrete submodules (`features`, `train`, `predict`, `backtesting`) only
when ML functionality is actually needed.
"""

__all__ = ["backtesting", "features", "predict", "train"]
