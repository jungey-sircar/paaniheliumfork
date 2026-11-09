// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

#include "chrome/browser/paani/adblock/paani_stub_url_loader.h"

#include <algorithm>
#include <utility>

#include "base/byte_size.h"
#include "base/functional/bind.h"
#include "base/memory/ref_counted.h"
#include "base/time/time.h"
#include "mojo/public/cpp/system/data_pipe.h"
#include "mojo/public/cpp/system/string_data_source.h"
#include "net/base/net_errors.h"
#include "net/http/http_response_headers.h"
#include "net/http/http_util.h"
#include "services/network/public/cpp/url_loader_completion_status.h"
#include "services/network/public/mojom/url_response_head.mojom.h"

namespace paani {

namespace {

// The stubs are tiny; asking for exactly their size keeps the pipes cheap.
constexpr uint32_t kMinimumPipeCapacity = 1024;

std::string BuildRawHeaders(const std::string& mime_type) {
  return net::HttpUtil::AssembleRawHeaders(
      "HTTP/1.1 200 OK\r\nContent-Type: " + mime_type + "\r\n\r\n");
}

}  // namespace

// static
void PaaniStubURLLoader::CreateAndStart(
    mojo::PendingReceiver<network::mojom::URLLoader> loader_receiver,
    mojo::PendingRemote<network::mojom::URLLoaderClient> client,
    std::string mime_type,
    std::string body) {
  // Owns itself, the way content/browser/loader's in-process loaders do. It
  // goes away when the client drops it or once the body has been written.
  auto* loader = new PaaniStubURLLoader();
  loader->Start(std::move(loader_receiver), std::move(client),
                std::move(mime_type), std::move(body));
}

PaaniStubURLLoader::PaaniStubURLLoader() = default;

PaaniStubURLLoader::~PaaniStubURLLoader() = default;

void PaaniStubURLLoader::Start(
    mojo::PendingReceiver<network::mojom::URLLoader> loader_receiver,
    mojo::PendingRemote<network::mojom::URLLoaderClient> client,
    std::string mime_type,
    std::string body) {
  body_ = std::move(body);

  receiver_.Bind(std::move(loader_receiver));
  receiver_.set_disconnect_handler(base::BindOnce(
      &PaaniStubURLLoader::OnMojoDisconnect, base::Unretained(this)));
  client_.Bind(std::move(client));

  mojo::ScopedDataPipeProducerHandle producer;
  mojo::ScopedDataPipeConsumerHandle consumer;
  const uint32_t capacity = static_cast<uint32_t>(
      std::max<size_t>(body_.size(), kMinimumPipeCapacity));
  if (mojo::CreateDataPipe(capacity, producer, consumer) != MOJO_RESULT_OK) {
    client_->OnComplete(network::URLLoaderCompletionStatus(net::ERR_FAILED));
    OnMojoDisconnect();
    return;
  }

  std::string raw_headers = BuildRawHeaders(mime_type);

  auto head = network::mojom::URLResponseHead::New();
  head->mime_type = mime_type;
  head->headers = base::MakeRefCounted<net::HttpResponseHeaders>(raw_headers);
  head->content_length = static_cast<int64_t>(body_.size());
  head->encoded_data_length =
      static_cast<int64_t>(raw_headers.size() + body_.size());
  head->response_time = base::Time::Now();
  client_->OnReceiveResponse(std::move(head), std::move(consumer),
                             std::nullopt);

  if (body_.empty()) {
    producer.reset();
    OnDataWritten(MOJO_RESULT_OK);
    return;
  }

  data_producer_ =
      std::make_unique<mojo::DataPipeProducer>(std::move(producer));
  data_producer_->Write(
      std::make_unique<mojo::StringDataSource>(
          body_, mojo::StringDataSource::AsyncWritingMode::
                     STRING_MAY_BE_INVALIDATED_BEFORE_COMPLETION),
      base::BindOnce(&PaaniStubURLLoader::OnDataWritten,
                     base::Unretained(this)));
}

void PaaniStubURLLoader::OnMojoDisconnect() {
  data_producer_.reset();
  receiver_.reset();
  client_.reset();
  MaybeDeleteSelf();
}

void PaaniStubURLLoader::MaybeDeleteSelf() {
  if (!receiver_.is_bound() && !client_.is_bound() && !data_producer_) {
    delete this;
  }
}

void PaaniStubURLLoader::OnDataWritten(MojoResult result) {
  const int status = result == MOJO_RESULT_OK ? net::OK : net::ERR_FAILED;

  // Closing the pipe tells the reader that the body is complete.
  data_producer_.reset();

  network::URLLoaderCompletionStatus completion_status(status);
  if (status == net::OK) {
    total_bytes_written_ = body_.size();
    completion_status.encoded_data_length =
        base::ByteSize(total_bytes_written_);
    completion_status.encoded_body_length =
        base::ByteSize(total_bytes_written_);
    completion_status.decoded_body_length =
        base::ByteSize(total_bytes_written_);
  }

  // The page can drop the request before the write finishes, which unbinds the
  // client without deleting this loader (the producer is still alive).
  if (client_.is_bound()) {
    client_->OnComplete(completion_status);
  }

  OnMojoDisconnect();
}

void PaaniStubURLLoader::FollowRedirect(
    network::HttpRequestHeadersUpdateParams headers_update_params,
    const std::optional<GURL>& new_url) {}

void PaaniStubURLLoader::SetPriority(net::RequestPriority priority,
                                     int32_t intra_priority_value) {}

}  // namespace paani
