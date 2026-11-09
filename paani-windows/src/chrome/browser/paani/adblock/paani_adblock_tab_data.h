// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_TAB_DATA_H_
#define CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_TAB_DATA_H_

#include <stdint.h>

#include "base/callback_list.h"
#include "base/sequence_checker.h"
#include "content/public/browser/web_contents_user_data.h"

namespace paani {

// The requests Paani's built in blocker stopped in one tab.
//
// The profile wide total in PaaniAdblockState cannot answer the question the
// toolbar button is asked, which is what happened on the page being looked at,
// so each tab keeps its own count too.
class PaaniAdblockTabData
    : public content::WebContentsUserData<PaaniAdblockTabData> {
 public:
  ~PaaniAdblockTabData() override;

  PaaniAdblockTabData(const PaaniAdblockTabData&) = delete;
  PaaniAdblockTabData& operator=(const PaaniAdblockTabData&) = delete;

  // Records one blocked request and tells whoever is watching this tab.
  void AddBlocked();

  int64_t blocked_count() const {
    DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
    return blocked_count_;
  }

  base::RepeatingClosureList& blocked_count_changed() {
    return blocked_count_changed_;
  }

 private:
  explicit PaaniAdblockTabData(content::WebContents* web_contents);

  friend class content::WebContentsUserData<PaaniAdblockTabData>;

  SEQUENCE_CHECKER(sequence_checker_);
  int64_t blocked_count_ = 0;
  base::RepeatingClosureList blocked_count_changed_;

  WEB_CONTENTS_USER_DATA_KEY_DECL();
};

}  // namespace paani

#endif  // CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_TAB_DATA_H_
