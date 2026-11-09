// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#include "chrome/browser/paani/adblock/paani_adblock_engine.h"

#include <stdint.h>

#include <utility>
#include <vector>

#include "base/base64.h"
#include "base/logging.h"
#include "chrome/browser/paani/adblock/paani_adblock_rust.h"

namespace paani {

namespace {

constexpr int kAllow = 0;
constexpr int kBlock = 1;
constexpr int kError = -1;

}  // namespace

std::unique_ptr<PaaniAdblockEngine> PaaniAdblockEngine::Create(
    const std::vector<std::string>& filter_lists,
    std::vector<PaaniRedirectResourceData> redirect_resources) {
  if (filter_lists.empty()) {
    return nullptr;
  }

  std::vector<const uint8_t*> list_ptrs;
  std::vector<size_t> list_lens;
  list_ptrs.reserve(filter_lists.size());
  list_lens.reserve(filter_lists.size());
  for (const std::string& list : filter_lists) {
    list_ptrs.push_back(reinterpret_cast<const uint8_t*>(list.data()));
    list_lens.push_back(list.size());
  }

  void* engine = paani_adblock_engine_create(list_ptrs.data(), list_lens.data(),
                                              list_ptrs.size());
  if (!engine) {
    return nullptr;
  }

  if (!redirect_resources.empty()) {
    // adblock-rust wants the payload as base64 text, and the descriptor
    // layout keeps every buffer alive for the duration of the call.
    for (PaaniRedirectResourceData& resource : redirect_resources) {
      resource.content = base::Base64Encode(resource.content);
    }

    std::vector<PaaniRedirectResourceC> descriptors;
    descriptors.reserve(redirect_resources.size());
    std::vector<std::vector<const uint8_t*>> alias_ptrs;
    std::vector<std::vector<size_t>> alias_lens;
    alias_ptrs.reserve(redirect_resources.size());
    alias_lens.reserve(redirect_resources.size());
    for (const PaaniRedirectResourceData& resource : redirect_resources) {
      std::vector<const uint8_t*>& pointers =
          alias_ptrs.emplace_back(resource.aliases.size());
      std::vector<size_t>& lengths =
          alias_lens.emplace_back(resource.aliases.size());
      for (size_t i = 0; i < resource.aliases.size(); ++i) {
        pointers[i] = reinterpret_cast<const uint8_t*>(
            resource.aliases[i].data());
        lengths[i] = resource.aliases[i].size();
      }

      PaaniRedirectResourceC descriptor = {};
      descriptor.name = reinterpret_cast<const uint8_t*>(resource.name.data());
      descriptor.name_len = resource.name.size();
      descriptor.content =
          reinterpret_cast<const uint8_t*>(resource.content.data());
      descriptor.content_len = resource.content.size();
      descriptor.alias_ptrs = pointers.empty() ? nullptr : pointers.data();
      descriptor.alias_lens = lengths.empty() ? nullptr : lengths.data();
      descriptor.alias_count = resource.aliases.size();
      descriptors.push_back(descriptor);
    }

    const int accepted = paani_adblock_use_resources(
        engine, descriptors.data(), descriptors.size());
    LOG_IF(WARNING, accepted <= 0)
        << "Paani: ad blocker could not load redirect stubs, so every rule "
           "with $redirect= matches nothing";
  }

  return std::unique_ptr<PaaniAdblockEngine>(new PaaniAdblockEngine(engine));
}

PaaniAdblockEngine::PaaniAdblockEngine(void* engine) : engine_(engine) {}

PaaniAdblockEngine::~PaaniAdblockEngine() {
  paani_adblock_engine_destroy(engine_);
}

bool PaaniAdblockEngine::ShouldBlock(const std::string& url,
                                      const std::string& source_url,
                                      const std::string& request_type,
                                      const std::string& method,
                                      std::string* rewritten_url,
                                      std::string* redirect) const {
  char* rewritten = nullptr;
  char* redirect_value = nullptr;
  const int result = paani_adblock_check(
      engine_, reinterpret_cast<const uint8_t*>(url.data()), url.size(),
      reinterpret_cast<const uint8_t*>(source_url.data()), source_url.size(),
      reinterpret_cast<const uint8_t*>(request_type.data()), request_type.size(),
      reinterpret_cast<const uint8_t*>(method.data()), method.size(),
      &rewritten, &redirect_value);

  if (rewritten) {
    if (rewritten_url) {
      rewritten_url->assign(rewritten);
    }
    paani_adblock_free_string(rewritten);
  }

  if (redirect_value) {
    if (redirect) {
      redirect->assign(redirect_value);
    }
    paani_adblock_free_string(redirect_value);
  }

  if (result == kError) {
    return false;
  }
  return result == kBlock;
}

}  // namespace paani
