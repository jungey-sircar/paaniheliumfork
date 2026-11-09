// Copyright 2026 The Paani Browser Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "chrome/browser/ui/webui/paani/paani_ui.h"

#include <utility>

#include "chrome/browser/profiles/profile.h"
#include "chrome/browser/ui/webui/paani/paani_handler.h"
#include "chrome/grit/paani_resources.h"
#include "chrome/grit/paani_resources_map.h"
#include "content/public/browser/web_ui.h"
#include "content/public/browser/web_ui_data_source.h"
#include "ui/webui/webui_util.h"

PaaniUI::PaaniUI(content::WebUI* web_ui) : ui::MojoWebUIController(web_ui) {
  Profile* profile = Profile::FromWebUI(web_ui);

  // Set up the chrome://paani source.
  content::WebUIDataSource* paani = content::WebUIDataSource::CreateAndAdd(
      profile, chrome::kChromeUIPaaniHost);
  webui::SetupWebUIDataSource(paani, kPaaniResources, IDR_PAANI_PAANI_HTML);
}

WEB_UI_CONTROLLER_TYPE_IMPL(PaaniUI)

PaaniUI::~PaaniUI() = default;

void PaaniUI::BindInterface(
    mojo::PendingReceiver<paani::mojom::PageHandlerFactory> receiver) {
  page_factory_receiver_.reset();
  page_factory_receiver_.Bind(std::move(receiver));
}

void PaaniUI::CreatePaaniHandler(
    mojo::PendingReceiver<paani::mojom::PaaniHandler> receiver) {
  page_handler_ = std::make_unique<PaaniHandler>(web_ui(), std::move(receiver));
}
