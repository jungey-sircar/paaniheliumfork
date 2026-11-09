// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_SERVICE_H_
#define CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_SERVICE_H_

#include <atomic>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "base/memory/ref_counted.h"
#include "base/memory/scoped_refptr.h"
#include "base/no_destructor.h"
#include "base/synchronization/lock.h"
#include "chrome/browser/paani/adblock/paani_adblock_engine.h"
#include "chrome/browser/profiles/profile_keyed_service_factory.h"
#include "components/keyed_service/core/keyed_service.h"
#include "url/gurl.h"

class PrefService;
class Profile;

namespace content {
class BrowserContext;
}

namespace user_prefs {
class PrefRegistrySyncable;
}

namespace paani {

class PaaniAdblockEngine;

// Preference that controls whether the built in ad blocker is active.
inline constexpr char kPaaniAdblockEnabledPref[] = "paani.adblock.enabled";

// Preference holding the per site allowlist. The value is a list of eTLD+1
// hosts, for example "example.com".
//
// This is intentionally a Paani owned preference instead of a content
// setting: Chromium's own subresource filter writes the "ads" content setting
// for the sites it allows, so sharing it would silently re-enable ads.
inline constexpr char kPaaniAdblockAllowlistPref[] = "paani.adblock.allowlist";

// Profile scoped state of the built in ad blocker.
//
// The engine is shared by every request of the profile, so it is built once in
// the background and then handed out to the request interceptors.
class PaaniAdblockState
    : public base::RefCountedThreadSafe<PaaniAdblockState> {
 public:
  PaaniAdblockState();
  ~PaaniAdblockState();

  PaaniAdblockState(const PaaniAdblockState&) = delete;
  PaaniAdblockState& operator=(const PaaniAdblockState&) = delete;

  // Starts building the engine in the background. Must be called on the UI
  // thread.
  void Initialize(PrefService* prefs);

  // Stops blocking and drops the engine. Must be called on the UI thread.
  void Shutdown();

  // Returns true when the request has to be blocked. `source_url` is the top
  // level site the request was made from.
  //
  // When a rule asked for a stub instead of a bare block, `redirect` receives
  // it as a data: URL. Only check it when the function returns true.
  bool ShouldBlockRequest(const GURL& url,
                          const GURL& source_url,
                          const std::string& request_type,
                          const std::string& method,
                          std::string* redirect);

  bool enabled() const { return enabled_.load(std::memory_order_relaxed); }
  void set_enabled(bool enabled) {
    enabled_.store(enabled, std::memory_order_relaxed);
  }

  int64_t blocked_request_count() const {
    return blocked_request_count_.load(std::memory_order_relaxed);
  }
  void reset_blocked_request_count() {
    blocked_request_count_.store(0, std::memory_order_relaxed);
  }
  void OnRequestBlocked() {
    blocked_request_count_.fetch_add(1, std::memory_order_relaxed);
  }

  // Per site allowlist. `IsSiteAllowed` may be called from any thread, the
  // mutators must be called on the UI thread.
  bool IsSiteAllowed(const GURL& url) const;
  void AllowSite(const GURL& url);
  void DisallowSite(const GURL& url);
  std::vector<std::string> GetAllowedSites() const;

  // Diagnostics, shown on chrome://paani. A blocker that failed to build its
  // engine has to look different from one that found nothing to block.
  bool engine_ready() const {
    return engine_ready_.load(std::memory_order_relaxed);
  }
  int lists_loaded() const { return lists_loaded_.load(std::memory_order_relaxed); }
  int64_t list_bytes() const {
    return list_bytes_.load(std::memory_order_relaxed);
  }
  int64_t approx_rules() const {
    return approx_rules_.load(std::memory_order_relaxed);
  }
  int64_t factories_installed() const {
    return factories_installed_.load(std::memory_order_relaxed);
  }
  void RecordFactoryInstalled() {
    factories_installed_.fetch_add(1, std::memory_order_relaxed);
  }

  // Number of $redirect= stubs the engine has. Zero means the rules that name
  // a stub match nothing, which is the difference between "blocked" and
  // "neutralised".
  int redirect_resources_loaded() const {
    return redirect_resources_loaded_.load(std::memory_order_relaxed);
  }

 private:
  void BuildEngine(std::vector<std::string> filter_lists,
                   std::vector<PaaniRedirectResourceData> redirect_resources);
  std::string SiteForURL(const GURL& url) const;
  void LoadAllowlist();
  void StoreAllowlist();

  // Guards engine_ and allowed_sites_. IsSiteAllowed() and GetAllowedSites()
  // are const but have to take it, hence mutable.
  mutable base::Lock lock_;
  std::shared_ptr<const PaaniAdblockEngine> engine_;
  std::vector<std::string> allowed_sites_;

  std::atomic<bool> enabled_{true};
  std::atomic<bool> shutdown_{false};
  std::atomic<bool> engine_ready_{false};
  std::atomic<int> lists_loaded_{0};
  std::atomic<int64_t> list_bytes_{0};
  std::atomic<int64_t> approx_rules_{0};
  std::atomic<int64_t> blocked_request_count_{0};
  std::atomic<int64_t> factories_installed_{0};
  std::atomic<int> redirect_resources_loaded_{0};

  // Owned by the profile. Only touched on the UI thread.
  PrefService* prefs_ = nullptr;
};

// Keyed service owning the ad blocker state of a profile.
class PaaniAdblockService : public KeyedService {
 public:
  explicit PaaniAdblockService(Profile* profile);
  ~PaaniAdblockService() override;

  PaaniAdblockService(const PaaniAdblockService&) = delete;
  PaaniAdblockService& operator=(const PaaniAdblockService&) = delete;

  // KeyedService:
  void Shutdown() override;

  scoped_refptr<PaaniAdblockState> state() const { return state_; }

 private:
  scoped_refptr<PaaniAdblockState> state_;
};

// Creates the PaaniAdblockService of a profile.
class PaaniAdblockServiceFactory : public ProfileKeyedServiceFactory {
 public:
  // Returns the ad blocker state of `profile`, creating the service if it does
  // not exist yet.
  static scoped_refptr<PaaniAdblockState> GetState(Profile* profile);

  static PaaniAdblockServiceFactory* GetInstance();

  PaaniAdblockServiceFactory(const PaaniAdblockServiceFactory&) = delete;
  PaaniAdblockServiceFactory& operator=(const PaaniAdblockServiceFactory&) =
      delete;

 private:
  friend class base::NoDestructor<PaaniAdblockServiceFactory>;

  PaaniAdblockServiceFactory();
  ~PaaniAdblockServiceFactory() override;

  // BrowserContextKeyedServiceFactory:
  std::unique_ptr<KeyedService> BuildServiceInstanceForBrowserContext(
      content::BrowserContext* context) const override;
  void RegisterProfilePrefs(user_prefs::PrefRegistrySyncable* registry) override;
};

}  // namespace paani

#endif  // CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_SERVICE_H_
