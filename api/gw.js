/**
 * Quota.Hub — Proxy Vercel → Passerelle VPS (signature HMAC).
 * Le secret QH_INTERNAL_SECRET vit UNIQUEMENT côté serveur Vercel.
 * Le navigateur ne connaît aucun secret : il appelle /gw/* et /v1/* sur son
 * propre domaine ; cette fonction signe (X-QH-TS, X-QH-SIG) puis relaie vers
 * la passerelle. Signature = HMAC-SHA256(SECRET, ts|path|sha256(body)|auth),
 * fenêtre 300 s côté gateway → pas de rejeu, le secret ne circule jamais.
 *
 * Routage : vercel.json rewrite /gw/:path* et /v1/:path* → /api/gw?path=:path*
 * (le catch-all [[...path]] multi-segments ne matche pas de façon fiable ici).
 */
import crypto from 'node:crypto';

const GW_BASE = process.env.QH_GATEWAY_URL || '';
const SECRET = process.env.QH_INTERNAL_SECRET || '';
const FORWARD = ['content-type', 'authorization', 'x-qh-session'];

export default async function handler(req, res) {
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('Referrer-Policy', 'no-referrer');

  if (!GW_BASE || !SECRET) {
    return res.status(503).json({
      error: { message: 'passerelle non configurée (QH_GATEWAY_URL / QH_INTERNAL_SECRET absents)', type: 'configuration_error' }
    });
  }

  const qp = new URL(req.url, 'http://x').searchParams;
  let path = '/' + (qp.get('path') || 'health');

  if (path.startsWith('/admin')) {
    return res.status(404).json({ error: { message: 'not found' } });
  }

  const headers = {};
  for (const h of FORWARD) {
    const v = req.headers[h];
    if (v) headers[h] = Array.isArray(v) ? v[0] : v;
  }

  let body;
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    const chunks = [];
    let size = 0;
    for await (const c of req) {
      size += c.length;
      if (size > 3_200_000) {
        return res.status(413).json({ error: { message: 'payload trop volumineux' } });
      }
      chunks.push(c);
    }
    body = Buffer.concat(chunks);
  }

  const ts = String(Math.floor(Date.now() / 1000));
  headers['x-qh-ts'] = ts;
  headers['x-qh-sig'] = crypto
    .createHmac('sha256', SECRET)
    .update(`${ts}|${path}|${crypto.createHash('sha256').update(body || '').digest('hex')}|${headers['authorization'] || ''}`)
    .digest('hex');

  const url = GW_BASE.replace(/\/$/, '') + path;
  try {
    const upstream = await fetch(url, {
      method: req.method,
      headers,
      body: body && body.length ? body : undefined,
      signal: AbortSignal.timeout(path.startsWith('/v1/') ? 120_000 : 30_000)
    });

    res.status(upstream.status);
    const ct = upstream.headers.get('content-type') || 'application/json';
    res.setHeader('Content-Type', ct);
    res.setHeader('Cache-Control', 'no-store');

    if (path.startsWith('/v1/')) {
      res.setHeader('Access-Control-Allow-Origin', '*');
      const reader = upstream.body.getReader();
      const pump = async () => {
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          if (!res.write(value)) await new Promise(r => res.once('drain', r));
        }
        res.end();
      };
      pump().catch(() => { try { res.end(); } catch (e) { /* socket morte */ } });
      return;
    }

    const buf = Buffer.from(await upstream.arrayBuffer());
    res.send(buf);
  } catch (e) {
    const code = e && e.name === 'TimeoutError' ? 504 : 502;
    res.status(code).json({ error: { message: `passerelle injoignable (${e && e.name})`, type: 'gateway_error' } });
  }
}
