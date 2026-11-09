// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#ifndef CHROME_BROWSER_PAANI_ADBLOCK_PAANI_STUB_URL_LOADER_H_
#define CHROME_BROWSER_PAANI_ADBLOCK_PAANI_STUB_URL_LOADER_H_

#include <stdint.h>

#include <memory>
#include <optional>
#include <string>

#include "mojo/public/cpp/bindings/pending_receiver.h"
#include "mojo/public/cpp/bindings/pending_remote.h"
#include "mojo/public/cpp/bindings/receiver.h"
#include "mojo/public/cpp/bindings/remote.h"
#include "mojo/public/cpp/system/data_pipe_producer.h"
#include "net/base/request_priority.h"
#include "services/network/public/mojom/url_loader.mojom.h"
#include "url/gurl.h"

namespace paani {

// Answers a request with a stub body instead of fetching it, which is how
// uBlock's $redirect= rules neutralise an ad script without breaking the page
// that waits for it.
//
// Owns itself; it deletes itself once the client is gone or the body has been
// written.
class PaaniStubURLLoader : public network::mojom::URLLoader {
 public:
  PaaniStubURLLoader(const PaaniStubURLLoader&) = delete;
  PaaniStubURLLoader& operator=(const PaaniStubURLLoader&) = delete;

  // Sends `body` back as the response, in place of the request the rule
  // matched. `mime_type` is the type the stub was declared with, for example
  // "application/javascript".
  static void CreateAndStart(
      mojo::PendingReceiver<network::mojom::URLLoader> loader_receiver,
      mojo::PendingRemote<network::mojom::URLLoaderClient> client,
      std::string mime_type,
      std::string body);

  // network::mojom::URLLoader:
  void FollowRedirect(
      network::HttpRequestHeadersUpdateParams headers_update_params,
      const std::optional<GURL>& new_url) override;
  void SetPriority(net::RequestPriority priority,
                   int32_t intra_priority_value) override;

 private:
  PaaniStubURLLoader();
  ~PaaniStubURLLoader() override;

  void Start(mojo::PendingReceiver<network::mojom::URLLoader> loader_receiver,
             mojo::PendingRemote<network::mojom::URLLoaderClient> client,
             std::string mime_type,
             std::string body);
  void OnMojoDisconnect();
  void MaybeDeleteSelf();
  void OnDataWritten(MojoResult result);

  mojo::Receiver<network::mojom::URLLoader> receiver_{this};
  mojo::Remote<network::mojom::URLLoaderClient> client_;
  std::unique_ptr<mojo::DataPipeProducer> data_producer_;
  std::string body_;
  size_t total_bytes_written_ = 0;
};

}  // namespace paani

#endif  // CHROME_BROWSER_PAANI_ADBLOCK_PAANI_STUB_URL_LOADER_H_
