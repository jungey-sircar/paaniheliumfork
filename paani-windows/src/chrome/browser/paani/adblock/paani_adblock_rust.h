// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_RUST_H_
#define CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_RUST_H_

#include <stddef.h>
#include <stdint.h>

// Declarations of the C ABI exported by chrome/browser/paani/adblock/rust.
//
// The adblock-rust engine is built with its `single-thread` feature, so the
// engine is neither `Send` nor `Sync`.  Every function below has to be called
// from the thread that created the engine.
extern "C" {

// One stub resource for $redirect= rules, in the layout the Rust side reads.
// `alias_ptrs` and `alias_lens` must each point to `alias_count` readable
// elements.
struct PaaniRedirectResourceC {
  const uint8_t* name;
  size_t name_len;
  const uint8_t* content;
  size_t content_len;
  const uint8_t* const* alias_ptrs;
  const size_t* alias_lens;
  size_t alias_count;
};

// Creates an engine from the given filter lists. `list_ptrs` and `list_lens`
// must each point to `list_count` readable elements. Returns a null pointer
// if no list could be used.
void* paani_adblock_engine_create(const uint8_t* const* list_ptrs,
                                  const size_t* list_lens,
                                  size_t list_count);

// Hands the redirect stubs to the engine. Without them the engine has an empty
// resource storage and silently drops every rule with a $redirect= or
// $redirect-rule= option, which is a large part of uBlock's lists.
// Returns the number of resources the engine accepted, or -1 on failure.
int paani_adblock_use_resources(void* engine,
                                const PaaniRedirectResourceC* resources,
                                size_t resource_count);

// Destroys an engine created by paani_adblock_engine_create.
void paani_adblock_engine_destroy(void* engine);

// Checks whether a request should be blocked. Returns 1 when the request is
// blocked, 0 when it is allowed and -1 when it could not be evaluated. When
// the request is allowed but a rule asked for the URL to be rewritten,
// `out_rewritten_url` receives a newly allocated NUL terminated string that
// has to be released with paani_adblock_free_string.
//
// When a matched rule names a redirect stub, `out_redirect` receives the stub
// as a data: URL. A redirect is reported for both $redirect= and
// $redirect-rule=, so the caller has to look at the return value as well:
// only a blocked request may be replaced by the stub.
int paani_adblock_check(void* engine,
                        const uint8_t* url,
                        size_t url_len,
                        const uint8_t* source_url,
                        size_t source_url_len,
                        const uint8_t* request_type,
                        size_t request_type_len,
                        const uint8_t* method,
                        size_t method_len,
                        char** out_rewritten_url,
                        char** out_redirect);

// Releases a string returned by paani_adblock_check.
void paani_adblock_free_string(char* value);
}

#endif  // CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_RUST_H_
