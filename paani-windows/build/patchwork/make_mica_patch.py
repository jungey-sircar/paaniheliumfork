"""Records the Windows backdrop (Mica) as a quilt patch.

`paani-native-frame.patch` already makes the Windows titlebar stop painting so
that a native backdrop can show through, and it already refuses the material
when Windows asks for reduced transparency or forced colours.  What was missing
is the call that actually asks the DWM for a backdrop: without it the unpainted
titlebar shows whatever the window compositor left there, which is worse than an
opaque frame.

This applies `DWMWA_SYSTEMBACKDROP_TYPE` to the browser window: Mica while the
native frame materials are on, `DWMSBT_NONE` when they are off, so the toggle in
chrome://settings keeps working in both directions.  Web contents are a separate
opaque layer, so a page is never tinted by the backdrop.

The attribute is refreshed from OnPaint, but only handed to the DWM when the
requested value differs from the one already applied, so the common case is one
integer comparison.
"""

import difflib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'src'
BACKUP = ROOT / 'build' / 'patchwork' / 'orig' / 'mica'
PATCH = ROOT / 'patches' / 'paani' / 'windows' / 'paani-mica-backdrop.patch'

HEADER = 'chrome/browser/ui/views/frame/browser_frame_view_win.h'
SOURCE_FILE = 'chrome/browser/ui/views/frame/browser_frame_view_win.cc'

EDITS = [
    {
        'path': HEADER,
        'marker': 'UpdateNativeFrameBackdrop',
        'replacements': [
            (
                '#include <array>\n',
                '#include <windows.h>\n'
                '\n'
                '#include <array>\n#include <optional>\n',
            ),
            (
                ' private:\n'
                '  friend class BrowserCaptionButtonContainer;\n',
                ' private:\n'
                '  friend class BrowserCaptionButtonContainer;\n'
                '\n'
                '  // Asks the DWM for, or away from, the native window backdrop. This is\n'
                '  // what the titlebar is left unpainted for; without it the frame would\n'
                '  // show whatever the compositor leaves behind.\n'
                '  void UpdateNativeFrameBackdrop();\n'
                '\n'
                '  // The backdrop last handed to the DWM, so that the attribute is only\n'
                '  // set when it actually changes.\n'
                '  std::optional<DWORD> applied_system_backdrop_;\n',
            ),
        ],
    },
    {
        'path': SOURCE_FILE,
        'marker': 'BrowserFrameViewWin::UpdateNativeFrameBackdrop',
        'replacements': [
            (
                'void BrowserFrameViewWin::OnPaint(gfx::Canvas* canvas) {\n'
                '  TRACE_EVENT0("views.frame", "BrowserFrameViewWin::OnPaint");\n'
                '  PaintTitlebar(canvas);\n'
                '}',
                'void BrowserFrameViewWin::OnPaint(gfx::Canvas* canvas) {\n'
                '  TRACE_EVENT0("views.frame", "BrowserFrameViewWin::OnPaint");\n'
                '  UpdateNativeFrameBackdrop();\n'
                '  PaintTitlebar(canvas);\n'
                '}',
            ),
            (
                '///////////////////////////////////////////////////////////////////////////////\n'
                '// BrowserFrameViewWin, private:\n'
                '\n'
                'int BrowserFrameViewWin::FrameBorderThickness() const {',
                '///////////////////////////////////////////////////////////////////////////////\n'
                '// BrowserFrameViewWin, private:\n'
                '\n'
                'void BrowserFrameViewWin::UpdateNativeFrameBackdrop() {\n'
                '  HWND hwnd = views::HWNDForWidget(browser_widget());\n'
                '  if (!hwnd) {\n'
                '    return;\n'
                '  }\n'
                '\n'
                '  // Mica is the desktop material Windows 11 uses behind a normal window;\n'
                '  // none of this happens unless the native frame materials are on, which\n'
                '  // already bails out on reduced transparency and forced colours.\n'
                '  const DWORD backdrop =\n'
                '      helium::ShouldUseNativeFrameMaterials(GetBrowserView())\n'
                '          ? DWMSBT_MAINWINDOW\n'
                '          : DWMSBT_NONE;\n'
                '  if (applied_system_backdrop_.has_value() &&\n'
                '      applied_system_backdrop_.value() == backdrop) {\n'
                '    return;\n'
                '  }\n'
                '\n'
                '  if (SUCCEEDED(::DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE,\n'
                '                                         &backdrop, sizeof(backdrop)))) {\n'
                '    applied_system_backdrop_ = backdrop;\n'
                '  }\n'
                '}\n'
                '\n'
                'int BrowserFrameViewWin::FrameBorderThickness() const {',
            ),
        ],
    },
]

DESCRIPTION = '''Draws the browser frame over the Windows 11 Mica backdrop.

paani-native-frame.patch leaves the titlebar unpainted on Windows so that a
native material can show through, but nothing asked the DWM for one.  This sets
DWMWA_SYSTEMBACKDROP_TYPE on the browser window: Mica while the native frame
materials are enabled, none when they are turned off.

Web contents keep their own opaque surface, so a page is never tinted.
'''

def main():
    BACKUP.mkdir(parents=True, exist_ok=True)
    chunks = [DESCRIPTION]

    for edit in EDITS:
        relative = edit['path']
        path = SOURCE / relative
        current = path.read_text(encoding='utf-8')

        if edit['marker'] in current:
            backup = BACKUP / (relative.replace('/', '_') + '.orig')
            if not backup.exists():
                raise SystemExit(f'{relative}: already patched, no pristine copy')
            original = backup.read_text(encoding='utf-8')
        else:
            shutil.copyfile(path, BACKUP / (relative.replace('/', '_') + '.orig'))
            original = current
            updated = current
            for old, new in edit['replacements']:
                if old not in updated:
                    raise SystemExit(f'{relative}: anchor not found:\n{old}')
                updated = updated.replace(old, new, 1)
            path.write_text(updated, encoding='utf-8', newline='\n')
            current = updated

        diff = ''.join(difflib.unified_diff(
            original.splitlines(keepends=True),
            current.splitlines(keepends=True),
            fromfile='a/' + relative,
            tofile='b/' + relative,
            n=3,
        ))
        if not diff:
            raise SystemExit(f'{relative}: produced no diff')
        chunks.append(diff)

    PATCH.write_text(''.join(chunks), encoding='utf-8', newline='\n')
    print(f'patch written to {PATCH}')


if __name__ == '__main__':
    main()
