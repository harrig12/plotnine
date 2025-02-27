from __future__ import annotations

import typing
from contextlib import suppress
from copy import copy, deepcopy
from functools import partial
from warnings import warn

import numpy as np
import pandas as pd
from mizani.bounds import censor, expand_range_distinct, rescale, zero_range
from mizani.breaks import date_breaks
from mizani.formatters import date_format
from mizani.transforms import gettrans

from ..doctools import document
from ..exceptions import PlotnineError, PlotnineWarning
from ..iapi import range_view, scale_view
from ..mapping.aes import is_position_aes, rename_aesthetics
from ..utils import Registry, ignore_warnings, is_waive, match, waiver
from .range import Range, RangeContinuous, RangeDiscrete

if typing.TYPE_CHECKING:
    from typing import Optional, Sequence

    from mizani.transforms import trans


class scale(metaclass=Registry):
    """
    Base class for all scales

    Parameters
    ----------
    breaks : array_like or callable, optional
        Major break points. Alternatively, a callable that
        takes a tuple of limits and returns a list of breaks.
        Default is to automatically calculate the breaks.
    expand : tuple, optional
        Multiplicative and additive expansion constants
        that determine how the scale is expanded. If
        specified must be of length 2 or 4. Specifically the
        values are in this order::

            (mul, add)
            (mul_low, add_low, mul_high, add_high)

        For example,

            - ``(0, 0)`` - Do not expand.
            - ``(0, 1)`` - Expand lower and upper limits by 1 unit.
            - ``(1, 0)`` - Expand lower and upper limits by 100%.
            - ``(0, 0, 0, 0)`` - Do not expand, as ``(0, 0)``.
            - ``(0, 0, 0, 1)`` - Expand upper limit by 1 unit.
            - ``(0, 1, 0.1, 0)`` - Expand lower limit by 1 unit and
              upper limit by 10%.
            - ``(0, 0, 0.1, 2)`` - Expand upper limit by 10% plus
              2 units.

        If not specified, suitable defaults are chosen.
    name : str, optional
        Name used as the label of the scale. This is what
        shows up as the axis label or legend title. Suitable
        defaults are chosen depending on the type of scale.
    labels : list or callable, optional
        List of :class:`str`. Labels at the `breaks`.
        Alternatively, a callable that takes an array_like of
        break points as input and returns a list of strings.
    limits : array_like, optional
        Limits of the scale. Most commonly, these are the
        min & max values for the scales. For scales that
        deal with categoricals, these may be a subset or
        superset of the categories.
    na_value : scalar
        What value to assign to missing values. Default
        is to assign ``np.nan``.
    palette : callable, optional
        Function to map data points onto the scale. Most
        scales define their own palettes.
    aesthetics : list, optional
        list of :class:`str`. Aesthetics covered by the
        scale. These are defined by each scale and the
        user should probably not change them. Have fun.
    """
    __base__ = True

    _aesthetics = []     # aesthetics affected by this scale
    na_value = np.nan   # What to do with the NA values
    name: str | None = None  # used as the axis label or legend title
    breaks = waiver()   # major breaks
    labels = waiver()   # labels at the breaks
    guide = 'legend'    # legend or any other guide
    _limits = None      # (min, max) - set by user

    #: multiplicative and additive expansion constants
    expand = None

    # range of aesthetic, instantiated by __init__ from the
    range: Range
    _range_class: type[Range] = Range

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
            else:
                msg = "{} could not recognise parameter `{}`"
                warn(msg.format(self.__class__.__name__, k), PlotnineWarning)

        self.range = self._range_class()

        if np.iterable(self.breaks) and np.iterable(self.labels):
            if len(self.breaks) != len(self.labels):
                raise PlotnineError(
                    "Breaks and labels have unequal lengths")

        if (self.breaks is None and
                not is_position_aes(self.aesthetics) and
                self.guide is not None):
            self.guide = None

    @property
    def aesthetics(self):
        return self._aesthetics

    @aesthetics.setter
    def aesthetics(self, value):
        if isinstance(value, str):
            value = [value]
        self._aesthetics = rename_aesthetics(value)

    def __radd__(self, gg):
        """
        Add this scale to ggplot object
        """
        gg.scales.append(copy(self))
        return gg

    @staticmethod
    def palette(x):
        """
        Aesthetic mapping function
        """
        raise NotImplementedError('Not Implemented')

    def map(self, x, limits=None):
        """
        Map every element of x

        The palette should do the real work, this should
        make sure that sensible values are sent and
        return from the palette.
        """
        raise NotImplementedError('Not Implemented')

    def train(self, x):
        """
        Train scale

        Parameters
        ----------
        x: pd.series | np.array
            a column of data to train over
        """
        raise NotImplementedError('Not Implemented')

    def dimension(self, expand=None, limits=None):
        """
        Get the phyical size of the scale.
        """
        raise NotImplementedError('Not Implemented')

    def expand_limits(
        self,
        limits: Sequence[float],
        expand: Optional[
            tuple[float, float, float, float] |
            tuple[float, float]
        ] = None,
        coord_limits: Optional[tuple[float, float]] = None,
        trans: Optional[trans] = None
    ) -> range_view:
        """
        Exand the limits of the scale
        """
        raise NotImplementedError('Not Implemented')

    def transform_df(self, df):
        """
        Transform dataframe
        """
        raise NotImplementedError('Not Implemented')

    def transform(self, x):
        """
        Transform array|series x
        """
        raise NotImplementedError('Not Implemented')

    def inverse(self, x):
        """
        Inverse transform array|series x
        """
        raise NotImplementedError('Not Implemented')

    def view(
        self,
        limits: Optional[tuple[float, float]] = None,
        range: Optional[tuple[float, float]] = None
    ) -> scale_view:
        """
        Information about the trained scale
        """
        raise NotImplementedError('Not Implemented')

    def default_expansion(self, mult=0, add=0, expand=True):
        """
        Get default expansion for this scale
        """
        if not expand:
            return (0, 0, 0, 0)

        if self.expand:
            n = len(self.expand)
            if n == 2:
                mult, add = self.expand
            elif n == 4:
                mult = self.expand[0], self.expand[2]
                add = self.expand[1], self.expand[3]
            else:
                raise ValueError(
                    "The scale.expand must be a tuple of "
                    "size 2 or 4. "
                )

        if isinstance(mult, (float, int)):
            mult = (mult, mult)

        if isinstance(add, (float, int)):
            add = (add, add)

        if len(mult) != 2:
            raise ValueError(
                "The scale expansion multiplication factor should "
                "either be a single float, or a tuple of two floats. "
            )

        if len(add) != 2:
            raise ValueError(
                "The scale expansion addition constant should "
                "either be a single float, or a tuple of two floats. "
            )

        return (mult[0], add[0], mult[1], add[1])

    def clone(self):
        return deepcopy(self)

    def reset(self):
        """
        Set the range of the scale to None.

        i.e Forget all the training
        """
        self.range.reset()

    def is_empty(self) -> bool:
        """
        Whether the scale has size information
        """
        if not hasattr(self, 'range'):
            return True
        return self.range.is_empty() and self._limits is None

    @property
    def limits(self):
        if self.is_empty():
            return (0, 1)

        if self._limits is None:
            return tuple(self.range.range)
        elif callable(self._limits):
            return tuple(self._limits(self.range.range))
        else:
            return tuple(self._limits)

    @limits.setter
    def limits(self, value):
        if isinstance(value, tuple):
            value = list(value)
        self._limits = value

    def train_df(self, df):
        """
        Train scale from a dataframe
        """
        aesthetics = sorted(set(self.aesthetics) & set(df.columns))
        for ae in aesthetics:
            self.train(df[ae])

    def map_df(self, df):
        """
        Map df
        """
        if len(df) == 0:
            return

        aesthetics = set(self.aesthetics) & set(df.columns)
        for ae in aesthetics:
            df[ae] = self.map(df[ae])

        return df


@document
class scale_discrete(scale):
    """
    Base class for all discrete scales

    Parameters
    ----------
    {superclass_parameters}
    limits : array_like, optional
        Limits of the scale. For scales that deal with
        categoricals, these may be a subset or superset of
        the categories. Data values that are not in the limits
        will be treated as missing data and represented with
        the ``na_value``.
    drop : bool
        Whether to drop unused categories from
        the scale
    na_translate : bool
        If ``True`` translate missing values and show them.
        If ``False`` remove missing values. Default value is
        ``True``
    na_value : object
        If ``na_translate=True``, what aesthetic value should be
        assigned to the missing values. This parameter does not
        apply to position scales where ``nan`` is always placed
        on the right.
    """
    _range_class = RangeDiscrete
    drop = True        # drop unused factor levels from the scale
    na_translate = True

    def train(self, x, drop=False):
        """
        Train scale

        Parameters
        ----------
        x: pd.series | np.array
            a column of data to train over
        drop : bool
            Whether to drop(not include) unused categories

        A discrete range is stored in a list
        """
        if not len(x):
            return

        na_rm = (not self.na_translate)
        self.range.train(x, drop, na_rm=na_rm)

    def dimension(self, expand=(0, 0, 0, 0), limits=None):
        """
        Get the phyical size of the scale

        Unlike limits, this always returns a numeric vector of length 2
        """
        if limits is None:
            limits = self.limits
        return expand_range_distinct(self.limits, expand)

    def expand_limits(
        self,
        limits: Sequence[str],
        expand: Optional[
            tuple[float, float, float, float] |
            tuple[float, float]
        ] = None,
        coord_limits: Optional[tuple[float, float]] = None,
        trans: Optional[trans] = None
    ) -> range_view:
        """
        Calculate the final range in coordinate space
        """
        expand_func = partial(
            scale_continuous.expand_limits,
            self,
            trans=trans
        )
        n_limits = len(limits)
        range_c = (0, 1)
        range_d = (1, n_limits)
        is_only_continuous = n_limits == 0

        if hasattr(self.range, 'range_c'):
            is_only_discrete = self.range.range_c.is_trained()
            range_c = self.range.range_c.range
        else:
            is_only_discrete = True

        if self.is_empty():
            return expand_func(range_c, expand, coord_limits),
        elif is_only_continuous:
            return expand_func(range_c, expand, coord_limits)
        elif is_only_discrete:
            return expand_func(range_d, expand, coord_limits)
        else:
            no_expand = self.default_expand(0, 0)
            ranges_d = expand_func(range_d, expand, coord_limits)
            ranges_c = expand_func(range_c, no_expand, coord_limits)
            limits = np.hstack(ranges_d.range, ranges_c.range)
            range = (np.min(limits), np.max(limits))
            ranges = range_view(range=range, range_coord=range)
            return ranges

    def view(
        self,
        limits: Optional[tuple[float, float]] = None,
        range: Optional[tuple[float, float]] = None
    ) -> scale_view:
        """
        Information about the trained scale
        """
        if limits is None:
            limits = self.limits

        if range is None:
            range = self.dimension(limits=limits)

        breaks_d = self.get_breaks(limits)
        breaks = self.map(pd.Categorical(breaks_d.keys()))
        minor_breaks = []
        labels = self.get_labels(breaks_d)

        sv = scale_view(
            scale=self,
            aesthetics=self.aesthetics,
            name=self.name,
            limits=limits,
            range=range,
            breaks=breaks,
            labels=labels,
            minor_breaks=minor_breaks
        )
        return sv

    def default_expansion(self, mult=0, add=0.6, expand=True):
        """
        Get the default expansion for a discrete scale
        """
        return super().default_expansion(mult, add, expand)

    def map(self, x, limits=None):
        """
        Map values in x to a palette
        """
        if limits is None:
            limits = self.limits

        n = sum(~pd.isnull(list(limits)))
        pal = self.palette(n)
        if isinstance(pal, dict):
            # manual palette with specific assignments
            pal_match = []
            for val in x:
                try:
                    pal_match.append(pal[val])
                except KeyError:
                    pal_match.append(self.na_value)
        else:
            if not isinstance(pal, np.ndarray):
                pal = np.asarray(pal, dtype=object)
            idx = np.asarray(match(x, limits))
            try:
                pal_match = [pal[i] if i >= 0 else None for i in idx]
            except IndexError:
                # Deal with missing data
                # - Insert NaN where there is no match
                pal = np.hstack((pal.astype(object), np.nan))
                idx = np.clip(idx, 0, len(pal)-1)
                pal_match = pal[idx]

        if self.na_translate:
            bool_pal_match = pd.isnull(pal_match)
            if len(bool_pal_match.shape) > 1:
                # linetypes take tuples, these return 2d
                bool_pal_match = bool_pal_match.any(axis=1)
            bool_idx = pd.isnull(x) | bool_pal_match
            if bool_idx.any():
                pal_match = [x if i else self.na_value
                             for x, i in zip(pal_match, ~bool_idx)]

        return pal_match

    def get_breaks(self, limits=None, strict=True):
        """
        Return a ordered dictionary of the form {break: position}

        The form is suitable for use by the guides

        e.g.
        {'fair': 1, 'good': 2, 'very good': 3,
        'premium': 4, 'ideal': 5}
        """
        if self.is_empty():
            return []

        if limits is None:
            limits = self.limits

        if self.breaks is None:
            return dict()
        elif is_waive(self.breaks):
            breaks = limits
        elif callable(self.breaks):
            breaks = self.breaks(limits)
        else:
            breaks = self.breaks

        # Breaks can only occur only on values in domain
        if strict:
            in_domain = list(set(breaks) & set(self.limits))
        else:
            in_domain = breaks
        pos = match(in_domain, breaks)
        tups = zip(in_domain, pos)
        return dict(sorted(tups, key=lambda t: t[1]))

    def get_labels(self, breaks=None):
        """
        Generate labels for the legend/guide breaks
        """
        if self.is_empty():
            return []

        if breaks is None:
            breaks = self.get_breaks()

        # The labels depend on the breaks if the breaks are None
        # or are waived, it is likewise for the labels
        if breaks is None or self.labels is None:
            return None
        elif is_waive(breaks):
            return waiver()
        elif is_waive(self.labels):
            # if breaks is a dict (ordered by value)
            #   {'I': 2, 'G': 1, 'P': 3, 'V': 4, 'F': 0}
            # The keys are the labels
            # i.e ['F', 'G', 'I', 'P', 'V']
            try:
                return list(breaks.keys())
            except AttributeError:
                return breaks
        elif callable(self.labels):
            return self.labels(breaks)
        # if a dict is used to rename some labels
        elif isinstance(self.labels, dict):
            labels = breaks
            lookup = list(self.labels.items())
            mp = match(lookup, labels, nomatch=-1)
            for idx in mp:
                if idx != -1:
                    labels[idx] = lookup[idx]
            return labels
        else:
            # TODO: see ggplot2
            # Need to ensure that if breaks were dropped,
            # corresponding labels are too
            return self.labels

    def transform_df(self, df):
        """
        Transform dataframe
        """
        # Discrete scales do not do transformations
        return df

    def transform(self, x):
        """
        Transform array|series x
        """
        # Discrete scales do not do transformations
        return x


@document
class scale_continuous(scale):
    """
    Base class for all continuous scales

    Parameters
    ----------
    {superclass_parameters}
    trans : str | function
        Name of a trans function or a trans function.
        See :mod:`mizani.transforms` for possible options.
    oob : function
        Function to deal with out of bounds (limits)
        data points. Default is to turn them into
        ``np.nan``, which then get dropped.
    minor_breaks : list-like or int or callable or None
        If a list-like, it is the minor breaks points.
        If an integer, it is the number of minor breaks between
        any set of major breaks.
        If a function, it should have the signature
        ``func(limits)`` and return a list-like of consisting
        of the minor break points.
        If ``None``, no minor breaks are calculated.
        The default is to automatically calculate them.
    rescaler : function, optional
        Function to rescale data points so that they can
        be handled by the palette. Default is to rescale
        them onto the [0, 1] range. Scales that inherit
        from this class may have another default.

    Notes
    -----
    If using the class directly all arguments must be
    keyword arguments.
    """
    _range_class = RangeContinuous
    rescaler = staticmethod(rescale)  # Used by diverging & n colour gradients
    oob = staticmethod(censor)     # what to do with out of bounds data points
    minor_breaks = waiver()
    _trans = 'identity'            # transform class

    def __init__(self, **kwargs):
        # Make sure we have a transform.
        self.trans = kwargs.pop('trans', self._trans)

        with suppress(KeyError):
            self.limits = kwargs.pop('limits')

        scale.__init__(self, **kwargs)

    def _check_trans(self, t):
        """
        Check if transform t is valid

        When scales specialise on a specific transform (other than
        the identity transform), the user should know when they
        try to change the transform.

        Parameters
        ----------
        t : mizani.transforms.trans
            Transform object
        """
        orig_trans_name = self.__class__._trans
        new_trans_name = t.__class__.__name__
        if new_trans_name.endswith('_trans'):
            new_trans_name = new_trans_name[:-6]
        if orig_trans_name != 'identity':
            if new_trans_name != orig_trans_name:
                warn(
                    "You have changed the transform of a specialised scale. "
                    "The result may not be what you expect.\n"
                    "Original transform: {}\n"
                    "New transform: {}"
                    .format(orig_trans_name, new_trans_name),
                    PlotnineWarning
                )

    @property
    def trans(self):
        return self._trans

    @trans.setter
    def trans(self, value):
        t = gettrans(value)
        self._check_trans(t)
        self._trans = t
        self._trans.aesthetic = self.aesthetics[0]

    @property
    def limits(self):
        if self.is_empty():
            return (0, 1)

        if self._limits is None:
            return self.range.range
        elif callable(self._limits):
            # Function works in the dataspace, but the limits are
            # stored in transformed space. The range of the scale is
            # in transformed space (i.e. with in the domain of the scale)
            _range = self.trans.inverse(self.range.range)
            return tuple(self.trans.transform(self._limits(_range)))
        elif self._limits is not None and not self.range.is_empty():
            # Fall back to the range if the limits
            # are not set or if any is None or NaN
            if len(self._limits) == len(self.range.range):
                return tuple(
                    self.trans.transform(r) if pd.isnull(l) else l
                    for l, r in zip(self._limits, self.range.range)
                )
        return tuple(self._limits)

    @limits.setter
    def limits(self, value):
        """
        Limits for the continuous scale

        Parameters
        ----------
        value : array-like | callable
            Limits in the dataspace.
        """
        # Notes
        # -----
        # The limits are given in original dataspace
        # but they are stored in transformed space since
        # all computations happen on transformed data. The
        # labeling of the plot axis and the guides are in
        # the original dataspace.
        if callable(value):
            self._limits = value
            return

        limits = tuple(
            self.trans.transform(x) if x is not None else None
            for x in value
        )
        try:
            self._limits = np.sort(limits)
        except TypeError:
            self._limits = limits

    def train(self, x):
        """
        Train scale

        Parameters
        ----------
        x: pd.series | np.array
            a column of data to train over

        """
        if not len(x):
            return

        self.range.train(x)

    def transform_df(self, df):
        """
        Transform dataframe
        """
        if len(df) == 0:
            return

        aesthetics = set(self.aesthetics) & set(df.columns)
        for ae in aesthetics:
            with suppress(TypeError):
                df[ae] = self.transform(df[ae])

        return df

    def transform(self, x):
        """
        Transform array|series x
        """
        try:
            return self.trans.transform(x)
        except TypeError:
            return np.array([self.trans.transform(val) for val in x])

    def inverse(self, x):
        """
        Inverse transform array|series x
        """
        try:
            return self.trans.inverse(x)
        except TypeError:
            return np.array([self.trans.inverse(val) for val in x])

    def dimension(self, expand=(0, 0, 0, 0), limits=None):
        """
        Get the phyical size of the scale

        Unlike limits, this always returns a numeric vector of length 2
        """
        if limits is None:
            limits = self.limits
        return expand_range_distinct(limits, expand)

    def expand_limits(self, limits, expand=None, coord_limits=None,
                      trans=None):
        """
        Calculate the final range in coordinate space
        """
        if limits is None:
            limits = (None, None)

        if coord_limits is None:
            coord_limits = (None, None)

        if trans is None:
            trans = self.trans

        def _expand_range_distinct(x, expand):
            # Expand ascending and descending order range
            if x[0] > x[1]:
                x = expand_range_distinct(x[::-1], expand)[::-1]
            else:
                x = expand_range_distinct(x, expand)
            return x

        # - Override None in coord_limits
        # - Expand limits in coordinate space
        # - Remove any computed infinite values &
        #   fallback on unexpanded limits
        limits = tuple(l if cl is None else cl
                       for cl, l in zip(coord_limits, limits))
        limits_coord_space = trans.transform(limits)
        range_coord = _expand_range_distinct(limits_coord_space, expand)
        with ignore_warnings(RuntimeWarning):
            # Consequences of the runtimewarning (NaNs and infs)
            # are dealt with below
            final_limits = trans.inverse(range_coord)
        final_range = tuple(fl if np.isfinite(fl) else l
                            for fl, l in zip(final_limits, limits))
        ranges = range_view(range=final_range, range_coord=range_coord)
        return ranges

    def view(
        self,
        limits: Optional[tuple[float, float]] = None,
        range: Optional[tuple[float, float]] = None
    ) -> scale_view:
        """
        Information about the trained scale
        """
        if limits is None:
            limits = self.limits

        if range is None:
            range = self.dimension(limits=limits)

        breaks = self.get_breaks(range)
        breaks = breaks.compress(np.isfinite(breaks))
        minor_breaks = self.get_minor_breaks(breaks, range)
        mask = (range[0] <= breaks) & (breaks <= range[1])
        breaks = breaks.compress(mask)
        labels = self.get_labels(breaks, mask)

        if minor_breaks is None:
            minor_breaks = []

        sv = scale_view(
            scale=self,
            aesthetics=self.aesthetics,
            name=self.name,
            limits=limits,
            range=range,
            breaks=breaks,
            labels=labels,
            minor_breaks=minor_breaks

        )
        return sv

    def default_expansion(self, mult=0.05, add=0, expand=True):
        """
        Get the default expansion for continuous scale
        """
        return super().default_expansion(mult, add, expand)

    def map(self, x, limits=None):
        if limits is None:
            limits = self.limits

        x = self.oob(self.rescaler(x, _from=limits))

        uniq = np.unique(x)
        pal = np.asarray(self.palette(uniq))
        scaled = pal[match(x, uniq)]
        if scaled.dtype.kind == 'U':
            scaled = [
                self.na_value if x == 'nan' else x
                for x in scaled
            ]
        else:
            scaled[pd.isnull(scaled)] = self.na_value
        return scaled

    def get_breaks(self, limits=None, strict=False):
        """
        Generate breaks for the axis or legend

        Parameters
        ----------
        limits : list-like | None
            If None the self.limits are used
            They are expected to be in transformed
            space.

        strict : bool
            If True then the breaks gauranteed to fall within
            the limits. e.g. when the legend uses this method.

        Returns
        -------
        out : array-like

        Notes
        -----
        Breaks are calculated in data space and
        returned in transformed space since all
        data is plotted in transformed space.
        """
        if limits is None:
            limits = self.limits

        # To data space
        _limits = self.inverse(limits)

        if self.is_empty():
            breaks = []
        elif self.breaks is None or self.breaks is False:
            breaks = []
        elif zero_range(_limits):
            breaks = [_limits[0]]
        elif is_waive(self.breaks):
            breaks = self.trans.breaks(_limits)
        elif callable(self.breaks):
            breaks = self.breaks(_limits)
        else:
            breaks = self.breaks

        breaks = self.transform(breaks)
        breaks = np.asarray(breaks)
        # At this point, any breaks beyond the limits
        # are kept since they may be used to calculate
        # minor breaks
        if strict:
            cond = (breaks >= limits[0]) & (limits[1] >= breaks)
            breaks = np.compress(cond, breaks)
        return breaks

    def get_minor_breaks(self, major, limits=None):
        """
        Return minor breaks
        """
        if major is None or len(major) == 0:
            return []

        if limits is None:
            limits = self.limits

        if callable(self.minor_breaks):
            breaks = self.minor_breaks(self.trans.inverse(limits))
            _major = set(major)
            minor = self.trans.transform(breaks)
            return [x for x in minor if x not in _major]
        elif isinstance(self.minor_breaks, int):
            res = self.trans.minor_breaks(
                major, limits, n=self.minor_breaks)
            return res
        elif not is_waive(self.minor_breaks):
            return self.trans.transform(self.minor_breaks)
        else:
            return self.trans.minor_breaks(major, limits)

    def get_labels(self, breaks=None, mask=None):
        """
        Generate labels for the axis or legend

        Parameters
        ----------
        breaks: None or array-like
            If None, use self.breaks.
        mask: array[bool]
            Restrict returned labels to those with True
            in mask (used to exclude labels outside of a scale's
            domain even if the user defined them)
        """
        if breaks is None:
            breaks = self.get_breaks()

        breaks = self.inverse(breaks)

        # The labels depend on the breaks if the breaks are None
        # or are waived, it is likewise for the labels
        if breaks is None or self.labels is None:
            return None
        elif is_waive(breaks):
            return waiver()
        elif is_waive(self.labels):
            labels = self.trans.format(breaks)
        elif callable(self.labels):
            labels = self.labels(breaks)
        else:
            if mask is not None:
                labels = np.array(self.labels)[mask]
            else:
                labels = self.labels

        if len(labels) != len(breaks):
            raise PlotnineError(
                "Breaks and labels are different lengths")

        return labels


@document
class scale_datetime(scale_continuous):
    """
    Base class for all date/datetime scales

    Parameters
    ----------
    date_breaks : str
        A string giving the distance between major breaks.
        For example `'2 weeks'`, `'5 years'`. If specified,
        ``date_breaks`` takes precedence over
        ``breaks``.
    date_labels : str
        Format string for the labels.
        See :ref:`strftime <strftime-strptime-behavior>`.
        If specified, ``date_labels`` takes precedence over
        ``labels``.
    date_minor_breaks : str
        A string giving the distance between minor breaks.
        For example `'2 weeks'`, `'5 years'`. If specified,
        ``date_minor_breaks`` takes precedence over
        ``minor_breaks``.
    {superclass_parameters}
    """
    _trans = 'datetime'

    def __init__(self, **kwargs):
        # Permit the use of the general parameters for
        # specifying the format strings
        with suppress(KeyError):
            breaks = kwargs['breaks']
            if isinstance(breaks, str):
                kwargs['breaks'] = date_breaks(breaks)

        with suppress(KeyError):
            minor_breaks = kwargs['minor_breaks']
            if isinstance(minor_breaks, str):
                kwargs['minor_breaks'] = date_breaks(minor_breaks)

        # Using the more specific parameters take precedence
        with suppress(KeyError):
            breaks_fmt = kwargs.pop('date_breaks')
            kwargs['breaks'] = date_breaks(breaks_fmt)

        with suppress(KeyError):
            labels_fmt = kwargs.pop('date_labels')
            kwargs['labels'] = date_format(labels_fmt)

        with suppress(KeyError):
            minor_breaks_fmt = kwargs.pop('date_minor_breaks')
            kwargs['minor_breaks'] = date_breaks(minor_breaks_fmt)

        scale_continuous.__init__(self, **kwargs)
