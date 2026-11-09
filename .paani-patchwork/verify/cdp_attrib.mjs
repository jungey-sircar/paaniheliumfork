// Attribution probe.
//
// Paani's proxy lets a request through when the first-party URL cannot be
// parsed (a `data:` document has an opaque origin).  uBlock Origin has no such
// rule.  Alternating the two origins therefore says which blocker acted.
//
//   data: round blocked   -> uBlock was responsible
//   data: round allowed, http round blocked -> Paani's own engine
const PORT = process.argv[2] || '9333';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const HTML = (nonce) => `<!doctype html><html><head><title>${nonce}</title></head><body><div id=r>pending</div>
<script>
 var seen={blocked:[],loaded:[]};
 var urls=['https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js',
           'https://securepubads.g.doubleclick.net/tag/js/gpt.js',
           'https://www.googletagservices.com/tag/js/gpt.js'];
 var pending=urls.length;
 function fin(){ if(pending>0) return;
   document.getElementById('r').textContent='RESULT blocked='+seen.blocked.length+' loaded='+seen.loaded.length; }
 urls.forEach(function(u){var s=document.createElement('script');
   s.src=u+'?n=${nonce}';
   s.onload=function(){seen.loaded.push(u);pending--;fin();};
   s.onerror=function(){seen.blocked.push(u);pending--;fin();};
   document.head.appendChild(s);});
 setTimeout(function(){document.getElementById('r').textContent='RESULT blocked='+seen.blocked.length+' loaded='+seen.loaded.length+' (timeout)';},14000);
</script></body></html>`;

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
    cdp.eval = async (expr) => {
      const o = await cdp.send('Runtime.evaluate', { expression: expr, returnByValue: true });
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

async function probe(label, makeUrl) {
  const nonce = label.replace(/[^a-z0-9]/gi, '') + '_' + Math.floor(Math.random() * 1e6);
  const url = makeUrl(nonce);
  let tab, cdp;
  try {
    if (url === 'about:blank') {
      // reuse an existing page target and navigate it to the data URL
      const list = await targets();
      tab = list.find((t) => t.type === 'page');
      cdp = await attach(tab.webSocketDebuggerUrl);
      await cdp.send('Runtime.enable');
      await cdp.send('Page.enable');
      await cdp.send('Page.navigate', { url: 'data:text/html;charset=utf-8,' + encodeURIComponent(HTML(nonce)) });
    } else {
      tab = await newTab(url);
      cdp = await attach(tab.webSocketDebuggerUrl);
      await cdp.send('Runtime.enable');
    }
    let value = '';
    for (let i = 0; i < 16; i++) {
      await sleep(1000);
      value = await cdp.eval("document.getElementById('r') ? document.getElementById('r').textContent : 'gone'");
      if (String(value).startsWith('RESULT blocked')) break;
    }
    console.log(`${label.padEnd(34)} ${value}`);
    cdp.ws.close();
    if (url !== 'about:blank') {
      await fetch(`http://127.0.0.1:${PORT}/json/close/${tab.id}`).catch(() => {});
    }
  } catch (e) {
    console.log(`${label.padEnd(34)} ERROR ${e.message}`);
    if (cdp) cdp.ws.close();
  }
}

async function main() {
  const before = await targets();
  console.log('targets: ' + before.map((t) => t.type + '=' + (t.url || '').slice(0, 46)).join(', '));

  const httpUrl = (nonce) => `http://127.0.0.1:8731/adtest.html?cb=${nonce}`;
  const dataUrl = () => 'about:blank';   // handled inside probe()

  await probe('A http new tab', httpUrl);
  await probe('B data: same tab', dataUrl);
  await probe('C http new tab', httpUrl);
  await probe('D data: same tab', dataUrl);
  await probe('E http new tab', httpUrl);

  const after = await targets();
  console.log('targets now: ' + after.map((t) => t.type + '=' + (t.url || '').slice(0, 46)).join(', '));
}

main().catch((e) => { console.error('FAILED ' + e.message); process.exit(1); });
