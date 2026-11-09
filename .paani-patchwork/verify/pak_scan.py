"""Reads the Chromium data packs the built browser loads and reports whether a
marker string is present in each resource.

A grit id existing is not proof the bytes are packed: LoadDataResourceString()
returns an empty string for a missing id, which shows up as a blank WebUI page
and an ad blocker compiled with zero filter lists. So look at the real pak.
"""
import struct
import sys
import zlib
from pathlib import Path

OUT = Path(r'E:\eric\PaaniBrowserChromiumFork\paani-windows\build\src\out\Default')

MARKERS = {
    'paani.html shadow host': b'<paani-app>',
    'paani.html inline style': b'background: #f1f8fb',
    'app.js class name': b"static get is()",
    'ublock filters header': b'[uBlock filters]',
    'ublock privacy header': b'[uBlock filters - Privacy]',
    'googlesyndication rule': b'googlesyndication.com',
    'doubleclick rule': b'doubleclick.net',
}


def read_pak(path):
    data = path.read_bytes()
    version, entry_count, total = struct.unpack_from('<HHI', data, 0)
    table_size = entry_count * 6 + 4 * entry_count
    # Layout after the header: uint32 ids[], then (uint32 offset+uint16 flags)[].
    ids = struct.unpack_from('<%dI' % entry_count, data, 8)
    entries_start = 8 + 4 * entry_count
    raw = []
    for i in range(entry_count):
        offset, flags = struct.unpack_from('<IH', data, entries_start + i * 6)
        raw.append((ids[i], offset, flags))
    raw.sort(key=lambda e: e[1])
    out = {}
    for i, (rid, offset, flags) in enumerate(raw):
        end = raw[i + 1][1] if i + 1 < len(raw) else total
        blob = data[offset:end]
        compression = (flags >> 1) & 0b111111
        if compression == 1:
            try:
                blob = zlib.decompressobj(-zlib.MAX_WBITS).decompress(blob)
            except zlib.error:
                pass
        out[rid] = blob
    return version, out


def main():
    for name in sys.argv[1:] or ['resources.pak', 'chrome_100_percent.pak']:
        path = OUT / name
        if not path.exists():
            print('%s: MISSING' % name)
            continue
        version, blobs = read_pak(path)
        joined = b''.join(blobs.values())
        print('=== %s v%d, %d entries, %d decoded bytes' %
              (name, version, len(blobs), len(joined)))
        for label, marker in MARKERS.items():
            where = joined.find(marker)
            print('  %-24s %s' % (label, 'FOUND' if where >= 0 else 'absent'))


if __name__ == '__main__':
    main()
