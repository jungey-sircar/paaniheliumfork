// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#include "chrome/browser/paani/adblock/paani_adblock_url_loader_factory.h"

#include <optional>
#include <string>
#include <utility>

#include "base/functional/bind.h"
#include "base/location.h"
#include "base/memory/self_deleting.h"
#include "base/task/single_thread_task_runner.h"
#include "chrome/browser/paani/adblock/paani_adblock_service.h"
#include "chrome/browser/paani/adblock/paani_adblock_tab_data.h"
#include "chrome/browser/paani/adblock/paani_stub_url_loader.h"
#include "chrome/browser/profiles/profile.h"
#include "content/public/browser/browser_context.h"
#include "content/public/browser/browser_thread.h"
#include "content/public/browser/render_frame_host.h"
#include "content/public/browser/web_contents.h"
#include "net/base/data_url.h"
#include "net/base/net_errors.h"
#include "net/traffic_annotation/network_traffic_annotation.h"
#include "services/network/public/cpp/resource_request.h"
#include "services/network/public/cpp/url_loader_completion_status.h"
#include "services/network/public/mojom/url_loader.mojom.h"
#include "services/network/public/mojom/url_loader_factory.mojom.h"
#include "url/origin.h"

namespace paani {

namespace {

// The request type names understood by the ad blocker engine. They are the
// same names that the Chromium extension API uses.
constexpr char kTypeOther[] = "other";
constexpr char kTypeMainFrame[] = "main_frame";
constexpr char kTypeSubFrame[] = "sub_frame";
constexpr char kTypeStylesheet[] = "stylesheet";
constexpr char kTypeScript[] = "script";
constexpr char kTypeImage[] = "image";
constexpr char kTypeFont[] = "font";
constexpr char kTypeObject[] = "object";
constexpr char kTypeMedia[] = "media";
constexpr char kTypeXhr[] = "xhr";
constexpr char kTypePing[] = "ping";
constexpr char kTypeCspReport[] = "csp_report";
constexpr char kTypeObjectSubrequest[] = "object_subrequest";

// Runs on the UI thread: the frame, the tab and the per tab counter all live
// there, and the toolbar reads the counter from there too.
void CountBlockedForFrame(content::GlobalRenderFrameHostId frame_id) {
  content::RenderFrameHost* frame = content::RenderFrameHost::FromID(frame_id);
  if (!frame) {
    // The frame went away with the request still in flight, so there is no
    // tab left to count it against.
    return;
  }
  content::WebContents* web_contents =
      content::WebContents::FromRenderFrameHost(frame);
  if (!web_contents) {
    return;
  }
  PaaniAdblockTabData::GetOrCreateForWebContents(web_contents)->AddBlocked();
}

}  // namespace

// static
std::string PaaniRequestTypeForResourceType(int resource_type) {
  switch (resource_type) {
    case 0:  // blink::mojom::ResourceType::kMainFrame
      return kTypeMainFrame;
    case 1:  // blink::mojom::ResourceType::kSubFrame
      return kTypeSubFrame;
    case 2:  // blink::mojom::ResourceType::kStylesheet
      return kTypeStylesheet;
    case 3:  // blink::mojom::ResourceType::kScript
      return kTypeScript;
    case 4:  // blink::mojom::ResourceType::kImage
      return kTypeImage;
    case 5:  // blink::mojom::ResourceType::kFontResource
      return kTypeFont;
    case 7:  // blink::mojom::ResourceType::kObject
      return kTypeObject;
    case 8:  // blink::mojom::ResourceType::kMedia
      return kTypeMedia;
    case 13:  // blink::mojom::ResourceType::kXhr
      return kTypeXhr;
    case 14:  // blink::mojom::ResourceType::kPing
      return kTypePing;
    case 16:  // blink::mojom::ResourceType::kCspReport
      return kTypeCspReport;
    case 17:  // blink::mojom::ResourceType::kPluginResource
      return kTypeObjectSubrequest;
    case 19:  // blink::mojom::ResourceType::kNavigationPreloadMainFrame
      return kTypeMainFrame;
    case 20:  // blink::mojom::ResourceType::kNavigationPreloadSubFrame
      return kTypeSubFrame;
    default:
      return kTypeOther;
  }
}

PaaniAdblockURLLoaderFactory::PaaniAdblockURLLoaderFactory(
    mojo::PendingReceiver<network::mojom::URLLoaderFactory> loader_receiver,
    mojo::PendingRemote<network::mojom::URLLoaderFactory> target_factory_remote,
    scoped_refptr<PaaniAdblockState> state,
    std::optional<content::GlobalRenderFrameHostId> frame_id,
    GURL top_level_url,
    base::SelfDeletingPassKey pass_key)
    : network::SelfDeletingURLLoaderFactory(std::move(loader_receiver),
                                            pass_key),
      state_(std::move(state)),
      frame_id_(frame_id),
      top_level_url_(std::move(top_level_url)) {
  target_factory_.Bind(std::move(target_factory_remote));
  target_factory_.set_disconnect_handler(base::BindOnce(
      &PaaniAdblockURLLoaderFactory::OnTargetFactoryError,
      base::Unretained(this)));
}

PaaniAdblockURLLoaderFactory::~PaaniAdblockURLLoaderFactory() = default;

// static
void PaaniAdblockURLLoaderFactory::MaybeProxyRequest(
    content::BrowserContext* browser_context,
    content::RenderFrameHost* frame,
    network::URLLoaderFactoryBuilder& factory_builder) {
  Profile* profile = Profile::FromBrowserContext(browser_context);
  if (!profile) {
    return;
  }

  scoped_refptr<PaaniAdblockState> state =
      PaaniAdblockServiceFactory::GetState(profile);
  if (!state || !state->enabled()) {
    return;
  }

  // The frame that owns this factory is what ties a blocked request to the tab
  // the user is looking at. It is optional only because a factory can be built
  // for a context with no frame at all, and guessing a tab from such a request
  // would miscount it.
  std::optional<content::GlobalRenderFrameHostId> frame_id;
  if (frame) {
    frame_id = frame->GetGlobalId();
  }

  // The page the user is looking at. A request that a third party frame makes
  // has no first party of its own -- a sandboxed frame from another site has
  // neither cookies nor a usable referrer -- so the frame tree is what says
  // which page the request belongs to. The allowlist is about the page.
  GURL top_level_url;
  if (frame) {
    content::RenderFrameHost* top_frame = frame->GetMainFrame();
    if (top_frame) {
      top_level_url = top_frame->GetLastCommittedURL();
    }
  }

  auto [receiver, remote] = factory_builder.Append();
  state->RecordFactoryInstalled();
  base::MakeSelfDeleting<PaaniAdblockURLLoaderFactory>(
      std::move(receiver), std::move(remote), std::move(state), frame_id,
      std::move(top_level_url));
}

void PaaniAdblockURLLoaderFactory::CreateLoaderAndStart(
    mojo::PendingReceiver<network::mojom::URLLoader> loader_receiver,
    int32_t request_id,
    uint32_t options,
    const network::ResourceRequest& request,
    mojo::PendingRemote<network::mojom::URLLoaderClient> client,
    const net::MutableNetworkTrafficAnnotationTag& traffic_annotation) {
  const GURL& url = request.url;
  if (!url.is_valid() || !url.has_host() || !url.SchemeIsHTTPOrHTTPS()) {
    target_factory_->CreateLoaderAndStart(std::move(loader_receiver),
                                          request_id, options, request,
                                          std::move(client), traffic_annotation);
    return;
  }

  // The top level site the request was made from. This is the site the
  // allowlist is checked against.
  GURL source_url;
  if (!request.site_for_cookies.IsNull()) {
    source_url = request.site_for_cookies.RepresentativeUrl();
  }
  if ((!source_url.is_valid() || !source_url.has_host()) &&
      request.request_initiator.has_value()) {
    source_url = request.request_initiator->GetURL();
  }
  if (!source_url.is_valid() || !source_url.has_host()) {
    source_url = request.referrer;
  }
  if ((!source_url.is_valid() || !source_url.has_host()) &&
      state_ && state_->enabled()) {
    // The document has an opaque origin (data:, blob:, view-source:), so there
    // is no first party to evaluate the rules against. Fall back to the
    // request's own URL: generic rules like "||doubleclick.net^" still match,
    // and the alternative is to let every ad through.
    source_url = url;
  }

  // A site on the allowlist is left alone: neither the requests it made
  // itself nor the requests a frame on its page made are blocked.
  if (state_ && (state_->IsSiteAllowed(source_url) ||
                 state_->IsSiteAllowed(top_level_url_))) {
    target_factory_->CreateLoaderAndStart(std::move(loader_receiver),
                                          request_id, options, request,
                                          std::move(client), traffic_annotation);
    return;
  }

  const std::string request_type =
      PaaniRequestTypeForResourceType(request.resource_type);

  std::string redirect;
  if (state_ && state_->ShouldBlockRequest(url, source_url, request_type,
                                            request.method, &redirect)) {
    state_->OnRequestBlocked();
    CountBlockedRequestForFrame();

    // A $redirect= rule does not want an empty failure, it wants one of the
    // stubs that ship in resources.pak in place of the ad. Serving the body
    // under the original URL is what keeps the page that waits for it alive.
    const GURL redirect_url(redirect);
    std::string mime_type;
    std::string charset;
    std::string body;
    if (redirect_url.is_valid() &&
        net::DataURL::Parse(redirect_url, &mime_type, &charset, &body)) {
      PaaniStubURLLoader::CreateAndStart(std::move(loader_receiver),
                                         std::move(client),
                                         std::move(mime_type), std::move(body));
      return;
    }

    mojo::Remote<network::mojom::URLLoaderClient>(std::move(client))
        ->OnComplete(network::URLLoaderCompletionStatus(
            net::ERR_BLOCKED_BY_CLIENT));
    return;
  }

  target_factory_->CreateLoaderAndStart(std::move(loader_receiver), request_id,
                                        options, request, std::move(client),
                                        traffic_annotation);
}

void PaaniAdblockURLLoaderFactory::OnTargetFactoryError() {
  DisconnectReceiversAndDestroy();
}

void PaaniAdblockURLLoaderFactory::CountBlockedRequestForFrame() {
  if (!frame_id_.has_value()) {
    return;
  }
  // The factory runs on the network IO thread, but the counter belongs to the
  // tab and the toolbar button is notified from the tab, so the counting is
  // done on the UI thread.
  content::GetUIThreadTaskRunner()->PostTask(
      FROM_HERE, base::BindOnce(&CountBlockedForFrame, *frame_id_));
}

}  // namespace paani
