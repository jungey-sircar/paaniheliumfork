// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_URL_LOADER_FACTORY_H_
#define CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_URL_LOADER_FACTORY_H_

#include <memory>
#include <optional>
#include <string>

#include "base/memory/scoped_refptr.h"
#include "base/memory/self_deleting.h"
#include "content/public/browser/global_routing_id.h"
#include "mojo/public/cpp/bindings/pending_receiver.h"
#include "mojo/public/cpp/bindings/pending_remote.h"
#include "mojo/public/cpp/bindings/remote.h"
#include "services/network/public/cpp/self_deleting_url_loader_factory.h"
#include "services/network/public/cpp/url_loader_factory_builder.h"
#include "url/gurl.h"

namespace content {
class BrowserContext;
class RenderFrameHost;
}  // namespace content

namespace net {
struct MutableNetworkTrafficAnnotationTag;
}  // namespace net

namespace network {
struct ResourceRequest;
}  // namespace network

namespace paani {

class PaaniAdblockState;

// Proxying URLLoaderFactory that blocks the requests matched by the built in
// ad blocker.
//
// The factory is created on the thread that owns the profile and stays bound
// to it, so the ad blocker state is only ever touched from that thread.
class PaaniAdblockURLLoaderFactory : public network::SelfDeletingURLLoaderFactory {
 public:
  PaaniAdblockURLLoaderFactory(
      mojo::PendingReceiver<network::mojom::URLLoaderFactory> loader_receiver,
      mojo::PendingRemote<network::mojom::URLLoaderFactory>
          target_factory_remote,
      scoped_refptr<PaaniAdblockState> state,
      std::optional<content::GlobalRenderFrameHostId> frame_id,
      GURL top_level_url,
      base::SelfDeletingPassKey pass_key);

  PaaniAdblockURLLoaderFactory(const PaaniAdblockURLLoaderFactory&) = delete;
  PaaniAdblockURLLoaderFactory& operator=(
      const PaaniAdblockURLLoaderFactory&) = delete;

  // Installs the proxying factory on `factory_builder` when the ad blocker is
  // active for the profile of `browser_context`. `frame` is the frame whose
  // subresources this factory serves and may be null.
  static void MaybeProxyRequest(content::BrowserContext* browser_context,
                                 content::RenderFrameHost* frame,
                                 network::URLLoaderFactoryBuilder& factory_builder);

  // network::mojom::URLLoaderFactory:
  void CreateLoaderAndStart(
      mojo::PendingReceiver<network::mojom::URLLoader> loader_receiver,
      int32_t request_id,
      uint32_t options,
      const network::ResourceRequest& request,
      mojo::PendingRemote<network::mojom::URLLoaderClient> client,
      const net::MutableNetworkTrafficAnnotationTag& traffic_annotation)
      override;

 private:
  ~PaaniAdblockURLLoaderFactory() override;

  void OnTargetFactoryError();

  // Adds this request to the count of the tab that made it, so the toolbar
  // can show what the blocker stopped on the page being looked at.
  void CountBlockedRequestForFrame();

  mojo::Remote<network::mojom::URLLoaderFactory> target_factory_;
  scoped_refptr<PaaniAdblockState> state_;
  std::optional<content::GlobalRenderFrameHostId> frame_id_;

  // The page this factory serves. A request from a frame that has no first
  // party of its own is judged against the page it is embedded in, so that an
  // allowlisted site really is left alone.
  GURL top_level_url_;
};

// Returns the request type name that the ad blocker engine understands for
// the given Blink resource type.
std::string PaaniRequestTypeForResourceType(int resource_type);

}  // namespace paani

#endif  // CHROME_BROWSER_PAANI_ADBLOCK_PAANI_ADBLOCK_URL_LOADER_FACTORY_H_
