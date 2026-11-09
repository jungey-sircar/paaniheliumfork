// Opens chrome://paani in the running verification browser and reads the
// blocked-request counter and allowlist the way the page shows them.
const PORT = process.argv[2] || '9333';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const cdp = { ws, id: 0, pending: new Map() };
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && cdp.pending.has(m.id)) {
        const { resolve, reject } = cdp.pending.get(m.id);
        cdp.pending.delete(m.id);
        m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
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
  const out = await cdp.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (out.exceptionDetails) return 'EXC ' + (out.exceptionDetails.exception?.description || '');
  return out.result.value;
}

const r = await fetch(`http://127.0.0.1:${PORT}/json/new?chrome://paani/`, { method: 'PUT' });
const tab = await r.json();
const cdp = await connect(tab.webSocketDebuggerUrl);
await cdp.send('Runtime.enable');
await sleep(3000);

console.log('url=' + tab.url);
console.log('title=' + (await evalIn(cdp, 'document.title')));
console.log('innerText=' + (await evalIn(cdp, 'document.body ? document.body.innerText.replace(/\\r?\\n/g," | ") : "NO BODY"')).slice(0, 500));
console.log('shadow=' + (await evalIn(cdp,
  "var a=document.querySelector('paani-app'); a ? a.shadowRoot.textContent.replace(/\\s+/g,' ').trim().slice(0,300) : 'no paani-app element'")));
console.log('props=' + (await evalIn(cdp,
  "var a=document.querySelector('paani-app'); a ? JSON.stringify({enabled:a.enabled_, blocked:a.blockedCount_, allowed:a.allowedSites_}) : 'no element'")));

cdp.ws.close();
