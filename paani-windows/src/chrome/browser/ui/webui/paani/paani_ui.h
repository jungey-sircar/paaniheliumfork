// Copyright 2026 The Paani Browser Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_UI_WEBUI_PAANI_PAANI_UI_H_
#define CHROME_BROWSER_UI_WEBUI_PAANI_PAANI_UI_H_

#include <memory>

#include "chrome/browser/ui/webui/paani/paani.mojom.h"
#include "chrome/common/webui_url_constants.h"
#include "content/public/browser/webui_config.h"
#include "content/public/common/url_constants.h"
#include "mojo/public/cpp/bindings/pending_receiver.h"
#include "mojo/public/cpp/bindings/receiver.h"
#include "ui/webui/mojo_web_ui_controller.h"

class PaaniHandler;
class PaaniUI;

class PaaniUIConfig : public content::DefaultWebUIConfig<PaaniUI> {
 public:
  PaaniUIConfig()
      : DefaultWebUIConfig(content::kChromeUIScheme,
                           chrome::kChromeUIPaaniHost) {}
};

// The WebUI for chrome://paani
class PaaniUI : public ui::MojoWebUIController,
                public paani::mojom::PageHandlerFactory {
 public:
  explicit PaaniUI(content::WebUI* web_ui);

  PaaniUI(const PaaniUI&) = delete;
  PaaniUI& operator=(const PaaniUI&) = delete;

  ~PaaniUI() override;

  // Instantiates the implementor of the paani::mojom::PageHandlerFactory mojo
  // interface passing the pending receiver that will be internally bound.
  void BindInterface(mojo::PendingReceiver<paani::mojom::PageHandlerFactory> receiver);

 private:
  // paani::mojom::PageHandlerFactory:
  void CreatePaaniHandler(
      mojo::PendingReceiver<paani::mojom::PaaniHandler> receiver) override;

  std::unique_ptr<PaaniHandler> page_handler_;
  mojo::Receiver<paani::mojom::PageHandlerFactory> page_factory_receiver_{this};

  WEB_UI_CONTROLLER_TYPE_DECL();
};

#endif  // CHROME_BROWSER_UI_WEBUI_PAANI_PAANI_UI_H_
