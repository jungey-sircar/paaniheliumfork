#!/usr/bin/env python3
"""Compares two measure_metrics.py runs and writes the Paani vs upstream table.

    python compare_metrics.py --paani paani.json --baseline helium.json \
        --out metrics-comparison.md
"""

import argparse
import json
from pathlib import Path

# metric key, label, unit, smaller_is_better
METRICS = [
    ('m1_cold_start_ms', 'Cold start', 'ms', True),
    ('m2_warm_start_ms', 'Warm start', 'ms', True),
    ('m3_idle_memory_mb', 'Idle memory', 'MB', True),
    ('m4_memory_5_tabs_mb', 'Memory at 5 tabs', 'MB', True),
    ('m5_memory_10_tabs_mb', 'Memory at 10 tabs', 'MB', True),
    ('m6_memory_20_tabs_mb', 'Memory at 20 tabs', 'MB', True),
    ('m7_idle_cpu_pct', 'Idle CPU', '%', True),
    ('m8_load_cpu_pct', 'CPU during page load', '%', True),
    ('m9_memory_reclaimed_mb', 'Memory reclaimed after closing tabs', 'MB', True),
    ('m10_navigation_latency_ms', 'Navigation latency', 'ms', True),
    ('m11_adblock_overhead_ms', 'Ad blocking overhead', 'ms', True),
]


def fmt(v):
    if v is None:
        return 'n/a'
    if isinstance(v, float):
        return ('%.1f' % v)
    return str(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--paani', required=True)
    ap.add_argument('--baseline', required=True)
    ap.add_argument('--baseline-shipped', default='')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()

    paani = json.loads(Path(args.paani).read_text(encoding='utf-8'))
    base = json.loads(Path(args.baseline).read_text(encoding='utf-8'))
    shipped = (json.loads(Path(args.baseline_shipped).read_text(encoding='utf-8'))
               if args.baseline_shipped else None)

    lines = []
    lines.append('# Paani vs upstream Helium: the eleven performance metrics\n')
    lines.append('Measured over the whole browser process tree on one machine, '
                 'same websites, same settings, same load.\n')
    lines.append('* Paani: %s' % paani.get('exe', '?'))
    lines.append('* Helium baseline: %s' % base.get('exe', '?'))
    if shipped:
        lines.append('* Helium as shipped: %s' % shipped.get('exe', '?'))
    lines.append('* Machine: %s logical CPUs, %.1f GB RAM, %s\n'
                 % (paani['machine']['cpu_count'],
                    paani['machine']['total_ram_gb'],
                    paani['machine']['platform']))

    if shipped:
        lines.append('Two Helium columns are given. "Helium as shipped" is the '
                     'unmodified upstream build with its uBlock Origin component '
                     'extension enabled, which is what a user of upstream Helium '
                     'gets. "Helium, blocker off" is the same build with '
                     '`--disable-component-extensions-with-background-pages`, so '
                     'that the comparison against Paani is between two engines '
                     'rather than between an engine and an extension. Paani has '
                     'no ad blocking extension at all.\n')
        lines.append('| Metric | Helium as shipped | Helium, blocker off | Paani | Paani vs Helium (blocker off) |')
    else:
        lines.append('| Metric | Helium | Paani | Difference |')
    lines.append('|---|---|---|---|---|' if shipped else '|---|---|---|---|')

    for key, label, unit, lower_better in METRICS:
        p = paani.get(key)
        b = base.get(key)
        s = shipped.get(key) if shipped else None

        def cell(value):
            return 'n/a' if value is None else '%s %s' % (fmt(value), unit)

        def diff_cell(other):
            if p is None or other is None:
                return 'not comparable'
            d = p - other
            pct = ('%+.1f%%' % (d / other * 100.0)) if other else 'n/a'
            if abs(d) < 1e-9:
                return 'identical'
            return '%+g %s (%s)' % (round(d, 1), unit, pct)

        if shipped:
            lines.append('| %s | %s | %s | %s | %s |'
                         % (label, cell(s), cell(b), cell(p), diff_cell(b)))
        else:
            if p is None and b is None:
                continue
            lines.append('| %s | %s | %s | %s |'
                         % (label, cell(b), cell(p), diff_cell(b)))

    lines.append('')
    lines.append('## Notes\n')
    for extra in ('m11_adblock_probe', 'memory_curve_mb', 'navigation_detail',
                  'cold_process_count', 'idle_process_count',
                  'load_wall_ms', 'warm_idle_memory_mb'):
        if extra in paani:
            lines.append('* Paani %s: `%s`'
                         % (extra, json.dumps(paani[extra])))
    lines.append('')

    Path(args.out).write_text('\n'.join(lines), encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
