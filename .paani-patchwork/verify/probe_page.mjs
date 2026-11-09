// One shot experiment: open a page, find out what actually happened.
//
// The three phase harness said "0 blocked" in every phase. That has three
// possible causes and this probe tells them apart:
//   * the tab never loaded the page, so there was nothing to block,
//   * the page loaded and uBlock blocked the ads while Paani counted nothing,
//   * the page loaded and nothing blocked anything at all.

const args = {};
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  if (argv[i].startsWith('--')) {
    args[argv[i].slice(2)] = argv[i + 1];
    i++;
  }
}
const port = args.port || '9345';
const url = args.url || 'https://www.foxnews.com/politics';
const wait = Number(args.wait || 25);

const list = async () => (await fetch(`http://127.0.0.1:${port}/json/list`)).json();

const send = (ws, id, method, params) =>
  new Promise((resolve, reject) => {
    const onMessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.id !== id) return;
      ws.removeEventListener('message', onMessage);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result);
    };
    ws.addEventListener('message', onMessage);
    ws.send(JSON.stringify({ id, method, params }));
    setTimeout(() => reject(new Error(`${method} timed out`)), 20000);
  });

const evaluate = async (target, expression) => {
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve);
    ws.addEventListener('error', (e) => reject(new Error('ws failed: ' + e.message)));
  });
  const result = await send(ws, 1, 'Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  ws.close();
  if (result.exceptionDetails) {
    return 'EXCEPTION: ' + JSON.stringify(result.exceptionDetails.exception?.description || result.exceptionDetails);
  }
  return result.result.value;
};

// Open the page the way the harness does.
const created = await (await fetch(
  `http://127.0.0.1:${port}/json/new?${encodeURIComponent(url)}`,
  { method: 'PUT' })).json();
console.log('new tab id           :', created.id);

console.log(`waiting ${wait}s for the page to load`);
await new Promise((r) => setTimeout(r, wait * 1000));

const targets = await list();
for (const t of targets) {
  console.log(`target               : ${t.type} | ${t.url} | ${t.title}`);
}

const page = targets.find((t) => t.url.startsWith('http'));
if (page) {
  const info = await evaluate(page, `(() => ({
    title: document.title,
    href: location.href,
    ready: document.readyState,
    links: document.querySelectorAll('link').length,
    scripts: document.querySelectorAll('script').length,
    bodyLength: (document.body && document.body.innerText || '').length,
  }))()`);
  console.log('page                 :', JSON.stringify(info));
} else {
  console.log('page                 : NO HTTP TARGET FOUND');
}

// What did Paani count?
const paani = targets.find((t) => (t.url || '').startsWith('chrome://paani/'));
if (paani) {
  console.log('paani counter        :', await evaluate(paani,
    `(() => { const roots=[document]; const work=[document];
       while (work.length) { for (const el of work.pop().querySelectorAll('*')) {
         if (el.shadowRoot) { roots.push(el.shadowRoot); work.push(el.shadowRoot); } } }
       for (const root of roots) { const c = root.querySelector('.counter');
         if (c) return c.textContent.trim();
         const e = root.querySelector('.engine-status');
         if (e) return 'engine: ' + e.textContent.trim(); }
       return 'NOT FOUND'; })()`));
} else {
  console.log('paani counter        : NO PAANI TAB');
}

// What did uBlock count? Its dashboard shows the number.
const ublock = targets.find((t) => (t.url || '').startsWith('chrome-extension://'));
if (ublock) {
  console.log('ublock target        :', ublock.url);
}
