"""Records the ad blocker's URL loader factory hook as a quilt patch section.

`patches/paani/windows/paani-adblock.patch` has three sections: the vendored
adblock crate's BUILD.gn, chrome/browser/BUILD.gn and the hook in
chrome_content_browser_client.cc.  Only the last one is derived from the tree
here; the other two are copied through untouched.

The hook moved to the head of the interceptor chain, so the recorded hunk has
to move with it: the position is the whole point of the change, and a patch
that no longer describes the tree silently hands the next build a browser that
blocks nothing.
"""

import difflib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'src'
PATCH = ROOT / 'patches' / 'paani' / 'windows' / 'paani-adblock.patch'
RELATIVE = 'chrome/browser/chrome_content_browser_client.cc'

INCLUDE = '#include "chrome/browser/paani/adblock/paani_adblock_url_loader_factory.h"\n'
HOOK_START = '  // Install the Paani built in ad blocker.'
HOOK_END = '#if BUILDFLAG(ENABLE_EXTENSIONS_CORE)\n'


def pristine(current: str) -> str:
    """Reverse the Paani layer to recover the upstream text."""
    if INCLUDE not in current:
        raise SystemExit(f'{RELATIVE}: the include is not in the tree')
    text = current.replace(INCLUDE, '', 1)

    start = text.find(HOOK_START)
    end = text.find(HOOK_END, start)
    if start < 0 or end < 0:
        raise SystemExit(f'{RELATIVE}: the hook is not before the webRequest proxy')
    return text[:start] + text[end:]


def section(body: str) -> str:
    """The ---/+++ chunk of the patch that covers RELATIVE."""
    out = []
    for line in body.splitlines(keepends=True):
        if out or line.startswith(f'--- a/{RELATIVE}'):
            out.append(line)
    if len(out) < 2:
        raise SystemExit(f'{PATCH}: no section for {RELATIVE}')
    return ''.join(out)


def main():
    current = (SOURCE / RELATIVE).read_text(encoding='utf-8')
    original = pristine(current)
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        current.splitlines(keepends=True),
        fromfile='a/' + RELATIVE,
        tofile='b/' + RELATIVE,
        n=3,
    )
    new_section = ''.join(diff)

    body = PATCH.read_text(encoding='utf-8')
    old = section(body)
    PATCH.write_text(body.replace(old, new_section, 1), encoding='utf-8',
                     newline='\n')
    print(f'{PATCH}: {RELATIVE} section rewritten '
          f'({len(old.splitlines())} -> {len(new_section.splitlines())} lines)')


if __name__ == '__main__':
    main()
