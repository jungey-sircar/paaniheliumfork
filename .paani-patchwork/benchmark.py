#!/usr/bin/env python3
# -*- coding: UTF-8 -*-
# Copyright 2026 The Paani Authors
# You can use, redistribute, and/or modify this source code under
# the terms of the GPL-3.0 license that can be found in the LICENSE file.
"""Measures the resource use of a Chromium browser build.

The script drives a real browser over the DevTools protocol and reads the
resource use of the whole process tree, not only of the main executable.  It
records the numbers that the Paani specification asks for:

  * cold start time
  * warm start time
  * idle memory after the start has settled
  * memory with 5, 10 and 20 open tabs
  * CPU while the browser is idle
  * CPU while a page is loading
  * memory recovery after the tabs have been closed
  * navigation responsiveness
  * overhead of the ad blocker

Every measurement is reported for one build, so that two builds can be
compared by running the script twice and diffing the JSON output.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import psutil
import websocket


# ---------------------------------------------------------------------------
# The browser
# ---------------------------------------------------------------------------

class Browser:
    """A running browser that is driven over the DevTools protocol."""

    def __init__(self, exe, profile_dir, extra_args, port=0):
        self.exe = str(exe)
        self.profile_dir = Path(profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self.extra_args = list(extra_args)
        self.process = None
        self._ws = None
        self._next_id = 0
        self._events = []
        self._port = port

    def start(self):
        """Launches the browser and waits until the DevTools port is open."""
        args = [
            self.exe,
            '--user-data-dir=%s' % self.profile_dir,
            '--remote-debugging-port=%d' % self._port,
            '--no-first-run',
            '--no-default-browser-check',
            '--disable-sync',
            '--disable-background-networking',
            '--disable-component-update',
            '--disable-features=Translate,MediaRouter,OptimizationHints',
            '--metrics-recording-only',
        ] + self.extra_args
        self.process = subprocess.Popen(
            args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.port = self._read_port()
        return self.process

    def _read_port(self, timeout=60):
        """Returns the DevTools port that the browser wrote to its profile."""
        marker = self.profile_dir / 'DevToolsActivePort'
        deadline = time.time() + timeout
        while time.time() < deadline:
            if marker.exists():
                content = marker.read_text(encoding='utf-8', errors='replace')
                lines = content.splitlines()
                if lines and lines[0].strip().isdigit():
                    return int(lines[0].strip())
            if self.process.poll() is not None:
                raise RuntimeError('the browser exited with %d'
                                   % self.process.returncode)
            time.sleep(0.05)
        raise TimeoutError('the browser did not open its DevTools port')

    def connect(self, timeout=30):
        """Opens the DevTools websocket of the first page."""
        import urllib.request
        deadline = time.time() + timeout
        url = None
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                        'http://127.0.0.1:%d/json/list' % self.port,
                        timeout=5) as response:
                    targets = json.loads(response.read().decode('utf-8'))
                for target in targets:
                    if target.get('type') == 'page' and target.get(
                            'webSocketDebuggerUrl'):
                        url = target['webSocketDebuggerUrl']
                        break
                if url:
                    break
            except Exception:
                pass
            time.sleep(0.2)
        if not url:
            raise TimeoutError('no DevTools page target appeared')
        self._ws = websocket.create_connection(url, suppress_origin=True,
                                               timeout=60)
        self._send('Page.enable')
        self._send('Runtime.enable')
        return url

    def _send(self, method, params=None):
        self._next_id += 1
        message_id = self._next_id
        self._ws.send(json.dumps({'id': message_id, 'method': method,
                                  'params': params or {}}))
        while True:
            message = json.loads(self._ws.recv())
            if message.get('id') == message_id:
                if 'error' in message:
                    raise RuntimeError('%s failed: %s'
                                       % (method, message['error']))
                return message.get('result', {})
            self._events.append(message)

    def event(self, name, timeout=30):
        """Waits for a DevTools event and returns it."""
        for message in self._events:
            if message.get('method') == name:
                self._events.remove(message)
                return message
        deadline = time.time() + timeout
        while time.time() < deadline:
            message = json.loads(self._ws.recv())
            if message.get('method') == name:
                return message
            self._events.append(message)
        raise TimeoutError('the event %s did not arrive' % name)

    def navigate(self, url, timeout=60):
        """Navigates the page and returns the seconds until it finished."""
        started = time.time()
        self._send('Page.navigate', {'url': url})
        self.event('Page.loadEventFired', timeout=timeout)
        return time.time() - started

    def open_tab(self, url='about:blank'):
        """Opens a new tab and returns its target id."""
        result = self._send('Target.createTarget', {'url': url})
        return result['targetId']

    def close_all_tabs(self):
        """Closes every tab except the first one."""
        targets = self._send('Target.getTargets')['targetInfos']
        pages = [t for t in targets if t['type'] == 'page']
        for target in pages[1:]:
            try:
                self._send('Target.closeTarget', {'targetId': target['targetId']})
            except RuntimeError:
                pass

    def evaluate(self, expression):
        """Runs a script in the page and returns its value."""
        result = self._send('Runtime.evaluate',
                            {'expression': expression, 'returnByValue': True})
        return result.get('result', {}).get('value')

    def stop(self):
        """Closes the browser."""
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=15)


# ---------------------------------------------------------------------------
# The measurements
# ---------------------------------------------------------------------------

def process_tree(pid):
    """Returns the browser process and every process it started."""
    try:
        root = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return []
    processes = [root]
    try:
        processes.extend(root.children(recursive=True))
    except psutil.Error:
        pass
    return processes


def memory_of(pid):
    """Returns the working set and the unique set size of the tree."""
    rss = 0
    uss = 0
    for process in process_tree(pid):
        try:
            rss += process.memory_info().rss
            try:
                uss += process.memory_full_info().uss
            except (psutil.Error, AttributeError):
                uss += process.memory_info().rss
        except psutil.Error:
            continue
    return rss, uss


def cpu_of(pid):
    """Returns the CPU seconds that the tree has used."""
    total = 0.0
    for process in process_tree(pid):
        try:
            times = process.cpu_times()
            total += times.user + times.system
        except psutil.Error:
            continue
    return total


def first_visible_window(pid, timeout=60):
    """Returns the seconds until the browser showed a window."""
    import ctypes
    import ctypes.wintypes

    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND,
                         ctypes.wintypes.LPARAM)
    def callback(hwnd, _):
        owner = ctypes.wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value != pid:
            return True
        if not user32.IsWindowVisible(hwnd):
            return True
        found.append(hwnd)
        return False

    deadline = time.time() + timeout
    while time.time() < deadline:
        found.clear()
        user32.EnumWindows(callback, 0)
        if found:
            return True
        time.sleep(0.02)
    return False


def watch_for_window(pid, started, result):
    """Looks for the first visible window and records when it appeared."""
    import threading

    def run():
        if first_visible_window(pid, timeout=90):
            result['seconds'] = time.time() - started
            result['visible'] = True
        else:
            result['visible'] = False

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def sample_cpu(pid, seconds):
    """Returns the CPU usage of the tree over a period of time.

    The result holds the percentage of a single core and the percentage of
    the whole machine.
    """
    started = time.time()
    before = cpu_of(pid)
    time.sleep(seconds)
    after = cpu_of(pid)
    wall = time.time() - started
    used = max(0.0, after - before)
    return {
        'seconds': round(wall, 3),
        'cpu_seconds': round(used, 3),
        'percent_of_one_core': round(used / wall * 100, 2) if wall else 0.0,
        'percent_of_machine': round(used / wall / (psutil.cpu_count() or 1) *
                                    100, 2) if wall else 0.0,
    }


def settle(pid, seconds, interval=1.0):
    """Waits until the memory use of the tree stops changing."""
    previous = None
    deadline = time.time() + seconds
    while time.time() < deadline:
        current = memory_of(pid)[0]
        if previous is not None and abs(current - previous) < 2 * 1024 * 1024:
            return True
        previous = current
        time.sleep(interval)
    return False


# The pref that turns the bundled ad blocker on and off.  Helium only hands
# the filter lists to uBlock Origin when the user agreed to its services.
UBLOCK_PREF = 'helium.services.ublock_assets'
SERVICES_PREFS = {
    'helium.services.enabled': True,
    'helium.services.user_consented': True,
}


def write_prefs(profile_dir, prefs):
    """Writes a pref file into a profile before the browser starts."""
    default_dir = Path(profile_dir) / 'Default'
    default_dir.mkdir(parents=True, exist_ok=True)
    (default_dir / 'Preferences').write_text(
        json.dumps(prefs, indent=2), encoding='utf-8')


def load_times(exe, profile_dir, urls, extra_args, settle_seconds):
    """Loads every page and returns the seconds that each load took."""
    browser = Browser(exe, profile_dir, extra_args)
    browser.start()
    browser.connect()
    settle(browser.process.pid, settle_seconds)
    times = {}
    for url in urls:
        times[url] = round(browser.navigate(url), 3)
    browser.stop()
    return times


def measure_ad_blocking(exe, label, urls, profile_root, extra_args,
                        settle_seconds):
    """Measures the overhead that the ad blocker adds to a page load."""
    results = {'with_ad_blocker': {}, 'without_ad_blocker': {}}

    on_profile = Path(profile_root) / ('%s-adblock-on' % label)
    off_profile = Path(profile_root) / ('%s-adblock-off' % label)
    for name in (on_profile, off_profile):
        shutil.rmtree(name, ignore_errors=True)

    enabled = dict(SERVICES_PREFS)
    enabled[UBLOCK_PREF] = True
    write_prefs(on_profile, enabled)

    disabled = dict(SERVICES_PREFS)
    disabled[UBLOCK_PREF] = False
    write_prefs(off_profile, disabled)

    results['with_ad_blocker'] = load_times(exe, on_profile, urls, extra_args,
                                            settle_seconds)
    results['without_ad_blocker'] = load_times(exe, off_profile, urls,
                                                extra_args, settle_seconds)

    results['overhead_seconds'] = {
        url: round(results['with_ad_blocker'][url] -
                   results['without_ad_blocker'][url], 3)
        for url in results['with_ad_blocker']
    }

    for name in (on_profile, off_profile):
        shutil.rmtree(name, ignore_errors=True)
    return results


# ---------------------------------------------------------------------------
# The measurement run
# ---------------------------------------------------------------------------

def measure(exe, label, urls, tab_counts, settle_seconds, idle_seconds,
            profile_root, extra_args, keep_profile):
    """Runs every measurement against one browser build."""
    results = {'label': label, 'executable': str(exe),
               'machine': {'cpu_count': psutil.cpu_count(),
                           'total_memory': psutil.virtual_memory().total},
               'startup': {}, 'memory': {}, 'cpu': {}, 'navigation': {},
               'ad_blocking': {}}

    fresh_profile = Path(profile_root) / ('%s-cold' % label)
    warm_profile = Path(profile_root) / ('%s-warm' % label)

    for name in (fresh_profile, warm_profile):
        if name.exists():
            shutil.rmtree(name, ignore_errors=True)

    # --- cold start ------------------------------------------------------
    browser = Browser(exe, fresh_profile, extra_args)
    started = time.time()
    browser.start()
    watcher = {'seconds': None, 'visible': False}
    thread = watch_for_window(browser.process.pid, started, watcher)
    browser.connect()
    thread.join(timeout=120)
    results['startup']['cold_window_seconds'] = (
        round(watcher['seconds'], 3) if watcher['visible'] else None)
    results['startup']['cold_devtools_seconds'] = round(
        time.time() - started, 3)

    # --- idle ------------------------------------------------------------
    settle(browser.process.pid, settle_seconds)
    rss, uss = memory_of(browser.process.pid)
    results['memory']['idle_rss_bytes'] = rss
    results['memory']['idle_uss_bytes'] = uss
    results['memory']['idle_process_count'] = len(process_tree(
        browser.process.pid))
    results['cpu']['idle'] = sample_cpu(browser.process.pid, idle_seconds)

    # --- tabs ------------------------------------------------------------
    for count in tab_counts:
        browser.close_all_tabs()
        for _ in range(count):
            browser.open_tab()
        settle(browser.process.pid, settle_seconds)
        rss, uss = memory_of(browser.process.pid)
        results['memory']['tabs_%d_rss_bytes' % count] = rss
        results['memory']['tabs_%d_uss_bytes' % count] = uss

    # --- recovery --------------------------------------------------------
    browser.close_all_tabs()
    settle(browser.process.pid, settle_seconds)
    rss, uss = memory_of(browser.process.pid)
    results['memory']['after_closing_tabs_rss_bytes'] = rss
    results['memory']['after_closing_tabs_uss_bytes'] = uss
    results['memory']['recovered_rss_bytes'] = (
        results['memory']['idle_rss_bytes'] - rss)
    results['memory']['recovered_uss_bytes'] = (
        results['memory']['idle_uss_bytes'] - uss)

    # --- navigation ------------------------------------------------------
    for url in urls:
        load = browser.navigate(url)
        results['cpu']['loading_%s' % url] = sample_cpu(
            browser.process.pid, max(3.0, load))
        results['navigation'][url] = round(load, 3)

    # --- responsiveness of the interface ----------------------------------
    started = time.time()
    browser.evaluate('1 + 1')
    results['navigation']['script_round_trip_ms'] = round(
        (time.time() - started) * 1000, 2)

    browser.stop()

    # --- ad blocking ------------------------------------------------------
    if urls:
        results['ad_blocking'] = measure_ad_blocking(
            exe, label, urls, profile_root, extra_args, settle_seconds)

    # --- warm start ------------------------------------------------------
    warm = Browser(exe, warm_profile, extra_args)
    started = time.time()
    warm.start()
    watcher = {'seconds': None, 'visible': False}
    thread = watch_for_window(warm.process.pid, started, watcher)
    warm.connect()
    thread.join(timeout=120)
    results['startup']['warm_window_seconds'] = (
        round(watcher['seconds'], 3) if watcher['visible'] else None)
    results['startup']['warm_devtools_seconds'] = round(
        time.time() - started, 3)
    warm.stop()

    if not keep_profile:
        for name in (fresh_profile, warm_profile):
            shutil.rmtree(name, ignore_errors=True)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe', required=True,
                        help='the chrome.exe of the build to measure')
    parser.add_argument('--label', required=True,
                        help='the name that the results are stored under')
    parser.add_argument('--url', action='append', default=[],
                        help='a page to load, may be given more than once')
    parser.add_argument('--tabs', default='5,10,20',
                        help='the tab counts to measure, comma separated')
    parser.add_argument('--settle', type=float, default=10.0,
                        help='seconds to wait for the browser to settle')
    parser.add_argument('--idle', type=float, default=15.0,
                        help='seconds of the idle CPU measurement')
    parser.add_argument('--profile-root', default=None,
                        help='where the test profiles are put')
    parser.add_argument('--extra-arg', action='append', default=[],
                        help='an extra command line argument for the browser')
    parser.add_argument('--out', required=True,
                        help='the JSON file that the results are written to')
    args = parser.parse_args()

    profile_root = args.profile_root or tempfile.mkdtemp(prefix='paani-bench-')
    tab_counts = [int(value) for value in args.tabs.split(',') if value]

    results = measure(args.exe, args.label, args.url, tab_counts,
                      args.settle, args.idle, profile_root, args.extra_arg,
                      False)

    Path(args.out).write_text(json.dumps(results, indent=2),
                              encoding='utf-8')
    print(json.dumps(results, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
