#!/usr/bin/env python
"""Validate and preview Chromium vector icon (.icon) files.

Chromium parses .icon files at runtime in gfx::ParsePathElements: every line
is split on ", ", comments are dropped, and each command consumes a fixed
number of arguments (gfx::GetCommandArgumentCount).  A file whose argument
counts do not match still compiles, because the aggregation script only
embeds the text -- it renders as garbage at runtime instead.

This script reproduces that parser, checks the argument counts, and can
render the result to a PNG so the geometry can be inspected.
"""

import argparse
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

# gfx::GetCommandArgumentCount, ui/gfx/vector_icon_utils.cc
ARG_COUNTS = {
    'STROKE': 1,
    'H_LINE_TO': 1,
    'R_H_LINE_TO': 1,
    'V_LINE_TO': 1,
    'R_V_LINE_TO': 1,
    'CANVAS_DIMENSIONS': 1,
    'PATH_COLOR_ALPHA': 1,
    'MOVE_TO': 2,
    'R_MOVE_TO': 2,
    'LINE_TO': 2,
    'R_LINE_TO': 2,
    'QUADRATIC_TO_SHORTHAND': 2,
    'R_QUADRATIC_TO_SHORTHAND': 2,
    'CIRCLE': 3,
    'PATH_COLOR_ARGB': 4,
    'CUBIC_TO_SHORTHAND': 4,
    'CLIP': 4,
    'QUADRATIC_TO': 4,
    'R_QUADRATIC_TO': 4,
    'OVAL': 4,
    'ROUND_RECT': 5,
    'CUBIC_TO': 6,
    'R_CUBIC_TO': 6,
    'ARC_TO': 7,
    'R_ARC_TO': 7,
    'FILL_RULE_NONZERO': 0,
    'NEW_PATH': 0,
    'PATH_MODE_CLEAR': 0,
    'CAP_SQUARE': 0,
    'CLOSE': 0,
    'DISABLE_AA': 0,
    'FLIPS_IN_RTL': 0,
}


class IconError(Exception):
    pass


def parse(path):
    """Return (canvas_size, [paths]) where each path is a list of commands."""
    text = Path(path).read_text(encoding='utf-8')
    canvas = None
    paths = []
    current = None
    for lineno, line in enumerate(text.split('\n'), 1):
        line = line.strip()
        if not line or line.startswith('//'):
            continue
        parts = [p.strip() for p in line.split(',') if p.strip()]
        name = parts[0]
        if name not in ARG_COUNTS:
            raise IconError(f'{path}:{lineno}: unknown command {name!r}')
        args = parts[1:]
        if len(args) != ARG_COUNTS[name]:
            raise IconError(
                f'{path}:{lineno}: {name} expects {ARG_COUNTS[name]} arguments, '
                f'got {len(args)}')
        values = []
        for a in args:
            if a.startswith('0x'):
                values.append(float(int(a, 16)))
            else:
                values.append(float(a.rstrip('f')))
        if name == 'CANVAS_DIMENSIONS':
            canvas = int(values[0])
            paths.append([])
            current = paths[-1]
            continue
        if current is None or name == 'NEW_PATH':
            paths.append([])
            current = paths[-1]
        current.append((name, values))
    if canvas is None:
        raise IconError(f'{path}: no CANVAS_DIMENSIONS')
    return canvas, paths


def flatten(paths):
    """Turn the command list into drawable sub-paths.

    Returns a list of (kind, points, colour) tuples, where kind is 'poly' for
    a filled polygon or 'round_rect' for a rounded rectangle.
    """
    out = []
    for cmds in paths:
        colour = None
        points = []
        cur = (0.0, 0.0)
        start = (0.0, 0.0)
        round_rect = None
        for name, v in cmds:
            if name == 'PATH_COLOR_ARGB':
                colour = tuple(int(c) for c in v)
            elif name == 'ROUND_RECT':
                round_rect = v
            elif name == 'MOVE_TO':
                cur = (v[0], v[1])
                start = cur
                points.append(cur)
            elif name == 'LINE_TO':
                cur = (v[0], v[1])
                points.append(cur)
            elif name == 'CUBIC_TO':
                p1 = (v[0], v[1])
                p2 = (v[2], v[3])
                p3 = (v[4], v[5])
                for i in range(1, 17):
                    t = i / 16.0
                    u = 1.0 - t
                    points.append((
                        u * u * u * cur[0] + 3 * u * u * t * p1[0]
                        + 3 * u * t * t * p2[0] + t * t * t * p3[0],
                        u * u * u * cur[1] + 3 * u * u * t * p1[1]
                        + 3 * u * t * t * p2[1] + t * t * t * p3[1]))
                cur = p3
            elif name == 'CLOSE':
                points.append(start)
        if round_rect is not None:
            out.append(('round_rect', round_rect, colour))
        elif len(points) > 1:
            out.append(('poly', points, colour))
    return out


def render(paths, size=256, background=(255, 255, 255)):
    canvas, cmds = paths
    scale = size / canvas
    img = Image.new('RGB', (size, size), background)
    d = ImageDraw.Draw(img)
    for kind, geom, colour in flatten(cmds):
        rgba = tuple(int(c) for c in (colour or (255, 0, 0, 0)))
        fill = (rgba[1], rgba[2], rgba[3])
        if kind == 'round_rect':
            x, y, w, h, r = geom
            d.rounded_rectangle([x * scale, y * scale,
                                 (x + w) * scale, (y + h) * scale],
                                radius=r * scale, fill=fill)
        else:
            d.polygon([(px * scale, py * scale) for px, py in geom], fill=fill)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('icons', nargs='+')
    ap.add_argument('--preview', help='write a PNG preview here')
    ap.add_argument('--size', type=int, default=256)
    args = ap.parse_args()

    failed = False
    for icon in args.icons:
        try:
            canvas, cmds = parse(icon)
            n = sum(len(c) for c in cmds)
            print(f'OK   {icon}: canvas {canvas}, {len(cmds)} path(s), {n} commands')
            if args.preview:
                render((canvas, cmds), args.size).save(args.preview)
        except IconError as exc:
            failed = True
            print(f'FAIL {exc}', file=sys.stderr)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
