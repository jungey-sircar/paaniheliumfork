// Lists the requests a page made and what happened to each of them, with the
// URL of the document that started the request.
//
// The allowlist is checked against the site the request was made from, so a
// request that is blocked while its site is allowlisted is a request whose
// initiator is a different site -- a third party frame, or a request with no
// initiator at all.
//
//   node cdp_allowlist_detail.mjs <cdp-port> <page-url> [wait-seconds]
const PORT = process.argv[2] || '9355';
const PAGE = process.argv[3] || 'https://www.foxnews.com/politics';
const WAIT = (Number(process.argv[4]) || 30) * 1000;
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

const r = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(PAGE)}`,
  { method: 'PUT' })).json();
const cdp = await connect(r.webSocketDebuggerUrl);
await cdp.send('Network.enable');
await cdp.send('Page.enable');
await sleep(WAIT);

const info = new Map();
const outcome = new Map();
for (const e of cdp.events) {
  const p = e.params || {};
  if (e.method === 'Network.requestWillBeSent') {
    if (!info.has(p.requestId)) {
      // The initiator of a script request carries the document it ran in on
      // the stack, which is the frame the request really belongs to.
      const ini = p.initiator || {};
      const frame = (ini.stack && ini.stack.callFrames && ini.stack.callFrames[0]) || {};
      info.set(p.requestId, {
        url: p.request.url,
        initiator: ini.documentURL || frame.url || ini.url || ini.type || 'none',
        kind: ini.type || '?',
        type: p.type || '?',
      });
    }
  } else if (e.method === 'Network.loadingFailed') {
    outcome.set(p.requestId, 'FAILED ' + p.errorText +
      (p.blockedReason ? ' [' + p.blockedReason + ']' : ''));
  } else if (e.method === 'Network.loadingFinished') {
    outcome.set(p.requestId, 'finished');
  } else if (e.method === 'Network.responseReceived') {
    outcome.set(p.requestId, 'response ' + p.response.status);
  }
}

let blocked = 0;
for (const [id, i] of info) {
  const o = outcome.get(id) || 'in-flight';
  const isBlocked = /ERR_BLOCKED_BY_CLIENT/.test(o);
  if (isBlocked) blocked++;
  console.log((isBlocked ? 'BLOCKED ' : '        ') +
    o.padEnd(30) + ' | ' + String(i.initiator).slice(0, 58).padEnd(58) +
    ' | ' + i.url.slice(0, 100));
}
console.log('SUMMARY blocked_by_client=' + blocked + ' total=' + info.size);
cdp.ws.close();
