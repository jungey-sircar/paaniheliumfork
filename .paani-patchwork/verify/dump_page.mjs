const PORT = process.argv[2] || '9333';
const url = process.argv[3] || 'chrome://paani/';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const r = await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
const tab = await r.json();
const ws = new WebSocket(tab.webSocketDebuggerUrl);
await new Promise((res) => { ws.onopen = res; });
const send = (id, method, params) => new Promise((res) => {
  const h = (ev) => { const m = JSON.parse(ev.data); if (m.id === id) { ws.removeEventListener('message', h); res(m); } };
  ws.addEventListener('message', h);
  ws.send(JSON.stringify({ id, method, params }));
});
await send(1, 'Runtime.enable');
await sleep(2500);
const out = await send(2, 'Runtime.evaluate', { expression: 'document.documentElement ? document.documentElement.outerHTML.slice(0,1200) : "NO DOC" + location.href + " | " + document.title', returnByValue: true });
console.log('HTML: ' + JSON.stringify(out.result?.result?.value ?? out.result?.exceptionDetails?.exception?.description));
const loc = await send(3, 'Runtime.evaluate', { expression: 'location.href + " | ready=" + document.readyState + | " | title=" + document.title', returnByValue: true });
console.log('LOC: ' + JSON.stringify(loc));
ws.close();
