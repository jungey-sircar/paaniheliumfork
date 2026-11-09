// Reads chrome://paani's own mojom state and returns it as a JSON string.
// Returning a string avoids "Object couldn't be returned by value": the mojom
// structs contain int64 fields that CDP cannot pass back as objects.
const PORT = process.argv[2] || '9339';
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

const r = await (await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent('chrome://paani/')}`,
  { method: 'PUT' })).json();
const cdp = await connect(r.webSocketDebuggerUrl);
await cdp.send('Runtime.enable');
await sleep(4000);
const out = await cdp.send('Runtime.evaluate', {
  returnByValue: true,
  awaitPromise: true,
  expression: `(async () => {
    const a = document.querySelector('paani-app');
    if (!a) return 'NO paani-app ELEMENT';
    const info = { hasProxy: !!a.browserProxy_, keys: Object.keys(a).slice(0, 40) };
    if (!a.browserProxy_ || !a.browserProxy_.handler) return 'proxy missing: ' + JSON.stringify(info);
    try {
      const s = await a.browserProxy_.handler.getState();
      info.state = JSON.parse(JSON.stringify(s));
    } catch (e) { info.error = String(e && e.message || e); }
    const el = a.shadowRoot && a.shadowRoot.querySelector('.engine-status');
    info.shown = el ? el.textContent : null;
    info.body = a.shadowRoot ? a.shadowRoot.textContent.replace(/\\s+/g, ' ').slice(0, 400) : null;
    return JSON.stringify(info, null, 1);
  })()` });
console.log(out.result.value ?? JSON.stringify(out));
cdp.ws.close();
