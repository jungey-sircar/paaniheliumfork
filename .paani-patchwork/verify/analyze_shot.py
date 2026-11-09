from PIL import Image
import collections

p = r"C:\Users\USER\.qoder\tmp\C--Users-USER-Documents-Qoder-2026-10-31-12cf5842\images\12cf5842-bb71-46e7-842d-e3b91594bd1c\f1bec4c6-2dcf-42d7-bf3e-dbeff2fffe1a.png"
im = Image.open(p).convert("RGB")
w, h = im.size
print("size", w, h)

# Top-region colour histogram (browser chrome band only).
band = im.crop((0, 0, w, min(h, 200)))
cnt = collections.Counter(band.getdata())
print("distinct colours in top 200px:", len(cnt))
for c, n in cnt.most_common(14):
    print("   ", c, "#%02X%02X%02X" % c, n)

# Vertical profile down the middle-left, to see where surfaces change.
print("vertical profile at x=700:")
prev = None
for y in range(0, h, 2):
    c = im.getpixel((700, y))
    if c != prev:
        print("   y=%4d  %s  #%02X%02X%02X" % (y, c, *c))
        prev = c

print("vertical profile at x=100:")
prev = None
for y in range(0, h, 2):
    c = im.getpixel((100, y))
    if c != prev:
        print("   y=%4d  %s  #%02X%02X%02X" % (y, c, *c))
        prev = c
