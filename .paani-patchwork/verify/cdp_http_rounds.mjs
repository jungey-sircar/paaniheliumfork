// Blocking stability from a real HTTP origin, one tab, cache-busted repeats.
const DEBUG_PORT = process.argv[2] || '9334';
const BASE_URL = process.argv[3] || 'http://127.0.0.1:8731/adtest.html';
const ROUNDS = Number(process.argv[4] || 4);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function getTarget() {
  const list = await (await fetch(`http://127.0.0.1:${DEBUG_PORT}/json`)).json();
  const page = list.find((t) => t.type === 'page');
  if (!page) throw new Error('no page target');
  return page;
}

function attach(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const cdp = { ws, id: 0, pending: new Map(), blockedByClient: 0 };
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && cdp.pending.has(msg.id)) {
        const { resolve, reject } = cdp.pending.get(msg.id);
        cdp.pending.delete(msg.id);
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
        return;
      }
      if (msg.method === 'Network.loadingFailed' &&
          msg.params.errorText === 'net::ERR_BLOCKED_BY_CLIENT') {
        cdp.blockedByClient++;
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

async function evalJs(cdp, expression) {
  const out = await cdp.send('Runtime.evaluate', { expression, returnByValue: true });
  return out.result.value;
}

async function main() {
  const target = await getTarget();
  const cdp = await attach(target.webSocketDebuggerUrl);
  await cdp.send('Runtime.enable');
  await cdp.send('Network.enable');
  await cdp.send('Page.enable');

  for (let round = 1; round <= ROUNDS; round++) {
    cdp.blockedByClient = 0;
    await cdp.send('Page.navigate', { url: `${BASE_URL}?cb=${round}_${Date.now()}` });
    let value = '';
    for (let i = 0; i < 18; i++) {
      await sleep(1000);
      value = await evalJs(cdp, "document.getElementById('result') ? document.getElementById('result').textContent : 'gone'");
      if (value.startsWith('RESULT blocked') || value.startsWith('RESULT TIMEOUT')) break;
    }
    console.log(`round ${round}: ${value.slice(0, 60)}  | browser ERR_BLOCKED_BY_CLIENT=${cdp.blockedByClient}`);
  }
  cdp.ws.close();
}

main().catch((e) => { console.error('FAILED ' + e.message); process.exit(1); });
