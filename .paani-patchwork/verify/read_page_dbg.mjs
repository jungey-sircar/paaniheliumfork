// Reads a value out of an open Paani tab over the DevTools protocol.
//
// The alternative was scraping pixels off a screenshot, which cannot tell
// "0 blocked" from "counter not wired up". This asks the page itself.
//
//   node read_page.mjs --port 9222 --match chrome://paani --expr "..."
//
// Launch the browser with --remote-debugging-port=9222 for it to answer.

const args = {};
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  if (argv[i].startsWith('--')) {
    args[argv[i].slice(2)] = argv[i + 1];
    i++;
  }
}
console.error("ARGV:", JSON.stringify(process.argv.slice(2))); const port = args.port || '9222';
const match = args.match || 'chrome://paani';
const expr = args.expr || 'document.body.innerText';

const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = list.find((t) => (t.url || '').startsWith(match));
if (!target) {
  console.error(`NO TARGET matching ${match}. Open pages:`);
  for (const t of list) console.error('  ' + t.type + ' ' + t.url);
  process.exit(2);
}

const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve);
  ws.addEventListener('error', (e) => reject(new Error('websocket failed: ' + e.message)));
});

const send = (id, method, params) =>
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

// The WebUI is a lit page, so its elements live inside a shadow root rather
// than in `document`. `__q` searches every shadow root it can find and returns
// the first match's text, which is what a counter or a status line is.
const wrapped = `(() => {
  const roots = [document];
  const work = [document];
  while (work.length) {
    for (const el of work.pop().querySelectorAll('*')) {
      if (el.shadowRoot) {
        roots.push(el.shadowRoot);
        work.push(el.shadowRoot);
      }
    }
  }
  window.__el = (selector) => {
    for (const root of roots) {
      const found = root.querySelector(selector);
      if (found) return found;
    }
    return null;
  };
  window.__q = (selector) => {
    const found = window.__el(selector);
    return found ? found.textContent.trim() : null;
  };
  const probe = (${expr});
  return typeof probe === 'string' ? probe : JSON.stringify(probe);
})()`;

const result = await send(1, 'Runtime.evaluate', {
  expression: wrapped,
  returnByValue: true,
});

if (result.exceptionDetails) {
  console.error('EVALUATE FAILED: ' + JSON.stringify(result.exceptionDetails));
  process.exit(3);
}
console.log(result.result.value);
ws.close();
