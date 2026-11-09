#!/usr/bin/env python3
"""Measures the eleven performance metrics of a Chromium based browser.

The metrics are the ones in docs/PAANI-PHASE1-ARCHITECTURE.md section 11 and
the unit of measurement is the whole process tree -- browser, renderer, GPU,
utility and network service -- because the browser process alone hides almost
every cost the user actually feels.

  1  cold start                 fresh profile, launch to a responsive browser
  2  warm start                 same profile, launch to a responsive browser
  3  idle memory                settled after start, nothing loaded
  4  memory at 5 tabs
  5  memory at 10 tabs
  6  memory at 20 tabs
  7  idle CPU                   percent of the whole machine
  8  CPU during a page load
  9  memory reclaimed           after the extra tabs are closed
 10  navigation latency         navigationStart to loadEventEnd
 11  ad blocking overhead       blocking on vs off, and vs the other browser

The tabs are served from local HTTP servers on different ports so each tab is a
different origin and therefore a different renderer process; tabs on one origin
would share a process and the memory curve would be flat and meaningless.

  python measure_metrics.py --exe out/Default/paani.exe --label paani
"""

import argparse
import http.server
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

import psutil
import websocket

BENCH_PAGE = b"""<!doctype html>
<html><head><meta charset="utf-8"><title>Paani bench</title></head>
<body style="margin:0;background:#fff">
<h1>Paani benchmark</h1>
<div id="host"></div>
<script>
const host = document.getElementById('host');
for (let i = 0; i < 600; i++) {
  const d = document.createElement('div');
  d.textContent = 'row ' + i;
  d.style.padding = '2px 4px';
  if (i % 3 === 0) d.style.background = '#eef';
  host.appendChild(d);
}
</script>
</body></html>"""

PIXEL = (b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
         b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
         b'\x00\x02\x02D\x01\x00;')


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        if self.path.endswith('.gif'):
            body, ctype = PIXEL, 'image/gif'
        else:
            body, ctype = BENCH_PAGE, 'text/html; charset=utf-8'
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        # The browser drops keep-alive connections; that is not an error worth
        # a traceback in the middle of a measurement run.
        pass


def free_port(start, count):
    """Finds `count` consecutive free TCP ports from `start`."""
    ports = []
    for port in range(start, start + count * 4):
        if len(ports) == count:
            break
        with socket.socket() as s:
            try:
                s.bind(('127.0.0.1', port))
            except OSError:
                continue
        ports.append(port)
    if len(ports) != count:
        raise RuntimeError('no free ports found')
    return ports


def start_servers(ports):
    servers = []
    for port in ports:
        srv = Server(('127.0.0.1', port), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servers.append(srv)
    return servers


# --- browser process tree -------------------------------------------------

def tree_of(root_pid):
    try:
        root = psutil.Process(root_pid)
    except psutil.NoSuchProcess:
        return []
    procs = [root]
    try:
        procs += root.children(recursive=True)
    except psutil.Error:
        pass
    return procs


def tree_rss_mb(root_pid):
    total = 0
    for p in tree_of(root_pid):
        try:
            total += p.memory_info().rss
        except psutil.Error:
            pass
    return round(total / (1024 * 1024), 1)


def tree_cpu(root_pid):
    """Returns (cpu_seconds, process_count) for the tree."""
    total = 0.0
    procs = tree_of(root_pid)
    for p in procs:
        try:
            t = p.cpu_times()
            total += t.user + t.system
        except psutil.Error:
            pass
    return total, len(procs)


def sample_cpu(root_pid, seconds):
    """Averages the CPU use of the tree over `seconds`."""
    before, count = tree_cpu(root_pid)
    t0 = time.perf_counter()
    time.sleep(seconds)
    after, _ = tree_cpu(root_pid)
    elapsed = time.perf_counter() - t0
    cores = os.cpu_count() or 1
    pct_total = (after - before) / elapsed / cores * 100.0
    return round(pct_total, 2), count


# --- CDP -------------------------------------------------------------------

def http_json(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def wait_for_cdp(port, timeout=120):
    t0 = time.perf_counter()
    deadline = t0 + timeout
    while time.perf_counter() < deadline:
        try:
            http_json('http://127.0.0.1:%d/json/version' % port, timeout=2)
            return time.perf_counter() - t0
        except Exception:
            time.sleep(0.05)
    raise RuntimeError('the browser never answered on port %d' % port)


def wait_for_target(port, timeout=60):
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        try:
            targets = http_json('http://127.0.0.1:%d/json/list' % port)
            pages = [t for t in targets if t.get('type') == 'page']
            if pages:
                return pages[0]
        except Exception:
            pass
        time.sleep(0.05)
    return None


class Cdp:
    """A tiny DevTools client: enough to navigate and to time a navigation."""

    def __init__(self, ws_url):
        self.ws = websocket.create_connection(ws_url, timeout=60)
        self.id = 0
        self.events = []

    def send(self, method, params=None):
        self.id += 1
        mid = self.id
        self.ws.send(json.dumps({'id': mid, 'method': method,
                                 'params': params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == mid:
                if 'error' in msg:
                    raise RuntimeError('%s: %s' % (method, msg['error']))
                return msg.get('result', {})
            self.events.append(msg)

    def wait_event(self, method, timeout=60):
        deadline = time.perf_counter() + timeout
        for ev in self.events:
            if ev.get('method') == method:
                self.events.remove(ev)
                return ev
        while time.perf_counter() < deadline:
            self.ws.settimeout(max(1.0, deadline - time.perf_counter()))
            msg = json.loads(self.ws.recv())
            if msg.get('method') == method:
                return msg
            self.events.append(msg)
        raise RuntimeError('timed out waiting for %s' % method)

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def open_tab(port, url):
    # The DevTools endpoint wants PUT /json/new?<url>, and urlopen sends POST
    # as soon as it is given a body, so the method is set explicitly.
    target = 'http://127.0.0.1:%d/json/new?%s' % (
        port, urllib.parse.quote(url, safe=''))
    req = urllib.request.Request(target, method='PUT')
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


def close_tab(port, target_id):
    try:
        urllib.request.urlopen(
            'http://127.0.0.1:%d/json/close/%s' % (port, target_id),
            timeout=10).read()
    except Exception:
        pass


def navigate_and_time(port, target_id, url):
    """Navigates and returns the page's own navigation timing in ms."""
    targets = http_json('http://127.0.0.1:%d/json/list' % port)
    ws_url = None
    for t in targets:
        if t.get('id') == target_id:
            ws_url = t.get('webSocketDebuggerUrl')
    if not ws_url:
        raise RuntimeError('no websocket for target %s' % target_id)
    cdp = Cdp(ws_url)
    try:
        cdp.send('Page.enable')
        cdp.send('Runtime.enable')
        cdp.send('Page.navigate', {'url': url})
        cdp.wait_event('Page.loadEventFired', timeout=60)
        res = cdp.send('Runtime.evaluate', {
            'expression': 'JSON.stringify({nav: performance.timing.navigationStart,'
                          ' load: performance.timing.loadEventEnd,'
                          ' dom: performance.timing.domComplete,'
                          ' first: performance.timing.responseStart})',
            'returnByValue': True})
        t = json.loads(res['result']['value'])
        return {
            'load_ms': round(t['load'] - t['nav'], 1),
            'dom_ms': round(t['dom'] - t['nav'], 1),
            'first_byte_ms': round(t['first'] - t['nav'], 1),
        }
    finally:
        cdp.close()


# --- process control ------------------------------------------------------

def kill_tree(proc):
    try:
        children = psutil.Process(proc.pid).children(recursive=True)
    except psutil.Error:
        children = []
    for p in children + [proc]:
        try:
            p.terminate()
        except psutil.Error:
            pass
    gone, alive = psutil.wait_procs(children + [proc], timeout=8)
    for p in alive:
        try:
            p.kill()
        except psutil.Error:
            pass


def launch(exe, profile, port, extra_args=()):
    args = [exe,
            '--user-data-dir=%s' % profile,
            '--no-first-run', '--no-default-browser-check',
            '--remote-debugging-port=%d' % port,
            '--window-position=40,40', '--window-size=1280,820',
            '--disable-background-timer-throttling',
            '--disable-renderer-backgrounding',
            '--disable-backgrounding-occluded-windows']
    args.extend(extra_args)
    proc = subprocess.Popen(args, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    return proc


# --- the measurement ------------------------------------------------------

def measure(args):
    label = args.label
    exe = str(Path(args.exe).resolve())
    profile = Path(args.profile).resolve()
    if profile.exists():
        shutil.rmtree(profile, ignore_errors=True)
    profile.mkdir(parents=True, exist_ok=True)

    tabs_needed = max(args.tab_counts) + 2
    ports = free_port(args.base_port, tabs_needed)
    servers = start_servers(ports)
    tab_urls = ['http://127.0.0.1:%d/bench' % p for p in ports]

    results = {'label': label, 'exe': exe, 'machine': {
        'cpu_count': os.cpu_count(),
        'total_ram_gb': round(psutil.virtual_memory().total / (1024 ** 3), 1),
        'platform': platform.platform(),
        'processor': platform.processor(),
    }}

    common = list(args.extra_args)

    # --- 1 cold start -----------------------------------------------------
    cold_profile = Path(str(profile) + '_cold')
    if cold_profile.exists():
        shutil.rmtree(cold_profile, ignore_errors=True)
    cold_profile.mkdir(parents=True, exist_ok=True)
    proc = launch(exe, cold_profile, args.port, common)
    cold_cdp = wait_for_cdp(args.port, timeout=180) * 1000.0
    cold_target = wait_for_target(args.port, timeout=60)
    cold_start_ms = round(cold_cdp, 1)
    results['m1_cold_start_ms'] = cold_start_ms
    results['cold_first_target_ms'] = round(cold_cdp, 1)
    results['cold_process_count'] = len(tree_of(proc.pid))

    # --- 3 idle memory and 7 idle CPU, still on the cold profile ----------
    time.sleep(args.settle)
    results['m3_idle_memory_mb'] = tree_rss_mb(proc.pid)
    results['m7_idle_cpu_pct'] = sample_cpu(proc.pid, args.cpu_window)[0]
    results['idle_process_count'] = len(tree_of(proc.pid))

    # --- 8 CPU during a page load -----------------------------------------
    load_tab = open_tab(args.port, tab_urls[0])
    cpu_before, _ = tree_cpu(proc.pid)
    t0 = time.perf_counter()
    navigate_and_time(args.port, load_tab['id'], tab_urls[0])
    load_wall = time.perf_counter() - t0
    cpu_after, _ = tree_cpu(proc.pid)
    cores = os.cpu_count() or 1
    results['m8_load_cpu_pct'] = round(
        (cpu_after - cpu_before) / load_wall / cores * 100.0, 2)
    results['load_wall_ms'] = round(load_wall * 1000, 1)

    # --- 10 navigation latency --------------------------------------------
    latencies = []
    for i in range(args.nav_runs):
        t = open_tab(args.port, tab_urls[i + 1])
        try:
            latencies.append(navigate_and_time(args.port, t['id'], tab_urls[i + 1]))
        finally:
            close_tab(args.port, t['id'])
    results['m10_navigation_latency_ms'] = round(
        sum(l['load_ms'] for l in latencies) / len(latencies), 1)
    results['navigation_detail'] = latencies

    # --- 4/5/6 memory at 5, 10 and 20 tabs --------------------------------
    opened = []
    mem_curve = {}
    for target_count in args.tab_counts:
        while len(opened) < target_count:
            idx = len(opened) % len(tab_urls)
            t = open_tab(args.port, tab_urls[idx])
            opened.append(t['id'])
            time.sleep(0.8)
        time.sleep(args.settle)
        mem_curve[str(target_count)] = tree_rss_mb(proc.pid)
    results['m4_memory_5_tabs_mb'] = mem_curve.get('5')
    results['m5_memory_10_tabs_mb'] = mem_curve.get('10')
    results['m6_memory_20_tabs_mb'] = mem_curve.get('20')
    results['memory_curve_mb'] = mem_curve

    # --- 9 memory reclaimed after closing the tabs ------------------------
    for tid in opened:
        close_tab(args.port, tid)
    time.sleep(args.settle * 2)
    after_close = tree_rss_mb(proc.pid)
    results['m9_memory_after_close_mb'] = after_close
    results['m9_memory_reclaimed_mb'] = round(
        (mem_curve.get('20', after_close) - after_close), 1)

    # --- 2 warm start -----------------------------------------------------
    kill_tree(proc)
    time.sleep(2)
    proc = launch(exe, profile, args.port, common)
    warm_cdp = wait_for_cdp(args.port, timeout=180) * 1000.0
    results['m2_warm_start_ms'] = round(warm_cdp, 1)
    wait_for_target(args.port, timeout=60)
    time.sleep(args.settle)
    results['warm_idle_memory_mb'] = tree_rss_mb(proc.pid)

    # --- 11 ad blocking overhead ------------------------------------------
    # The same page, loaded once with blocking on and once with it off. The
    # difference is what Paani's own engine costs; it is not the difference
    # between Paani and the other browser, which is measured separately.
    if args.blocking_probe_url:
        for mode, enabled in (('on', True), ('off', False)):
            set_blocking(args.port, enabled)
            t = open_tab(args.port, args.blocking_probe_url)
            try:
                timing = navigate_and_time(args.port, t['id'], args.blocking_probe_url)
            finally:
                close_tab(args.port, t['id'])
            results.setdefault('m11_adblock_probe', {})[mode] = timing
        on = results['m11_adblock_probe']['on']['load_ms']
        off = results['m11_adblock_probe']['off']['load_ms']
        results['m11_adblock_overhead_ms'] = round(on - off, 1)
        results['m11_adblock_overhead_pct'] = round(
            (on - off) / off * 100.0, 1) if off else None

    kill_tree(proc)
    for srv in servers:
        srv.shutdown()
    shutil.rmtree(cold_profile, ignore_errors=True)
    return results


def set_blocking(port, enabled):
    """Flips Paani's ad blocking through its own WebUI.

    Chromium ignores a chrome:// URL that is handed to /json/new, so the tab is
    opened on about:blank and the browser's own navigation call takes it to
    the WebUI.
    """
    target = open_tab(port, 'about:blank')
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            targets = http_json('http://127.0.0.1:%d/json/list' % port)
            ws_url = None
            for t in targets:
                if t.get('id') == target['id']:
                    ws_url = t.get('webSocketDebuggerUrl')
            if ws_url:
                cdp = Cdp(ws_url)
                try:
                    cdp.send('Page.enable')
                    cdp.send('Page.navigate', {'url': 'chrome://paani'})
                except Exception:
                    pass
                finally:
                    cdp.close()
            time.sleep(1.5)

            targets = http_json('http://127.0.0.1:%d/json/list' % port)
            for t in targets:
                if t.get('url', '').startswith('chrome://paani'):
                    ws_url = t.get('webSocketDebuggerUrl')
                    if ws_url:
                        cdp = Cdp(ws_url)
                        try:
                            cdp.send('Runtime.enable')
                            expr = (
                                '(() => { const btns = [];'
                                ' const scan = (r) => { for (const x of r.querySelectorAll("button")) btns.push(x);'
                                ' for (const el of r.querySelectorAll("*")) if (el.shadowRoot) scan(el.shadowRoot); };'
                                ' scan(document);'
                                ' const t = btns.find(x => x.getAttribute("role") === "switch");'
                                ' if (!t) return "NO TOGGLE";'
                                ' const on = t.getAttribute("aria-checked") === "true";'
                                ' if (on !== %s) t.click();'
                                ' return "ok"; })()' % ('true' if enabled else 'false'))
                            res = cdp.send('Runtime.evaluate',
                                           {'expression': expr,
                                            'returnByValue': True})
                            val = res.get('result', {}).get('value')
                            if val == 'ok':
                                time.sleep(1.5)
                                return True
                        finally:
                            cdp.close()
            time.sleep(1.0)
        raise RuntimeError('could not reach the Paani WebUI')
    finally:
        close_tab(port, target['id'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--exe', required=True)
    ap.add_argument('--label', required=True)
    ap.add_argument('--profile', required=True)
    ap.add_argument('--port', type=int, default=9401)
    ap.add_argument('--base-port', type=int, default=8731)
    ap.add_argument('--tab-counts', type=int, nargs='+', default=[5, 10, 20])
    ap.add_argument('--settle', type=float, default=12.0)
    ap.add_argument('--cpu-window', type=float, default=30.0)
    ap.add_argument('--nav-runs', type=int, default=5)
    ap.add_argument('--out', required=True)
    ap.add_argument('--blocking-probe-url', default='')
    ap.add_argument('--extra-args', nargs='*', default=[])
    args = ap.parse_args()

    results = measure(args)
    Path(args.out).write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
