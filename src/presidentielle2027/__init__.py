"""Presidentielle 2027 polls package."""

from __future__ import annotations

import warnings

with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="The NumPy module was reloaded \\(imported a second time\\).*",
        category=UserWarning,
    )
    from numpy._core import _methods as _numpy_methods


def _install_numpy_reduce_compatibility_patch() -> None:
    """Patch NumPy reduce helpers for a pytest-cov reload edge case.

    In this environment, running the test suite with coverage enabled can put
    NumPy in a bad reload state where `_methods._amax/_amin` pass the internal
    `<no value>` sentinel through to the C reduce implementation. Pandas then
    crashes on ordinary boolean indexing, `dropna`, `min`, and `max`.

    The patch is deliberately narrow: when `initial` is still NumPy's sentinel,
    we call the underlying ufunc reduce without that argument, which is NumPy's
    normal behavior.
    """

    no_value_type = type(_numpy_methods._NoValue)

    def _safe_amax(
        a: object,
        axis: int | None = None,
        out: object = None,
        keepdims: bool = False,
        initial: object = _numpy_methods._NoValue,
        where: object = True,
    ) -> object:
        if isinstance(initial, no_value_type):
            if where is True:
                return _numpy_methods.umr_maximum(a, axis, None, out, keepdims)
            return _numpy_methods.umr_maximum(a, axis, None, out, keepdims, where=where)
        return _numpy_methods.umr_maximum(a, axis, None, out, keepdims, initial, where)

    def _safe_amin(
        a: object,
        axis: int | None = None,
        out: object = None,
        keepdims: bool = False,
        initial: object = _numpy_methods._NoValue,
        where: object = True,
    ) -> object:
        if isinstance(initial, no_value_type):
            if where is True:
                return _numpy_methods.umr_minimum(a, axis, None, out, keepdims)
            return _numpy_methods.umr_minimum(a, axis, None, out, keepdims, where=where)
        return _numpy_methods.umr_minimum(a, axis, None, out, keepdims, initial, where)

    def _safe_sum(
        a: object,
        axis: int | None = None,
        dtype: object = None,
        out: object = None,
        keepdims: bool = False,
        initial: object = _numpy_methods._NoValue,
        where: object = True,
    ) -> object:
        if isinstance(initial, no_value_type):
            if where is True:
                return _numpy_methods.umr_sum(a, axis, dtype, out, keepdims)
            return _numpy_methods.umr_sum(a, axis, dtype, out, keepdims, where=where)
        return _numpy_methods.umr_sum(a, axis, dtype, out, keepdims, initial, where)

    def _safe_prod(
        a: object,
        axis: int | None = None,
        dtype: object = None,
        out: object = None,
        keepdims: bool = False,
        initial: object = _numpy_methods._NoValue,
        where: object = True,
    ) -> object:
        if isinstance(initial, no_value_type):
            if where is True:
                return _numpy_methods.umr_prod(a, axis, dtype, out, keepdims)
            return _numpy_methods.umr_prod(a, axis, dtype, out, keepdims, where=where)
        return _numpy_methods.umr_prod(a, axis, dtype, out, keepdims, initial, where)

    _numpy_methods._amax = _safe_amax
    _numpy_methods._amin = _safe_amin
    _numpy_methods._sum = _safe_sum
    _numpy_methods._prod = _safe_prod


_install_numpy_reduce_compatibility_patch()

__all__ = ["__version__"]

__version__ = "0.1.0"
