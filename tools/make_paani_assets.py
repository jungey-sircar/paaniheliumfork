#!/usr/bin/env python
"""Paani brand asset generator.

Produces every asset the Chromium theme expects, at the same sizes and formats
as the upstream Helium branding so that the resource list can be reused
verbatim with different paths:

    app_icon/raw.png                 1024x1024  application icon source
    app_icon/file.png                 512x512   document / file icon
    product_logo.png                  140x32     wordmark, dark
    product_logo_white.png            140x32     wordmark, light
    product_logo_200.png              280x64     wordmark, dark, 200%
    product_logo_white_200.png        280x64     wordmark, light, 200%
    product_logo_22_mono.png           22x22     monochrome mark
    product_logo.svg                  256x256    application icon, vector
    product_logo.icon                  56x56     monochrome vector mark
    product_logo_color.icon           256x256    colour vector icon

The mark is a droplet whose base is a single wave: "paani" means water, and
the wave keeps the silhouette readable down to 16 px, where the wave amplitude
falls below a pixel and the mark degrades to a clean droplet.
"""

import argparse
import math
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------- palette ---
GRADIENT_TOP = (0x35, 0xC5, 0xD8)
GRADIENT_BOTTOM = (0x0B, 0x5F, 0x92)
MARK_LIGHT = (0xFF, 0xFF, 0xFF)
WORDMARK_INK = (0x0A, 0x5D, 0x8C)

SS = 8  # supersampling factor for anti-aliasing
WAVE_AMPLITUDE = 12.0
WAVE_LOBES = 1.0


# ------------------------------------------------------------- geometry ----
def cubic(p0, p1, p2, p3, steps=40):
    """Points along a cubic Bezier."""
    out = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        out.append((
            u * u * u * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t * t * t * p3[0],
            u * u * u * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t * t * t * p3[1],
        ))
    return out


def wave_edge(x0, x1, base_y, amplitude, lobes, steps=48):
    """A single wave spanning x0..x1, dipping below base_y in the middle."""
    pts = []
    for i in range(steps + 1):
        x = x0 + (x1 - x0) * i / steps
        phase = math.pi * lobes * (x - x0) / (x1 - x0)
        pts.append((x, base_y + amplitude * math.sin(phase)))
    return pts


def mark_path():
    """Closed outline of the Paani mark in the 256x256 unit square."""
    apex = (128.0, 26.0)
    left = (62.0, 150.0)
    right = (194.0, 150.0)

    pts = []
    pts += cubic(apex, (126.0, 92.0), (62.0, 102.0), left)
    pts += wave_edge(62.0, 194.0, 150.0, WAVE_AMPLITUDE, WAVE_LOBES)
    pts += cubic(right, (194.0, 102.0), (130.0, 92.0), apex)
    return pts


def mark_bbox():
    xs = [p[0] for p in mark_path()]
    ys = [p[1] for p in mark_path()]
    return min(xs), min(ys), max(xs), max(ys)


# -------------------------------------------------------------- rendering --
def rounded_square_mask(size, radius_ratio=67.0 / 256.0):
    mask = Image.new('L', (size * SS, size * SS), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size * SS - 1, size * SS - 1],
        radius=radius_ratio * size * SS,
        fill=255)
    return mask.resize((size, size), Image.LANCZOS)


def gradient_image(size):
    """Vertical gradient, returned at the requested pixel size."""
    column = Image.new('RGB', (1, size))
    px = column.load()
    for y in range(size):
        t = y / max(1, size - 1)
        px[0, y] = tuple(
            int(round(GRADIENT_TOP[i] + (GRADIENT_BOTTOM[i] - GRADIENT_TOP[i]) * t))
            for i in range(3))
    return column.resize((size, size), Image.BILINEAR)


def render_mark_mask(size):
    """Anti-aliased coverage mask of the mark silhouette."""
    big = size * SS
    layer = Image.new('L', (big, big), 0)
    ImageDraw.Draw(layer).polygon(
        [(x / 256.0 * big, y / 256.0 * big) for x, y in mark_path()], fill=255)
    return layer.resize((size, size), Image.LANCZOS)


def render_mark(size, colour=MARK_LIGHT):
    """Mark silhouette in a single colour on a transparent background."""
    img = Image.new('RGBA', (size, size), colour + (0,))
    img.putalpha(render_mark_mask(size))
    return img


def render_mark_gradient(size):
    """Mark silhouette filled with the brand gradient."""
    img = gradient_image(size).convert('RGBA')
    img.putalpha(render_mark_mask(size))
    return img


def render_app_icon(size):
    icon = gradient_image(size).convert('RGBA')
    icon.putalpha(rounded_square_mask(size))
    mark_size = int(round(size * 0.62))
    mark = render_mark(mark_size)
    offset = (size - mark_size) // 2
    icon.alpha_composite(mark, (offset, offset))
    return icon


def render_wordmark(width, height, colour=WORDMARK_INK, mark=None, word='Paani'):
    """Mark plus wordmark, scaled to the requested box."""
    img = Image.new('RGBA', (width * SS, height * SS), (0, 0, 0, 0))
    mark_size = int(height * SS * 0.92)
    if mark is None:
        mark = render_mark(mark_size, MARK_LIGHT)
    else:
        mark = mark.resize((mark_size, mark_size), Image.LANCZOS)
    img.alpha_composite(mark, (0, (height * SS - mark_size) // 2))

    text_x = int(mark_size * 1.16)
    font_path = r'C:\Windows\Fonts\seguisb.ttf'
    if not os.path.exists(font_path):
        font_path = r'C:\Windows\Fonts\segoeuib.ttf'
    font = ImageFont.truetype(font_path, int(height * SS * 0.60))
    d = ImageDraw.Draw(img)
    box = d.textbbox((0, 0), word, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    d.text((text_x - box[0], (height * SS - th) / 2 - box[1]),
           word, font=font, fill=colour + (255,))
    return img.resize((width, height), Image.LANCZOS)


def on_light(img):
    """Composite an RGBA image over white."""
    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
    bg.alpha_composite(img)
    return bg.convert('RGB')


# ------------------------------------------------------------ vector form --
def fmt(v):
    return f'{v:.2f}'.rstrip('0').rstrip('.')


def svg_mark_path():
    """The mark outline as an SVG path, with the flanks kept as cubics."""
    apex = (128.0, 26.0)
    left = (62.0, 150.0)

    parts = [f'M {fmt(apex[0])} {fmt(apex[1])}',
             f'C {fmt(126.0)} {fmt(92.0)} {fmt(62.0)} {fmt(102.0)} '
             f'{fmt(left[0])} {fmt(left[1])}']
    wave = wave_edge(62.0, 194.0, 150.0, WAVE_AMPLITUDE, WAVE_LOBES)
    parts.append('L ' + ' L '.join(f'{fmt(x)} {fmt(y)}' for x, y in wave[1:]))
    parts.append(f'C {fmt(194.0)} {fmt(102.0)} {fmt(130.0)} {fmt(92.0)} '
                 f'{fmt(apex[0])} {fmt(apex[1])}')
    parts.append('Z')
    return ' '.join(parts)


def render_svg():
    grad_top = '#%02X%02X%02X' % GRADIENT_TOP
    grad_bottom = '#%02X%02X%02X' % GRADIENT_BOTTOM
    mark_light = '#%02X%02X%02X' % MARK_LIGHT
    path = svg_mark_path()
    return f'''<svg width="256" height="256" viewBox="0 0 256 256" fill="none" xmlns="http://www.w3.org/2000/svg">
<defs>
<linearGradient id="paani" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="256">
<stop offset="0" stop-color="{grad_top}"/>
<stop offset="1" stop-color="{grad_bottom}"/>
</linearGradient>
</defs>
<rect width="256" height="256" rx="67" fill="url(#paani)"/>
<path d="{path}" fill="{mark_light}"/>
</svg>
'''


def icon_commands(canvas, scale, dx, dy, background=None, foreground=None):
    """Vector icon drawing commands for the mark.

    Chromium's vector icon parser reads a fixed number of arguments per
    command (see gfx::GetCommandArgumentCount), so every curve has to be
    written as a single CUBIC_TO line carrying all three control points.
    """
    apex = (128.0, 26.0)
    left = (62.0, 150.0)
    right = (194.0, 150.0)

    def pt(p):
        return fmt(p[0] * scale + dx), fmt(p[1] * scale + dy)

    def cubic_line(p1, p2, p3):
        a = pt(p1) + pt(p2) + pt(p3)
        return 'CUBIC_TO, ' + ', '.join(a) + ','

    lines = [f'CANVAS_DIMENSIONS, {canvas},']
    if background:
        lines.append('NEW_PATH,')
        lines.append('PATH_COLOR_ARGB, 0x%02X, 0x%02X, 0x%02X, 0x%02X,' % background)
        lines.append('ROUND_RECT, 0, 0, %d, %d, %d,' % (canvas, canvas, canvas * 67 // 256))
        lines.append('NEW_PATH,')
    lines.append('FILL_RULE_NONZERO,')
    if foreground:
        lines.append('PATH_COLOR_ARGB, 0x%02X, 0x%02X, 0x%02X, 0x%02X,' % foreground)
    x, y = pt(apex)
    lines.append(f'MOVE_TO, {x}, {y},')
    lines.append(cubic_line((126.0, 92.0), (62.0, 102.0), left))
    wave = wave_edge(62.0, 194.0, 150.0, WAVE_AMPLITUDE, WAVE_LOBES)
    for p in wave[1:-1]:
        x, y = pt(p)
        lines.append(f'LINE_TO, {x}, {y},')
    lines.append(cubic_line((194.0, 102.0), (130.0, 92.0), apex))
    lines.append('CLOSE,')
    return '\n'.join(lines) + '\n'


def render_icon_file(mono=True):
    """Chromium .icon vector source (the format is plain C-like text)."""
    header = ('// Copyright 2026 The Paani Authors\n'
              '// You can use, redistribute, and/or modify this source code under\n'
              '// the terms of the GPL-3.0 license that can be found in the LICENSE file.\n\n')
    if mono:
        x0, y0, x1, y1 = mark_bbox()
        scale = 52.0 / (y1 - y0)
        dx = (56.0 - (x1 - x0) * scale) / 2.0 - x0 * scale
        dy = 2.0 - y0 * scale
        body = icon_commands(56, scale, dx, dy)
    else:
        body = icon_commands(256, 1.0, 0.0, 0.0,
                             background=(0xFF,) + GRADIENT_BOTTOM,
                             foreground=(0xFF,) + MARK_LIGHT)
    return header + body


# ------------------------------------------------------------------ main ---
def generate(out_dir):
    out = Path(out_dir)
    (out / 'app_icon').mkdir(parents=True, exist_ok=True)

    render_app_icon(1024).save(out / 'app_icon' / 'raw.png')
    render_app_icon(512).save(out / 'app_icon' / 'file.png')
    render_app_icon(128).save(out / 'app_icon' / 'favicon.png')
    render_wordmark(140, 32, WORDMARK_INK,
                    mark=render_mark_gradient(29)).save(out / 'product_logo.png')
    render_wordmark(140, 32, MARK_LIGHT).save(out / 'product_logo_white.png')
    render_wordmark(280, 64, WORDMARK_INK,
                    mark=render_mark_gradient(58)).save(out / 'product_logo_200.png')
    render_wordmark(280, 64, MARK_LIGHT).save(out / 'product_logo_white_200.png')
    render_mark(22, (0, 0, 0)).save(out / 'product_logo_22_mono.png')
    (out / 'product_logo.svg').write_text(render_svg(), encoding='utf-8')
    (out / 'product_logo.icon').write_text(render_icon_file(mono=True), encoding='utf-8')
    (out / 'product_logo_color.icon').write_text(render_icon_file(mono=False), encoding='utf-8')
    print(f'wrote {out}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    generate(args.out)


if __name__ == '__main__':
    main()
