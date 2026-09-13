/* Smart API Cheap — Interface haute fidélité Unorouter x Smart API Cheap */
const API = '/gw';
const APP_STATE = {
  session: sessionStorage.getItem('qh_session') || '',
  me: null,
  keys: [],
  currentTab: 'models',
  selectedRecharge: 10,
  chatModel: 'auto',
  chatHistory: []
};

const $ = id => document.getElementById(id);
const fmtBalanceUSD = tokens => '$' + Math.max(0, (tokens || 0) / 1e9 * 10).toFixed(2);

/* Modele PUBLIC unique : le routeur sonde tous les modeles du pool, elit le
   moins cher vivant (cache reel compris) et le sert sous ce nom de marque.
   Le client ne voit jamais l'identite reelle du modele ni du canal amont. */
const PUBLIC_MODEL = { id: 'autosmart-flash-1.0', name: 'AutoSmart Flash 1.0' };

function escapeHtml(value) {
  return String(value || '').replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[c]));
}

/* === DONNÉES OFFICIELLES DES 20 MODÈLES SÉLECTIONNÉS === */
const MODELS_DATA = [
  {
    id: "qwen3.8-flash",
    name: "Qwen3.8 Flash",
    provider: "alibaba",
    provider_name: "Alibaba",
    logo: "assets/logos/qwen.svg",
    cat: "value",
    modalities: ["text", "tools", "vision"],
    tokens_weekly: "1.45B",
    tokens_num: 1450000000,
    input_official: "$0.16",
    input_ours: "$0.0024",
    output_official: "$0.47",
    output_ours: "$0.0070",
    discount: "−99%",
    discount_num: 99,
    context: "1.0M",
    availability: "100.0%",
    success: "99.8%",
    latency: "2.20s",
    badge: "Champion Cache",
    desc: "Ultra-rapide, prompt cache mémorisé à 80%+, idéal pour agents et code."
  },
  {
    id: "glm-5.3-flash",
    name: "GLM-5.3 Flash",
    provider: "zhipu",
    provider_name: "Zhipu (Z.ai)",
    logo: "assets/logos/zhipu.svg",
    cat: "value",
    modalities: ["text", "tools"],
    tokens_weekly: "2.76B",
    tokens_num: 2760000000,
    input_official: "$0.07",
    input_ours: "$0.02",
    output_official: "$0.25",
    output_ours: "$0.08",
    discount: "−68%",
    discount_num: 68,
    context: "1.0M",
    availability: "100.0%",
    success: "99.4%",
    latency: "2.85s",
    badge: "Populaire",
    desc: "Rapide, excellent en français, outillage et synthèses, cache 93.5%."
  },
  {
    id: "glm-5.3",
    name: "GLM-5.3",
    provider: "zhipu",
    provider_name: "Zhipu (Z.ai)",
    logo: "assets/logos/zhipu.svg",
    cat: "frontier",
    modalities: ["text", "tools"],
    tokens_weekly: "11.8B",
    tokens_num: 11800000000,
    input_official: "$1.40",
    input_ours: "$0.03",
    output_official: "$4.40",
    output_ours: "$0.09",
    discount: "−98%",
    discount_num: 98,
    context: "1.0M",
    availability: "99.9%",
    success: "99.1%",
    latency: "5.40s",
    badge: "Top Raisonnement",
    desc: "Le modèle frontière Zhipu pour raisonnement complexe à tarif quasi nul."
  },
  {
    id: "grok-4.6",
    name: "Grok 4.6",
    provider: "xai",
    provider_name: "xAI",
    logo: "assets/logos/xai.svg",
    cat: "frontier",
    modalities: ["text", "tools"],
    tokens_weekly: "93.1M",
    tokens_num: 93100000,
    input_official: "$2.00",
    input_ours: "$0.05",
    output_official: "$6.00",
    output_ours: "$0.15",
    discount: "−98%",
    discount_num: 98,
    context: "500K",
    availability: "99.7%",
    success: "98.5%",
    latency: "9.18s",
    badge: "xAI Raisonnement",
    desc: "Modèle de pointe xAI, programmation avancée et ton direct."
  },
  {
    id: "gemini-3.8-flash",
    name: "Gemini 3.8 Flash",
    provider: "google",
    provider_name: "Google",
    logo: "assets/logos/googlegemini.svg",
    cat: "value",
    modalities: ["text", "vision", "audio", "tools"],
    tokens_weekly: "3.52B",
    tokens_num: 3520000000,
    input_official: "$0.75",
    input_ours: "$0.08",
    output_official: "$3.75",
    output_ours: "$0.39",
    discount: "−90%",
    discount_num: 90,
    context: "1.0M",
    availability: "100.0%",
    success: "99.9%",
    latency: "2.40s",
    badge: "Multimodal",
    desc: "Multimodal complet Google : analyse texte, images, audio et outils."
  },
  {
    id: "gemini-3.7-flash",
    name: "Gemini 3.7 Flash",
    provider: "google",
    provider_name: "Google",
    logo: "assets/logos/googlegemini.svg",
    cat: "value",
    modalities: ["text", "vision", "tools"],
    tokens_weekly: "322.7M",
    tokens_num: 322700000,
    input_official: "$0.75",
    input_ours: "$0.09",
    output_official: "$3.75",
    output_ours: "$0.47",
    discount: "−88%",
    discount_num: 88,
    context: "1.0M",
    availability: "100.0%",
    success: "99.7%",
    latency: "2.60s",
    badge: "Équilibré",
    desc: "Grande fenêtre de 1M et vitesse constante pour tout pipeline."
  },
  {
    id: "deepseek-v4.1-flash",
    name: "DeepSeek V4.1 Flash",
    provider: "deepseek",
    provider_name: "DeepSeek",
    logo: "assets/logos/deepseek.svg",
    cat: "value",
    modalities: ["text", "tools"],
    tokens_weekly: "266.3M",
    tokens_num: 266300000,
    input_official: "$0.18",
    input_ours: "$0.18",
    output_official: "$0.54",
    output_ours: "$0.54",
    discount: "Tarif brut",
    discount_num: 0,
    context: "1.0M",
    availability: "100.0%",
    success: "98.8%",
    latency: "3.58s",
    badge: "Rapide",
    desc: "Architecture V4.1 légère, rapide et économique pour questions directes."
  },
  {
    id: "deepseek-v4-pro",
    name: "DeepSeek V4 Pro",
    provider: "deepseek",
    provider_name: "DeepSeek",
    logo: "assets/logos/deepseek.svg",
    cat: "frontier",
    modalities: ["text", "tools"],
    tokens_weekly: "797.7M",
    tokens_num: 797700000,
    input_official: "$1.32",
    input_ours: "$0.04",
    output_official: "$3.96",
    output_ours: "$0.11",
    discount: "−97%",
    discount_num: 97,
    context: "1.0M",
    availability: "99.8%",
    success: "98.9%",
    latency: "6.22s",
    badge: "Code Expert",
    desc: "Puissance brute de raisonnement DeepSeek avec 97% de remise immédiate."
  },
  {
    id: "claude-fable-5.1",
    name: "Claude Fable 5.1",
    provider: "anthropic",
    provider_name: "Anthropic",
    logo: "assets/logos/anthropic.svg",
    cat: "frontier",
    modalities: ["text", "tools"],
    tokens_weekly: "407.4M",
    tokens_num: 407400000,
    input_official: "$10.00",
    input_ours: "$1.69",
    output_official: "$50.00",
    output_ours: "$8.45",
    discount: "−83%",
    discount_num: 83,
    context: "1.0M",
    availability: "99.9%",
    success: "99.2%",
    latency: "4.80s",
    badge: "Top Créatif",
    desc: "Nuance littéraire et code précis d'Anthropic avec 83% d'économie."
  },
  {
    id: "claude-fable-5",
    name: "Claude Fable 5",
    provider: "anthropic",
    provider_name: "Anthropic",
    logo: "assets/logos/anthropic.svg",
    cat: "frontier",
    modalities: ["text", "tools"],
    tokens_weekly: "380.0M",
    tokens_num: 380000000,
    input_official: "$10.00",
    input_ours: "$1.32",
    output_official: "$50.00",
    output_ours: "$6.60",
    discount: "−87%",
    discount_num: 87,
    context: "1.0M",
    availability: "100.0%",
    success: "99.5%",
    latency: "4.50s",
    badge: "Anthropic",
    desc: "Version éprouvée pour agents d'écriture, synthèses et édition."
  },
  {
    id: "claude-opus-5",
    name: "Claude Opus 5",
    provider: "anthropic",
    provider_name: "Anthropic",
    logo: "assets/logos/anthropic.svg",
    cat: "frontier",
    modalities: ["text", "vision", "tools"],
    tokens_weekly: "150.0M",
    tokens_num: 150000000,
    input_official: "$5.00",
    input_ours: "$1.88",
    output_official: "$25.00",
    output_ours: "$9.38",
    discount: "−63%",
    discount_num: 63,
    context: "1.0M",
    availability: "99.6%",
    success: "98.7%",
    latency: "8.10s",
    badge: "Raisonnement Lourd",
    desc: "Analyse approfondie, recherche mathématique et déductions d'experts."
  },
  {
    id: "claude-sonnet-5",
    name: "Claude Sonnet 5",
    provider: "anthropic",
    provider_name: "Anthropic",
    logo: "assets/logos/anthropic.svg",
    cat: "frontier",
    modalities: ["text", "vision", "tools"],
    tokens_weekly: "850.0M",
    tokens_num: 850000000,
    input_official: "$2.00",
    input_ours: "$0.26",
    output_official: "$10.00",
    output_ours: "$1.32",
    discount: "−87%",
    discount_num: 87,
    context: "1.0M",
    availability: "100.0%",
    success: "99.6%",
    latency: "3.10s",
    badge: "Star du Code",
    desc: "La référence mondiale pour le dev logiciel avec Claude Code et Cursor."
  },
  {
    id: "gpt-6-astra",
    name: "GPT-6 Astra",
    provider: "openai",
    provider_name: "OpenAI",
    logo: "assets/logos/openai.svg",
    cat: "frontier",
    modalities: ["text", "tools"],
    tokens_weekly: "425.2M",
    tokens_num: 425200000,
    input_official: "$10.00",
    input_ours: "$1.50",
    output_official: "$50.00",
    output_ours: "$7.50",
    discount: "−85%",
    discount_num: 85,
    context: "1.1M",
    availability: "99.9%",
    success: "99.3%",
    latency: "5.60s",
    badge: "Flagship OpenAI",
    desc: "Le modèle d'alignement et de capacités généralistes de référence OpenAI."
  },
  {
    id: "gpt-5.6-sol",
    name: "GPT-5.6 Sol",
    provider: "openai",
    provider_name: "OpenAI",
    logo: "assets/logos/openai.svg",
    cat: "frontier",
    modalities: ["text", "tools"],
    tokens_weekly: "310.0M",
    tokens_num: 310000000,
    input_official: "$4.00",
    input_ours: "$1.00",
    output_official: "$20.00",
    output_ours: "$5.00",
    discount: "−75%",
    discount_num: 75,
    context: "1.1M",
    availability: "100.0%",
    success: "99.4%",
    latency: "4.20s",
    badge: "Raisonnement Solide",
    desc: "Raisonnement étape par étape et vérification rigoureuse de logique."
  },
  {
    id: "gpt-5.6-terra",
    name: "GPT-5.6 Terra",
    provider: "openai",
    provider_name: "OpenAI",
    logo: "assets/logos/openai.svg",
    cat: "frontier",
    modalities: ["text", "tools"],
    tokens_weekly: "180.0M",
    tokens_num: 180000000,
    input_official: "$2.00",
    input_ours: "$1.80",
    output_official: "$12.00",
    output_ours: "$10.80",
    discount: "−10%",
    discount_num: 10,
    context: "1.1M",
    availability: "100.0%",
    success: "99.8%",
    latency: "3.80s",
    badge: "Équilibré",
    desc: "Conçu pour les flux d'entreprise nécessitant une constance absolue."
  },
  {
    id: "gpt-5.6-luna",
    name: "GPT-5.6 Luna",
    provider: "openai",
    provider_name: "OpenAI",
    logo: "assets/logos/openai.svg",
    cat: "value",
    modalities: ["text", "tools"],
    tokens_weekly: "520.0M",
    tokens_num: 520000000,
    input_official: "$0.20",
    input_ours: "$0.04",
    output_official: "$1.20",
    output_ours: "$0.24",
    discount: "−80%",
    discount_num: 80,
    context: "1.1M",
    availability: "100.0%",
    success: "99.7%",
    latency: "1.90s",
    badge: "Ultra Rapide",
    desc: "Modèle compact pour parsing JSON, réécriture et classification."
  },
  {
    id: "qwen3.8-max",
    name: "Qwen3.8 Max",
    provider: "alibaba",
    provider_name: "Alibaba",
    logo: "assets/logos/qwen.svg",
    cat: "frontier",
    modalities: ["text", "tools"],
    tokens_weekly: "1.61M",
    tokens_num: 1610000,
    input_official: "$2.00",
    input_ours: "$1.85",
    output_official: "$6.00",
    output_ours: "$5.54",
    discount: "−8%",
    discount_num: 8,
    context: "1.0M",
    availability: "100.0%",
    success: "99.5%",
    latency: "5.10s",
    badge: "Alibaba Flagship",
    desc: "Le modèle d'envergure d'Alibaba Cloud pour les requêtes complexes."
  },
  {
    id: "hy4-preview",
    name: "HY4 Preview",
    provider: "tencent",
    provider_name: "Tencent",
    logo: "assets/logos/tencentqq.svg",
    cat: "value",
    modalities: ["text", "tools"],
    tokens_weekly: "396.6M",
    tokens_num: 396600000,
    input_official: "$0.83",
    input_ours: "$0.04",
    output_official: "$2.50",
    output_ours: "$0.13",
    discount: "−95%",
    discount_num: 95,
    context: "1.0M",
    availability: "99.8%",
    success: "99.1%",
    latency: "2.70s",
    badge: "Tencent",
    desc: "Architecture Hunyuan moderne, rapide et à 95% d'économie immédiate."
  },
  {
    id: "kimi-k3",
    name: "Kimi K3",
    provider: "moonshot",
    provider_name: "Moonshot",
    logo: "assets/logos/moonshotai.svg",
    cat: "frontier",
    modalities: ["text", "tools"],
    tokens_weekly: "210.0M",
    tokens_num: 210000000,
    input_official: "$3.00",
    input_ours: "$0.05",
    output_official: "$15.00",
    output_ours: "$0.27",
    discount: "−98%",
    discount_num: 98,
    context: "1.0M",
    availability: "99.7%",
    success: "98.8%",
    latency: "4.90s",
    badge: "Contexte Long",
    desc: "Recherche profonde dans les documents massifs et les archives PDF."
  },
  {
    id: "gpt-image-2.5-flare",
    name: "GPT Image 2.5 Flare",
    provider: "openai",
    provider_name: "OpenAI",
    logo: "assets/logos/openai.svg",
    cat: "image",
    modalities: ["image"],
    tokens_weekly: "87.5M",
    tokens_num: 87500000,
    input_official: "—",
    input_ours: "—",
    output_official: "$0.04/img",
    output_ours: "$0.01/img",
    discount: "−65%",
    discount_num: 65,
    context: "—",
    availability: "100.0%",
    success: "99.2%",
    latency: "4.10s",
    badge: "Génération Image",
    desc: "Génération d'images photoréalistes à 1 centime par image générée."
  }
];

/* === FILTRES DU CATALOGUE === */
const FILTER_STATE = {
  modality: 'all',
  provider: 'all',
  promoOnly: false,
  query: ''
};

function renderModelsTable() {
  const tbody = $('models-table-body');
  if (!tbody) return;

  const q = FILTER_STATE.query.toLowerCase().trim();
  const filtered = MODELS_DATA.filter(m => {
    // 1. Modality
    if (FILTER_STATE.modality !== 'all') {
      if (!m.modalities.includes(FILTER_STATE.modality)) return false;
    }
    // 2. Provider
    if (FILTER_STATE.provider !== 'all') {
      if (m.provider !== FILTER_STATE.provider) return false;
    }
    // 3. Promo only
    if (FILTER_STATE.promoOnly) {
      if (m.discount_num <= 0) return false;
    }
    // 4. Query
    if (q) {
      const haystack = (m.id + ' ' + m.name + ' ' + m.provider_name + ' ' + m.desc).toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });

  if (!filtered.length) {
    tbody.innerHTML = `<tr><td colspan="9" class="empty-table">Aucun modèle ne correspond à vos critères de recherche.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(m => {
    const hasDiscount = m.discount_num > 0;
    const isImage = m.modalities.includes('image') && m.input_ours === '—';

    return `
      <tr class="unorouter-row">
        <!-- 1. Modèle -->
        <td class="td-model">
          <div class="model-flex">
            <span class="model-avatar">
              <img src="${m.logo}" alt="${escapeHtml(m.provider_name)}" loading="lazy">
            </span>
            <div class="model-meta">
              <strong class="model-title">${escapeHtml(m.id)}</strong>
              <div class="model-tags">
                <span class="provider-tag">${escapeHtml(m.provider_name)}</span>
                ${m.modalities.includes('tools') ? '<span class="mod-tag">Outils</span>' : ''}
                ${m.modalities.includes('vision') ? '<span class="mod-tag">Vision</span>' : ''}
                ${m.modalities.includes('audio') ? '<span class="mod-tag">Audio</span>' : ''}
                ${m.modalities.includes('image') ? '<span class="mod-tag">Image</span>' : ''}
              </div>
            </div>
          </div>
        </td>

        <!-- 2. Tokens hebdo -->
        <td class="td-tokens">
          <b>${m.tokens_weekly}</b>
        </td>

        <!-- 3. Entrée -->
        <td class="td-price">
          ${isImage ? '<span class="dash">—</span>' : `
            <span class="price-val"><b>${m.input_ours}</b></span>
            ${hasDiscount ? `<del class="price-del">${m.input_official}</del>` : ''}
          `}
        </td>

        <!-- 4. Sortie -->
        <td class="td-price">
          <div class="out-price-wrap">
            <span class="price-val"><b>${m.output_ours}</b></span>
            ${hasDiscount ? `<del class="price-del">${m.output_official}</del>` : ''}
            ${hasDiscount ? `<span class="discount-badge">${m.discount}</span>` : ''}
          </div>
        </td>

        <!-- 5. Contexte -->
        <td class="td-ctx">
          <span class="ctx-pill">${m.context}</span>
        </td>

        <!-- 6. Disponibilité -->
        <td class="td-stat">${m.availability}</td>

        <!-- 7. Réussite -->
        <td class="td-stat">${m.success}</td>

        <!-- 8. Latence -->
        <td class="td-stat"><code>${m.latency}</code></td>

        <!-- 9. Action -->
        <td class="td-action">
          <div class="action-btn-group">
            <button class="btn-table-test" onclick="launchChatWithModel('${m.id}')" title="Tester dans le Chat">Tester</button>
            <button class="btn-table-copy" onclick="copyText('${m.id}', this)" title="Copier l'identifiant">Copier</button>
          </div>
        </td>
      </tr>
    `;
  }).join('');
}

window.setModalityFilter = function(mod, btn) {
  FILTER_STATE.modality = mod;
  document.querySelectorAll('#modality-pills .filter-pill').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderModelsTable();
};

window.setProviderFilter = function(prov, btn) {
  FILTER_STATE.provider = prov;
  document.querySelectorAll('#provider-strip .filter-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');
  renderModelsTable();
};

window.togglePromoOnly = function(checked) {
  FILTER_STATE.promoOnly = checked;
  renderModelsTable();
};

window.handleModelSearch = function(val) {
  FILTER_STATE.query = val;
  renderModelsTable();
};

/* === GESTION DES CLASSEMENTS === */
function renderClassements() {
  const savingsBox = $('ranking-savings-items');
  const speedBox = $('ranking-speed-items');
  if (!savingsBox || !speedBox) return;

  // Top remises
  const topSavings = [...MODELS_DATA]
    .filter(m => m.discount_num > 0)
    .sort((a, b) => b.discount_num - a.discount_num)
    .slice(0, 5);

  savingsBox.innerHTML = topSavings.map((m, idx) => `
    <div class="ranking-row">
      <span class="rank-pos">#${idx + 1}</span>
      <img class="rank-logo" src="${m.logo}" alt="">
      <div class="rank-info">
        <strong>${escapeHtml(m.id)}</strong>
        <span>${escapeHtml(m.provider_name)} · Entrée ${m.input_ours}</span>
      </div>
      <span class="rank-badge green">${m.discount} de réduction</span>
      <button class="btn-mini" onclick="launchChatWithModel('${m.id}')">Tester</button>
    </div>
  `).join('');

  // Champions latence
  const topSpeed = [...MODELS_DATA]
    .filter(m => m.latency && m.latency !== '—')
    .sort((a, b) => parseFloat(a.latency) - parseFloat(b.latency))
    .slice(0, 5);

  speedBox.innerHTML = topSpeed.map((m, idx) => `
    <div class="ranking-row">
      <span class="rank-pos">#${idx + 1}</span>
      <img class="rank-logo" src="${m.logo}" alt="">
      <div class="rank-info">
        <strong>${escapeHtml(m.id)}</strong>
        <span>${escapeHtml(m.provider_name)} · ${m.tokens_weekly} tok/sem</span>
      </div>
      <span class="rank-badge blue">⚡ ${m.latency}</span>
      <button class="btn-mini" onclick="launchChatWithModel('${m.id}')">Tester</button>
    </div>
  `).join('');
}

/* === SÉLECTEUR DE RECHARGE (TARIFS) === */
window.selectRecharge = function(amount, btn) {
  APP_STATE.selectedRecharge = amount;
  document.querySelectorAll('#recharge-buttons .amount-btn').forEach(b => b.classList.remove('active'));
  if (btn) btn.classList.add('active');

  const summaryAmt = $('summary-amount');
  const summaryTok = $('summary-tokens');
  if (summaryAmt) summaryAmt.textContent = '$' + amount.toFixed(2);

  // Calcul d'équivalence de tokens sur Qwen3.8 Flash (0.0024$/1M in, 0.0070$/1M out -> moyen ~0.0035$/1M)
  const tokB = (amount / 0.0024).toFixed(2);
  if (summaryTok) summaryTok.textContent = `~ ${(amount / 0.0024).toLocaleString('fr-FR', {maximumFractionDigits: 1})} Millions de tokens réels`;
};

/* === CHAT INTERACTIF === */
function initChatDropdown() {
  const select = $('chat-model-select');
  if (!select) return;

  // CATALOGUE PUBLIC = UN SEUL MODELE. Le routeur choisit tout seul le moins
  // cher vivant : le client n'a rien a selectionner et ne voit aucun nom reel.
  select.innerHTML =
    `<option value="${PUBLIC_MODEL.id}">${PUBLIC_MODEL.name} — routage automatique (le moins cher à l'instant)</option>`;
  select.value = PUBLIC_MODEL.id;
}

window.onChatModelChange = function() {
  APP_STATE.chatModel = PUBLIC_MODEL.id;
  const title = $('chat-active-model-title');
  const desc = $('chat-active-model-desc');
  if (title) title.textContent = PUBLIC_MODEL.name;
  if (desc) desc.textContent = 'Routage automatique : à chaque requête, le modèle vivant le moins cher — cache réel compris.';
};

window.launchChatWithModel = function() {
  // Le catalogue est vitrine : toute requete passe par le modele public unique.
  switchTab('chat');
  const select = $('chat-model-select');
  if (select) {
    select.value = PUBLIC_MODEL.id;
    onChatModelChange();
  }
  const input = $('chat-input');
  if (input) input.focus();
};

window.fillStarterPrompt = function(text) {
  const input = $('chat-input');
  if (input) {
    input.value = text;
    input.focus();
  }
};

window.clearChat = function() {
  APP_STATE.chatHistory = [];
  const box = $('chat-messages');
  if (box) {
    box.innerHTML = `
      <div class="chat-empty">
        <div class="empty-orb">✦</div>
        <h2>Nouvelle discussion démarrée</h2>
        <p>Sélectionnez un modèle ci-dessus ou posez directement votre question.</p>
      </div>
    `;
  }
};

async function sendChatMessageReal(userText) {
  const box = $('chat-messages');
  if (!box) return;

  box.querySelector('.chat-empty')?.remove();

  // 1. Ajouter le message utilisateur dans le DOM
  const uBubble = document.createElement('div');
  uBubble.className = 'chat-bubble chat-user';
  uBubble.textContent = userText;
  box.appendChild(uBubble);
  box.scrollTop = box.scrollHeight;

  // 2. Préparer l'historique
  APP_STATE.chatHistory.push({ role: 'user', content: userText });

  // 3. Bulle temporaire de réponse de l'assistant
  const aBubble = document.createElement('div');
  aBubble.className = 'chat-bubble chat-assistant loading';
  aBubble.innerHTML = '<span class="typing-indicator"><i></i><i></i><i></i></span> Routage en cours…';
  box.appendChild(aBubble);
  box.scrollTop = box.scrollHeight;

  // Clé API : soit clé de session, soit clé playground stockée
  let key = APP_STATE.keys?.[0]?.prefix ? sessionStorage.getItem('qh_play_key') : sessionStorage.getItem('qh_play_key');
  if (!key && APP_STATE.me?.keys?.length) {
    // Si l'utilisateur est connecté et qu'une clé est stockée
    key = sessionStorage.getItem('qh_play_key');
  }

  const modelRequested = PUBLIC_MODEL.id;
  const t0 = performance.now();

  try {
    const payload = {
      model: modelRequested,
      messages: APP_STATE.chatHistory,
      max_tokens: 1200,
      stream: true            // vrai flux : le texte s'affiche au fil de l'eau
    };

    const headers = { 'Content-Type': 'application/json' };
    if (key) headers['Authorization'] = 'Bearer ' + key;

    const res = await fetch('/v1/chat/completions', {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    });

    if (!res.ok || !res.body) {
      const data = await res.json().catch(() => ({}));
      const errMsg = data.error?.message || `Erreur serveur (${res.status})`;
      aBubble.classList.remove('loading');
      aBubble.classList.add('error');
      aBubble.innerHTML = `
        <div class="assistant-body">${escapeHtml(errMsg)}</div>
        <div class="assistant-telemetry error">
          <span>Pour tester avec votre propre compte, ajoutez votre clé Smart API Cheap depuis la Console.</span>
        </div>
      `;
    } else {
      aBubble.classList.remove('loading');
      aBubble.innerHTML = '<div class="assistant-body"><span class="typing-indicator"><i></i><i></i><i></i></span></div><div class="assistant-telemetry"></div>';
      const bodyEl = aBubble.querySelector('.assistant-body');
      const teleEl = aBubble.querySelector('.assistant-telemetry');
      const reader = res.body.getReader();
      const dec = new TextDecoder();
      let buf = '', full = '', usage = null, started = false;
      while (true) {
        const chunk = await reader.read();
        if (chunk.done) break;
        buf += dec.decode(chunk.value, { stream: true });
        let cut;
        while ((cut = buf.indexOf('\n\n')) >= 0) {
          const blk = buf.slice(0, cut);
          buf = buf.slice(cut + 2);
          for (const line of blk.split('\n')) {
            const s = line.trim();
            if (!s.startsWith('data:')) continue;
            const p = s.slice(5).trim();
            if (!p || p === '[DONE]') continue;
            let d;
            try { d = JSON.parse(p); } catch (e) { continue; }
            if (d.usage) usage = d.usage;
            const delta = ((d.choices || [])[0] || {}).delta || {};
            if (delta.content) {
              if (!started) { started = true; bodyEl.innerHTML = ''; }
              full += delta.content;
              bodyEl.innerHTML = escapeHtml(full).replace(/\n/g, '<br>');
              box.scrollTop = box.scrollHeight;
            }
          }
        }
      }
      const duration = ((performance.now() - t0) / 1000).toFixed(2);
      if (!full) bodyEl.innerHTML = 'Réponse vide.';
      const u = usage || {};
      const tin = u.prompt_tokens || 0;
      const tout = u.completion_tokens || 0;
      const tcached = (u.prompt_tokens_details || {}).cached_tokens || 0;
      const cachePct = tin > 0 ? Math.round((tcached / tin) * 100) : 0;
      // jamais le nom reel : on affiche la marque publique
      teleEl.innerHTML = `
        <span class="tele-item"><b>Modèle servi :</b> ${escapeHtml(PUBLIC_MODEL.name)}</span>
        <span class="tele-item"><b>Tokens :</b> ${tin} in / ${tout} out</span>
        ${tcached > 0 ? `<span class="tele-item text-green"><b>Cache économisé :</b> ${tcached} tok (${cachePct}%)</span>` : ''}
        <span class="tele-item"><b>Latence :</b> ${duration}s</span>
      `;
      if (full) APP_STATE.chatHistory.push({ role: 'assistant', content: full });
    }
  } catch (err) {
    aBubble.classList.remove('loading');
    aBubble.classList.add('error');
    aBubble.textContent = `Erreur de connexion : ${err.message}`;
  }

  box.scrollTop = box.scrollHeight;
}

function initChatSubmit() {
  const form = $('chat-form');
  const input = $('chat-input');
  if (!form || !input) return;

  form.onsubmit = e => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;
    input.value = '';
    sendChatMessageReal(text);
  };

  input.onkeydown = e => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      form.dispatchEvent(new Event('submit'));
    }
  };
}

/* === API CALL & NAVIGATION === */
async function apiCall(path, opts = {}) {
  const loader = $('top-loader');
  if (loader) { loader.style.opacity = '1'; loader.style.width = '42%'; }
  const headers = { 'Content-Type': 'application/json' };
  if (APP_STATE.session) headers['X-QH-Session'] = APP_STATE.session;
  try {
    const res = await fetch(API + path, {
      method: opts.method || 'POST',
      headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined
    });
    const data = await res.json().catch(() => ({ error: { message: 'Réponse serveur invalide' } }));
    if (loader) {
      loader.style.width = '100%';
      setTimeout(() => { loader.style.opacity = '0'; loader.style.width = '0'; }, 220);
    }
    return { status: res.status, data };
  } catch (_) {
    if (loader) loader.style.opacity = '0';
    return { status: 500, data: { error: { message: 'Impossible de joindre Smart API Cheap' } } };
  }
}

window.switchTab = function(tab) {
  // 1. Mise à jour des boutons de navigation (support .nav-btn et .nav-link)
  document.querySelectorAll('.nav-btn, .nav-link').forEach(x => {
    const isActive = (x.dataset.tab === tab);
    x.classList.toggle('active', isActive);
    if (isActive) {
      x.classList.add('text-foreground');
      x.classList.remove('text-muted-foreground');
    } else {
      x.classList.remove('text-foreground');
      x.classList.add('text-muted-foreground');
    }
  });

  // 2. Gestion de l'affichage des sections (retrait impératif de 'hidden' sur la cible)
  document.querySelectorAll('.tab-pane').forEach(pane => {
    if (pane.id === 'tab-' + tab) {
      pane.classList.remove('hidden');
      pane.classList.add('active');
    } else {
      pane.classList.add('hidden');
      pane.classList.remove('active');
    }
  });

  APP_STATE.currentTab = tab;
  window.scrollTo({ top: 0, behavior: 'smooth' });

  // 3. Rendu des données spécifiques
  if (tab === 'models') renderModelsTableUno();
  if (tab === 'classements') renderClassements();
  if (tab === 'chat') {
    const input = document.getElementById('chat-input');
    if (input) setTimeout(() => input.focus(), 100);
  }
};

/* === AUTHENTIFICATION === */
let currentAuthMode = 'login';
window.openAuth = mode => {
  currentAuthMode = mode;
  setAuthMode(mode);
  $('auth-modal').style.display = 'flex';
  document.body.style.overflow = 'hidden';
};
window.closeAuth = () => {
  $('auth-modal').style.display = 'none';
  document.body.style.overflow = '';
};

window.setAuthMode = mode => {
  currentAuthMode = mode;
  $('tab-auth-signin').classList.toggle('active', mode === 'login');
  $('tab-auth-signup').classList.toggle('active', mode === 'signup');
  $('auth-title').textContent = mode === 'login' ? 'Bienvenue.' : 'Créer votre espace.';
  $('auth-subtitle').textContent = mode === 'login' ? 'Connectez-vous pour retrouver votre console.' : 'Créez un compte pour générer vos clés API.';
  $('btn-auth-submit').textContent = mode === 'login' ? 'Se connecter' : 'Créer mon compte';
  $('auth-error').hidden = true;
};

function initAuth() {
  $('form-auth').onsubmit = async e => {
    e.preventDefault();
    const btn = $('btn-auth-submit');
    btn.disabled = true;
    btn.textContent = 'Connexion…';
    const endpoint = currentAuthMode === 'login' ? '/api/auth/login' : '/api/auth/register';
    const r = await apiCall(endpoint, {
      body: { email: $('auth-email').value.trim(), password: $('auth-password').value }
    });
    if (r.status === 200 && r.data.session) {
      APP_STATE.session = r.data.session;
      sessionStorage.setItem('qh_session', r.data.session);
      closeAuth();
      await refreshMe();
      switchTab('console');
    } else {
      $('auth-error').textContent = r.data.error?.message || 'Échec de la connexion';
      $('auth-error').hidden = false;
    }
    btn.disabled = false;
    btn.textContent = currentAuthMode === 'login' ? 'Se connecter' : 'Créer mon compte';
  };

  const oauth = async provider => {
    const note = $('oauth-note');
    const r = await apiCall('/api/auth/oauth/start?provider=' + provider, { method: 'GET' });
    if (r.status === 200 && r.data.url) {
      if (note) note.hidden = true;
      location.href = r.data.url;
      return;
    }
    if (note) {
      note.textContent = 'La connexion ' + (provider === 'google' ? 'Google' : 'GitHub') + ' arrive bientôt. Utilisez votre email pour démarrer immédiatement.';
      note.hidden = false;
    }
  };

  $('btn-oauth-google').onclick = () => oauth('google');
  $('btn-oauth-github').onclick = () => oauth('github');

  const session = new URLSearchParams(location.search).get('oauth_session');
  if (session) {
    history.replaceState({}, '', location.pathname);
    APP_STATE.session = session;
    sessionStorage.setItem('qh_session', session);
    refreshMe();
  }
}

window.logout = () => {
  APP_STATE.session = '';
  APP_STATE.me = null;
  sessionStorage.removeItem('qh_session');
  setAuthUI();
  switchTab('models');
};

function setAuthUI() {
  const logged = !!APP_STATE.me?.user;
  $('auth-guest-view').style.display = logged ? 'none' : 'flex';
  $('auth-user-view').style.display = logged ? 'flex' : 'none';
  if (logged) {
    const email = APP_STATE.me.user.email || '';
    const avatar = document.querySelector('.user-avatar');
    if (avatar) avatar.textContent = (email.split('@')[0] || 'Q').charAt(0).toUpperCase();
  }
  renderKeys();
}

function renderMe() {
  const auto = APP_STATE.me?.subscription?.auto || {};
  const balance = fmtBalanceUSD((auto.tokens_total || 0) - (auto.tokens_used || 0));
  const pill = document.querySelector('.header-balance');
  if (pill) pill.textContent = balance;
  APP_STATE.keys = APP_STATE.me?.keys || [];
  renderKeys();
}

async function refreshMe() {
  if (!APP_STATE.session) return;
  const r = await apiCall('/api/me', { method: 'GET' });
  if (r.status === 200) {
    APP_STATE.me = r.data;
    renderMe();
    setAuthUI();
  } else logout();
}

/* === CLÉS API === */
function renderKeys() {
  const box = $('keys-login-box'), table = $('keys-table-container');
  if (!box || !table) return;
  const logged = !!APP_STATE.me;
  box.style.display = logged ? 'none' : 'block';
  table.style.display = logged ? 'block' : 'none';
  if (!logged) return;

  const keys = APP_STATE.keys || [];
  $('keys-table-body').innerHTML = keys.length ? keys.map(k => `
    <tr>
      <td><strong>${escapeHtml(k.name)}</strong></td>
      <td><code>${escapeHtml(k.prefix)}…</code></td>
      <td>${new Date((k.created_at || 0) * 1000).toISOString().slice(0, 10)}</td>
      <td>${Number(k.n || 0).toLocaleString('fr-FR')} req · ${Number(k.tok || 0).toLocaleString('fr-FR')} tok</td>
      <td><span class="key-state ${k.revoked ? 'revoked' : ''}">${k.revoked ? 'Révoquée' : 'Active'}</span></td>
      <td>${k.revoked ? '' : `<button class="table-action" onclick="revokeKey(${k.id})">Révoquer</button>`}</td>
    </tr>
  `).join('') : `<tr><td colspan="6" class="empty-table">Aucune clé. Créez votre première clé.</td></tr>`;
}

window.openKeyModal = () => {
  if (!APP_STATE.me) { openAuth('login'); return; }
  $('key-name-input').value = '';
  $('modal-key').showModal();
};

function initKeyCreation() {
  $('form-create-key').onsubmit = async e => {
    e.preventDefault();
    const r = await apiCall('/api/keys', {
      body: { name: $('key-name-input').value.trim() || 'Mon agent', plan: 'auto' }
    });
    if (r.status === 200 && r.data.key) {
      $('modal-key').close();
      $('new-key-val').value = r.data.key;
      sessionStorage.setItem('qh_play_key', r.data.key);
      $('modal-key-success').showModal();
      refreshMe();
    } else alert(r.data.error?.message || 'Impossible de créer la clé');
  };
  $('btn-copy-key').onclick = () => {
    navigator.clipboard.writeText($('new-key-val').value);
    $('btn-copy-key').textContent = 'Copié ✓';
  };
}

window.revokeKey = async id => {
  if (!confirm('Révoquer cette clé ?')) return;
  const r = await apiCall('/api/keys/' + id, { method: 'DELETE' });
  if (r.status === 200) refreshMe();
};

/* === JOURNAUX === */
async function loadUsage() {
  const box = $('usage-login-box'), content = $('usage-content');
  if (!box || !content) return;
  if (!APP_STATE.session) { box.style.display = 'block'; content.style.display = 'none'; return; }
  box.style.display = 'none'; content.style.display = 'block';

  const r = await apiCall('/api/usage?limit=50', { method: 'GET' });
  if (r.status !== 200) {
    $('usage-table-body').innerHTML = '<tr><td colspan="7" class="empty-table">' + escapeHtml(r.data.error?.message || 'Journaux indisponibles') + '</td></tr>';
    return;
  }
  const d = r.data || {}, nf = n => Number(n || 0).toLocaleString('fr-FR');
  $('usage-stats').innerHTML =
    `<div class="usage-stat"><b>${nf(d.totals?.requests)}</b><span>Requêtes au total</span></div>` +
    `<div class="usage-stat"><b>${nf(d.totals?.tokens)}</b><span>Tokens facturés</span></div>` +
    `<div class="usage-stat"><b>$${Number(d.totals?.cost_usd || 0).toFixed(4)}</b><span>Coût réel des requêtes</span></div>`;

  const days = d.per_day || [], mx = Math.max(1, ...days.map(x => x.tokens || 0));
  $('usage-chart').innerHTML = days.length ? days.map(x => `
    <div class="usage-bar" title="${escapeHtml(x.d)} · ${nf(x.tokens)} tokens">
      <i style="height:${Math.max(3, Math.round(100 * (x.tokens || 0) / mx))}%"></i>
      <span>${escapeHtml((x.d || '').slice(5))}</span>
    </div>
  `).join('') : '<span class="auto-mix-hint">Aucune requête sur les 30 derniers jours.</span>';

  const rows = d.rows || [];
  $('usage-table-body').innerHTML = rows.length ? rows.map(x => `
    <tr>
      <td>${new Date((x.ts || 0) * 1000).toLocaleString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}</td>
      <td><code>${escapeHtml(x.key || '—')}</code></td>
      <td><code>${escapeHtml(x.model)}</code></td>
      <td>${nf(x.in)}</td>
      <td>${nf(x.out)}</td>
      <td><b>${nf(x.tokens)}</b></td>
      <td>$${Number(x.cost_usd || 0).toFixed(5)}</td>
    </tr>
  `).join('') : '<tr><td colspan="7" class="empty-table">Aucune requête pour le moment — lancez-en une depuis le chat ou avec votre clé.</td></tr>';

  const items = d.per_model || [], COLORS = ['#5de5e1', '#9876ff', '#ffd479', '#6ef0b0', '#61a8ff', '#ff8d9d', '#8ef0e8'];
  $('usage-models').innerHTML = items.length ? items.map((it, i) => `
    <div class="usage-model-item">
      <i style="background:${COLORS[i % COLORS.length]}"></i>
      <span>${escapeHtml(it.model)}</span>
      <b>${nf(it.tokens)} tok · ${nf(it.n)} req</b>
    </div>
  `).join('') : '<span class="auto-mix-hint">Pas encore de données.</span>';

  $('usage-refresh-note').textContent = 'mis à jour à ' + new Date().toLocaleTimeString('fr-FR');
}

/* === RECHARGE / CODE === */
function initRedeem() {
  const btn = $('btn-redeem');
  if (!btn) return;
  btn.onclick = async () => {
    const msg = $('redeem-msg');
    const r = await apiCall('/api/redeem', { body: { code: $('redeem-input').value.trim().toUpperCase() } });
    msg.hidden = false;
    msg.textContent = r.status === 200 ? 'Crédit activé ✓' : (r.data.error?.message || 'Code invalide');
    msg.className = r.status === 200 ? 'success-message' : 'form-error';
    if (r.status === 200) {
      $('redeem-input').value = '';
      refreshMe();
    }
  };
}

/* === ROUTEUR LIVE & AUTOMIX === */
function initRouterStatus() {
  const dot = $('router-live-state'), src = $('router-metric-source'), mdl = $('router-metric-models'), age = $('router-metric-age');
  const badge = document.querySelector('.live-badge');
  fetch(API + '/health').then(r => r.ok ? r.json() : null).then(d => {
    const m = d && d.market30;
    if (dot) { dot.classList.add('ok'); dot.innerHTML = '<i></i> routeur actif'; }
    if (badge) badge.innerHTML = '<b></b> ACTIF';
    if (m) {
      const minutes = Math.max(0, Math.round((m.age_s || 0) / 60));
      if (src) src.textContent = 'Sonde 30 min';
      if (mdl) mdl.textContent = '20 modèles';
      if (age) age.textContent = minutes <= 1 ? 'à l’instant' : minutes + ' min';
    }
  }).catch(() => {});
}

function initAutoMix() {
  const svg = $('automix-donut'), legend = $('automix-legend'), count = $('automix-count');
  if (!svg) return;
  fetch(API + '/api/auto-mix', { method: 'GET' }).then(r => r.ok ? r.json() : null).then(d => {
    if (!d || !d.total || !(d.mix || []).length) {
      if (legend) legend.innerHTML = '<span class="auto-mix-hint">Le routeur préserve le cache et publie ici le trafic des dernières 24 h.</span>';
      if (count) count.textContent = '0';
      return;
    }
    const COLORS = ['#5de5e1', '#9876ff', '#ffd479', '#6ef0b0', '#61a8ff', '#ff8d9d', '#8ef0e8'];
    const items = d.mix.slice(0, 7), totalN = d.total, R = 52, C = 2 * Math.PI * R;
    let acc = 0, segs = '';
    items.forEach((it, i) => {
      const frac = it.n / totalN, len = frac * C, col = COLORS[i % COLORS.length];
      segs += `<circle r="${R}" cx="60" cy="60" fill="none" stroke="${col}" stroke-width="14" stroke-dasharray="${len} ${C - len}" stroke-dashoffset="${-acc}" transform="rotate(-90 60 60)"/>`;
      acc += len;
    });
    svg.innerHTML = segs;
    if (count) count.textContent = String(totalN);
    if (legend) {
      legend.innerHTML = items.map((it, i) => `
        <div class="auto-mix-item">
          <i style="background:${COLORS[i % COLORS.length]}"></i>
          <span>${escapeHtml(it.model)}</span>
          <b>${Math.round(100 * it.n / totalN)}%</b>
        </div>
      `).join('');
    }
  }).catch(() => {});
}

/* === COPIES UTILS === */
window.copyCli = btn => {
  navigator.clipboard.writeText('curl -fsSL https://smartapi.cheap/connect.sh | sh').then(() => {
    if (btn) { btn.textContent = 'Copié ✓'; setTimeout(() => btn.textContent = 'Copier', 1400); }
  }).catch(() => {});
};

window.copyText = (text, btn) => {
  navigator.clipboard.writeText(text).then(() => {
    if (btn) { btn.textContent = 'Copié ✓'; setTimeout(() => btn.textContent = 'Copier', 1400); }
  }).catch(() => {});
};

/* === INITIALISATION GLOBALE === */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.nav-link').forEach(x => x.onclick = () => switchTab(x.dataset.tab));
  initAuth();
  initKeyCreation();
  initRedeem();
  initRouterStatus();
  initAutoMix();
  initChatDropdown();
  initChatSubmit();
  renderModelsTable();
  renderClassements();

  const menu = $('mobile-menu-toggle'), nav = $('main-nav');
  if (menu && nav) {
    menu.onclick = () => {
      const open = nav.classList.toggle('open');
      menu.setAttribute('aria-expanded', open);
      menu.textContent = open ? '×' : '☰';
    };
    nav.querySelectorAll('.nav-link').forEach(x => x.addEventListener('click', () => {
      nav.classList.remove('open');
      menu.setAttribute('aria-expanded', 'false');
      menu.textContent = '☰';
    }));
  }

  if (APP_STATE.session) refreshMe();
});


/* ==================== ANIMATIONS ET COMPOSANTS UNOROUTER ==================== */

// 1. Scramble Rotate Text pour le Hero
const SCRAMBLE_WORDS = ["API", "CHAT", "PERSONNAGES", "CODE", "INTELLIGENCE", "AGENTS"];
let scrambleIndex = 0;
const CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";

function scrambleText(targetText, element, onComplete) {
  let iterations = 0;
  const interval = setInterval(() => {
    element.innerText = targetText.split("")
      .map((letter, index) => {
        if (index < iterations) return targetText[index];
        return CHARS[Math.floor(Math.random() * CHARS.length)];
      })
      .join("");
    if (iterations >= targetText.length) {
      clearInterval(interval);
      if (onComplete) onComplete();
    }
    iterations += 1 / 2;
  }, 40);
}

function initScrambleRotate() {
  const el = $('hero-scramble-word');
  if (!el) return;
  setInterval(() => {
    scrambleIndex = (scrambleIndex + 1) % SCRAMBLE_WORDS.length;
    scrambleText(SCRAMBLE_WORDS[scrambleIndex], el);
  }, 2800);
}

// 2. Remplissage du ruban Marquee
function initMarquee() {
  const track = $('marquee-models');
  if (!track) return;
  const doubled = [...MODELS_DATA, ...MODELS_DATA];
  track.innerHTML = doubled.map(m => `
    <div class="flex items-center gap-2 px-3 py-1 rounded bg-secondary/50 border border-border/40 shrink-0 cursor-pointer hover:border-cyan-400/50 transition-colors" onclick="launchChatWithModel('${m.id}')">
      <img src="${m.logo}" class="h-3.5 w-3.5 object-contain" alt="">
      <span class="font-bold text-foreground text-[11px]">${m.name}</span>
      <span class="text-emerald-400 font-semibold text-[10px]">${m.discount}</span>
    </div>
  `).join('');
}

// 3. Filtres interactifs pour le tableau
let CURRENT_MODALITY = 'all';
let CURRENT_VENDOR = 'all';
let PROMO_ONLY = false;
let SEARCH_QUERY = '';

window.filterByModality = function(mod) {
  CURRENT_MODALITY = mod;
  document.querySelectorAll('.modality-tab').forEach(t => t.classList.remove('active'));
  document.querySelector(`.modality-tab[data-mod="${mod}"]`)?.classList.add('active');
  renderModelsTableUno();
};

window.filterByVendor = function(vendor) {
  CURRENT_VENDOR = vendor;
  document.querySelectorAll('.vendor-chip').forEach(c => c.classList.remove('active'));
  document.querySelector(`.vendor-chip[data-vendor="${vendor}"]`)?.classList.add('active');
  renderModelsTableUno();
};

window.togglePromoFilter = function(checked) {
  PROMO_ONLY = checked;
  renderModelsTableUno();
};

window.onModelSearch = function(val) {
  SEARCH_QUERY = val.toLowerCase().trim();
  renderModelsTableUno();
};

function renderModelsTableUno() {
  const tbody = $('models-tbody');
  if (!tbody) return;

  const filtered = MODELS_DATA.filter(m => {
    if (CURRENT_MODALITY !== 'all' && !m.modalities.includes(CURRENT_MODALITY)) return false;
    if (CURRENT_VENDOR !== 'all' && m.provider !== CURRENT_VENDOR) return false;
    if (PROMO_ONLY && m.discount_num < 50) return false;
    if (SEARCH_QUERY && !m.name.toLowerCase().includes(SEARCH_QUERY) && !m.id.toLowerCase().includes(SEARCH_QUERY) && !m.provider_name.toLowerCase().includes(SEARCH_QUERY)) return false;
    return true;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="py-8 text-center text-muted-foreground">Aucun modèle ne correspond à vos filtres.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(m => `
    <tr class="hover:bg-secondary/30 transition-colors">
      <!-- 1. Modèle (Logo + Nom + Badge) -->
      <td class="py-3 px-4">
        <div class="flex items-center gap-3">
          <img src="${m.logo}" class="h-6 w-6 object-contain rounded p-0.5 bg-white/5 border border-border/40" alt="">
          <div>
            <div class="font-bold text-foreground flex items-center gap-2">
              <span>${m.name}</span>
              ${m.badge ? `<span class="text-[9px] px-1.5 py-0.2 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-500/20">${m.badge}</span>` : ''}
            </div>
            <span class="text-[10px] text-muted-foreground">${m.id}</span>
          </div>
        </div>
      </td>

      <!-- 2. Tokens Hebdo -->
      <td class="py-3 px-3 text-right font-semibold text-foreground">${m.tokens_weekly}</td>

      <!-- 3. Prix Entrée / 1M -->
      <td class="py-3 px-3 text-right">
        <div class="font-bold text-foreground">${m.input_ours}</div>
        <div class="flex items-center justify-end gap-1 text-[10px]">
          <span class="text-muted-foreground line-through">${m.input_official}</span>
          <span class="discount-badge-table">${m.discount}</span>
        </div>
      </td>

      <!-- 4. Prix Sortie / 1M -->
      <td class="py-3 px-3 text-right">
        <div class="font-bold text-foreground">${m.output_ours}</div>
        <div class="flex items-center justify-end gap-1 text-[10px]">
          <span class="text-muted-foreground line-through">${m.output_official}</span>
          <span class="discount-badge-table">${m.discount}</span>
        </div>
      </td>

      <!-- 5. Contexte -->
      <td class="py-3 px-3 text-center">
        <span class="px-2 py-0.5 rounded bg-secondary/60 text-muted-foreground text-[10px] border border-border/30">${m.context}</span>
      </td>

      <!-- 6. Uptime -->
      <td class="py-3 px-3 text-center text-emerald-400 font-semibold">${m.availability}</td>

      <!-- 7. Succès -->
      <td class="py-3 px-3 text-center text-emerald-400">${m.success}</td>

      <!-- 8. Latence -->
      <td class="py-3 px-3 text-center text-muted-foreground">${m.latency}</td>

      <!-- 9. Actions -->
      <td class="py-3 px-4 text-center">
        <div class="flex items-center justify-center gap-1.5">
          <button class="btn-table-test text-[11px]" onclick="launchChatWithModel('${m.id}')">Tester</button>
          <button class="btn-table-copy text-[11px]" onclick="copyText('${m.id}', this)">Copier</button>
        </div>
      </td>
    </tr>
  `).join('');
}

// Initialisation globale au chargement
window.addEventListener('DOMContentLoaded', () => {
  initScrambleRotate();
  initMarquee();
  renderModelsTableUno();
  renderClassements();
});


window.showDashboardSection = function(section) {
  document.querySelectorAll('.dash-btn').forEach(b => {
    const isAct = (b.dataset.dash === section);
    b.classList.toggle('active', isAct);
    b.classList.toggle('border-white', isAct);
    b.classList.toggle('bg-secondary', isAct);
    b.classList.toggle('text-white', isAct);
    b.classList.toggle('text-muted-foreground', !isAct);
  });

  document.querySelectorAll('.dash-section').forEach(sec => {
    if (sec.id === 'dash-section-' + section) {
      sec.classList.remove('hidden');
    } else {
      sec.classList.add('hidden');
    }
  });
};

window.switchToDashboard = function(section = 'overview') {
  document.getElementById('public-view').classList.add('hidden');
  document.getElementById('main-header').classList.add('hidden');
  document.getElementById('dashboard-view').classList.remove('hidden');
  showDashboardSection(section);
  loadDashboardData();
};

window.switchToPublic = function() {
  document.getElementById('dashboard-view').classList.add('hidden');
  document.getElementById('public-view').classList.remove('hidden');
  document.getElementById('main-header').classList.remove('hidden');
  switchTab('home');
};


/* ==========================================================================
   SMART API CHEAP - LIAISONS API REELLES (STATS, PRICES, KEYS, LOGS, OAUTH)
   ========================================================================== */

// 1. Chargement de la télémétrie réelle depuis la table usage_logs
async function loadLivePlatformStats() {
  try {
    const res = await fetch('/api/gw?path=api/public/stats');
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.ok) {
      const elTokens = $('stat-hero-tokens');
      if (elTokens && data.total_tokens) {
        elTokens.innerText = Number(data.total_tokens).toLocaleString('fr-FR');
      }
      const elTpm = document.querySelector('#tab-home .text-emerald-400.font-mono.text-xl');
      if (elTpm && data.tokens_per_minute) {
        elTpm.innerText = '~ ' + Number(data.tokens_per_minute).toLocaleString('fr-FR');
      }
      const elReqs = document.querySelector('#tab-home .font-mono.text-xl.font-bold.text-foreground');
      if (elReqs && data.total_requests) {
        elReqs.innerText = Number(data.total_requests).toLocaleString('fr-FR');
      }
    }
  } catch (err) {
    console.debug('Télémétrie en cours d\'agrégation:', err);
  }
}

// 2. Synchronisation du tableau des modèles avec la sonde active /api/prices
async function syncModelsWithLiveMarket() {
  try {
    const res = await fetch('/api/gw?path=api/prices');
    if (!res.ok) return;
    const data = await res.json();
    if (data && data.models) {
      // Mettre à jour MODELS_DATA avec les vrais tarifs de la sonde
      Object.keys(data.models).forEach(mId => {
        const live = data.models[mId];
        const match = MODELS_DATA.find(x => x.id.toLowerCase() === mId.toLowerCase());
        if (match && live.top && live.top.length > 0) {
          const best = live.top[0];
          if (best.in_now) match.input_ours = '$' + Number(best.in_now).toFixed(4);
          if (best.out_now) match.output_ours = '$' + Number(best.out_now).toFixed(4);
          if (best.latency_s) match.latency = Number(best.latency_s).toFixed(2) + 's';
          if (best.sr24) match.success = best.sr24.toFixed(1) + '%';
        }
      });
      renderModelsTableUno();
    }
  } catch (err) {
    console.debug('Sonde marché non disponible immédiatement:', err);
  }
}

// 3. Gestion réelle des Clés API (Tokens) pour le Dashboard
async function loadDashboardKeys() {
  const tbody = $('dash-keys-tbody');
  if (!tbody) return;
  const sess = localStorage.getItem('qh_session');
  if (!sess) {
    tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-muted-foreground">Veuillez vous connecter pour voir vos clés API.</td></tr>';
    return;
  }

  try {
    const res = await fetch('/api/gw?path=api/keys', {
      headers: { 'X-QH-Session': sess }
    });
    const data = await res.json();
    if (data && data.keys && data.keys.length > 0) {
      const keysCountEl = $('dash-stat-keys');
      if (keysCountEl) keysCountEl.innerText = data.keys.filter(k => !k.revoked).length;

      tbody.innerHTML = data.keys.map(k => `
        <tr class="hover:bg-secondary/40 transition-colors">
          <td class="py-3 px-4 font-bold text-foreground">${k.name || 'Clé sans nom'}</td>
          <td class="py-3 px-4 text-cyan-300 font-mono">${k.prefix ? k.prefix + '••••••••' : 'sk-sm-••••••••'}</td>
          <td class="py-3 px-4 text-muted-foreground">${new Date(k.created_at * 1000).toLocaleDateString('fr-FR')}</td>
          <td class="py-3 px-4 text-center">
            ${k.revoked ? '<span class="text-red-400 font-bold">Révoquée</span>' : '<span class="text-emerald-400 font-bold">Active</span>'}
          </td>
          <td class="py-3 px-4 text-right">
            ${k.revoked ? '-' : `<button class="text-red-400 hover:text-red-300 text-xs uppercase tracking-wider" onclick="revokeKey(${k.id})">Révoquer</button>`}
          </td>
        </tr>
      `).join('');
    } else {
      tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-muted-foreground">Aucune clé créée pour le moment. Cliquez sur "+ Nouvelle Clé".</td></tr>';
    }
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-red-400">Erreur lors de la récupération des clés.</td></tr>';
  }
}

// 4. Création réelle de Clé API
window.submitCreateKey = async function() {
  const nameInput = $('new-key-name');
  const name = nameInput ? nameInput.value.trim() : 'Agent';
  const sess = localStorage.getItem('qh_session');
  if (!sess) {
    alert('Session expirée. Veuillez vous reconnecter.');
    return;
  }

  try {
    const res = await fetch('/api/gw?path=api/keys', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-QH-Session': sess
      },
      body: JSON.stringify({ name: name })
    });
    const data = await res.json();
    if (data && data.key) {
      $('key-create-form').classList.add('hidden');
      const resBox = $('key-result-box');
      resBox.classList.remove('hidden');
      $('created-key-display').innerText = data.key;
      loadDashboardKeys();
    } else {
      alert(data.error?.message || 'Erreur lors de la création de la clé');
    }
  } catch (err) {
    alert('Erreur réseau lors de la génération de la clé.');
  }
};

// 5. Révocation de Clé API
window.revokeKey = async function(keyId) {
  if (!confirm('Confirmez-vous la révocation immédiate de cette clé API ?')) return;
  const sess = localStorage.getItem('qh_session');
  try {
    const res = await fetch('/api/gw?path=api/keys/' + keyId, {
      method: 'DELETE',
      headers: { 'X-QH-Session': sess }
    });
    loadDashboardKeys();
  } catch (err) {
    alert('Impossible de révoquer la clé');
  }
};

// 6. Chargement des Journaux d'utilisation récents (/logs)
async function loadDashboardUsageLogs() {
  const tbody = $('dash-logs-tbody');
  if (!tbody) return;
  const sess = localStorage.getItem('qh_session');
  if (!sess) return;

  try {
    const res = await fetch('/api/gw?path=api/usage', {
      headers: { 'X-QH-Session': sess }
    });
    const data = await res.json();
    if (data && data.logs && data.logs.length > 0) {
      tbody.innerHTML = data.logs.map(l => `
        <tr class="hover:bg-secondary/40 transition-colors">
          <td class="py-3 px-4 text-muted-foreground">${new Date(l.created_at * 1000).toLocaleTimeString('fr-FR')}</td>
          <td class="py-3 px-4 font-bold text-foreground">${l.model_public || 'AutoSmart Flash 1.0'}</td>
          <td class="py-3 px-4 text-right">${Number(l.prompt_tokens || 0).toLocaleString('fr-FR')}</td>
          <td class="py-3 px-4 text-right text-emerald-400 font-bold">${Number(l.cached_tokens || 0).toLocaleString('fr-FR')}</td>
          <td class="py-3 px-4 text-right text-cyan-300">$${Number(l.cost_usd || 0).toFixed(5)}</td>
        </tr>
      `).join('');
    } else {
      tbody.innerHTML = '<tr><td colspan="5" class="py-6 text-center text-muted-foreground">Aucune consommation enregistrée récemment. Vos requêtes d\'API apparaîtront ici.</td></tr>';
    }
  } catch (err) {
    console.debug('Erreur chargement logs:', err);
  }
}

// 7. Initialisation globale et persistance OAuth de session
window.loadDashboardData = function() {
  loadDashboardKeys();
  loadDashboardUsageLogs();
};

window.addEventListener('DOMContentLoaded', () => {
  // Capture de token de session si retour d'OAuth Google ou GitHub dans l'URL
  const params = new URLSearchParams(window.location.search);
  const qhSession = params.get('session_token') || params.get('qh_session');
  if (qhSession) {
    localStorage.setItem('qh_session', qhSession);
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  const existingSess = localStorage.getItem('qh_session');
  if (existingSess) {
    $('auth-unlogged')?.classList.add('hidden');
    $('auth-logged')?.classList.remove('hidden');
    fetch('/api/gw?path=api/me', { headers: { 'X-QH-Session': existingSess } })
      .then(r => r.json())
      .then(d => {
        if (d && d.user) {
          const emailEl = $('dash-user-email');
          if (emailEl) emailEl.innerText = d.user.email;
          const greetEl = $('dash-greeting');
          if (greetEl) greetEl.innerText = 'Bonjour, ' + (d.user.email.split('@')[0]);
          const planEl = $('dash-stat-plan');
          if (planEl) planEl.innerText = d.user.plan || 'Pay-as-you-go';
          const tokEl = $('dash-stat-tokens');
          if (tokEl) tokEl.innerText = (d.user.balance_tokens != null ? Number(d.user.balance_tokens).toLocaleString('fr-FR') : 'Illimité');
        }
      }).catch(() => {});
  }

  loadLivePlatformStats();
  syncModelsWithLiveMarket();
});


/* ==================== ALIGNEMENT AUTHENTIFICATION UNOROUTER ==================== */

// 1. Fonctions d'ouverture / fermeture appelées par les boutons de index.html
window.openAuthModal = function(mode = 'login') {
  currentAuthMode = mode;
  const modal = document.getElementById('auth-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  modal.style.display = 'flex';
  document.body.style.overflow = 'hidden';

  const titleEl = document.getElementById('auth-modal-title');
  const descEl = document.getElementById('auth-modal-desc');
  const submitBtn = document.getElementById('auth-submit-btn');
  const switchText = document.getElementById('auth-switch-text');
  const switchBtn = document.getElementById('auth-switch-btn');
  const errEl = document.getElementById('auth-error-msg');
  if (errEl) errEl.classList.add('hidden');

  if (mode === 'login') {
    if (titleEl) titleEl.innerText = 'Connexion';
    if (descEl) descEl.innerText = 'Accédez à votre console Smart API Cheap';
    if (submitBtn) submitBtn.innerText = 'Se connecter';
    if (switchText) switchText.innerText = 'Pas encore de compte ?';
    if (switchBtn) switchBtn.innerText = 'Créer un compte';
  } else {
    if (titleEl) titleEl.innerText = 'Inscription';
    if (descEl) descEl.innerText = 'Créez votre compte développeur gratuit';
    if (submitBtn) submitBtn.innerText = 'Créer mon compte';
    if (switchText) switchText.innerText = 'Déjà inscrit ?';
    if (switchBtn) switchBtn.innerText = 'Se connecter';
  }
};

window.closeAuthModal = function() {
  const modal = document.getElementById('auth-modal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.style.display = 'none';
  document.body.style.overflow = '';
};

window.toggleAuthMode = function() {
  currentAuthMode = (currentAuthMode === 'login' ? 'register' : 'login');
  openAuthModal(currentAuthMode);
};

// 2. Déclencheur OAuth réel Google / GitHub
window.startOAuth = async function(provider) {
  try {
    const res = await fetch(`/api/gw?path=api/auth/oauth/start&provider=${provider}`);
    const data = await res.json();
    if (data && data.url) {
      window.location.href = data.url; // Redirection réelle du navigateur vers Google / GitHub
    } else {
      alert("Erreur lors de l'initialisation OAuth (" + (data.error?.message || 'inconnu') + ")");
    }
  } catch (err) {
    alert("Impossible de joindre le serveur d'authentification.");
  }
};

// 3. Soumission du formulaire email/password
window.submitAuth = async function() {
  const emailInput = document.getElementById('auth-email');
  const pwdInput = document.getElementById('auth-password');
  const errEl = document.getElementById('auth-error-msg');
  const submitBtn = document.getElementById('auth-submit-btn');

  const email = emailInput ? emailInput.value.trim() : '';
  const password = pwdInput ? pwdInput.value : '';

  if (!email || !password) {
    if (errEl) {
      errEl.innerText = 'Veuillez renseigner un email et un mot de passe.';
      errEl.classList.remove('hidden');
    }
    return;
  }

  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerText = 'Traitement en cours...';
  }

  const endpoint = (currentAuthMode === 'login' ? 'api/auth/login' : 'api/auth/register');

  try {
    const res = await fetch('/api/gw?path=' + endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json();

    if (res.ok && data.status === 'ok' && data.session) {
      localStorage.setItem('qh_session', data.session);
      closeAuthModal();
      window.location.reload();
    } else {
      if (errEl) {
        errEl.innerText = data.error?.message || (data.status === 'ok' ? 'Compte créé ! Veuillez vous connecter.' : 'Erreur de connexion');
        errEl.classList.remove('hidden');
      }
      if (currentAuthMode === 'register' && data.status === 'ok') {
        setTimeout(() => openAuthModal('login'), 1200);
      }
    }
  } catch (err) {
    if (errEl) {
      errEl.innerText = 'Erreur réseau avec la passerelle.';
      errEl.classList.remove('hidden');
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerText = (currentAuthMode === 'login' ? 'Se connecter' : 'Créer mon compte');
    }
  }
};
