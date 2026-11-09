"""Rasterises a Chromium .icon file so its shape can be looked at.

The icon format is a list of drawing commands (MOVE_TO, CUBIC_TO, ARC_TO,
CLOSE ...). Chromium parses them at run time, so a malformed icon is not a
build error but an invisible button. This renders the same commands with
Pillow, which is enough to see whether the shape is the one intended.

    python render_icon.py <icon file> [out.png]
"""
import math
import sys

from PIL import Image, ImageDraw

SCALE = 10


def parse(path):
    commands = []
    current = None
    for raw in open(path, encoding='utf-8'):
        line = raw.partition('//')[0].strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(',')]
        name = parts[0]
        args = []
        for p in parts[1:]:
            if not p:
                continue
            args.append(float(p.rstrip('f')))
        if name in ('CANVAS_DIMENSIONS',):
            current = args[0]
            continue
        if name in ('FILL_RULE_NONZERO', 'FILL_RULE_EVENODD', 'CLOSE'):
            commands.append((name, []))
            continue
        commands.append((name, args))
    return commands


def bezier(p0, p1, p2, p3, steps=32):
    points = []
    for i in range(1, steps + 1):
        t = i / steps
        u = 1 - t
        x = (u ** 3 * p0[0] + 3 * u * u * t * p1[0] +
             3 * u * t * t * p2[0] + t ** 3 * p3[0])
        y = (u ** 3 * p0[1] + 3 * u * u * t * p1[1] +
             3 * u * t * t * p2[1] + t ** 3 * p3[1])
        points.append((x, y))
    return points


def arc(p0, rx, ry, angle, large, sweep, p1, steps=32):
    # Endpoints on an axis aligned ellipse; the icons only use that case.
    # The centre is not the chord midpoint except for a semicircle, so it is
    # solved the way SVG does it.
    dx2 = (p0[0] - p1[0]) / 2
    dy2 = (p0[1] - p1[1]) / 2
    x1 = p0[0]
    y1 = p0[1]
    x2 = p1[0]
    y2 = p1[1]
    rxs = rx * rx
    rys = ry * ry
    x1p = x1
    y1p = y1
    lam = (x1p - x2) ** 2 / rxs + (y1p - y2) ** 2 / rys
    if lam > 1:
        scale = math.sqrt(lam)
        rx = rx * scale
        ry = ry * scale
        rxs = rx * rx
        rys = ry * ry
    num = rxs * rys - rxs * dy2 * dy2 - rys * dx2 * dx2
    den = rxs * dy2 * dy2 + rys * dx2 * dx2
    coef = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large == sweep:
        coef = -coef
    cxp = coef * rx * dy2 / ry
    cyp = -coef * ry * dx2 / rx
    cx = cxp + (x1 + x2) / 2
    cy = cyp + (y1 + y2) / 2
    a0 = math.atan2((y1p - cy) / ry, (x1p - cx) / rx)
    a1 = math.atan2((y2 - cy) / ry, (x2 - cx) / rx)
    da = a1 - a0
    if sweep and da < 0:
        da += 2 * math.pi
    elif not sweep and da > 0:
        da -= 2 * math.pi
    points = []
    for i in range(1, steps + 1):
        a = a0 + da * i / steps
        points.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return points


def render(commands, canvas, out_path):
    size = int(canvas * SCALE)
    img = Image.new('RGBA', (size, size), (255, 255, 255, 255))
    draw = ImageDraw.Draw(img)
    points = []
    cur = (0.0, 0.0)
    for name, args in commands:
        if name == 'MOVE_TO':
            cur = (args[0], args[1])
            points = [cur]
        elif name == 'CUBIC_TO':
            c1 = (args[0], args[1])
            c2 = (args[2], args[3])
            end = (args[4], args[5])
            points += bezier(cur, c1, c2, end)
            cur = end
        elif name == 'ARC_TO':
            end = (args[5], args[6])
            points += arc(cur, args[0], args[1], args[2], args[3], args[4], end)
            cur = end
        elif name == 'LINE_TO':
            cur = (args[0], args[1])
            points.append(cur)
        elif name == 'CLOSE':
            if len(points) > 2:
                draw.polygon([(x * SCALE, y * SCALE) for x, y in points],
                             fill=(20, 90, 140, 255))
            points = []
    img.save(out_path)
    print('wrote', out_path)


def main():
    icon = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else icon.rsplit('.', 1)[0] + '.png'
    commands = parse(icon)
    canvas = 24
    for name, args in commands:
        if name == 'CANVAS_DIMENSIONS':
            canvas = int(args[0])
    render(commands, canvas, out)


if __name__ == '__main__':
    main()
