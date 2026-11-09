// Verification chain for the built in ad blocker, run against a live browser.
//
// Every number here comes out of PaaniAdblockState itself over mojom, so a
// result cannot be credited to Helium's bundled uBlock Origin by mistake: the
// only way this counter moves is that Paani's own URLLoaderFactory returned
// net::ERR_BLOCKED_BY_CLIENT.
//
// The mojom state struct carries int64 fields, which reach JS as BigInt and
// which CDP refuses to return by value ("Do not know how to serialize a
// BigInt"). The page therefore converts them and hands back a JSON string.
//
//   node verify_paani.mjs <cdp-port> [adtest-base-url]
const PORT = process.argv[2] || '9333';
const ADTEST = process.argv[3] || 'http://127.0.0.1:8731/adtest.html';
const AD_HOSTS = /googlesyndication|doubleclick|googletagservices/;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const { writeFileSync } = await import('node:fs');

function connect(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const cdp = { ws, id: 0, pending: new Map(), events: [] };
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id && cdp.pending.has(m.id)) {
        const { resolve, reject } = cdp.pending.get(m.id);
        cdp.pending.delete(m.id);
        m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
      } else if (m.method) {
        cdp.events.push(m);
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
  const out = await cdp.send('Runtime.evaluate',
    { expression, returnByValue: true, awaitPromise: true });
  if (out.exceptionDetails) {
    return { error: out.exceptionDetails.exception?.description ||
                    JSON.stringify(out.exceptionDetails) };
  }
  return { value: out.result.value };
}

// mojom int64 arrives as BigInt, which neither JSON.stringify nor CDP accepts.
const BIGINT_SAFE = '(k, v) => typeof v === "bigint" ? Number(v) : v';

function decode(value) {
  if (typeof value !== 'string') return value;
  try { return JSON.parse(value); } catch { return value; }
}

async function openTab(url) {
  const r = await fetch(`http://127.0.0.1:${PORT}/json/new?${encodeURIComponent(url)}`,
    { method: 'PUT' });
  const tab = await r.json();
  const cdp = await connect(tab.webSocketDebuggerUrl);
  await cdp.send('Runtime.enable');
  await cdp.send('Network.enable');
  return { tab, cdp };
}

async function getState() {
  const { cdp } = await openTab('chrome://paani/');
  await sleep(3500);
  const out = await evalIn(cdp,
    '(async () => { const a = document.querySelector("paani-app");' +
    'if (!a || !a.browserProxy_) return JSON.stringify({fatal: "no paani-app element or proxy"});' +
    `const fix = ${BIGINT_SAFE};` +
    'const s = await a.browserProxy_.handler.getState();' +
    'return JSON.stringify({enabled: s.enabled, blocked: s.blockedCount,' +
    'sites: s.allowedSites, engine: s.engine,' +
    'shown: a.shadowRoot.querySelector(".engine-status") ?' +
    '  a.shadowRoot.querySelector(".engine-status").textContent : null,' +
    'page: a.shadowRoot.textContent.replace(/\\s+/g, " ").slice(0, 220)}, fix); })()');
  await cdp.send('Page.enable');
  await cdp.send('Page.captureScreenshot', { format: 'png' })
    .then((r) => writeFileSync('paani_page.png', Buffer.from(r.data, 'base64')))
    .catch(() => {});
  cdp.ws.close();
  return decode(out.value ?? out);
}

// Loads the test page once and reports what the network layer did to the ads.
async function adtestRound(cb) {
  const { cdp } = await openTab(`${ADTEST}?cb=${cb}`);
  await sleep(14000);
  const urls = new Map();
  const failures = new Map();
  const loaded = new Map();
  for (const e of cdp.events) {
    const p = e.params || {};
    if (e.method === 'Network.requestWillBeSent') {
      if (!urls.has(p.requestId)) urls.set(p.requestId, []);
      urls.get(p.requestId).push(p.request.url);
    } else if (e.method === 'Network.loadingFailed') {
      failures.set(p.requestId, p.errorText);
    } else if (e.method === 'Network.loadingFinished') {
      loaded.set(p.requestId, true);
    }
  }
  const isAd = (id) => (urls.get(id) || []).some((u) => AD_HOSTS.test(u));
  const blockedAds = [...failures.entries()].filter(([id, t]) => isAd(id) &&
    /BLOCKED_BY_CLIENT|ERR_BLOCKED/.test(t));
  // uBlock answers a matched ad with a redirect into its own extension
  // resources; counting those separately keeps them from being read as a
  // Paani block.
  const redirectedAds = [...urls.entries()].filter(([id, list]) =>
    list.some((u) => AD_HOSTS.test(u)) &&
    list.some((u) => u.startsWith('chrome-extension://')));
  const pageResult = await evalIn(cdp,
    "var d=document.getElementById('result'); d ? d.textContent : 'no #result'");
  cdp.ws.close();
  return {
    page: pageResult.value ?? pageResult,
    blocked: blockedAds.map(([id, t]) => [(urls.get(id) || [])[0], t]),
    uBlockRedirects: redirectedAds.length,
    loadedAdIds: [...loaded.keys()].filter(isAd).length,
  };
}

// Adds or removes an entry through the page's proxy, like the button does.
async function editSite(method, site) {
  const { cdp } = await openTab('chrome://paani/');
  await sleep(2500);
  const out = await evalIn(cdp,
    `(async () => { const a = document.querySelector("paani-app");` +
    `const s = await a.browserProxy_.handler.${method}('${site}');` +
    `return JSON.stringify(s.allowedSites, ${BIGINT_SAFE}); })()`);
  cdp.ws.close();
  return decode(out.value ?? out);
}

const log = (...a) => console.log(...a);

log('--- 1. page state over mojom (proves the binder works) ---');
log('getState=', JSON.stringify(await getState()));

log('--- 2. three ad requests, cache busted ---');
const round1 = await adtestRound(Date.now());
log('page=', round1.page);
log('blocked_by_paani=', JSON.stringify(round1.blocked));
log('uBlock_redirects=', round1.uBlockRedirects, 'ads_that_loaded=', round1.loadedAdIds);

log('--- 3. counter after the round ---');
log('getState=', JSON.stringify(await getState()));

log('--- 4. allowlist 127.0.0.1, then repeat ---');
log('allowSite=', JSON.stringify(await editSite('allowSite', '127.0.0.1')));
const round2 = await adtestRound(Date.now() + 1);
log('page=', round2.page);
log('blocked_by_paani=', JSON.stringify(round2.blocked));
log('getState=', JSON.stringify(await getState()));

log('--- 5. remove the allowlist entry, then repeat ---');
log('disallowSite=', JSON.stringify(await editSite('disallowSite', '127.0.0.1')));
const round3 = await adtestRound(Date.now() + 2);
log('page=', round3.page);
log('blocked_by_paani=', JSON.stringify(round3.blocked));
log('getState=', JSON.stringify(await getState()));
