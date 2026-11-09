// Direct attribution: read uBlock Origin's own blocked-request counter from its
// extension background page, then load the ad test page from a real http
// origin and read uBlock's counter again.
//
//   delta == number blocked  -> uBlock Origin did the blocking
//   delta == 0 but page says blocked -> the Paani engine did it
const PORT = process.argv[2] || '9336';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function targets() {
  return (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json());
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
    cdp.send = (m, p = {}) => new Promise((res, rej) => {
      const id = ++cdp.id;
      cdp.pending.set(id, { resolve: res, reject: rej });
      ws.send(JSON.stringify({ id, method: m, params: p }));
    });
    cdp.eval = async (expression) => {
      const o = await cdp.send('Runtime.evaluate', { expression, returnByValue: true });
      if (o.exceptionDetails) return 'EXC ' + JSON.stringify(o.exceptionDetails.text);
      return o.result && o.result.value;
    };
    ws.onopen = () => resolve(cdp);
    ws.onerror = (e) => reject(new Error('ws error ' + e.message));
  });
}

async function newTab(url) {
  const r = await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' });
  if (!r.ok) throw new Error('json/new ' + r.status);
  return r.json();
}

async function main() {
  const list = await targets();
  const ub = list.find((t) => t.url.startsWith('chrome-extension://'));
  if (!ub) throw new Error('no extension background target');
  const ubCdp = await attach(ub.webSocketDebuggerUrl);
  await ubCdp.send('Runtime.enable');

  const globals = await ubCdp.eval(
    "Object.getOwnPropertyNames(self).filter(function(n){return /block|Count|count/.test(n)}).join(',')");
  console.log('extension globals matching block/count: ' + globals);
  const probeExpr =
    "(function(){var o={}; ['blockedRequestCount','totalBlockStats','µblockedRequestCount']" +
    ".forEach(function(k){ try{ o[k]=eval('typeof '+k)+'='+ (typeof eval(k)==='number'? eval(k):'-'); }catch(e){ o[k]='err'; }}); " +
    "return JSON.stringify(o);})()";
  console.log('uBlock counters before: ' + await ubCdp.eval(probeExpr));

  for (let i = 1; i <= 3; i++) {
    const url = `http://127.0.0.1:8731/adtest.html?cb=${i}_${Date.now()}`;
    const tab = await newTab(url);
    const cdp = await attach(tab.webSocketDebuggerUrl);
    await cdp.send('Runtime.enable');
    let value = '';
    for (let k = 0; k < 16; k++) {
      await sleep(1000);
      value = await cdp.eval(
        "document.getElementById('result') ? document.getElementById('result').textContent : 'gone'");
      if (String(value).startsWith('RESULT blocked')) break;
    }
    console.log(`http round ${i}: ${String(value).slice(0, 40)} | uBlock: ${await ubCdp.eval(probeExpr)}`);
    cdp.ws.close();
    await fetch(`http://127.0.0.1:${PORT}/json/close/${tab.id}`).catch(() => {});
  }
  ubCdp.ws.close();
}

main().catch((e) => { console.error('FAILED ' + e.message); process.exit(1); });
