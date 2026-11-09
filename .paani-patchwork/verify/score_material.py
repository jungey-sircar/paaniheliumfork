"""Scores the screenshots taken by verify_material.ps1.

The chrome band has to be a real material, not the near-black the frame used to
paint: it must be brighter than black, must have texture, and must change when
the window moves to a different part of the desktop. The page below it must not
change at all, because web content is meant to stay opaque.
"""
import os
import sys

from PIL import Image

LOGS = r'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs'
BAND = (100, 4, 900, 100)        # titlebar + tab strip + toolbar
CONTENT = (200, 300, 900, 600)   # inside the page


def stats(path, box):
    im = Image.open(path).convert('RGB')
    px = list(im.crop(box).getdata())
    n = len(px)
    mean = tuple(round(sum(c[i] for c in px) / n, 1) for i in range(3))
    var = [round((sum((c[i] - mean[i]) ** 2 for c in px) / n) ** 0.5, 1)
           for i in range(3)]
    return im, mean, var, len(set(px))


def mean_abs_delta(path_a, path_b, box):
    a = list(Image.open(path_a).convert('RGB').crop(box).getdata())
    b = list(Image.open(path_b).convert('RGB').crop(box).getdata())
    total = sum(abs(x[i] - y[i]) for x, y in zip(a, b) for i in range(3))
    return round(total / (len(a) * 3), 2)


def main():
    a = os.path.join(LOGS, 'material_pos_a.png')
    b = os.path.join(LOGS, 'material_pos_b.png')
    for path in (a, b):
        if not os.path.exists(path):
            print(f'FAIL missing {path}')
            return 1

    _, band_mean_a, band_var_a, band_uniq_a = stats(a, BAND)
    _, band_mean_b, band_var_b, band_uniq_b = stats(b, BAND)
    _, content_mean_a, _, _ = stats(a, CONTENT)
    content_delta = mean_abs_delta(a, b, CONTENT)
    band_delta = mean_abs_delta(a, b, BAND)

    print(f'band A mean={band_mean_a} spread={band_var_a} distinct={band_uniq_a}')
    print(f'band B mean={band_mean_b} spread={band_var_b} distinct={band_uniq_b}')
    print(f'content A mean={content_mean_a} content move delta={content_delta}')
    print(f'band move delta={band_delta}')

    checks = [
        ('band is not near-black', min(band_mean_a) > 8.0 and min(band_mean_b) > 8.0),
        ('band has texture, not one flat colour', max(band_var_a + band_var_b) > 3.0),
        ('band follows the desktop', band_delta > 2.0),
        ('web content stays opaque', content_delta < 2.0),
        ('content is the page, not the material', min(content_mean_a) > 60.0),
    ]
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f'{"PASS" if ok else "FAIL"}  {name}')
    print('MATERIAL VERDICT: ' + ('PASS' if not failed else 'FAIL ' + str(failed)))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
