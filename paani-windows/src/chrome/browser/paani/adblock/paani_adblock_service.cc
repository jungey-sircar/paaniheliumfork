// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#include "chrome/browser/paani/adblock/paani_adblock_service.h"

#include <algorithm>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include "base/functional/bind.h"
#include "base/logging.h"
#include "base/no_destructor.h"
#include "base/strings/string_util.h"
#include "base/task/thread_pool.h"
#include "base/values.h"
#include "chrome/browser/paani/adblock/paani_adblock_engine.h"
#include "chrome/browser/paani/adblock/paani_redirect_resources.h"
#include "chrome/browser/profiles/profile.h"
#include "components/keyed_service/core/keyed_service.h"
#include "components/pref_registry/pref_registry_syncable.h"
#include "components/prefs/pref_service.h"
#include "content/public/browser/browser_context.h"
#include "net/base/registry_controlled_domains/registry_controlled_domain.h"
#include "third_party/ublock/resources/grit/ublock_resources.h"
#include "ui/base/resource/resource_bundle.h"

namespace paani {

namespace {

// The filter lists that are compiled into the browser. They are the same
// files that Helium ships inside its uBlock Origin component extension, so no
// extra download is needed.
//
// EasyList and EasyPrivacy carry the generic "this host is an ad server" rules.
// The uBlock lists are a supplement, and a large part of their rules use
// $redirect= to swap in a stub resource instead of failing the request. Those
// rules only match when the stubs are loaded as well, which is what
// LoadRedirectResources() below is for; without them the supplement lists
// contribute almost nothing.
constexpr int kFilterListResourceIds[] = {
    IDR_UBLOCK_ASSETS_UBLOCK_FILTERS_MIN_TXT,
    IDR_UBLOCK_ASSETS_UBLOCK_PRIVACY_MIN_TXT,
    IDR_UBLOCK_ASSETS_UBLOCK_QUICK_FIXES_MIN_TXT,
    IDR_UBLOCK_ASSETS_UBLOCK_UNBREAK_MIN_TXT,
    IDR_UBLOCK_ASSETS_UBLOCK_BADLISTS_TXT,
    IDR_UBLOCK_ASSETS_HELIUM_UNBREAK_TXT,
    IDR_UBLOCK_ASSETS_THIRDPARTIES_EASYLIST_EASYLIST_TXT,
    IDR_UBLOCK_ASSETS_THIRDPARTIES_EASYLIST_EASYPRIVACY_TXT,
};

std::vector<std::string> LoadFilterLists() {
  std::vector<std::string> lists;
  if (!ui::ResourceBundle::HasSharedInstance()) {
    return lists;
  }
  const ui::ResourceBundle& bundle = ui::ResourceBundle::GetSharedInstance();
  for (int resource_id : kFilterListResourceIds) {
    std::string contents = bundle.LoadDataResourceString(resource_id);
    if (!contents.empty()) {
      lists.push_back(std::move(contents));
    }
  }
  return lists;
}

// The stub payloads a $redirect= rule can name. They ship inside
// resources.pak, so reading them costs no download and no extension.
//
// This has to run on the UI thread: the resource bundle is not safe to read
// from a worker pool thread.
std::vector<PaaniRedirectResourceData> LoadRedirectResources() {
  std::vector<PaaniRedirectResourceData> resources;
  if (!ui::ResourceBundle::HasSharedInstance()) {
    return resources;
  }
  const ui::ResourceBundle& bundle = ui::ResourceBundle::GetSharedInstance();
  for (size_t i = 0; i < kPaaniRedirectResourceCount; ++i) {
    const PaaniRedirectResource& entry = kPaaniRedirectResources[i];
    std::string contents = bundle.LoadDataResourceString(entry.resource_id);
    if (contents.empty()) {
      continue;
    }

    PaaniRedirectResourceData data;
    data.name = entry.name;
    data.content = std::move(contents);
    data.aliases.reserve(entry.alias_count);
    for (size_t alias_index = 0; alias_index < entry.alias_count;
         ++alias_index) {
      data.aliases.push_back(entry.aliases[alias_index]);
    }
    resources.push_back(std::move(data));
  }
  return resources;
}

// Returns the eTLD+1 of `url`, for example "example.com" for
// "https://www.example.com/x". Falls back to the host for hosts that have no
// registrable domain, such as IP addresses.
std::string ComputeSiteForURL(const GURL& url) {
  if (!url.is_valid() || url.host().empty()) {
    return std::string();
  }
  std::string site = net::registry_controlled_domains::GetDomainAndRegistry(
      url.host(),
      net::registry_controlled_domains::INCLUDE_PRIVATE_REGISTRIES);
  if (site.empty()) {
    site = std::string(url.host());
  }
  return site;
}

}  // namespace

PaaniAdblockState::PaaniAdblockState() = default;

PaaniAdblockState::~PaaniAdblockState() = default;

void PaaniAdblockState::Initialize(PrefService* prefs) {
  prefs_ = prefs;
  LoadAllowlist();

  // Everything the engine needs is read here, on the UI thread, because the
  // resource bundle is not safe to touch from a pool thread. Compiling the
  // lists is what takes the time, so that part runs in the background.
  std::vector<std::string> lists = LoadFilterLists();
  std::vector<PaaniRedirectResourceData> redirect_resources =
      LoadRedirectResources();

  scoped_refptr<PaaniAdblockState> self(this);
  base::ThreadPool::PostTask(
      FROM_HERE,
      base::BindOnce(&PaaniAdblockState::BuildEngine, std::move(self),
                     std::move(lists), std::move(redirect_resources)));
}

void PaaniAdblockState::Shutdown() {
  shutdown_.store(true, std::memory_order_release);
  enabled_.store(false, std::memory_order_release);
  prefs_ = nullptr;

  base::AutoLock lock(lock_);
  engine_.reset();
}

void PaaniAdblockState::BuildEngine(
    std::vector<std::string> lists,
    std::vector<PaaniRedirectResourceData> redirect_resources) {
  if (shutdown_.load(std::memory_order_acquire)) {
    return;
  }

  int64_t bytes = 0;
  int64_t rules = 0;
  for (const std::string& list : lists) {
    bytes += static_cast<int64_t>(list.size());
    size_t line_start = 0;
    while (line_start < list.size()) {
      size_t line_end = list.find('\n', line_start);
      if (line_end == std::string::npos) {
        line_end = list.size();
      }
      std::string_view line(list.data() + line_start, line_end - line_start);
      line = base::TrimWhitespaceASCII(line, base::TRIM_ALL);
      // uBlock comment and metadata lines start with "!" or "[", empty lines
      // carry no rule.
      if (!line.empty() && line[0] != '!' && line[0] != '[') {
        ++rules;
      }
      line_start = line_end + 1;
    }
  }

  lists_loaded_.store(static_cast<int>(lists.size()), std::memory_order_relaxed);
  list_bytes_.store(bytes, std::memory_order_relaxed);
  approx_rules_.store(rules, std::memory_order_relaxed);

  redirect_resources_loaded_.store(
      static_cast<int>(redirect_resources.size()), std::memory_order_relaxed);
  std::unique_ptr<PaaniAdblockEngine> engine = PaaniAdblockEngine::Create(
      lists, std::move(redirect_resources));
  LOG_IF(WARNING, !engine)
      << "Paani: ad blocker engine could not be built from " << lists.size()
      << " filter list(s)";
  if (!engine) {
    return;
  }

  {
    base::AutoLock lock(lock_);
    if (shutdown_.load(std::memory_order_acquire)) {
      return;
    }
    engine_ = std::move(engine);
  }
  engine_ready_.store(true, std::memory_order_relaxed);
  LOG(INFO) << "Paani: ad blocker ready (" << lists.size() << " lists, "
            << bytes << " bytes, ~" << rules << " rules)";
}

bool PaaniAdblockState::ShouldBlockRequest(const GURL& url,
                                           const GURL& source_url,
                                           const std::string& request_type,
                                           const std::string& method,
                                           std::string* redirect) {
  if (!enabled()) {
    return false;
  }

  std::shared_ptr<const PaaniAdblockEngine> engine;
  {
    base::AutoLock lock(lock_);
    engine = engine_;
  }
  if (!engine) {
    // The engine is still being built, so nothing is blocked yet.
    return false;
  }

  std::string rewritten_url;
  return engine->ShouldBlock(url.spec(), source_url.spec(), request_type,
                             method, &rewritten_url, redirect);
}

std::string PaaniAdblockState::SiteForURL(const GURL& url) const {
  return ComputeSiteForURL(url);
}

bool PaaniAdblockState::IsSiteAllowed(const GURL& url) const {
  const std::string site = SiteForURL(url);
  if (site.empty()) {
    return false;
  }

  base::AutoLock lock(lock_);
  return std::find(allowed_sites_.begin(), allowed_sites_.end(), site) !=
         allowed_sites_.end();
}

void PaaniAdblockState::AllowSite(const GURL& url) {
  const std::string site = SiteForURL(url);
  if (site.empty()) {
    return;
  }

  {
    base::AutoLock lock(lock_);
    if (std::find(allowed_sites_.begin(), allowed_sites_.end(), site) ==
        allowed_sites_.end()) {
      allowed_sites_.push_back(site);
    }
  }
  StoreAllowlist();
}

void PaaniAdblockState::DisallowSite(const GURL& url) {
  const std::string site = SiteForURL(url);
  if (site.empty()) {
    return;
  }

  {
    base::AutoLock lock(lock_);
    allowed_sites_.erase(
        std::remove(allowed_sites_.begin(), allowed_sites_.end(), site),
        allowed_sites_.end());
  }
  StoreAllowlist();
}

std::vector<std::string> PaaniAdblockState::GetAllowedSites() const {
  base::AutoLock lock(lock_);
  return allowed_sites_;
}

void PaaniAdblockState::LoadAllowlist() {
  if (!prefs_) {
    return;
  }

  const base::ListValue& list = prefs_->GetList(kPaaniAdblockAllowlistPref);

  std::vector<std::string> sites;
  for (const base::Value& value : list) {
    if (value.is_string()) {
      sites.push_back(value.GetString());
    }
  }

  base::AutoLock lock(lock_);
  allowed_sites_ = std::move(sites);
}

void PaaniAdblockState::StoreAllowlist() {
  if (!prefs_) {
    return;
  }

  base::ListValue list;
  for (const std::string& site : GetAllowedSites()) {
    list.Append(std::string_view(site));
  }
  prefs_->SetList(kPaaniAdblockAllowlistPref, std::move(list));
}

PaaniAdblockService::PaaniAdblockService(Profile* profile)
    : state_(new PaaniAdblockState()) {
  state_->Initialize(profile->GetPrefs());
  state_->set_enabled(
      profile->GetPrefs()->GetBoolean(kPaaniAdblockEnabledPref));
}

PaaniAdblockService::~PaaniAdblockService() = default;

void PaaniAdblockService::Shutdown() {
  if (state_) {
    state_->Shutdown();
  }
}

// static
scoped_refptr<PaaniAdblockState> PaaniAdblockServiceFactory::GetState(
    Profile* profile) {
  PaaniAdblockService* service = static_cast<PaaniAdblockService*>(
      GetInstance()->GetServiceForBrowserContext(profile, true /* create */));
  if (!service) {
    return nullptr;
  }
  return service->state();
}

// static
PaaniAdblockServiceFactory* PaaniAdblockServiceFactory::GetInstance() {
  static base::NoDestructor<PaaniAdblockServiceFactory> instance;
  return instance.get();
}

PaaniAdblockServiceFactory::PaaniAdblockServiceFactory()
    : ProfileKeyedServiceFactory(
          "PaaniAdblockService",
          ProfileSelections::Builder()
              .WithRegular(ProfileSelection::kOwnInstance)
              .WithGuest(ProfileSelection::kOwnInstance)
              .WithAshInternals(ProfileSelection::kOwnInstance)
              .Build()) {
}

PaaniAdblockServiceFactory::~PaaniAdblockServiceFactory() = default;

std::unique_ptr<KeyedService>
PaaniAdblockServiceFactory::BuildServiceInstanceForBrowserContext(
    content::BrowserContext* context) const {
  Profile* profile = Profile::FromBrowserContext(context);
  return std::make_unique<PaaniAdblockService>(profile);
}

void PaaniAdblockServiceFactory::RegisterProfilePrefs(
    user_prefs::PrefRegistrySyncable* registry) {
  registry->RegisterBooleanPref(kPaaniAdblockEnabledPref, true);
  registry->RegisterListPref(kPaaniAdblockAllowlistPref);
}

}  // namespace paani
