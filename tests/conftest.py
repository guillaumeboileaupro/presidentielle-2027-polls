from __future__ import annotations

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _install_numpy_reduce_compatibility_patch() -> None:
    """Patch NumPy reduce helpers for a pytest-cov reload edge case.

    Running the test suite with coverage enabled can put NumPy in a bad reload
    state where `_methods._amax/_amin` pass the internal `<no value>` sentinel
    through to the C reduce implementation. Pandas then crashes on ordinary
    boolean indexing, `dropna`, `min`, and `max`.

    This is a coverage-instrumentation artifact, not a production concern, so
    the patch is installed here (test collection only) rather than in the
    `presidentielle2027` package itself, which every dashboard/CLI/notebook
    consumer imports.

    The patch is deliberately narrow: when `initial` is still NumPy's
    sentinel, we call the underlying ufunc reduce without that argument,
    which is NumPy's normal behavior.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="The NumPy module was reloaded \\(imported a second time\\).*",
            category=UserWarning,
        )
        from numpy._core import _methods as numpy_methods

    no_value_type = type(numpy_methods._NoValue)

    def _safe_amax(
        a: object,
        axis: int | None = None,
        out: object = None,
        keepdims: bool = False,
        initial: object = numpy_methods._NoValue,
        where: object = True,
    ) -> object:
        if isinstance(initial, no_value_type):
            if where is True:
                return numpy_methods.umr_maximum(a, axis, None, out, keepdims)
            return numpy_methods.umr_maximum(a, axis, None, out, keepdims, where=where)
        return numpy_methods.umr_maximum(a, axis, None, out, keepdims, initial, where)

    def _safe_amin(
        a: object,
        axis: int | None = None,
        out: object = None,
        keepdims: bool = False,
        initial: object = numpy_methods._NoValue,
        where: object = True,
    ) -> object:
        if isinstance(initial, no_value_type):
            if where is True:
                return numpy_methods.umr_minimum(a, axis, None, out, keepdims)
            return numpy_methods.umr_minimum(a, axis, None, out, keepdims, where=where)
        return numpy_methods.umr_minimum(a, axis, None, out, keepdims, initial, where)

    def _safe_sum(
        a: object,
        axis: int | None = None,
        dtype: object = None,
        out: object = None,
        keepdims: bool = False,
        initial: object = numpy_methods._NoValue,
        where: object = True,
    ) -> object:
        if isinstance(initial, no_value_type):
            if where is True:
                return numpy_methods.umr_sum(a, axis, dtype, out, keepdims)
            return numpy_methods.umr_sum(a, axis, dtype, out, keepdims, where=where)
        return numpy_methods.umr_sum(a, axis, dtype, out, keepdims, initial, where)

    def _safe_prod(
        a: object,
        axis: int | None = None,
        dtype: object = None,
        out: object = None,
        keepdims: bool = False,
        initial: object = numpy_methods._NoValue,
        where: object = True,
    ) -> object:
        if isinstance(initial, no_value_type):
            if where is True:
                return numpy_methods.umr_prod(a, axis, dtype, out, keepdims)
            return numpy_methods.umr_prod(a, axis, dtype, out, keepdims, where=where)
        return numpy_methods.umr_prod(a, axis, dtype, out, keepdims, initial, where)

    numpy_methods._amax = _safe_amax
    numpy_methods._amin = _safe_amin
    numpy_methods._sum = _safe_sum
    numpy_methods._prod = _safe_prod


_install_numpy_reduce_compatibility_patch()
