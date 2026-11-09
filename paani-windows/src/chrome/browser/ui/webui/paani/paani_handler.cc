// Copyright 2026 The Paani Browser Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "chrome/browser/ui/webui/paani/paani_handler.h"

#include <string>
#include <utility>
#include <vector>

#include "base/memory/raw_ptr.h"
#include "chrome/browser/paani/adblock/paani_adblock_service.h"
#include "chrome/browser/profiles/profile.h"
#include "components/prefs/pref_service.h"
#include "content/public/browser/web_ui.h"
#include "url/gurl.h"

namespace {

// Turns a bare host into a URL so that the allowlist helpers can use the
// regular registrable domain logic.
GURL URLForSite(const std::string& site) {
  if (site.empty()) {
    return GURL();
  }
  if (site.find("://") != std::string::npos) {
    return GURL(site);
  }
  return GURL("https://" + site);
}

}  // namespace

PaaniHandler::PaaniHandler(content::WebUI* web_ui,
                           mojo::PendingReceiver<paani::mojom::PaaniHandler> receiver)
    : profile_(Profile::FromWebUI(web_ui)),
      receiver_(this, std::move(receiver)) {}

PaaniHandler::~PaaniHandler() = default;

void PaaniHandler::GetState(GetStateCallback callback) {
  scoped_refptr<paani::PaaniAdblockState> state =
      paani::PaaniAdblockServiceFactory::GetState(profile_);
  if (!state) {
    std::move(callback).Run(false, 0, std::vector<std::string>(),
                            paani::mojom::PaaniEngineInfo::New());
    return;
  }

  auto engine = paani::mojom::PaaniEngineInfo::New();
  engine->engine_ready = state->engine_ready();
  engine->lists_loaded = state->lists_loaded();
  engine->list_bytes = state->list_bytes();
  engine->approx_rules = state->approx_rules();
  engine->factories_installed = state->factories_installed();

  std::move(callback).Run(state->enabled(), state->blocked_request_count(),
                          state->GetAllowedSites(), std::move(engine));
}

void PaaniHandler::SetEnabled(bool enabled, SetEnabledCallback callback) {
  scoped_refptr<paani::PaaniAdblockState> state =
      paani::PaaniAdblockServiceFactory::GetState(profile_);
  if (!state) {
    std::move(callback).Run(false);
    return;
  }
  state->set_enabled(enabled);
  // The preference is the value the blocker starts with on the next run, so it
  // has to follow the toggle.
  profile_->GetPrefs()->SetBoolean(paani::kPaaniAdblockEnabledPref, enabled);
  std::move(callback).Run(state->enabled());
}

void PaaniHandler::AllowSite(const std::string& site,
                             AllowSiteCallback callback) {
  scoped_refptr<paani::PaaniAdblockState> state =
      paani::PaaniAdblockServiceFactory::GetState(profile_);
  if (!state) {
    std::move(callback).Run(std::vector<std::string>());
    return;
  }
  state->AllowSite(URLForSite(site));
  std::move(callback).Run(state->GetAllowedSites());
}

void PaaniHandler::DisallowSite(const std::string& site,
                                DisallowSiteCallback callback) {
  scoped_refptr<paani::PaaniAdblockState> state =
      paani::PaaniAdblockServiceFactory::GetState(profile_);
  if (!state) {
    std::move(callback).Run(std::vector<std::string>());
    return;
  }
  state->DisallowSite(URLForSite(site));
  std::move(callback).Run(state->GetAllowedSites());
}

void PaaniHandler::ResetCounter(ResetCounterCallback callback) {
  scoped_refptr<paani::PaaniAdblockState> state =
      paani::PaaniAdblockServiceFactory::GetState(profile_);
  if (!state) {
    std::move(callback).Run(0);
    return;
  }
  state->reset_blocked_request_count();
  std::move(callback).Run(state->blocked_request_count());
}
