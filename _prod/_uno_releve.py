#!/usr/bin/env python3
# Releve AUTORITAIRE des prix UnoRouter : le JSON-LD des fiches modele
# ("price": X, "description":"USD per 1M input tokens, pay as you go").
# Une passe precedente par web_extract avait melange des blocs -> verif stricte.
import json, re, sys, time, urllib.request, urllib.error

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36')

MODELS = {
    'glm-5.3-flash':      'zhipu/glm-5.3-flash',
    'glm-5.3':            'zhipu/glm-5.3',
    'grok-4.6':           'xai/grok-4.6',
    'gemini-3.8-flash':   'google/gemini-3.8-flash',
    'gemini-3.7-flash':   'google/gemini-3.7-flash',
    'deepseek-v4.1-flash': 'deepseek/deepseek-v4.1-flash',
    'deepseek-v4-pro':    'deepseek/deepseek-v4-pro',
    'claude-fable-5.1':   'anthropic/claude-fable-5.1',
    'claude-fable-5':     'anthropic/claude-fable-5',
    'claude-opus-5':      'anthropic/claude-opus-5',
    'claude-sonnet-5':    'anthropic/claude-sonnet-5',
    'gpt-6-astra':        'openai/gpt-6-astra',
    'gpt-5.6-sol':        'openai/gpt-5.6-sol',
    'gpt-5.6-terra':      'openai/gpt-5.6-terra',
    'gpt-5.6-luna':       'openai/gpt-5.6-luna',
    'qwen3.8-max':        'alibaba/qwen3.8-max',
    'hy4-preview':        'tencent/hy4-preview',
    'kimi-k3':            'moonshot/kimi-k3',
}

def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': UA,
                                               'Accept-Language': 'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode('utf-8', 'replace')

out = {}
for mid, slug in MODELS.items():
    url = 'https://unorouter.com/fr/modeles/' + slug
    try:
        html = fetch(url)
    except urllib.error.HTTPError as e:
        print('%-22s HTTP %s' % (mid, e.code)); out[mid] = None; continue
    except Exception as e:
        print('%-22s %s' % (mid, type(e).__name__)); out[mid] = None; continue
    # JSON-LD : chaque Offer porte un price + description input/output
    offers = re.findall(r'\{"@type":"Offer","price":([0-9.]+),"priceCurrency":"USD",'
                        r'"description":"([^"]+)"', html)
    pin = pout = None
    for price, desc in offers:
        d = desc.lower()
        if 'output' in d:
            pout = float(price)
        elif 'input' in d:
            pin = float(price)
        elif 'pay as you go' in d and pout is None:
            pin = float(price)
    out[mid] = (pin, pout)
    print('%-22s in=%-10s out=%-10s' % (mid, pin, pout))
    time.sleep(0.4)

json.dump(out, open('uno_prices.json', 'w'), indent=1)
print('\nsauvegarde -> uno_prices.json')
