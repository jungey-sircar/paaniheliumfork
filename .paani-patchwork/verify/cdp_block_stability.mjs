// Is the block decision stable?  One tab, several navigations, cache disabled.
const DEBUG_PORT = process.argv[2] || '9334';
const TEST_URL = process.argv[3] || 'http://127.0.0.1:8731/adtest.html';
const ROUNDS = Number(process.argv[4] || 4);
const PAUSE_MS = Number(process.argv[5] || 4000);

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function getTarget() {
  const r = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json`);
  const list = await r.json();
  const page = list.find((t) => t.type === 'page');
  if (!page) throw new Error('no page target');
  return page;
}

function attach(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const cdp = { ws, id: 0, pending: new Map(), blocked: [], loaded: [] };
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
        cdp.blocked.push(msg.params.requestId);
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
  if (out.exceptionDetails) throw new Error('eval threw');
  return out.result.value;
}

async function main() {
  const target = await getTarget();
  const cdp = await attach(target.webSocketDebuggerUrl);
  await cdp.send('Runtime.enable');
  await cdp.send('Network.enable');
  await cdp.send('Network.setCacheDisabled', { cacheDisabled: true });

  for (let round = 1; round <= ROUNDS; round++) {
    cdp.blocked.length = 0;
    // Fresh <script> elements each round, with a unique document so that
    // neither the HTTP nor the Blink memory cache can answer the request.
    const html = `<!doctype html><html><head><title>r${round}</title></head><body><div id=result>pending</div>
      <script>
        const urls=['https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js',
                   'https://securepubads.g.doubleclick.net/tag/js/gpt.js',
                   'https://www.googletagservices.com/tag/js/gpt.js'];
        let blocked=0, loaded=0, done=0;
        function fin(){ if(done<3) return;
          document.getElementById('result').textContent='RESULT blocked='+blocked+' loaded='+loaded+' netfail='+window.__paaniNetFail; }
        urls.forEach(u=>{const s=document.createElement('script');
          s.src=u+'?cb=${round}'+Math.random();
          s.onload=()=>{loaded++;done++;fin();};
          s.onerror=()=>{blocked++;done++;fin();};
          document.head.appendChild(s);});
        setTimeout(()=>{document.getElementById('result').textContent='RESULT TIMEOUT blocked='+blocked+' loaded='+loaded;},12000);
      </script></body></html>`;
    await cdp.send('Page.enable');
    await cdp.send('Page.navigate', { url: 'data:text/html;charset=utf-8,' + encodeURIComponent(html) });
    let value = '';
    for (let i = 0; i < 16; i++) {
      await sleep(1000);
      try { value = await evalJs(cdp, "document.getElementById('result') ? document.getElementById('result').textContent : 'gone'"); }
      catch (e) { value = 'eval ' + e.message; }
      if (value.startsWith('RESULT blocked') || value.startsWith('RESULT TIMEOUT')) break;
    }
    console.log(`round ${round}: ${value}   (ERR_BLOCKED_BY_CLIENT events seen by browser: ${cdp.blocked.length})`);
    await sleep(PAUSE_MS);
  }
  cdp.ws.close();
}

main().catch((e) => { console.error('FAILED ' + e.message); process.exit(1); });
