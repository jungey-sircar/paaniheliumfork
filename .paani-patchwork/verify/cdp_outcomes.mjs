// Reports, per third-party request, what the network layer actually did.
// Attribution rule: a request counts as blocked by Paani only when the
// original URL itself fails with net::ERR_BLOCKED_BY_CLIENT. A request whose
// chain contains a chrome-extension:// URL is Helium's uBlock, not Paani.
//
//   node cdp_outcomes.mjs <cdp-port> <page-url> [wait-seconds]
const PORT = process.argv[2] || '9339';
const PAGE = process.argv[3] || 'http://127.0.0.1:8731/trackertest.html';
const WAIT = (Number(process.argv[4]) || 20) * 1000;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const cdp = { ws, id: 0, pending: new Map(), events: [] };
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && cdp.pending.has(m.id)) {
        const { resolve, reject } = cdp.pending.get(m.id);
        cdp.pending.delete(m.id);
        m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
      } else if (m.method) cdp.events.push(m);
    };
    cdp.send = (method, params = {}) => new Promise((res, rej) => {
      const id = ++cdp.id;
      cdp.pending.set(id, { resolve: res, reject: rej });
      ws.send(JSON.stringify({ id, method, params }));
    });
    ws.onopen = () => resolve(cdp);
    ws.onerror = () => reject(new Error('ws error'));
  });
}

const r = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(PAGE + '?cb=' + Date.now())}`,
  { method: 'PUT' })).json();
const cdp = await connect(r.webSocketDebuggerUrl);
await cdp.send('Network.enable');
await cdp.send('Runtime.enable');
await sleep(WAIT);

const urls = new Map();
const outcome = new Map();
for (const e of cdp.events) {
  const p = e.params || {};
  if (e.method === 'Network.requestWillBeSent') {
    if (!urls.has(p.requestId)) urls.set(p.requestId, []);
    urls.get(p.requestId).push(p.request.url);
    if (!outcome.has(p.requestId)) outcome.set(p.requestId, 'in-flight');
  } else if (e.method === 'Network.requestWillBeSentRedirect') {
    if (!urls.has(p.requestId)) urls.set(p.requestId, []);
    urls.get(p.requestId).push(p.request.url);
  } else if (e.method === 'Network.loadingFailed') {
    outcome.set(p.requestId, 'FAILED ' + p.errorText + (p.blockedReason ? ' [' + p.blockedReason + ']' : ''));
  } else if (e.method === 'Network.loadingFinished') {
    outcome.set(p.requestId, 'finished');
  } else if (e.method === 'Network.responseReceived') {
    outcome.set(p.requestId, 'response ' + p.response.status +
      (p.response.fromMemoryCache || p.response.fromDiskCache ? ' (cache)' : ''));
  } else if (e.method === 'Network.loadingRewrapped') {
    const b = p.blocked || {};
    outcome.set(p.requestId, 'BLOCKED_BY ' + (b.blockedReason || '?') +
      ' source=' + (b.source || '?'));
  }
}

let blockedByClient = 0, extensionRedirects = 0, other = 0;
for (const [id, list] of urls) {
  const first = list[0];
  if (/^http:\/\/127\.0\.0\.1/.test(first)) continue;
  const o = outcome.get(id) || 'in-flight';
  if (/BLOCKED_BY_CLIENT/.test(o)) blockedByClient++;
  else if (list.some((u) => u.startsWith('chrome-extension://'))) extensionRedirects++;
  else other++;
  console.log((o.padEnd(34) + ' | ' + first.slice(0, 96) +
    (list.length > 1 ? ' | chain-> ' + list[1].slice(0, 60) : '')));
}
const st = await cdp.send('Runtime.evaluate', {
  returnByValue: true,
  expression: "document.getElementById('result').textContent" });
console.log('page=', st.result.value);
console.log('SUMMARY blocked_by_client=' + blockedByClient +
  ' uBlock_extension_redirects=' + extensionRedirects + ' other=' + other);
cdp.ws.close();
