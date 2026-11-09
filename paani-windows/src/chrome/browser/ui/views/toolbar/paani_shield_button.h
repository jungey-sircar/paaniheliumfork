// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_UI_VIEWS_TOOLBAR_PAANI_SHIELD_BUTTON_H_
#define CHROME_BROWSER_UI_VIEWS_TOOLBAR_PAANI_SHIELD_BUTTON_H_

#include <memory>

#include "base/callback_list.h"
#include "base/memory/raw_ptr.h"
#include "base/memory/scoped_refptr.h"
#include "base/memory/weak_ptr.h"
#include "chrome/browser/ui/views/toolbar/toolbar_button.h"
#include "components/prefs/pref_member.h"
#include "ui/base/metadata/metadata_header_macros.h"
#include "ui/menus/simple_menu_model.h"

class BrowserWindowInterface;

namespace content {
class WebContents;
}

namespace paani {

class PaaniAdblockState;

// Shows what Paani's built in blocker did to the tab being looked at, and lets
// that one site be allowlisted without leaving the toolbar.
//
// The number is per tab, taken from PaaniAdblockTabData, because the profile
// wide total in PaaniAdblockState would only ever go up and would say nothing
// about the page in front of the user.
class PaaniShieldButton : public ToolbarButton,
                          public ui::SimpleMenuModel::Delegate {
  METADATA_HEADER(PaaniShieldButton, ToolbarButton)

 public:
  explicit PaaniShieldButton(BrowserWindowInterface* browser);
  ~PaaniShieldButton() override;

  PaaniShieldButton(const PaaniShieldButton&) = delete;
  PaaniShieldButton& operator=(const PaaniShieldButton&) = delete;

  // Points the button at the tab whose counts and allowlist state it shows.
  // Called from ToolbarView::Update() whenever the active tab changes.
  void SetTab(content::WebContents* tab);

 private:
  enum CommandId {
    // Menu ids are local to this model, so they do not have to live in
    // chrome/browser/ui/chrome_commands_internal.
    kToggleSiteBlocking = 1,
  };

  void OnClicked();
  void OnAdblockPrefChanged();
  void UpdateContent();
  content::WebContents* CurrentTab() const;

  // ui::SimpleMenuModel::Delegate:
  bool IsCommandIdChecked(int command_id) const override;
  bool IsCommandIdEnabled(int command_id) const override;
  void ExecuteCommand(int command_id, int event_flags) override;

  const raw_ptr<BrowserWindowInterface> browser_;
  const scoped_refptr<PaaniAdblockState> state_;

  std::unique_ptr<ui::SimpleMenuModel> menu_model_;

  // Not owned; the tab data lives as long as the tab it counts for.
  raw_ptr<content::WebContents> observed_tab_ = nullptr;
  base::CallbackListSubscription blocked_count_subscription_;

  // Turns the button off with the blocker itself, so a disabled blocker does
  // not leave a control that pretends to be doing something.
  BooleanPrefMember enabled_pref_;

  base::WeakPtrFactory<PaaniShieldButton> weak_ptr_factory_{this};
};

}  // namespace paani

#endif  // CHROME_BROWSER_UI_VIEWS_TOOLBAR_PAANI_SHIELD_BUTTON_H_
