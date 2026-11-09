// One-shot CDP probe: read the ad-test page result and the chrome://paani counter.
const PORT = process.argv[2] || '9333';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function targets() {
  const r = await fetch(`http://127.0.0.1:${PORT}/json`);
  return r.json();
}

async function evalIn(wsUrl, expression) {
  const ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  const out = await new Promise((res) => {
    ws.send(JSON.stringify({ id: 1, method: 'Runtime.evaluate',
                            params: { expression, returnByValue: true } }));
    ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id === 1) res(m); };
  });
  ws.close();
  if (out.result?.exceptionDetails) return 'EXC: ' + (out.result.exceptionDetails.exception?.description || '');
  return JSON.stringify(out.result?.result?.value ?? out.error);
}

const list = await targets();
const test = list.find((t) => t.url.includes('adtest'));
console.log('test target: ' + (test ? test.url : 'NONE'));
if (test) {
  console.log('title=' + (await evalIn(test.webSocketDebuggerUrl, 'document.title')));
  console.log('readyState=' + (await evalIn(test.webSocketDebuggerUrl, 'document.readyState')));
  console.log('result=' + (await evalIn(test.webSocketDebuggerUrl,
      "document.getElementById('result') ? document.getElementById('result').textContent : 'NO #result DIV; body=' + document.body.innerHTML.slice(0,200)")));
  console.log('scripts=' + (await evalIn(test.webSocketDebuggerUrl,
      "Array.from(document.head.querySelectorAll('script[src]')).map(s=>s.src).join(' ')")));
}
const ext = list.find((t) => t.type === 'background_page');
console.log('extension background page: ' + (ext ? ext.url : 'none'));
