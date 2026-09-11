// Clic souris réel via CDP (Input.dispatchMouseEvent) sur un onglet Comet.
// Usage: node _cdp_click.mjs <tabPrefix> <x> <y>
"use strict";
const PORT = '9223';
const [tabPrefix, x, y] = process.argv.slice(2);
const tabs = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
const page = tabs.find(t => t.type === 'page' && t.id.startsWith(tabPrefix));
if (!page) { console.error('TAB NOT FOUND'); process.exit(1); }
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((ok, ko) => { ws.onopen = ok; ws.onerror = ko; });
let id = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
};
const send = (method, params = {}) => new Promise(res => {
  const mid = ++id; pending.set(mid, res);
  ws.send(JSON.stringify({ id: mid, method, params }));
});
await send('Runtime.enable'); await send('Page.enable');
await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: +x, y: +y, button: 'left', clickCount: 1 });
await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: +x, y: +y, button: 'left', clickCount: 1 });
await new Promise(r => setTimeout(r, 2500));
const { result } = await send('Runtime.evaluate', { expression: 'document.title', returnByValue: true });
console.log(result.value);
process.exit(0);