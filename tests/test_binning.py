import numpy as np

from plotnine.scales import scale_x_continuous, scale_x_discrete
from plotnine.stats.binning import (
    _adjust_breaks,
    breaks_from_bins,
    breaks_from_binwidth,
    fuzzybreaks,
)


def test_breaks_from_bins():
    n = 10
    x = list(range(n))
    limits = min(x), max(x)
    breaks = breaks_from_bins(limits, n)
    breaks2 = breaks_from_bins(limits, n, center=limits[0])

    # correct no. of breaks
    assert len(breaks)-1 == n
    # breaks include the limits
    assert min(breaks) <= limits[0]
    assert max(breaks) >= limits[1]
    # limits are at mid-points of the bins in which they fall
    assert (breaks[1]+breaks[0])/2 == limits[0]
    assert (breaks[-1]+breaks[-2])/2 == limits[1]
    assert list(breaks) == list(breaks2)

    breaks = breaks_from_bins(limits, n, boundary=limits[0])
    assert list(breaks) == x


def test_breaks_from_binwidth():
    n = 10
    x = list(range(n))
    limits = min(x), max(x)
    breaks = breaks_from_binwidth(limits, binwidth=1)
    breaks2 = breaks_from_binwidth(limits, binwidth=1,
                                   center=limits[0])

    # correct no. of breaks
    assert len(breaks)-1 == n
    # breaks include the limits
    assert min(breaks) <= limits[0]
    assert max(breaks) >= limits[1]
    # limits are at mid-points of the bins in which they fall
    assert (breaks[1]+breaks[0])/2 == limits[0]
    assert (breaks[-1]+breaks[-2])/2 == limits[1]
    assert list(breaks) == list(breaks2)


def test_fuzzybreaks():
    n = 10
    x = list(range(n))
    limits = min(x), max(x)
    # continuous scale
    cscale = scale_x_continuous(limits=limits)
    cscale.train(x)

    breaks = fuzzybreaks(cscale, bins=n-1, right=True)
    assert breaks[0] <= limits[0]
    assert breaks[-1] >= limits[1]
    assert all(_x < b for _x, b in zip(x[1:-1], breaks[1:-1]))

    breaks = fuzzybreaks(cscale, bins=n-1, right=False)
    assert breaks[0] <= limits[0]
    assert breaks[-1] >= limits[1]
    assert all(b < _x for _x, b in zip(x[1:-1], breaks[1:-1]))

    breaks = fuzzybreaks(cscale, binwidth=1, right=True)
    assert breaks[0] <= limits[0]
    assert breaks[-1] >= limits[1]
    assert all(_x < b for _x, b in zip(x[1:-1], breaks[1:-1]))

    # discrete scale
    x = list(range(1, n+1))  # items are "labelled" 1 to n
    dscale = scale_x_discrete(limits=x)
    breaks = fuzzybreaks(dscale)
    # The breaks create bins centered on the limits
    assert list((breaks[:-1]+breaks[1:])/2) == x


def test_adjust_breaks_right():
    def _test(a, b):
        assert b[0] <= a[0]
        assert all(a[1:] <= b[1:])

    # All positive
    a = np.linspace(1, 2, 11)
    b = _adjust_breaks(a, right=True)
    _test(a, b)

    # zero on the Left
    a = np.linspace(0, 1, 11)
    b = _adjust_breaks(a, right=True)
    _test(a, b)

    # zero on the right
    a = np.linspace(-1, 0, 11)
    b = _adjust_breaks(a, right=True)
    _test(a, b)

    # All negative
    a = np.linspace(-2, -1, 11)
    b = _adjust_breaks(a, right=True)
    _test(a, b)


def test_adjust_breaks_right_False():
    def _test(a, b):
        assert a[-1] <= b[-1]
        assert all(b[:-1] <= a[:-1])

    # All positive
    a = np.linspace(1, 2, 11)
    b = _adjust_breaks(a, right=False)
    _test(a, b)

    # zero on the Left
    a = np.linspace(0, 1, 11)
    b = _adjust_breaks(a, right=False)
    _test(a, b)

    # zero on the right
    a = np.linspace(-1, 0, 11)
    b = _adjust_breaks(a, right=False)
    _test(a, b)

    # All negative
    a = np.linspace(-2, -1, 11)
    b = _adjust_breaks(a, right=False)
    _test(a, b)
