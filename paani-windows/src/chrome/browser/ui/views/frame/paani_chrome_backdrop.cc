// Copyright 2026 The Paani Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "chrome/browser/ui/views/frame/paani_chrome_backdrop.h"

#include "build/build_config.h"

#if BUILDFLAG(IS_WIN)

#include <windows.h>

#include <algorithm>
#include <memory>
#include <string>

#include "base/no_destructor.h"
#include "base/strings/string_number_conversions.h"
#include "base/strings/utf_string_conversions.h"
#include "base/time/time.h"
#include "third_party/skia/include/codec/SkCodec.h"
#include "third_party/skia/include/core/SkBitmap.h"
#include "third_party/skia/include/core/SkCanvas.h"
#include "third_party/skia/include/core/SkColor.h"
#include "third_party/skia/include/core/SkData.h"
#include "third_party/skia/include/core/SkImage.h"
#include "third_party/skia/include/core/SkPaint.h"
#include "third_party/skia/include/core/SkRefCnt.h"
#include "third_party/skia/include/core/SkRect.h"
#include "third_party/skia/include/core/SkSamplingOptions.h"
#include "third_party/skia/include/core/SkSize.h"
#include "third_party/skia/include/effects/SkImageFilters.h"
#include "ui/display/display.h"
#include "ui/display/screen.h"
#include "ui/gfx/canvas.h"
#include "ui/gfx/geometry/rect.h"
#include "ui/gfx/geometry/size.h"
#include "ui/gfx/image/image_skia.h"
#include "ui/gfx/image/image_skia_rep.h"
#include "ui/views/view.h"
#include "ui/views/widget/widget.h"

namespace paani {
namespace {

// Windows blurs the desktop before it tints it. This is in the same ballpark,
// and unlike the real material it is only paid for when the desktop changes,
// because the result is cached at the size of the display.
constexpr float kBlurSigmaInDip = 30.0f;

// The Paani water tint, laid over the blurred desktop: transparent enough that
// the desktop still reads through the chrome, opaque enough that chrome text
// stays legible on any wallpaper.
constexpr SkColor kTintColor =
    SkColorSetARGB(static_cast<SkAlpha>(0x99), 0x0E, 0x2A, 0x38);

// How often the shell is asked for the wallpaper while painting, so a desktop
// change is picked up without a registry read on every frame.
constexpr base::TimeDelta kWallpaperRecheckInterval = base::Seconds(5);

// `WallpaperStyle` values from the wallpaper settings page. Anything unknown is
// treated as fill, which is what Windows 11 uses by default.
constexpr int kStyleCenter = 0;
constexpr int kStyleStretch = 2;
constexpr int kStyleFit = 6;
constexpr int kStyleFill = 10;

std::wstring ReadWallpaperPath() {
  wchar_t path[MAX_PATH] = {};
  if (!::SystemParametersInfoW(SPI_GETDESKWALLPAPER, MAX_PATH - 1, &path, 0)) {
    return std::wstring();
  }
  return std::wstring(path);
}

int ReadWallpaperStyle() {
  wchar_t buffer[16] = {};
  DWORD size = sizeof(buffer);
  if (::RegGetValueW(HKEY_CURRENT_USER, L"Control Panel\\Desktop",
                     L"WallpaperStyle", RRF_RT_REG_SZ, nullptr, buffer,
                     &size) != ERROR_SUCCESS) {
    return kStyleFill;
  }
  int style = kStyleFill;
  if (!base::StringToInt(base::WideToUTF8(std::wstring(buffer)), &style)) {
    return kStyleFill;
  }
  return style;
}

// The part of `dst_size` that a `src_size` wallpaper occupies under `style`.
// Whatever a style leaves uncovered is painted with the desktop colour first,
// the same way the shell does.
gfx::Rect FittedWallpaperRect(SkISize src_size,
                              const gfx::Size& dst_size,
                              int style) {
  if (src_size.width() <= 0 || src_size.height() <= 0 || dst_size.IsEmpty()) {
    return gfx::Rect();
  }

  if (style == kStyleStretch) {
    return gfx::Rect(dst_size);
  }

  const double src_w = src_size.width();
  const double src_h = src_size.height();
  double scale = 1.0;
  if (style == kStyleFit) {
    scale = std::min(dst_size.width() / src_w, dst_size.height() / src_h);
  } else if (style != kStyleCenter) {
    scale = std::max(dst_size.width() / src_w, dst_size.height() / src_h);
  }

  const int w = std::max(1, static_cast<int>(src_w * scale));
  const int h = std::max(1, static_cast<int>(src_h * scale));
  return gfx::Rect((dst_size.width() - w) / 2, (dst_size.height() - h) / 2, w,
                   h);
}

struct DesktopMaterial {
  // What the cached image was built from. A change in any of these means the
  // image is rebuilt.
  std::wstring wallpaper_path;
  int style = kStyleFill;
  gfx::Size size_in_pixels;
  float device_scale_factor = 1.0f;

  gfx::ImageSkia image;
  base::TimeTicks last_checked;
};

DesktopMaterial& state() {
  static base::NoDestructor<DesktopMaterial> material;
  return *material;
}

// Returns the blurred, tinted desktop image for `display`, rebuilt only when
// the wallpaper, its style, or the display changed. Returns an empty image when
// there is no desktop to blur, which callers answer with a solid colour.
const gfx::ImageSkia& GetMaterial(const display::Display& display) {
  DesktopMaterial& material = state();

  const base::TimeTicks now = base::TimeTicks::Now();
  const bool due = material.last_checked.is_null() ||
                   now - material.last_checked >= kWallpaperRecheckInterval;
  if (due) {
    material.last_checked = now;
  }
  const std::wstring path = due ? ReadWallpaperPath() : material.wallpaper_path;
  const int style = due ? ReadWallpaperStyle() : material.style;
  const gfx::Size pixels = display.GetSizeInPixel();
  const float dsf = static_cast<float>(display.device_scale_factor());

  const bool unchanged =
      path == material.wallpaper_path && style == material.style &&
      pixels == material.size_in_pixels && dsf == material.device_scale_factor;
  if (unchanged) {
    return material.image;
  }

  material.wallpaper_path = path;
  material.style = style;
  material.size_in_pixels = pixels;
  material.device_scale_factor = dsf;
  // The empty image is what callers of GetMaterial() see until a desktop is
  // found, so an unusable desktop is not retried on every paint either.
  material.image = gfx::ImageSkia();

  // A solid-colour desktop has nothing to blur; the chrome falls back to solid.
  if (path.empty()) {
    return material.image;
  }

  sk_sp<SkData> encoded =
      SkData::MakeFromFileName(base::WideToUTF8(path).c_str());
  if (!encoded) {
    return material.image;
  }

  std::unique_ptr<SkCodec> codec = SkCodec::MakeFromData(std::move(encoded));
  if (!codec) {
    return material.image;
  }
  const SkImageInfo info = codec->getInfo().makeAlphaType(kPremul_SkAlphaType);
  if (info.width() <= 0 || info.height() <= 0) {
    return material.image;
  }
  SkBitmap wallpaper;
  wallpaper.allocPixels(info);
  if (wallpaper.empty()) {
    return material.image;
  }
  if (codec->getPixels(info, wallpaper.getPixels(), wallpaper.rowBytes()) !=
      SkCodec::kSuccess) {
    return material.image;
  }

  const COLORREF desktop_color = ::GetSysColor(COLOR_DESKTOP);
  sk_sp<SkImage> wallpaper_image = wallpaper.asImage();
  if (!wallpaper_image) {
    return material.image;
  }

  // The whole desktop is painted once, at its pixel size, so moving or resizing
  // a window only changes which part of it gets sampled.
  SkBitmap desktop_bitmap;
  desktop_bitmap.allocPixels(
      SkImageInfo::MakeN32Premul(pixels.width(), pixels.height()));
  if (desktop_bitmap.empty()) {
    return material.image;
  }

  SkCanvas desktop_canvas(desktop_bitmap);
  desktop_canvas.clear(SkColorSetRGB(GetRValue(desktop_color),
                                     GetGValue(desktop_color),
                                     GetBValue(desktop_color)));

  const gfx::Rect fitted = FittedWallpaperRect(
      SkISize::Make(wallpaper.width(), wallpaper.height()), pixels, style);
  if (fitted.IsEmpty()) {
    return material.image;
  }

  const float sigma = std::max(1.0f, kBlurSigmaInDip * dsf);
  SkPaint blur_paint;
  blur_paint.setImageFilter(SkImageFilters::Blur(sigma, sigma, SkTileMode::kClamp,
                                                 nullptr, nullptr));
  desktop_canvas.drawImageRect(
      wallpaper_image.get(),
      SkRect::MakeIWH(wallpaper_image->width(), wallpaper_image->height()),
      SkRect::MakeXYWH(fitted.x(), fitted.y(), fitted.width(), fitted.height()),
      SkSamplingOptions(SkFilterMode::kLinear), &blur_paint,
      SkCanvas::kFast_SrcRectConstraint);
  desktop_canvas.drawColor(kTintColor);

  // The cached image is tagged with the display's scale factor, so its DIP size
  // is the desktop's DIP size and a window's chrome can be filled from it
  // without any resampling.
  material.image = gfx::ImageSkia(
      gfx::ImageSkiaRep(desktop_bitmap, display.device_scale_factor()));
  return material.image;
}

}  // namespace

void PaintChromeBackdrop(gfx::Canvas* canvas,
                         views::View* view,
                         const gfx::Rect& bounds_in_view,
                         SkColor fallback_color) {
  if (bounds_in_view.IsEmpty()) {
    return;
  }

  views::Widget* widget = view ? view->GetWidget() : nullptr;
  display::Screen* screen = display::Screen::Get();
  const gfx::ImageSkia* material = nullptr;
  display::Display display;
  gfx::Rect screen_bounds;
  if (widget && screen) {
    const gfx::Rect window_bounds = widget->GetWindowBoundsInScreen();
    display = screen->GetDisplayNearestPoint(window_bounds.CenterPoint());
    material = &GetMaterial(display);
    screen_bounds = bounds_in_view;
    screen_bounds.Offset(window_bounds.OffsetFromOrigin());
  }

  if (!material || material->isNull()) {
    canvas->FillRect(bounds_in_view, fallback_color);
    return;
  }

  // Map the region being painted from screen DIPs onto the cached desktop, and
  // clamp to what the cache holds. A window can hang over the edge of the
  // display it is mapped to, and then the chrome only covers as much desktop as
  // there is.
  const double left = screen_bounds.x() - display.bounds().x();
  const double top = screen_bounds.y() - display.bounds().y();
  const double right = screen_bounds.right() - display.bounds().x();
  const double bottom = screen_bounds.bottom() - display.bounds().y();

  const double max_x = material->width();
  const double max_y = material->height();
  const double crop_left = std::clamp(left, 0.0, max_x);
  const double crop_top = std::clamp(top, 0.0, max_y);
  const double crop_right = std::clamp(right, crop_left, max_x);
  const double crop_bottom = std::clamp(bottom, crop_top, max_y);
  if (crop_right <= crop_left || crop_bottom <= crop_top) {
    canvas->FillRect(bounds_in_view, fallback_color);
    return;
  }

  // Source and destination are both in DIPs here, so the desktop lands on the
  // chrome at the same scale it has on the screen.
  canvas->DrawImageInt(
      *material, static_cast<int>(crop_left), static_cast<int>(crop_top),
      static_cast<int>(crop_right - crop_left),
      static_cast<int>(crop_bottom - crop_top),
      bounds_in_view.x() + static_cast<int>(crop_left - left),
      bounds_in_view.y() + static_cast<int>(crop_top - top),
      static_cast<int>(crop_right - crop_left),
      static_cast<int>(crop_bottom - crop_top),
      /*filter=*/true);
}

}  // namespace paani

#endif  // BUILDFLAG(IS_WIN)
