// Checks the WebUI expressions the verification harness uses, against a
// browser that is already running, so a broken selector is found here
// instead of half way through a verification run.
//
//   node check_webui_exprs.mjs --port 9351

const args = {};
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  if (argv[i].startsWith('--')) {
    args[argv[i].slice(2)] = argv[i + 1];
    i++;
  }
}
const port = args.port || '9222';

const Scan =
  "const all = []; const scan = (root) => {" +
  " for (const x of root.querySelectorAll('button')) all.push(x);" +
  " for (const x of root.querySelectorAll('input')) all.push(x);" +
  " for (const el of root.querySelectorAll('*')) { if (el.shadowRoot) scan(el.shadowRoot); } };" +
  " scan(document);";

const expressions = {
  counter: "(() => { const roots = [document]; const work = [document]; while (work.length) { for (const el of work.pop().querySelectorAll('*')) { if (el.shadowRoot) { roots.push(el.shadowRoot); work.push(el.shadowRoot); } } } for (const root of roots) { const t = root.querySelector('.counter'); if (t) return t.textContent.trim(); } return 'NO COUNTER'; })()",
  engine: "(() => { const roots = [document]; const work = [document]; while (work.length) { for (const el of work.pop().querySelectorAll('*')) { if (el.shadowRoot) { roots.push(el.shadowRoot); work.push(el.shadowRoot); } } } for (const root of roots) { const t = root.querySelector('.engine-status'); if (t) return t.textContent.trim(); } return 'NO ENGINE STATUS'; })()",
  toggle_state: "(() => { " + Scan + " const t = all.find(x => x.classList && x.classList.contains('toggle')); return t ? t.getAttribute('aria-checked') : 'NO TOGGLE'; })()",
  buttons: "(() => { " + Scan + " return all.filter(x => x.tagName === 'BUTTON').map(x => x.textContent.trim()).join('|'); })()",
  inputs: "(() => { " + Scan + " return all.filter(x => x.tagName === 'INPUT').length; })()",
};

const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = list.find((t) => (t.url || '').startsWith('chrome://paani/'));
if (!target) {
  console.error('NO chrome://paani/ target. Open pages:');
  for (const t of list) console.error('  ' + t.type + ' ' + t.url);
  process.exit(2);
}

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve);
  ws.addEventListener('error', (e) => reject(new Error('websocket failed: ' + e.message)));
});

let id = 0;
const call = (method, params) =>
  new Promise((resolve, reject) => {
    const myId = ++id;
    const onMessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.id !== myId) return;
      ws.removeEventListener('message', onMessage);
      if (message.error) reject(new Error(JSON.stringify(message.error)));
      else resolve(message.result);
    };
    ws.addEventListener('message', onMessage);
    ws.send(JSON.stringify({ id: myId, method, params }));
    setTimeout(() => reject(new Error(`${method} timed out`)), 20000);
  });

for (const [name, expression] of Object.entries(expressions)) {
  const result = await call('Runtime.evaluate', { expression, returnByValue: true });
  if (result.exceptionDetails) {
    console.log(name.padEnd(14), 'FAILED', JSON.stringify(result.exceptionDetails).slice(0, 200));
  } else {
    console.log(name.padEnd(14), JSON.stringify(result.result.value));
  }
}
ws.close();
