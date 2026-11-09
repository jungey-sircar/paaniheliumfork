// Copyright 2026 The Paani Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_UI_VIEWS_FRAME_PAANI_CHROME_BACKDROP_H_
#define CHROME_BROWSER_UI_VIEWS_FRAME_PAANI_CHROME_BACKDROP_H_

#include "build/build_config.h"
#include "third_party/skia/include/core/SkColor.h"
#include "ui/gfx/geometry/rect.h"

namespace gfx {
class Canvas;
}

namespace views {
class View;
}

namespace paani {

#if BUILDFLAG(IS_WIN)

// Paints the desktop material that Paani shows behind its translucent chrome.
//
// Windows only renders its own backdrop where the app leaves pixels transparent,
// and Chromium composites an opaque surface, so an unpainted titlebar reads as
// black rather than Mica. This draws the equivalent material itself: the desktop
// wallpaper, blurred and tinted the way Windows tints it, cropped to the part of
// the desktop the window covers, so the chrome lines up with the desktop the way
// a real backdrop would.
//
// `bounds_in_view` is in the local coordinates of `view`. When no desktop
// material can be produced, because the desktop has no readable wallpaper or the
// image cannot be decoded, `fallback_color` is painted instead so the chrome is
// solid rather than black. Web contents live on a separate opaque surface and
// are never reached by this.
void PaintChromeBackdrop(gfx::Canvas* canvas,
                         views::View* view,
                         const gfx::Rect& bounds_in_view,
                         SkColor fallback_color);

#endif  // BUILDFLAG(IS_WIN)

}  // namespace paani

#endif  // CHROME_BROWSER_UI_VIEWS_FRAME_PAANI_CHROME_BACKDROP_H_
