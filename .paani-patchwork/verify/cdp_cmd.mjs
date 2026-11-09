// Drives one CDP command against a target picked by URL prefix.
//
//   node cdp_cmd.mjs --port 9222 --match chrome:// --method Page.navigate --params '{"url":"chrome://paani/"}'
//
// The reader evaluates expressions; this one calls a browser method, which is
// what a chrome:// URL needs: a page that navigates itself to a WebUI is
// refused, while the browser's own navigation call is not.

const args = {};
const argv = process.argv.slice(2);
for (let i = 0; i < argv.length; i++) {
  if (argv[i].startsWith('--')) {
    args[argv[i].slice(2)] = argv[i + 1];
    i++;
  }
}
const port = args.port || '9222';
const match = args.match || 'chrome://';
// A prefix is enough most of the time, but a run also has to find a tab that
// only shows up as chrome://newtab/, so a regex can be asked for instead.
const isRegex = args.regex === 'true';
const method = args.method || 'Page.navigate';
// PowerShell mangles a JSON blob on the native command line, so the URL is
// passed on its own and the parameters are built here instead.
const params = args.url ? { url: args.url }
  : args.params ? JSON.parse(args.params)
  : {};

const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
const target = list.find((t) => (t.url || '').startsWith(match))
  || (isRegex ? list.find((t) => new RegExp(match).test(t.url || '')) : undefined);
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

const result = await send(1, method, params);
console.log(JSON.stringify(result));
ws.close();
