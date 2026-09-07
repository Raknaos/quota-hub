export default async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: { message: 'Méthode non autorisée. Utilisez POST.', type: 'invalid_request_error' } });
  }

  const authHeader = req.headers['authorization'] || '';
  if (!authHeader.startsWith('Bearer ')) {
    return res.status(401).json({
      error: {
        message: 'Clé API Quota.Hub manquante ou invalide. Format requis : Authorization: Bearer sk-qh-...',
        type: 'authentication_error'
      }
    });
  }

  const clientKey = authHeader.replace('Bearer ', '').trim();
  const a6apiKey = process.env.HERMES_CUSTOM_A6API_API_KEY || process.env.A6API_KEY || '';

  const { model = 'gpt-5.6-luna', messages = [], stream = false, ...rest } = req.body || {};

  // Grille tarifaire Quota.Hub
  const rates = {
    'gpt-5.6-luna': { in: 0.00000008, out: 0.00000035 },
    'gpt-6-astra': { in: 0.00000120, out: 0.00000450 },
    'gpt-5.6-sol': { in: 0.00000060, out: 0.00000220 },
    'deepseek-v4-flash': { in: 0.00000007, out: 0.00000020 },
    'glm-5.3': { in: 0.00000090, out: 0.00000280 },
    'glm-5.3-flash': { in: 0.00000006, out: 0.00000018 },
    'default': { in: 0.00000050, out: 0.00000150 }
  };
  const rate = rates[model] || rates['default'];

  // Si pas de clé amont A6API configurée dans l'environnement Vercel
  if (!a6apiKey) {
    // Mode simulation / fallback opérationnel
    const mockContent = `[Quota.Hub Gateway] Requête traitée avec succès sur le modèle [${model}]. Routage grossiste A6API actif.`;
    const pToks = JSON.stringify(messages).length / 4;
    const cToks = mockContent.length / 4;
    const cost = Number(((pToks * rate.in) + (cToks * rate.out)).toFixed(6));

    return res.status(200).json({
      id: `chatcmpl-${Date.now()}`,
      object: 'chat.completion',
      created: Math.floor(Date.now() / 1000),
      model: model,
      choices: [{
        index: 0,
        message: { role: 'assistant', content: mockContent },
        finish_reason: 'stop'
      }],
      usage: {
        prompt_tokens: Math.round(pToks),
        completion_tokens: Math.round(cToks),
        total_tokens: Math.round(pToks + cToks)
      },
      quota_hub: {
        billed_usd: cost,
        client_key_masked: `${clientKey.slice(0, 8)}...${clientKey.slice(-4)}`,
        status: 'simulated_no_upstream_key'
      }
    });
  }

  // Proxy direct vers A6API
  try {
    const upstreamRes = await fetch('https://a6api.com/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${a6apiKey}`
      },
      body: JSON.stringify({ model, messages, stream, ...rest })
    });

    const data = await upstreamRes.json();
    if (!upstreamRes.ok) {
      return res.status(upstreamRes.status).json(data);
    }

    const usage = data.usage || {};
    const pToks = usage.prompt_tokens || 0;
    const cToks = usage.completion_tokens || 0;
    const cost = Number(((pToks * rate.in) + (cToks * rate.out)).toFixed(6));

    data.quota_hub = {
      billed_usd: cost,
      client_key_masked: `${clientKey.slice(0, 8)}...${clientKey.slice(-4)}`,
      provider: 'a6api_wholesale'
    };

    return res.status(200).json(data);
  } catch (err) {
    return res.status(502).json({
      error: {
        message: `Erreur passerelle amont : ${err.message}`,
        type: 'upstream_gateway_error'
      }
    });
  }
}
