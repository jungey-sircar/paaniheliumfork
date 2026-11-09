#!/usr/bin/env python
"""Launches a built Chromium binary and captures its window as a PNG.

This is the verification step for the build phases: it starts the browser
exactly the way a user would, waits for the first window, and saves what is on
the screen.  It is deliberately independent of the browser under test -- it
uses plain Win32 calls, so it works for any Chromium flavour.

    python tools/capture_browser.py out/Default/chrome.exe -o shot.png
"""

import argparse
import ctypes
import ctypes.wintypes as wintypes
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

SW_RESTORE = 9
SW_SHOW = 5
SRCCOPY = 0x00CC0020
DIB_RGB_COLORS = 0
PW_RENDERFULLCONTENT = 0x00000002


class RECT(ctypes.Structure):
    _fields_ = [('left', wintypes.LONG), ('top', wintypes.LONG),
                ('right', wintypes.LONG), ('bottom', wintypes.LONG)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wintypes.DWORD),
                ('biWidth', wintypes.LONG),
                ('biHeight', wintypes.LONG),
                ('biPlanes', wintypes.WORD),
                ('biBitCount', wintypes.WORD),
                ('biCompression', wintypes.DWORD),
                ('biSizeImage', wintypes.DWORD),
                ('biXPelsPerMeter', wintypes.LONG),
                ('biYPelsPerMeter', wintypes.LONG),
                ('biClrUsed', wintypes.DWORD),
                ('biClrImportant', wintypes.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER),
                ('bmiColors', wintypes.DWORD * 3)]


def find_window(process_id, timeout):
    """Returns the handle of the first visible top level window of a process."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def callback(hwnd, _):
            owner = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
            if owner.value != process_id:
                return True
            if not user32.IsWindowVisible(hwnd):
                return True
            found.append(hwnd)
            return False

        user32.EnumWindows(callback, 0)
        if found:
            return found[0]
        time.sleep(0.5)
    return None


def capture(hwnd, path):
    """Saves the window contents to |path|."""
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    if width <= 0 or height <= 0:
        raise RuntimeError('the window has no size')

    window_dc = user32.GetWindowDC(hwnd)
    memory_dc = gdi32.CreateCompatibleDC(window_dc)
    bitmap = gdi32.CreateCompatibleBitmap(window_dc, width, height)
    gdi32.SelectObject(memory_dc, bitmap)

    # PW_RENDERFULLCONTENT asks the window to repaint itself into the DC,
    # which is what a GPU composited Chromium window needs.
    if not user32.PrintWindow(hwnd, memory_dc, PW_RENDERFULLCONTENT):
        gdi32.BitBlt(memory_dc, 0, 0, width, height, window_dc, 0, 0,
                     SRCCOPY)

    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = width
    info.bmiHeader.biHeight = -height
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    info.bmiHeader.biCompression = 0

    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(memory_dc, bitmap, 0, height, buffer,
                    ctypes.byref(info), DIB_RGB_COLORS)

    image = Image.frombuffer('RGBA', (width, height), buffer, 'raw', 'BGRA', 0, 1)
    image.convert('RGB').save(path)

    gdi32.DeleteObject(bitmap)
    gdi32.DeleteDC(memory_dc)
    user32.ReleaseDC(hwnd, window_dc)
    return width, height


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary', help='path to chrome.exe')
    parser.add_argument('-o', '--output', default='browser.png')
    parser.add_argument('-u', '--url', default='about:blank')
    parser.add_argument('-p', '--profile', default=None,
                        help='user data directory (a temporary one by default)')
    parser.add_argument('-t', '--timeout', type=float, default=60.0)
    parser.add_argument('--window-size', default='1280,860')
    parser.add_argument('--window-position', default='40,40')
    parser.add_argument('--keep-open', action='store_true',
                        help='leave the browser running after the capture')
    args = parser.parse_args()

    binary = Path(args.binary).resolve()
    if not binary.exists():
        print('no such binary: %s' % binary)
        return 1

    profile = args.profile or str(Path(os.environ['TEMP']) /
                                  ('paani-capture-%d' % os.getpid()))
    command = [str(binary),
               '--user-data-dir=%s' % profile,
               '--no-first-run',
               '--no-default-browser-check',
               '--disable-features=Translate',
               '--window-size=%s' % args.window_size,
               '--window-position=%s' % args.window_position,
               args.url]
    print('launching: %s' % ' '.join(command))
    process = subprocess.Popen(command)

    try:
        hwnd = find_window(process.pid, args.timeout)
        if hwnd is None:
            print('no window appeared within %.0f seconds' % args.timeout)
            return 2
        user32.ShowWindow(hwnd, SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        time.sleep(5.0)
        width, height = capture(hwnd, args.output)
        print('captured %dx%d -> %s' % (width, height, args.output))
    finally:
        if not args.keep_open:
            process.terminate()
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
    return 0


if __name__ == '__main__':
    sys.exit(main())
