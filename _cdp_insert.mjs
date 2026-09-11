// Focus + saisie texte réelle via CDP (Runtime + Input.insertText) sur un onglet Comet.
// Usage: node _cdp_insert.mjs <tabPrefix> <selectorJS> <text>
"use strict";
const PORT = '9223';
const [tabPrefix, selector, text] = process.argv.slice(2);
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
// focus via évaluation
await send('Runtime.evaluate', { expression: `(()=>{const el=${selector}; if(!el)return 'NO_EL'; el.focus(); el.click(); return el.tagName+':'+el.getAttribute('aria-label');})()`, returnByValue: true });
await new Promise(r => setTimeout(r, 600));
await send('Input.insertText', { text });
await new Promise(r => setTimeout(r, 800));
const { result } = await send('Runtime.evaluate', { expression: `(()=>{const el=${selector}; return el?('val='+el.value):'NO_EL';})()`, returnByValue: true });
console.log(result.value || 'no value');
process.exit(0);