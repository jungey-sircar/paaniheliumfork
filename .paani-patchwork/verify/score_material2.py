"""Scores the three captures taken by verify_material2.ps1.

A is one spot on the desktop, B another spot, C back at A's spot.  Only a real
material changes with position and then comes back when the position comes
back; a page still rendering, an animation, or a colour that is simply painted
flat cannot do both.  Web contents must not change at all, because Paani keeps
them opaque.
"""
import os
import sys

from PIL import Image

LOGS = r'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\verify\logs'
BAND = (60, 2, 960, 78)         # titlebar + tab strip + toolbar row
CONTENT = (200, 300, 900, 600)  # inside the page


def region(path, box):
    crop = Image.open(path).convert('RGB').crop(box)
    if hasattr(crop, 'get_flattened_data'):
        return list(crop.get_flattened_data())
    return list(crop.getdata())


def stats(px):
    n = len(px)
    mean = tuple(round(sum(c[i] for c in px) / n, 1) for i in range(3))
    spread = [round((sum((c[i] - mean[i]) ** 2 for c in px) / n) ** 0.5, 1)
              for i in range(3)]
    return mean, spread, len(set(px))


def mean_abs_delta(a, b):
    total = sum(abs(x[i] - y[i]) for x, y in zip(a, b) for i in range(3))
    return round(total / (len(a) * 3), 2)


def main():
    paths = {k: os.path.join(LOGS, f'material2_{k}.png') for k in 'abc'}
    missing = [p for p in paths.values() if not os.path.exists(p)]
    if missing:
        print('FAIL missing', missing)
        return 1

    band = {k: region(paths[k], BAND) for k in 'abc'}
    content = {k: region(paths[k], CONTENT) for k in 'abc'}

    for k in 'abc':
        mean, spread, uniq = stats(band[k])
        print(f'band {k.upper()}: mean={mean} spread={spread} distinct={uniq}')
    for k in 'abc':
        mean, spread, uniq = stats(content[k])
        print(f'content {k.upper()}: mean={mean} spread={spread} distinct={uniq}')

    band_ab = mean_abs_delta(band['a'], band['b'])
    band_ac = mean_abs_delta(band['a'], band['c'])
    content_ab = mean_abs_delta(content['a'], content['b'])
    content_ac = mean_abs_delta(content['a'], content['c'])
    print(f'band delta A-B={band_ab} A-C={band_ac}')
    print(f'content delta A-B={content_ab} A-C={content_ac}')

    _, band_spread_a, _ = stats(band['a'])
    _, band_spread_b, _ = stats(band['b'])
    band_mean_a, _, _ = stats(band['a'])
    band_mean_b, _, _ = stats(band['b'])
    content_mean_a, _, _ = stats(content['a'])

    checks = [
        ('chrome band is not near-black',
         min(band_mean_a) > 8.0 and min(band_mean_b) > 8.0),
        ('chrome band has texture, not one flat colour',
         max(band_spread_a + band_spread_b) > 3.0),
        ('chrome band changes with desktop position', band_ab > 2.0),
        ('chrome band returns to A when the window returns', band_ac < 2.0),
        ('web contents do not move with position',
         content_ab < 2.0 and content_ac < 2.0),
        ('contents are the loaded page, not a blank surface',
         max(content_mean_a) > 40.0),
    ]
    failed = [name for name, ok in checks if not ok]
    for name, ok in checks:
        print(f'{"PASS" if ok else "FAIL"}  {name}')
    print('MATERIAL VERDICT: ' + ('PASS' if not failed else 'FAIL ' + str(failed)))
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main())
