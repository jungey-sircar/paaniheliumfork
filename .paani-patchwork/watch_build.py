#!/usr/bin/env python3
"""Samples the build progress rate and the machine load."""
import re
import time
from pathlib import Path

LOG = Path(r'E:\eric\PaaniBrowserChromiumFork\.paani-patchwork\logs\baseline-build.log')

counter = re.compile(r'^\[(\d+)/(\d+)\] (\S+)s')

for _ in range(40):
    last = None
    total = None
    with LOG.open('r', encoding='utf-8', errors='replace') as handle:
        for line in handle:
            match = counter.match(line)
            if match:
                last = int(match.group(1))
                total = int(match.group(2))
    print('%s done=%s total=%s' % (time.strftime('%H:%M:%S'), last, total),
          flush=True)
    time.sleep(60)
