// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_ENGINE_H_
#define CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_ENGINE_H_

#include <memory>
#include <string>
#include <vector>

namespace paani {

// One stub resource a $redirect= rule can name. `content` holds the raw bytes
// of the payload; the engine encodes them the way adblock-rust expects.
struct PaaniRedirectResourceData {
  std::string name;
  std::vector<std::string> aliases;
  std::string content;
};

// Owns a Brave adblock-rust engine.
//
// The engine is not thread safe, so an instance must only be used from the
// thread that created it.
class PaaniAdblockEngine {
 public:
  // Builds an engine from the given filter lists and redirect stubs. Returns
  // nullptr if the engine could not be created.
  static std::unique_ptr<PaaniAdblockEngine> Create(
      const std::vector<std::string>& filter_lists,
      std::vector<PaaniRedirectResourceData> redirect_resources);

  ~PaaniAdblockEngine();

  PaaniAdblockEngine(const PaaniAdblockEngine&) = delete;
  PaaniAdblockEngine& operator=(const PaaniAdblockEngine&) = delete;

  // Returns true if the request must be blocked. `rewritten_url` is set when
  // a filter rule asked for the request URL to be rewritten.
  //
  // `redirect` is set to the stub that should be served in place of the
  // request, as a data: URL. It is only useful when the function also returns
  // true: a rule with $redirect-rule= names a stub without blocking, and
  // replacing the body of a request that is allowed to load would be wrong.
  bool ShouldBlock(const std::string& url,
                   const std::string& source_url,
                   const std::string& request_type,
                   const std::string& method,
                   std::string* rewritten_url,
                   std::string* redirect) const;

 private:
  explicit PaaniAdblockEngine(void* engine);

  void* engine_;
};

}  // namespace paani

#endif  // CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_ENGINE_H_
