"""Records the Paani desktop material as a quilt patch.

Helium's native frame materials leave the chrome unpainted so that the operating
system's own material shows through. That works on macOS, where a real visual
effect view sits behind the window, but on Windows Chromium composites an opaque
surface: the DWM never gets a chance to draw Mica, and an unpainted titlebar
reads as black. This was measured on a live window -- forcing the backdrop to
none, Acrylic and Mica from outside the process left the titlebar pixels
identical (mean RGB 2,2,2 in all three).

So Paani paints the material itself: the desktop wallpaper, blurred and tinted
the way Windows tints it, cropped to the part of the desktop the window covers.
The band it paints is the whole top of the window -- titlebar, tab strip,
toolbar and bookmark bar -- because those are the views that skip painting under
native materials, and the tabs composite their own translucent colours on top of
it. Web contents stay on their opaque surface and are never covered.

`paani_chrome_backdrop.{h,cc}` are staged sources; this patch is only the call
site and its BUILD.gn wiring.
"""

import difflib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'build' / 'src'
BACKUP = ROOT / 'build' / 'patchwork' / 'orig' / 'backdrop'
PATCH = ROOT / 'patches' / 'paani' / 'windows' / 'paani-water-backdrop.patch'

HEADER = 'chrome/browser/ui/views/frame/browser_frame_view_win.h'
SOURCE_FILE = 'chrome/browser/ui/views/frame/browser_frame_view_win.cc'
BUILD = 'chrome/browser/ui/views/frame/BUILD.gn'

EDITS = [
    {
        'path': HEADER,
        'marker': 'PaintPaaniChromeBackdrop',
        'replacements': [
            (
                '  // Asks the DWM for, or away from, the native window backdrop. This is\n'
                '  // what the titlebar is left unpainted for; without it the frame would\n'
                '  // show whatever the compositor leaves behind.\n'
                '  void UpdateNativeFrameBackdrop();\n',
                '  // Asks the DWM for, or away from, the native window backdrop. This is\n'
                '  // what the titlebar is left unpainted for; without it the frame would\n'
                '  // show whatever the compositor leaves behind.\n'
                '  void UpdateNativeFrameBackdrop();\n'
                '\n'
                '  // Paints the desktop material across the band of chrome above the web\n'
                '  // contents and reports whether it did. Windows only draws its own\n'
                '  // material where an app leaves pixels transparent, and Chromium\n'
                '  // composites an opaque surface, so the material is drawn here instead.\n'
                '  bool PaintPaaniChromeBackdrop(gfx::Canvas* canvas);\n',
            ),
        ],
    },
    {
        'path': SOURCE_FILE,
        'marker': 'BrowserFrameViewWin::PaintPaaniChromeBackdrop',
        'replacements': [
            (
                '#include "chrome/browser/ui/views/frame/minimize_button_metrics_win.h"\n',
                '#include "chrome/browser/ui/views/frame/minimize_button_metrics_win.h"\n'
                '#include "chrome/browser/ui/views/frame/paani_chrome_backdrop.h"\n'
                '#include "chrome/browser/ui/views/frame/top_container_view.h"\n',
            ),
            (
                'void BrowserFrameViewWin::OnPaint(gfx::Canvas* canvas) {\n'
                '  TRACE_EVENT0("views.frame", "BrowserFrameViewWin::OnPaint");\n'
                '  UpdateNativeFrameBackdrop();\n'
                '  PaintTitlebar(canvas);\n'
                '}',
                'void BrowserFrameViewWin::OnPaint(gfx::Canvas* canvas) {\n'
                '  TRACE_EVENT0("views.frame", "BrowserFrameViewWin::OnPaint");\n'
                '  UpdateNativeFrameBackdrop();\n'
                '  if (PaintPaaniChromeBackdrop(canvas)) {\n'
                '    return;\n'
                '  }\n'
                '  PaintTitlebar(canvas);\n'
                '}',
            ),
            (
                '  if (SUCCEEDED(::DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE,\n'
                '                                         &backdrop, sizeof(backdrop)))) {\n'
                '    applied_system_backdrop_ = backdrop;\n'
                '  }\n'
                '}\n',
                '  if (SUCCEEDED(::DwmSetWindowAttribute(hwnd, DWMWA_SYSTEMBACKDROP_TYPE,\n'
                '                                         &backdrop, sizeof(backdrop)))) {\n'
                '    applied_system_backdrop_ = backdrop;\n'
                '  }\n'
                '}\n'
                '\n'
                'bool BrowserFrameViewWin::PaintPaaniChromeBackdrop(gfx::Canvas* canvas) {\n'
                '  if (!helium::ShouldUseNativeFrameMaterials(GetBrowserView())) {\n'
                '    return false;\n'
                '  }\n'
                '\n'
                '  // Under native materials every view in this band declines to paint a\n'
                '  // background of its own, so one draw behind all of them is the whole\n'
                '  // translucent chrome: titlebar, tab strip, toolbar and bookmark bar.\n'
                '  // The tabs themselves blend their tab colour towards transparent, so\n'
                '  // they read as frosted over this rather than sitting on black.\n'
                '  int bottom = TitlebarHeight(false);\n'
                '  if (views::View* top_container = GetBrowserView()->top_container()) {\n'
                '    gfx::Point container_bottom =\n'
                '        top_container->GetLocalBounds().bottom_right();\n'
                '    views::View::ConvertPointToTarget(top_container, this,\n'
                '                                     &container_bottom);\n'
                '    bottom = std::max(bottom, container_bottom.y());\n'
                '  }\n'
                '\n'
                '  // A desktop with no readable wallpaper is answered with a solid frame,\n'
                '  // which is what the fallback in the paint helper already does.\n'
                '  paani::PaintChromeBackdrop(canvas, this,\n'
                '                               gfx::Rect(0, 0, width(), bottom),\n'
                '                               GetFrameColor(BrowserFrameActiveState::\n'
                '                                             kUseCurrent));\n'
                '  return true;\n'
                '}\n',
            ),
        ],
    },
    {
        'path': BUILD,
        'marker': 'paani_chrome_backdrop',
        'replacements': [
            (
                '  source_set("browser_frame_view_win_impl") {\n',
                '  source_set("paani_chrome_backdrop") {\n'
                '    public = [ "paani_chrome_backdrop.h" ]\n'
                '    sources = [ "paani_chrome_backdrop.cc" ]\n'
                '    public_deps = [\n'
                '      "//base",\n'
                '      "//ui/gfx",\n'
                '      "//ui/gfx/geometry",\n'
                '      "//ui/views",\n'
                '    ]\n'
                '\n'
                '    deps = [\n'
                '      "//cc/paint",\n'
                '      "//skia",\n'
                '      "//ui/display",\n'
                '    ]\n'
                '  }\n'
                '\n'
                '  source_set("browser_frame_view_win_impl") {\n',
            ),
            (
                '    deps = [\n'
                '      ":browser_caption_button_container_win",\n',
                '    deps = [\n'
                '      ":browser_caption_button_container_win",\n'
                '      ":paani_chrome_backdrop",\n',
            ),
        ],
    },
]

DESCRIPTION = '''Paints the Paani chrome material where Windows will not.

Helium leaves the frame unpainted under native frame materials so a native
material can show through, and paani-mica-backdrop.patch asks the DWM for Mica.
Neither is visible on Windows: Chromium composites an opaque surface, so the
unpainted chrome shows black. Measured on a live window - forcing the backdrop
to none, Acrylic and Mica from outside the process left identical titlebar
pixels - while the attribute itself reads back DWMSBT_MAINWINDOW with S_OK.

So Paani draws the material itself over the band of chrome above the web
contents: the desktop wallpaper, blurred and tinted the way Windows tints it,
cropped to the part of the desktop the window covers. Tabs already blend their
colour towards transparent under native materials, so they sit on it as frosted
glass instead of on black. When the desktop has no readable wallpaper the band is
painted with the frame colour, which is the documented solid fallback.

Web contents are a separate opaque surface and are never covered.
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
