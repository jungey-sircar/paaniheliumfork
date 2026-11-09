// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#include "chrome/browser/ui/views/toolbar/paani_shield_button.h"

#include <string_view>

#include "base/functional/bind.h"
#include "base/strings/string_number_conversions.h"
#include "chrome/app/vector_icons/vector_icons.h"
#include "chrome/browser/paani/adblock/paani_adblock_service.h"
#include "chrome/browser/paani/adblock/paani_adblock_tab_data.h"
#include "chrome/browser/profiles/profile.h"
#include "chrome/browser/ui/browser_window/public/browser_window_interface.h"
#include "components/prefs/pref_member.h"
#include "components/tabs/public/tab_interface.h"
#include "content/public/browser/web_contents.h"
#include "ui/base/metadata/metadata_impl_macros.h"
#include "ui/base/mojom/menu_source_type.mojom.h"
#include "ui/views/accessibility/view_accessibility.h"
#include "ui/menus/simple_menu_model.h"
#include "url/gurl.h"

namespace paani {

namespace {

// The words live here instead of in generated_resources.grd because that
// header is included by a large part of the tree: one new IDS_ id rebuilds far
// more than the blocker itself is worth.
constexpr std::u16string_view kMenuTitle = u"Paani blocker";
constexpr std::u16string_view kToggleSiteLabel =
    u"Block ads and trackers on this site";
constexpr std::u16string_view kAccessibleName = u"Paani ad blocker";

std::u16string TooltipFor(bool blocking, int64_t blocked) {
  if (!blocking) {
    return u"Paani lets ads and trackers through on this site";
  }
  if (blocked == 0) {
    return u"Paani is blocking ads and trackers on this site";
  }
  return u"Paani blocked " +
         base::NumberToString16(blocked) +
         u" requests on this site";
}

}  // namespace

PaaniShieldButton::PaaniShieldButton(BrowserWindowInterface* browser)
    : ToolbarButton(base::BindRepeating(&PaaniShieldButton::OnClicked,
                                        base::Unretained(this))),
      browser_(browser),
      state_(PaaniAdblockServiceFactory::GetState(browser->GetProfile())) {
  menu_model_ = std::make_unique<ui::SimpleMenuModel>(this);
  menu_model_->AddTitle(std::u16string(kMenuTitle));
  menu_model_->AddCheckItem(kToggleSiteBlocking,
                            std::u16string(kToggleSiteLabel));

  SetVectorIcon(kPaaniDropIcon);
  SetImageLabelSpacing(4);
  GetViewAccessibility().SetName(std::u16string(kAccessibleName));

  enabled_pref_.Init(
      kPaaniAdblockEnabledPref, browser->GetProfile()->GetPrefs(),
      base::BindRepeating(&PaaniShieldButton::OnAdblockPrefChanged,
                          base::Unretained(this)));
  SetVisible(enabled_pref_.GetValue());

  UpdateContent();
}

PaaniShieldButton::~PaaniShieldButton() = default;

void PaaniShieldButton::SetTab(content::WebContents* tab) {
  if (tab != observed_tab_) {
    observed_tab_ = tab;
    // Dropping the subscription detaches from the tab that is going away; the
    // count of the next tab is watched instead.
    blocked_count_subscription_ = base::CallbackListSubscription();
    if (tab) {
      // The tab data is created here rather than waited for, because the first
      // blocked request is what would otherwise create it, and the button has
      // to be subscribed before that happens.
      PaaniAdblockTabData* tab_data =
          PaaniAdblockTabData::GetOrCreateForWebContents(tab);
      blocked_count_subscription_ = tab_data->blocked_count_changed().Add(
          base::BindRepeating(&PaaniShieldButton::UpdateContent,
                              weak_ptr_factory_.GetWeakPtr()));
    }
  }

  UpdateContent();
}

void PaaniShieldButton::OnClicked() {
  ShowMenuForModel(ui::mojom::MenuSourceType::kMouse, menu_model_.get());
}

void PaaniShieldButton::OnAdblockPrefChanged() {
  SetVisible(enabled_pref_.GetValue());
  if (GetVisible()) {
    UpdateContent();
  }
}

content::WebContents* PaaniShieldButton::CurrentTab() const {
  tabs::TabInterface* tab = browser_->GetActiveTabInterface();
  return tab ? tab->GetContents() : nullptr;
}

void PaaniShieldButton::UpdateContent() {
  content::WebContents* tab = CurrentTab();
  PaaniAdblockTabData* tab_data =
      tab ? PaaniAdblockTabData::FromWebContents(tab) : nullptr;
  const int64_t blocked = tab_data ? tab_data->blocked_count() : 0;
  const bool site_allowed = tab && state_->IsSiteAllowed(tab->GetURL());

  // Only a number that belongs to the page in front of the user is shown, and
  // only while this page is actually being filtered.
  SetText((site_allowed || blocked == 0)
              ? std::u16string()
              : base::NumberToString16(blocked));
  SetTooltipText(TooltipFor(!site_allowed, blocked));
  PreferredSizeChanged();
}

bool PaaniShieldButton::IsCommandIdChecked(int command_id) const {
  if (command_id != kToggleSiteBlocking) {
    return false;
  }
  content::WebContents* tab = CurrentTab();
  return !tab || !state_->IsSiteAllowed(tab->GetURL());
}

bool PaaniShieldButton::IsCommandIdEnabled(int command_id) const {
  if (command_id != kToggleSiteBlocking) {
    return false;
  }
  // There is no site to allow or block on an error page or on one of Paani's
  // own pages, so the item would do nothing there.
  content::WebContents* tab = CurrentTab();
  return tab && tab->GetURL().is_valid() &&
         tab->GetURL().SchemeIsHTTPOrHTTPS();
}

void PaaniShieldButton::ExecuteCommand(int command_id, int event_flags) {
  if (command_id != kToggleSiteBlocking) {
    return;
  }
  content::WebContents* tab = CurrentTab();
  if (!tab) {
    return;
  }

  const GURL url = tab->GetURL();
  if (state_->IsSiteAllowed(url)) {
    state_->DisallowSite(url);
  } else {
    state_->AllowSite(url);
  }

  UpdateContent();
}

BEGIN_METADATA(PaaniShieldButton)
END_METADATA

}  // namespace paani
