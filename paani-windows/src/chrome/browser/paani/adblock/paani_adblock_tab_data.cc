// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#include "chrome/browser/paani/adblock/paani_adblock_tab_data.h"

#include "content/public/browser/web_contents.h"

namespace paani {

PaaniAdblockTabData::PaaniAdblockTabData(content::WebContents* web_contents)
    : content::WebContentsUserData<PaaniAdblockTabData>(*web_contents) {}

PaaniAdblockTabData::~PaaniAdblockTabData() = default;

void PaaniAdblockTabData::AddBlocked() {
  DCHECK_CALLED_ON_VALID_SEQUENCE(sequence_checker_);
  ++blocked_count_;
  blocked_count_changed_.Notify();
}

WEB_CONTENTS_USER_DATA_KEY_IMPL(PaaniAdblockTabData);

}  // namespace paani
