// Copyright 2026 The Paani Browser Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_UI_WEBUI_PAANI_PAANI_HANDLER_H_
#define CHROME_BROWSER_UI_WEBUI_PAANI_PAANI_HANDLER_H_

#include <string>
#include <vector>

#include "base/memory/raw_ptr.h"
#include "chrome/browser/ui/webui/paani/paani.mojom.h"
#include "mojo/public/cpp/bindings/pending_receiver.h"
#include "mojo/public/cpp/bindings/receiver.h"

class Profile;

namespace content {
class WebUI;
}  // namespace content

// Handles API requests from the chrome://paani page by implementing
// paani::mojom::PaaniHandler.
class PaaniHandler : public paani::mojom::PaaniHandler {
 public:
  PaaniHandler(content::WebUI* web_ui,
               mojo::PendingReceiver<paani::mojom::PaaniHandler> receiver);

  PaaniHandler(const PaaniHandler&) = delete;
  PaaniHandler& operator=(const PaaniHandler&) = delete;

  ~PaaniHandler() override;

  // paani::mojom::PaaniHandler:
  void GetState(GetStateCallback callback) override;
  void SetEnabled(bool enabled, SetEnabledCallback callback) override;
  void AllowSite(const std::string& site, AllowSiteCallback callback) override;
  void DisallowSite(const std::string& site,
                    DisallowSiteCallback callback) override;
  void ResetCounter(ResetCounterCallback callback) override;

 private:
  raw_ptr<Profile> profile_;
  mojo::Receiver<paani::mojom::PaaniHandler> receiver_;
};

#endif  // CHROME_BROWSER_UI_WEBUI_PAANI_PAANI_HANDLER_H_
