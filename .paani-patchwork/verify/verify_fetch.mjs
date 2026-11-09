// Asks the running browser what the WebUI data source actually serves.
// A grit id can exist while the pak chunk holding its bytes is not linked in,
// which shows up as an empty (200) response.
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
  const out = await cdp.send('Runtime.evaluate', {
    expression, returnByValue: true, awaitPromise: true,
  });
  if (out.exceptionDetails) {
    return 'EXC ' + (out.exceptionDetails.exception?.description || out.exceptionDetails.text);
  }
  return out.result.value;
}

const r = await fetch(`http://127.0.0.1:${PORT}/json/new?chrome://paani/`, { method: 'PUT' });
const tab = await r.json();
const cdp = await connect(tab.webSocketDebuggerUrl);
await cdp.send('Runtime.enable');
await sleep(2000);

const probe = `(async () => {
  const names = ['/', '/paani.html', '/app.js', '/app.css.js', '/app.html.js',
                 '/paani.mojom-webui.js', '/favicon.ico'];
  const out = [];
  for (const n of names) {
    try {
      const res = await fetch(n, { cache: 'reload' });
      const t = await res.text();
      out.push(n + ' -> ' + res.status + ' ' + t.length + 'B ' + JSON.stringify(t.slice(0, 40)));
    } catch (e) { out.push(n + ' -> ERR ' + e.message); }
  }
  try {
    const res = await fetch('chrome://resources/css/text_defaults.css', { cache: 'reload' });
    out.push('upstream text_defaults.css -> ' + res.status + ' ' + (await res.text()).length + 'B');
  } catch (e) { out.push('upstream css -> ERR ' + e.message); }
  try {
    const res = await fetch('chrome://setup/', { cache: 'reload' });
    const t = await res.text();
    out.push('helium chrome://setup/ -> ' + res.status + ' ' + t.length + 'B');
  } catch (e) { out.push('chrome://setup -> ERR ' + e.message); }
  return out.join('\\n');
})()`;

console.log(await evalIn(cdp, probe));
cdp.ws.close();
