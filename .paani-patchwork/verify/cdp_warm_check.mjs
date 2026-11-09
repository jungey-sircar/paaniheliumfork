// Distinguishes "the Paani proxy is not in the network chain" from "the
// adblock engine had not finished building when the page loaded".
// Loads the ad test page twice: once immediately after startup and once after
// a long wait, and records the per-request CDP failures for both.
const DEBUG_PORT = process.argv[2] || '9334';
const TEST_URL = process.argv[3] || 'http://127.0.0.1:8731/adtest.html';
const WAIT_MS = Number(process.argv[4] || 60000);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function waitForBrowser() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/version`);
      if (r.ok) return await r.json();
    } catch {}
    await sleep(1000);
  }
  throw new Error('browser did not come up on ' + DEBUG_PORT);
}

function attach(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const cdp = { ws, id: 0, pending: new Map(), failures: [], urls: new Map() };
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && cdp.pending.has(msg.id)) {
        const { resolve, reject } = cdp.pending.get(msg.id);
        cdp.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
        return;
      }
      if (msg.method === 'Network.requestWillBeSent') {
        cdp.urls.set(msg.params.requestId, msg.params.request.url);
      }
      if (msg.method === 'Network.loadingFailed') {
        cdp.failures.push({ url: cdp.urls.get(msg.params.requestId) || msg.params.requestId,
          type: msg.params.type, error: msg.params.errorText,
          blocked: msg.params.blockedReason });
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
  if (out.exceptionDetails) throw new Error('eval threw: ' + JSON.stringify(out.exceptionDetails.exception));
  return out.result.value;
}

async function runOnce(label) {
  const tab = await newTab(TEST_URL);
  const cdp = await attach(tab.webSocketDebuggerUrl);
  await cdp.send('Runtime.enable');
  await cdp.send('Network.enable');
  let result = '';
  for (let i = 0; i < 25; i++) {
    try {
      result = await evalJs(cdp, "document.getElementById('result') ? document.getElementById('result').textContent : 'no result node'");
    } catch (e) {
      result = 'eval error ' + e.message;
    }
    if (result.startsWith('RESULT')) break;
    await sleep(1000);
  }
  const events = cdp.failures.filter((f) => f.error || /googlesyndication|doubleclick|googletagservices/.test(f.url || ''));
  console.log(`[${label}] ${result}`);
  for (const e of events) {
    console.log(`    ${e.error ? 'FAILED ' + e.error + ' ' + (e.blocked || '') : '200    '} ${String(e.url).slice(0, 90)}`);
  }
  cdp.ws.close();
  return result;
}

async function main() {
  const info = await waitForBrowser();
  console.log('browser: ' + info.Browser);
  await runOnce('t=0s');
  console.log('waiting ' + WAIT_MS / 1000 + 's for the engine to build...');
  await sleep(WAIT_MS);
  await runOnce('t=' + WAIT_MS / 1000 + 's');
}

main().catch((e) => { console.error('FAILED ' + e.message); process.exit(1); });
