// Loads the ad test page once in a running browser and prints what the page
// itself observed, plus the network-level view of the three ad URLs.
const PORT = process.argv[2] || '9333';
const BASE = process.argv[3] || 'http://127.0.0.1:8731/adtest.html';
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
      } else if (m.method) {
        cdp.events.push(m);
      }
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

async function evalIn(cdp, expression) {
  const out = await cdp.send('Runtime.evaluate',
    { expression, returnByValue: true, awaitPromise: true });
  if (out.exceptionDetails) {
    return 'EXC ' + (out.exceptionDetails.exception?.description || '');
  }
  return out.result.value;
}

const url = BASE + '?cb=' + Date.now();
const r = await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(url)}`,
  { method: 'PUT' });
const tab = await r.json();
const cdp = await connect(tab.webSocketDebuggerUrl);
await cdp.send('Runtime.enable');
await cdp.send('Network.enable');
await sleep(12000);

console.log('url=' + url);
console.log('page=' + await evalIn(cdp,
  "var d=document.getElementById('result'); d ? d.textContent : 'no #result'"));

const byId = new Map();
const failures = [];
const finishes = [];
for (const e of cdp.events) {
  const p = e.params || {};
  if (e.method === 'Network.requestWillBeSent') {
    byId.set(p.requestId, p.request.url);
  } else if (e.method === 'Network.loadingFailed') {
    failures.push([byId.get(p.requestId) || p.url, p.errorText, p.blockedReason]);
  } else if (e.method === 'Network.loadingFinished') {
    finishes.push(byId.get(p.requestId) || p.url);
  }
}
const ads = (u) => /googlesyndication|doubleclick|googletagservices/.test(u || '');
console.log('net_failed_ads=' +
  JSON.stringify(failures.filter((f) => ads(f[0])).map((f) => [f[0], f[1], f[2]])));
console.log('net_loaded_ads=' +
  JSON.stringify(finishes.filter(ads).map((u) => u.slice(0, 70))));

cdp.ws.close();
process.exit(0);
