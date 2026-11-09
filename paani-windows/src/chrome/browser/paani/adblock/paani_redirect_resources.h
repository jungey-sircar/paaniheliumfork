// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_PAANI_ADBLOCK_PAANI_REDIRECT_RESOURCES_H_
#define CHROME_BROWSER_PAANI_ADBLOCK_PAANI_REDIRECT_RESOURCES_H_

#include <stddef.h>

namespace paani {

// One stub resource a $redirect= rule can name, for example "gpt.js" in place
// of googletagservices.com/faf/gpt.js.
//
// The table is generated from Helium's uBlock component, see
// build/patchwork/make_redirect_resources.py. The payload is not duplicated:
// `resource_id` is the grit id of the file inside resources.pak, so the bytes
// ship with the browser already.
struct PaaniRedirectResource {
  const char* name;
  int resource_id;
  const char* const* aliases;
  size_t alias_count;
};

extern const PaaniRedirectResource kPaaniRedirectResources[];
extern const size_t kPaaniRedirectResourceCount;

}  // namespace paani

#endif  // CHROME_BROWSER_PAANI_ADBLOCK_PAANI_REDIRECT_RESOURCES_H_
