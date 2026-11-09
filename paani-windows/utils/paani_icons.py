#!/usr/bin/env python3

"""Generates the Paani waterdrop branding assets.

The Paani identity is a waterdrop.  This module derives every asset the
Chromium theme and the Windows installer need from one master image:

  * the master 1024x1024 image (app_icon/raw.png),
  * the scaled PNGs the GRIT resources ask for (product_logo_16 ... 256),
  * the wordmarks (product_logo.png and the _200/@2x variant, in colour and
    in white),
  * the monochrome 22x22 tab icon,
  * real multi-resolution .ico files for chrome.exe, chrome.dll, setup.exe
    and mini_installer.exe.

The .ico files are written here rather than by the upstream
generate_resources.py, because that helper only rescales PNGs and would
leave a PNG under an .ico name, which the Windows resource compiler refuses
to embed.

Usage:
    python paani_icons.py <master.png> <branding_dir> <generated_dir>
"""

import os
import sys

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Sizes the Chromium theme asks for.
THEME_SIZES = (16, 24, 32, 48, 64, 128, 256)

# Sizes Windows expects in an .ico.
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256)

WORDMARK_TEXT = 'Paani'
WORDMARK_SIZE = (140, 32)

# The waterdrop as a vector path in Chromium's .icon format (56x56 canvas).
# The .icon files are recoloured by the UI, so the shape carries no colour.
DROPPATH_ICON = """// Copyright 2026 The Paani Authors
// You can use, redistribute, and/or modify this source code under
// the terms of the GPL-3.0 license that can be found in the LICENSE file.

CANVAS_DIMENSIONS, 56,
FILL_RULE_NONZERO,
MOVE_TO, 28, 2,
CUBIC_TO, 24.5f, 13.5f, 9.5f, 24.5f, 8.5f, 34,
CUBIC_TO, 7.5f, 45.5f, 16.5f, 54, 28, 54,
CUBIC_TO, 39.5f, 54, 48.5f, 45.5f, 47.5f, 34,
CUBIC_TO, 46.5f, 24.5f, 31.5f, 13.5f, 28, 2,
"""

DROPPATH_COLOR_ICON = """// Copyright 2026 The Paani Authors
// You can use, redistribute, and/or modify this source code under
// the terms of the GPL-3.0 license that can be found in the LICENSE file.

CANVAS_DIMENSIONS, 56,
FILL_RULE_NONZERO,
PATH_COLOR_ARGB, 0xFF, 0x1B, 0x7F, 0xD4,
MOVE_TO, 28, 2,
CUBIC_TO, 24.5f, 13.5f, 9.5f, 24.5f, 8.5f, 34,
CUBIC_TO, 7.5f, 45.5f, 16.5f, 54, 28, 54,
CUBIC_TO, 39.5f, 54, 48.5f, 45.5f, 47.5f, 34,
CUBIC_TO, 46.5f, 24.5f, 31.5f, 13.5f, 28, 2,
"""

DROPPATH_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 56 56"
     width="56" height="56">
  <defs>
    <linearGradient id="paani-drop" x1="0.2" y1="0.1" x2="0.8" y2="0.95">
      <stop offset="0" stop-color="#4fe3ff"/>
      <stop offset="0.45" stop-color="#25b6f2"/>
      <stop offset="1" stop-color="#1236c9"/>
    </linearGradient>
  </defs>
  <path fill="url(#paani-drop)"
        d="M28 2C24.5 13.5 9.5 24.5 8.5 34 7.5 45.5 16.5 54 28 54s19.5-8.5 19.5-20C46.5 24.5 31.5 13.5 28 2Z"/>
  <path fill="#ffffff" fill-opacity="0.45"
        d="M23 12c-4.5 6.4-9.5 13.6-10.6 19.6 1.6-4.6 5.2-10 9-14.6Z"/>
</svg>
"""


def _square_master(master):
    """Crops the master to its opaque content and centres it on a square."""
    image = Image.open(master).convert('RGBA')
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)
    side = max(image.size)
    canvas = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    margin = int(side * 0.06)
    inner = side - 2 * margin
    canvas = canvas.resize((inner, inner), Image.LANCZOS)
    out = Image.new('RGBA', (side, side), (0, 0, 0, 0))
    out.paste(canvas, (margin, margin))
    return out


def _font(size):
    for name in ('segoeuib.ttf', 'arialbd.ttf', 'segoeui.ttf'):
        path = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Fonts' / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _wordmark(master, scale, colour, text_colour):
    """Builds the Paani wordmark: a waterdrop followed by the name."""
    width, height = WORDMARK_SIZE
    width *= scale
    height *= scale
    drop_size = int(height * 0.92)
    drop = master.resize((drop_size, drop_size), Image.LANCZOS)
    if colour is not None:
        alpha = drop.getchannel('A')
        solid = Image.new('RGBA', drop.size, colour)
        solid.putalpha(alpha)
        drop = solid

    canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    canvas.paste(drop, (0, (height - drop_size) // 2), drop)

    font = _font(int(height * 0.78))
    draw = ImageDraw.Draw(canvas)
    text_x = int(drop_size * 1.12)
    box = draw.textbbox((0, 0), WORDMARK_TEXT, font=font)
    text_h = box[3] - box[1]
    draw.text((text_x, (height - text_h) // 2 - box[1]), WORDMARK_TEXT,
              font=font, fill=text_colour)
    return canvas


def _document_icon(master, size):
    """A page with the Paani waterdrop on it."""
    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    page = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(page)
    margin = int(size * 0.12)
    draw.rounded_rectangle(
        [margin, margin * 0.7, size - margin, size - margin * 0.7],
        radius=int(size * 0.05), fill=(255, 255, 255, 255),
        outline=(196, 206, 222, 255), width=max(1, size // 64))
    drop = master.resize((int(size * 0.44), int(size * 0.44)), Image.LANCZOS)
    canvas.paste(page, (0, 0), page)
    canvas.paste(drop, ((size - drop.width) // 2, (size - drop.height) // 2), drop)
    return canvas


def _mono_icon(master, size):
    """The 22x22 monochrome tab icon: the waterdrop silhouette."""
    alpha = master.getchannel('A')
    silhouette = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    silhouette.putalpha(alpha.resize((size, size), Image.LANCZOS))
    return silhouette


def _write_ico(image, path, sizes):
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(str(path), format='ICO', sizes=[(s, s) for s in sizes])


def generate(master_path, branding_dir, generated_dir):
    """Regenerates every Paani branding asset from the master image."""
    branding = Path(branding_dir)
    generated = Path(generated_dir)
    branding.mkdir(parents=True, exist_ok=True)
    generated.mkdir(parents=True, exist_ok=True)

    master = _square_master(master_path)

    app_icon = branding / 'app_icon'
    app_icon.mkdir(parents=True, exist_ok=True)
    master.save(str(app_icon / 'raw.png'), optimize=True)
    master.resize((128, 128), Image.LANCZOS).save(
        str(app_icon / 'favicon.png'), optimize=True)
    document = _document_icon(master, 512)
    document.save(str(app_icon / 'file.png'), optimize=True)

    # The GRIT theme wants the master at these exact sizes.
    icon_dir = generated / 'product_icon'
    icon_dir.mkdir(parents=True, exist_ok=True)
    for size in THEME_SIZES:
        master.resize((size, size), Image.LANCZOS).save(
            str(icon_dir / ('%dx%d.png' % (size, size))), optimize=True)

    # Wordmarks.
    dark = (32, 33, 36, 255)
    white = (255, 255, 255, 255)
    _wordmark(master, 1, None, dark).save(
        str(branding / 'product_logo.png'), optimize=True)
    _wordmark(master, 2, None, dark).save(
        str(branding / 'product_logo_200.png'), optimize=True)
    _wordmark(master, 1, white, white).save(
        str(branding / 'product_logo_white.png'), optimize=True)
    _wordmark(master, 2, white, white).save(
        str(branding / 'product_logo_white_200.png'), optimize=True)

    _mono_icon(master, 22).save(
        str(branding / 'product_logo_22_mono.png'), optimize=True)

    # Vector assets.
    (branding / 'product_logo.icon').write_text(DROPPATH_ICON, encoding='utf-8')
    (branding / 'product_logo_color.icon').write_text(
        DROPPATH_COLOR_ICON, encoding='utf-8')
    (branding / 'product_logo.svg').write_text(DROPPATH_SVG, encoding='utf-8')

    # Real multi-resolution icons for the executables.
    _write_ico(master, generated / 'app.ico', ICON_SIZES)
    _write_ico(document, generated / 'document.ico', ICON_SIZES)

    print('Paani icons generated from %s' % master_path)


def main():
    if len(sys.argv) != 4:
        print('Usage: python paani_icons.py <master.png> <branding_dir> '
              '<generated_dir>')
        return 1
    generate(sys.argv[1], sys.argv[2], sys.argv[3])
    return 0


if __name__ == '__main__':
    sys.exit(main())
