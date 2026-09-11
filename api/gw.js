/**
 * Quota.Hub — Proxy Vercel → Passerelle VPS (TLS + pin + HMAC).
 * - TLS vers la passerelle (QH_GATEWAY_URL=https://…), certificat auto-signé
 *   ÉPINGLÉ (QH_TLS_PIN = fingerprint sha256, format "AA:BB:…" ou base64) :
 *   un MITM réseau ne peut pas intercepter la jambe Vercel→VPS.
 * - Signature HMAC par requête (secret serveur uniquement, rejeu impossible).
 * - /v1/* : flux binaire relaisé natif (SSE compatible SDK OpenAI).
 */
import crypto from 'node:crypto';
import https from 'node:https';
import { URL } from 'node:url';

const GW_BASE = process.env.QH_GATEWAY_URL || '';
// Répliques de la passerelle (failover) : « url1,url2,url3 ». Le primaire reste
// QH_GATEWAY_URL ; on n'essaie les suivantes que si le nœud est INJOIGNABLE.
const GW_NODES = (process.env.QH_GATEWAY_NODES || '')
  .split(',').map(s => s.trim().replace(/\/$/, '')).filter(Boolean);
const SECRET = process.env.QH_INTERNAL_SECRET || '';
const TLS_PIN = (process.env.QH_TLS_PIN || '').trim();
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
  // anti-traversée : collapsing ../ et double-slash, normalisation AVANT tout check
  path = '/' + path.replace(/\/{2,}/g, '/').split('/').filter(s => s && s !== '.' && s !== '..').join('/');
  if (path.startsWith('/admin')) {
    return res.status(404).json({ error: { message: 'not found' } });
  }
  if (!/^\/[a-z0-9/.-]*$/i.test(path)) {
    return res.status(400).json({ error: { message: 'chemin invalide' } });
  }
  // query restante (OAuth : code, state...) forwardée telle quelle à la passerelle
  const qsExtra = [];
  qp.forEach((v, k) => { if (k !== 'path') qsExtra.push(`${k}=${encodeURIComponent(v)}`); });

  const headers = {};
  for (const h of FORWARD) {
    const v = req.headers[h];
    if (v) headers[h] = Array.isArray(v) ? v[0] : v;
  }

  let body = null;
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
  if (body && body.length) {
    headers['content-length'] = String(body.length); // sinon Node part en chunked et la passerelle lit un body vide → 403
  }
  headers['x-qh-sig'] = crypto
    .createHmac('sha256', SECRET)
    .update(`${ts}|${path}|${crypto.createHash('sha256').update(body || '').digest('hex')}|${headers['authorization'] || ''}`)
    .digest('hex');

  // Failover : primaire + répliques (dédupliquées). Un nœud n'est abandonné que
  // s'il est réellement injoignable (connexion refusée / pin TLS / DNS) — jamais
  // après un début de réponse (aucune double requête chat possible).
  const NODES = [GW_BASE.replace(/\/$/, ''), ...GW_NODES].filter((v, i, a) => v && a.indexOf(v) === i);

  let lastErr = null;
  for (const base of NODES) {
    if (res.headersSent) break;
    const target = new URL(base + path);
    if (qsExtra.length) target.search = '?' + qsExtra.join('&');
    const isHttps = target.protocol === 'https:';
    const lib = isHttps ? https : await import('node:http');

    const options = {
      hostname: target.hostname,
      port: target.port || (isHttps ? 443 : 80),
      path: target.pathname + (target.search || ''),
      method: req.method,
      headers,
      timeout: path.startsWith('/v1/') ? 120_000 : 30_000
    };
    if (isHttps && TLS_PIN) {
      options.rejectUnauthorized = false; // auto-signé : l'identité est LE PIN, pas une CA
      options.checkServerIdentity = (host, cert) => {
        const fp = cert.fingerprint256 || '';
        const b64 = Buffer.from(fp.replace(/:/g, ''), 'hex').toString('base64');
        if (fp === TLS_PIN || b64 === TLS_PIN) return undefined;
        return new Error('certificat passerelle non reconnu (pin TLS)');
      };
    }

    try {
      await new Promise((resolve, reject) => {
        const up = lib.request(options, urs => {
          res.status(urs.statusCode);
          const ct = urs.headers['content-type'] || 'application/json';
          res.setHeader('Content-Type', ct);
          res.setHeader('Cache-Control', 'no-store');
          if (path.startsWith('/v1/')) {
            res.setHeader('Access-Control-Allow-Origin', '*');
            urs.pipe(res); // flux natif (SSE/JSON), back-pressure géré par Node
            urs.on('end', resolve);
            urs.on('error', reject);
          } else {
            const bufs = [];
            urs.on('data', c => bufs.push(c));
            urs.on('end', () => { res.send(Buffer.concat(bufs)); resolve(); });
            urs.on('error', reject);
          }
          // redirections OAuth (Location) et cookies : indispensables au flow social
          const loc = urs.headers['location'];
          if (loc) res.setHeader('Location', loc);
          const sc = urs.headers['set-cookie'];
          if (sc) res.setHeader('Set-Cookie', Array.isArray(sc) ? sc : [sc]);
        });
        up.on('timeout', () => { up.destroy(new Error('timeout passerelle')); });
        up.on('error', reject);
        if (body && body.length) up.write(body);
        up.end();
      });
      return; // nœud sain : réponse servie, on s'arrête là
    } catch (e) {
      lastErr = e;
      const msg = String((e && e.message) || e);
      // Bascule uniquement si le nœud n'a PAS pu commencer à traiter :
      // connexion refusée/joignable, DNS, pin TLS — pas un timeout de réponse.
      const retryable = /ECONNREFUSED|EHOSTUNREACH|ENETUNREACH|EAI_AGAIN|ENOTFOUND|pin TLS|socket hang up|ECONNRESET|EPIPE/i.test(msg);
      if (!retryable || res.headersSent) break;
    }
  }
  if (!res.headersSent) {
    const msg = String((lastErr && lastErr.message) || lastErr || 'injoignable');
    const code = /timeout/i.test(msg) ? 504 : 502;
    res.status(code).json({ error: { message: `passerelle injoignable (${msg})`, type: 'gateway_error' } });
  } else {
    try { res.end(); } catch (e2) { /* socket morte */ }
  }
}
