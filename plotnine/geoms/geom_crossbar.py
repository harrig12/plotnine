from __future__ import annotations

import typing
from warnings import warn

import matplotlib.lines as mlines
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

from ..doctools import document
from ..exceptions import PlotnineWarning
from ..utils import SIZE_FACTOR, copy_missing_columns, resolution, to_rgba
from .geom import geom
from .geom_polygon import geom_polygon
from .geom_segment import geom_segment

if typing.TYPE_CHECKING:
    from typing import Any

    import matplotlib as mpl
    import numpy.typing as npt

    import plotnine as p9


@document
class geom_crossbar(geom):
    """
    Vertical interval represented by a crossbar

    {usage}

    Parameters
    ----------
    {common_parameters}
    width : float or None, optional (default: 0.5)
        Box width. If :py:`None`, the width is set to
        `90%` of the resolution of the data.
    fatten : float, optional (default: 2)
        A multiplicative factor used to increase the size of the
        middle bar across the box.
    """
    DEFAULT_AES = {'alpha': 1, 'color': 'black', 'fill': None,
                   'linetype': 'solid', 'size': 0.5}
    REQUIRED_AES = {'x', 'y', 'ymin', 'ymax'}
    DEFAULT_PARAMS = {'stat': 'identity', 'position': 'identity',
                      'na_rm': False, 'width': 0.5, 'fatten': 2}

    def setup_data(self, data: pd.DataFrame) -> pd.DataFrame:
        if 'width' not in data:
            if self.params['width']:
                data['width'] = self.params['width']
            else:
                data['width'] = resolution(data['x'], False) * 0.9

        data['xmin'] = data['x'] - data['width']/2
        data['xmax'] = data['x'] + data['width']/2
        del data['width']
        return data

    @staticmethod
    def draw_group(
        data: pd.DataFrame,
        panel_params: p9.iapi.panel_view,
        coord: p9.coords.coord.coord,
        ax: mpl.axes.Axes,
        **params: Any
    ) -> None:
        y = data['y']
        xmin = data['xmin']
        xmax = data['xmax']
        ymin = data['ymin']
        ymax = data['ymax']
        group = data['group']

        # From violin
        notchwidth = typing.cast(float, params.get('notchwidth'))
        # ynotchupper = data.get('ynotchupper')
        # ynotchlower = data.get('ynotchlower')

        def flat(*args: pd.Series[Any]) -> npt.NDArray[Any]:
            """Flatten list-likes"""
            return np.hstack(args)

        middle = pd.DataFrame({'x': xmin,
                               'y': y,
                               'xend': xmax,
                               'yend': y,
                               'group': group})
        copy_missing_columns(middle, data)
        middle['alpha'] = 1
        middle['size'] *= params['fatten']

        has_notch = 'ynotchupper' in data and 'ynotchlower' in data
        if has_notch:  # 10 points + 1 closing
            ynotchupper = data['ynotchupper']
            ynotchlower = data['ynotchlower']

            if (any(ynotchlower < ymin) or any(ynotchupper > ymax)):
                warn("Notch went outside the hinges. "
                     "Try setting notch=False.", PlotnineWarning)

            notchindent = (1 - notchwidth) * (xmax-xmin)/2

            middle['x'] += notchindent
            middle['xend'] -= notchindent
            box = pd.DataFrame({
                'x': flat(xmin, xmin, xmin+notchindent, xmin, xmin,
                          xmax, xmax, xmax-notchindent, xmax, xmax,
                          xmin),
                'y': flat(ymax, ynotchupper, y, ynotchlower, ymin,
                          ymin, ynotchlower, y, ynotchupper, ymax,
                          ymax),
                'group': np.tile(np.arange(1, len(group)+1), 11)})
        else:
            # No notch, 4 points + 1 closing
            box = pd.DataFrame({
                'x': flat(xmin, xmin, xmax, xmax, xmin),
                'y': flat(ymax, ymax, ymax, ymin, ymin),
                'group': np.tile(np.arange(1, len(group)+1), 5)})

        copy_missing_columns(box, data)
        geom_polygon.draw_group(box, panel_params, coord, ax, **params)
        geom_segment.draw_group(middle, panel_params, coord, ax, **params)

    @staticmethod
    def draw_legend(
        data: pd.Series[Any],
        da: mpl.patches.DrawingArea,
        lyr: p9.layer.layer
    ) -> mpl.patches.DrawingArea:
        """
        Draw a rectangle with a horizontal strike in the box

        Parameters
        ----------
        data : Series
            Data Row
        da : DrawingArea
            Canvas
        lyr : layer
            Layer

        Returns
        -------
        out : DrawingArea
        """
        data['size'] *= SIZE_FACTOR

        # background
        facecolor = to_rgba(data['fill'], data['alpha'])
        if facecolor is None:
            facecolor = 'none'

        bg = Rectangle((da.width*.125, da.height*.25),
                       width=da.width*.75,
                       height=da.height*.5,
                       linewidth=data['size'],
                       facecolor=facecolor,
                       edgecolor=data['color'],
                       linestyle=data['linetype'],
                       capstyle='projecting',
                       antialiased=False)
        da.add_artist(bg)

        strike = mlines.Line2D([da.width*.125, da.width*.875],
                               [da.height*.5, da.height*.5],
                               linestyle=data['linetype'],
                               linewidth=data['size'],
                               color=data['color'])
        da.add_artist(strike)
        return da
