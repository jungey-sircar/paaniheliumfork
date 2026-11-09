// Clicks the WebUI toggle and the buttons the verification harness uses, so a
// broken click is found here instead of half way through a verification run.
//
//   node check_webui_clicks.mjs --port 9351

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
  toggle_state: "(() => { " + Scan + " const t = all.find(x => x.classList && x.classList.contains('toggle')); return t ? t.getAttribute('aria-checked') : 'NO TOGGLE'; })()",
  toggle_click: "(() => { " + Scan + " const t = all.find(x => x.classList && x.classList.contains('toggle')); if (!t) return 'NO TOGGLE'; t.click(); return 'TOGGLE CLICKED'; })()",
  reset_click: "(() => { " + Scan + " const hit = all.find(x => x.textContent.trim() === 'Reset counter'); if (!hit) return 'NO RESET BUTTON'; hit.click(); return 'RESET CLICKED'; })()",
  add_site: "(() => { " + Scan + " const i = all.find(x => x.tagName === 'INPUT'); if (!i) return 'NO INPUT'; i.value = 'probe.example'; i.dispatchEvent(new Event('input', {bubbles: true})); const add = all.find(x => x.textContent.trim() === 'Add'); if (!add) return 'NO ADD BUTTON'; add.click(); return 'ADD CLICKED'; })()",
  list_sites: "(() => { " + Scan + " const spans = []; const scan2 = (root) => { for (const x of root.querySelectorAll('span')) spans.push(x); for (const el of root.querySelectorAll('*')) if (el.shadowRoot) scan2(el.shadowRoot); }; scan2(document); return spans.map(x => x.textContent.trim()).join(','); })()",
};

const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = list.find((t) => (t.url || '').startsWith('chrome://paani/'));
if (!target) {
  console.error('NO chrome://paani/ target.');
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

const evaluate = async (expression) => {
  const result = await call('Runtime.evaluate', { expression, returnByValue: true });
  if (result.exceptionDetails) return 'FAILED ' + JSON.stringify(result.exceptionDetails).slice(0, 160);
  return result.result.value;
};

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

console.log('toggle before   ', await evaluate(expressions.toggle_state));
console.log('toggle click    ', await evaluate(expressions.toggle_click));
await sleep(1500);
console.log('toggle after off', await evaluate(expressions.toggle_state));
console.log('toggle click    ', await evaluate(expressions.toggle_click));
await sleep(1500);
console.log('toggle after on ', await evaluate(expressions.toggle_state));
console.log('reset           ', await evaluate(expressions.reset_click));
console.log('add site        ', await evaluate(expressions.add_site));
await sleep(1500);
console.log('sites           ', await evaluate(expressions.list_sites));
ws.close();
