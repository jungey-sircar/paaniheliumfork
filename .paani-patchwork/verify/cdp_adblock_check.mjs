// Drives the built Paani browser over CDP to prove ad blocking works.
//
// 1. loads a page that requests three well-known ad scripts
// 2. reads how many of them failed (blocked) versus loaded
// 3. reads the blocked-request counter rendered on chrome://paani
//
// Both pages run in the same browser process, so the counter on chrome://paani
// is the same PaaniAdblockState that served the test page.
const DEBUG_PORT = process.argv[2] || '9333';
const TEST_URL = process.argv[3] || 'http://127.0.0.1:8731/adtest.html';

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitForBrowser() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/version`);
      if (r.ok) return await r.json();
    } catch {}
    await sleep(1000);
  }
  throw new Error('browser did not come up on port ' + DEBUG_PORT);
}

function attach(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const cdp = { ws, id: 0, pending: new Map() };
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && cdp.pending.has(msg.id)) {
        const { resolve, reject } = cdp.pending.get(msg.id);
        cdp.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
      }
    };
    cdp.send = (method, params = {}) =>
      new Promise((res, rej) => {
        const id = ++cdp.id;
        cdp.pending.set(id, { resolve: res, reject: rej });
        ws.send(JSON.stringify({ id, method, params }));
      });
    ws.onopen = () => resolve(cdp);
    ws.onerror = (e) => reject(new Error('websocket error ' + e.message));
  });
}

async function newTab(url) {
  const r = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/new?${encodeURIComponent(url)}`,
                        { method: 'PUT' });
  if (!r.ok) throw new Error('json/new failed: ' + r.status);
  return r.json();
}

async function evalJs(cdp, expression) {
  const out = await cdp.send('Runtime.evaluate', {
    expression, returnByValue: true, awaitPromise: true,
  });
  if (out.exceptionDetails) {
    throw new Error('eval threw: ' + JSON.stringify(out.exceptionDetails.exception));
  }
  return out.result.value;
}

async function main() {
  const info = await waitForBrowser();
  console.log('browser: ' + info.Browser);

  const test = await newTab(TEST_URL);
  const testCdp = await attach(test.webSocketDebuggerUrl);
  await testCdp.send('Runtime.enable');

  let result = '';
  for (let i = 0; i < 40; i++) {
    result = await evalJs(testCdp, "document.getElementById('result').textContent");
    if (result.startsWith('RESULT')) break;
    await sleep(1000);
  }
  console.log('TEST PAGE   ' + result);

  const ui = await newTab('chrome://paani/');
  const uiCdp = await attach(ui.webSocketDebuggerUrl);
  await uiCdp.send('Runtime.enable');
  await sleep(2500);
  const text = await evalJs(
    uiCdp,
    "document.querySelector('paani-app') ? document.querySelector('paani-app').shadowRoot.textContent.replace(/\\s+/g,' ').trim() : document.body.innerText"
  );
  console.log('CHROME://PAANI  ' + text.slice(0, 400));

  const enabled = await evalJs(
    uiCdp,
    "document.querySelector('paani-app') ? JSON.stringify({blocked: document.querySelector('paani-app').blockedCount_, enabled: document.querySelector('paani-app').enabled_}) : 'n/a'"
  );
  console.log('STATE  ' + enabled);

  testCdp.ws.close();
  uiCdp.ws.close();
}

main().catch((e) => { console.error('FAILED ' + e.message); process.exit(1); });
