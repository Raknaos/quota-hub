/**
 * QUOTA HUB — LOGIQUE APPLICATIVE COMPLETE
 * Catalogue de prix réels, Gestion des clés, Calculs de recharge, Playground interactif
 */

// 1. DATASET DES MODÈLES RÉELS (BASE DE DONNÉES DU MARCHÉ & DU PROJET)
const MODELS_CATALOG = [
  {
    id: "gpt-6-astra",
    name: "GPT-6 Astra (Flagship Frontier)",
    family: "OpenAI",
    officialPriceIn: 10.00,
    officialPriceOut: 50.00,
    quotaPriceIn: 0.85,
    quotaPriceOut: 3.80,
    tier: "s-grade",
    latency: "280ms",
    successRate: "99.8%",
    recommendedChannel: "Azure Pool S-Grade",
    hotDeal: true,
    desc: "Le plus puissant modèle de raisonnement & architecture logicielle."
  },
  {
    id: "gpt-5.6-sol",
    name: "GPT-5.6 Sol (Deep Reasoning)",
    family: "OpenAI",
    officialPriceIn: 4.00,
    officialPriceOut: 20.00,
    quotaPriceIn: 0.45,
    quotaPriceOut: 1.95,
    tier: "s-grade",
    latency: "310ms",
    successRate: "99.7%",
    recommendedChannel: "Relais S-Tier Certifié",
    hotDeal: true,
    desc: "Raisonnement poussé et benchmarks maths/code avancés."
  },
  {
    id: "gpt-5.6-luna",
    name: "GPT-5.6 Luna (Fast Ultra-Cheap)",
    family: "OpenAI",
    officialPriceIn: 0.20,
    officialPriceOut: 1.20,
    quotaPriceIn: 0.045,
    quotaPriceOut: 0.24,
    tier: "eco",
    latency: "115ms",
    successRate: "99.9%",
    recommendedChannel: "Canal Éco S-Vérifié (LinkAI/UU)",
    hotDeal: true,
    desc: "Idéal pour le routage de compression de session et agents background."
  },
  {
    id: "deepseek-v4-flash",
    name: "DeepSeek-V4-Flash-0731",
    family: "DeepSeek",
    officialPriceIn: 0.22,
    officialPriceOut: 0.66,
    quotaPriceIn: 0.055,
    quotaPriceOut: 0.16,
    tier: "eco",
    latency: "140ms",
    successRate: "99.8%",
    recommendedChannel: "DeepSeek Direct Spot",
    hotDeal: true,
    desc: "Modèle ultra rapide pour le dev et les tâches répétitives."
  },
  {
    id: "deepseek-v4-flash-vision-exp",
    name: "DeepSeek-V4-Flash Vision Exp",
    family: "DeepSeek",
    officialPriceIn: 0.30,
    officialPriceOut: 0.90,
    quotaPriceIn: 0.08,
    quotaPriceOut: 0.25,
    tier: "eco",
    latency: "190ms",
    successRate: "99.4%",
    recommendedChannel: "Spot Vision Router",
    hotDeal: false,
    desc: "Vision multimodal basse latence & analyse d'interfaces."
  },
  {
    id: "glm-5.3",
    name: "GLM-5.3 (Zhipu Enterprise)",
    family: "Zhipu",
    officialPriceIn: 1.40,
    officialPriceOut: 4.40,
    quotaPriceIn: 0.55,
    quotaPriceOut: 1.80,
    tier: "s-grade",
    latency: "240ms",
    successRate: "99.6%",
    recommendedChannel: "Zhipu Cloud VIP Direct",
    hotDeal: false,
    desc: "Modèle polyglotte très fort sur le français et le code backend."
  },
  {
    id: "glm-5.3-flash",
    name: "GLM-5.3 Flash (Promo)",
    family: "Zhipu",
    officialPriceIn: 0.075,
    officialPriceOut: 0.25,
    quotaPriceIn: 0.045,
    quotaPriceOut: 0.15,
    tier: "eco",
    latency: "95ms",
    successRate: "99.9%",
    recommendedChannel: "Zhipu Flash Router",
    hotDeal: true,
    desc: "Le plus économique du marché sur les tâches courtes de tri."
  },
  {
    id: "gemini-3.8-flash",
    name: "Gemini 3.8 Flash",
    family: "Google",
    officialPriceIn: 0.75,
    officialPriceOut: 3.75,
    quotaPriceIn: 0.22,
    quotaPriceOut: 0.95,
    tier: "direct",
    latency: "130ms",
    successRate: "99.9%",
    recommendedChannel: "Google Vertex EU Direct",
    hotDeal: false,
    desc: "Fenêtre de contexte géante 1M+ tokens à vitesse éclair."
  },
  {
    id: "kimi-k3",
    name: "Kimi K3 (Moonshot Long-Context)",
    family: "Moonshot",
    officialPriceIn: 3.00,
    officialPriceOut: 15.00,
    quotaPriceIn: 1.10,
    quotaPriceOut: 4.90,
    tier: "s-grade",
    latency: "260ms",
    successRate: "99.5%",
    recommendedChannel: "Moonshot Sail Tier",
    hotDeal: false,
    desc: "Excellence sur la recherche web et la lecture de longs documents."
  },
  {
    id: "hy4-preview",
    name: "HY4 Preview (Tencent Hunyuan)",
    family: "Tencent",
    officialPriceIn: 0.834,
    officialPriceOut: 2.501,
    quotaPriceIn: 0.35,
    quotaPriceOut: 1.10,
    tier: "s-grade",
    latency: "220ms",
    successRate: "99.2%",
    recommendedChannel: "Tencent Cloud Direct",
    hotDeal: false,
    desc: "Moteur Hunyuan nouvelle génération pour l'analyse logique."
  },
  {
    id: "qwen3.8-flash",
    name: "Qwen 3.8 Flash (Alibaba Cloud)",
    family: "Alibaba",
    officialPriceIn: 0.15,
    officialPriceOut: 0.47,
    quotaPriceIn: 0.05,
    quotaPriceOut: 0.16,
    tier: "eco",
    latency: "105ms",
    successRate: "99.8%",
    recommendedChannel: "Alibaba Bailian Cloud",
    hotDeal: true,
    desc: "Rapport performance/prix exceptionnel en code et instruction following."
  },
  {
    id: "claude-3-7-sonnet",
    name: "Claude 3.7 Sonnet (Thinking)",
    family: "Anthropic",
    officialPriceIn: 3.00,
    officialPriceOut: 15.00,
    quotaPriceIn: 1.20,
    quotaPriceOut: 5.40,
    tier: "direct",
    latency: "290ms",
    successRate: "99.9%",
    recommendedChannel: "AWS Bedrock / Direct Anthropic",
    hotDeal: false,
    desc: "La référence mondiale absolue pour le code autonome et Claude Code."
  }
];

// État initial de l'application
const APP_STATE = {
  currentTab: "market",
  searchQuery: "",
  selectedFamily: "all",
  selectedTier: "s-grade",
  currentUser: JSON.parse(localStorage.getItem("quota_user") || '{"id": 1, "username": "baptiste_dev", "balance": 10.00}'),
  userBalance: 10.00,
  glassAlpha: 0.85,
  keys: []
};

// INITIALISATION DOM
document.addEventListener("DOMContentLoaded", () => {
  initAuth();
  initTabs();
  initMarket();
  initKeysTable();
  initWallet();
  initPlayground();
  initGlassControl();
});

/* =========================================================================
   AUTHENTIFICATION & UTILISATEUR
   ========================================================================= */
function initAuth() {
  const authModal = document.getElementById("modal-auth");
  const authBtn = document.getElementById("btn-open-auth-modal");
  const authBtnLabel = document.getElementById("auth-btn-label");
  const tabLogin = document.getElementById("tab-auth-login");
  const tabRegister = document.getElementById("tab-auth-register");
  const authTitle = document.getElementById("auth-modal-title");
  const authSubmit = document.getElementById("btn-submit-auth");
  const authForm = document.getElementById("form-auth");
  const authError = document.getElementById("auth-error-msg");

  let authMode = "login"; // 'login' ou 'register'

  function updateAuthUI() {
    if (APP_STATE.currentUser && APP_STATE.currentUser.username) {
      authBtnLabel.textContent = APP_STATE.currentUser.username;
      document.getElementById("user-balance").textContent = `$${APP_STATE.currentUser.balance.toFixed(2)}`;
      loadUserData();
    } else {
      authBtnLabel.textContent = "Connexion";
    }
  }

  authBtn.addEventListener("click", () => {
    authError.hidden = true;
    authModal.showModal();
  });

  document.getElementById("btn-close-auth-modal").addEventListener("click", () => authModal.close());
  document.getElementById("btn-cancel-auth").addEventListener("click", () => authModal.close());

  tabLogin.addEventListener("click", (e) => {
    e.preventDefault();
    authMode = "login";
    tabLogin.classList.add("active");
    tabRegister.classList.remove("active");
    authTitle.textContent = "Connexion Espace Dev";
    authSubmit.textContent = "Se Connecter";
    authError.hidden = true;
  });

  tabRegister.addEventListener("click", (e) => {
    e.preventDefault();
    authMode = "register";
    tabRegister.classList.add("active");
    tabLogin.classList.remove("active");
    authTitle.textContent = "Créer un Compte (+10$ de Crédit)";
    authSubmit.textContent = "Créer mon Compte";
    authError.hidden = true;
  });

  // OAuth Google & GitHub
  document.getElementById("btn-oauth-google").addEventListener("click", () => {
    const email = prompt("Connexion Google OAuth 2.0 (Simulation) :\nEntrez votre adresse Gmail :", "baptiste@gmail.com");
    if (email && email.includes("@")) {
      const username = email.split("@")[0];
      APP_STATE.currentUser = { id: 101, username: username, balance: 10.00, email: email };
      localStorage.setItem("quota_user", JSON.stringify(APP_STATE.currentUser));
      updateAuthUI();
      authModal.close();
      alert(`🎉 Connecté avec succès via Google (${email}) !`);
    }
  });

  document.getElementById("btn-oauth-github").addEventListener("click", () => {
    const ghUser = prompt("Connexion GitHub OAuth (Simulation) :\nEntrez votre pseudo GitHub :", "Raknaos");
    if (ghUser) {
      APP_STATE.currentUser = { id: 102, username: ghUser, balance: 10.00, github: ghUser };
      localStorage.setItem("quota_user", JSON.stringify(APP_STATE.currentUser));
      updateAuthUI();
      authModal.close();
      alert(`🎉 Connecté avec succès via GitHub (@${ghUser}) !`);
    }
  });

  authForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("auth-username").value.trim();
    const password = document.getElementById("auth-password").value.trim();

    authSubmit.disabled = true;
    authSubmit.textContent = "Traitement...";

    const endpoint = authMode === "login" ? "/api/auth/login" : "/api/auth/register";

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password })
      });
      const data = await res.json();

      if (data.status === "success") {
        APP_STATE.currentUser = data.user;
        localStorage.setItem("quota_user", JSON.stringify(data.user));
        updateAuthUI();
        authModal.close();
        alert(`Bienvenue ${data.user.username} ! Votre compte est opérationnel.`);
      } else {
        authError.textContent = data.error || "Erreur d'authentification";
        authError.hidden = false;
      }
    } catch (err) {
      authError.textContent = "Impossible de joindre le serveur d'authentification.";
      authError.hidden = false;
    } finally {
      authSubmit.disabled = false;
      authSubmit.textContent = authMode === "login" ? "Se Connecter" : "Créer mon Compte";
    }
  });

  updateAuthUI();
}

async function loadUserData() {
  if (!APP_STATE.currentUser || !APP_STATE.currentUser.id) return;
  try {
    const res = await fetch(`/api/user/${APP_STATE.currentUser.id}`);
    if (res.ok) {
      const data = await res.json();
      APP_STATE.currentUser.balance = data.balance;
      document.getElementById("user-balance").textContent = `$${data.balance.toFixed(2)}`;
      
      if (data.keys && data.keys.length > 0) {
        APP_STATE.keys = data.keys.map(k => ({
          id: `key-${k.id}`,
          name: k.name,
          keyMasked: `${k.key.slice(0, 10)}...${k.key.slice(-4)}`,
          fullKey: k.key,
          limit: k.limit,
          spent: k.spent,
          createdAt: k.created_at ? k.created_at.slice(0, 10) : "2026-09-07",
          status: "active"
        }));
        renderKeysTable();
      }
    }
  } catch (e) {
    // Mode local ou hors-ligne
  }
}

/* =========================================================================
   NAVIGATION PAR ONGLETS
   ========================================================================= */
function initTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  tabs.forEach(tab => {
    tab.addEventListener("click", () => {
      tabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      const target = tab.dataset.tab;
      
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
      const activePane = document.getElementById(`tab-${target}`);
      if (activePane) activePane.classList.add("active");
    });
  });

  // Clic sur le solde dans la topbar -> ouvre l'onglet recharge
  document.getElementById("balance-badge").addEventListener("click", () => {
    document.querySelector('.nav-tab[data-tab="wallet"]').click();
  });
}

/* =========================================================================
   CATALOGUE DU MARCHÉ (MODÈLES & FILTRAGE)
   ========================================================================= */
function initMarket() {
  renderHotTicker();
  renderMarketTable();

  // Search input
  const searchInput = document.getElementById("model-search-input");
  const clearBtn = document.getElementById("clear-search");
  
  searchInput.addEventListener("input", (e) => {
    APP_STATE.searchQuery = e.target.value.toLowerCase().trim();
    clearBtn.hidden = APP_STATE.searchQuery.length === 0;
    renderMarketTable();
  });

  clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    APP_STATE.searchQuery = "";
    clearBtn.hidden = true;
    renderMarketTable();
  });

  // Famille Filter Pills
  document.querySelectorAll("#family-filter .filter-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      document.querySelectorAll("#family-filter .filter-pill").forEach(p => p.classList.remove("active"));
      pill.classList.add("active");
      APP_STATE.selectedFamily = pill.dataset.family;
      renderMarketTable();
    });
  });

  // Tier Selector Dropdown
  document.getElementById("channel-tier-select").addEventListener("change", (e) => {
    APP_STATE.selectedTier = e.target.value;
    renderMarketTable();
  });
}

function renderHotTicker() {
  const tickerContainer = document.getElementById("hot-ticker-list");
  const hotModels = MODELS_CATALOG.filter(m => m.hotDeal);

  tickerContainer.innerHTML = hotModels.map(m => {
    const savePercent = Math.round((1 - (m.quotaPriceIn / m.officialPriceIn)) * 100);
    return `
      <div class="ticker-item" onclick="selectModelInPlayground('${m.id}')">
        <span class="ticker-model-name">${m.id}</span>
        <span class="ticker-price">$${m.quotaPriceIn.toFixed(3)}/1M</span>
        <span class="ticker-discount-badge">-${savePercent}%</span>
      </div>
    `;
  }).join("");
}

function renderMarketTable() {
  const tbody = document.getElementById("models-table-body");
  const emptyState = document.getElementById("no-models-found");

  const filtered = MODELS_CATALOG.filter(m => {
    // Filtre texte
    const matchSearch = APP_STATE.searchQuery === "" || 
      m.id.toLowerCase().includes(APP_STATE.searchQuery) ||
      m.name.toLowerCase().includes(APP_STATE.searchQuery) ||
      m.family.toLowerCase().includes(APP_STATE.searchQuery);

    // Filtre famille
    const matchFamily = APP_STATE.selectedFamily === "all" || m.family === APP_STATE.selectedFamily;

    // Filtre tier
    const matchTier = APP_STATE.selectedTier === "all" || m.tier === APP_STATE.selectedTier;

    return matchSearch && matchFamily && matchTier;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = "";
    emptyState.hidden = false;
    return;
  }

  emptyState.hidden = true;
  tbody.innerHTML = filtered.map(m => {
    const savePercent = Math.round((1 - (m.quotaPriceIn / m.officialPriceIn)) * 100);
    const isHuge = savePercent >= 75;

    return `
      <tr>
        <td>
          <div class="model-title-cell">
            <span class="model-name">${m.name}</span>
            <span class="model-id-tag">${m.id}</span>
          </div>
        </td>
        <td>
          <span class="provider-badge">${m.family}</span>
        </td>
        <td>
          <div class="official-price-cell">
            In: $${m.officialPriceIn.toFixed(2)} / Out: $${m.officialPriceOut.toFixed(2)}
          </div>
        </td>
        <td>
          <div class="quota-price-cell">
            <span class="quota-price-main">In: $${m.quotaPriceIn.toFixed(3)} / Out: $${m.quotaPriceOut.toFixed(3)}</span>
            <span class="quota-price-sub">par million de tokens</span>
          </div>
        </td>
        <td>
          <span class="discount-badge ${isHuge ? 'huge' : ''}">-${savePercent}%</span>
        </td>
        <td>
          <div class="quality-cell">
            <span class="success-rate-tag">✓ ${m.successRate}</span>
            <span class="latency-tag">⚡ ${m.latency} P50</span>
          </div>
        </td>
        <td>
          <span class="channel-tag">${m.recommendedChannel}</span>
        </td>
        <td style="text-align: right;">
          <button class="action-btn" onclick="selectModelInPlayground('${m.id}')">Tester</button>
        </td>
      </tr>
    `;
  }).join("");
}

/* =========================================================================
   GESTION DES CLÉS API
   ========================================================================= */
function initKeysTable() {
  renderKeysTable();

  const createModal = document.getElementById("modal-create-key");
  const createdModal = document.getElementById("modal-key-created");

  document.getElementById("open-create-key-modal").addEventListener("click", () => {
    document.getElementById("key-name-input").value = "";
    document.getElementById("key-limit-input").value = "";
    createModal.showModal();
  });

  document.getElementById("btn-close-modal").addEventListener("click", () => createModal.close());
  document.getElementById("btn-cancel-key").addEventListener("click", () => createModal.close());

  document.getElementById("form-create-key").addEventListener("submit", (e) => {
    e.preventDefault();
    const name = document.getElementById("key-name-input").value.trim();
    const limit = parseFloat(document.getElementById("key-limit-input").value) || 100;
    
    // Génération d'une vraie clé aléatoire formatée
    const randHex = Array.from(crypto.getRandomValues(new Uint8Array(16)))
      .map(b => b.toString(16).padStart(2, '0')).join('');
    const fullKey = `sk-quota-live-${randHex}`;
    const keyMasked = `sk-quota-live-${randHex.slice(0, 4)}...${randHex.slice(-4)}`;

    const newKey = {
      id: `key-${Date.now()}`,
      name: name,
      keyMasked: keyMasked,
      fullKey: fullKey,
      limit: limit,
      spent: 0.00,
      createdAt: new Date().toISOString().slice(0, 10),
      status: "active"
    };

    APP_STATE.keys.unshift(newKey);
    renderKeysTable();
    createModal.close();

    // Affiche le modal de clé créée
    document.getElementById("newly-created-key-val").value = fullKey;
    createdModal.showModal();
  });

  document.getElementById("btn-close-created-modal").addEventListener("click", () => createdModal.close());
  document.getElementById("btn-done-created").addEventListener("click", () => createdModal.close());

  document.getElementById("btn-copy-new-key").addEventListener("click", () => {
    const keyVal = document.getElementById("newly-created-key-val").value;
    navigator.clipboard.writeText(keyVal);
    const btn = document.getElementById("btn-copy-new-key");
    btn.textContent = "✓ Copié !";
    setTimeout(() => btn.textContent = "Copier", 2000);
  });

  // Global copy buttons
  document.querySelectorAll(".copy-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      const textToCopy = e.target.dataset.copy;
      if (textToCopy) {
        navigator.clipboard.writeText(textToCopy);
        const prevText = e.target.textContent;
        e.target.textContent = "✓ Copié";
        setTimeout(() => e.target.textContent = prevText, 1800);
      }
    });
  });
}

function renderKeysTable() {
  const tbody = document.getElementById("keys-table-body");
  const countBadge = document.getElementById("keys-count-badge");
  countBadge.textContent = `${APP_STATE.keys.length} clé${APP_STATE.keys.length > 1 ? 's' : ''} active${APP_STATE.keys.length > 1 ? 's' : ''}`;

  tbody.innerHTML = APP_STATE.keys.map(k => `
    <tr>
      <td><strong>${k.name}</strong></td>
      <td><span class="key-code">${k.keyMasked}</span></td>
      <td>$${k.spent.toFixed(2)} / $${k.limit.toFixed(2)}</td>
      <td>${k.createdAt}</td>
      <td><span class="status-tag active">● Actif</span></td>
      <td style="text-align: right;">
        <button class="ghost-btn" onclick="copyFullKey('${k.id}')">Copier</button>
        <button class="ghost-btn" style="color:#e11d48;" onclick="revokeKey('${k.id}')">Révoquer</button>
      </td>
    </tr>
  `).join("");
}

window.copyFullKey = function(keyId) {
  const keyObj = APP_STATE.keys.find(k => k.id === keyId);
  if (keyObj) {
    navigator.clipboard.writeText(keyObj.fullKey);
    alert(`Clé [${keyObj.name}] copiée dans le presse-papier.`);
  }
};

window.revokeKey = function(keyId) {
  if (confirm("Êtes-vous sûr de vouloir révoquer définitivement cette clé API ?")) {
    APP_STATE.keys = APP_STATE.keys.filter(k => k.id !== keyId);
    renderKeysTable();
  }
};

/* =========================================================================
   PORTEFEUILLE & CALCULS DE RECHARGE
   ========================================================================= */
function initWallet() {
  const tierCards = document.querySelectorAll(".tier-card");
  const rechargeBtnSum = document.getElementById("recharge-btn-sum");
  const rechargeBtn = document.getElementById("btn-proceed-recharge");

  tierCards.forEach(card => {
    card.addEventListener("click", () => {
      tierCards.forEach(c => c.classList.remove("selected"));
      card.classList.add("selected");
      
      const amount = card.dataset.amount;
      const discount = parseFloat(card.dataset.discount) || 0;

      if (amount === "custom") {
        const customVal = prompt("Indiquez le montant de recharge souhaité ($USD) :", "20");
        if (customVal && !isNaN(customVal) && parseFloat(customVal) >= 5) {
          const val = parseFloat(customVal);
          rechargeBtnSum.textContent = `$${val.toFixed(2)}`;
          rechargeBtn.textContent = `Procéder au Rechargement ($${val.toFixed(2)} de crédit)`;
        }
      } else {
        const nominal = parseFloat(amount);
        const toPay = nominal * (1 - (discount / 100));
        rechargeBtnSum.textContent = `$${toPay.toFixed(2)}`;
        rechargeBtn.textContent = `Procéder au Rechargement ($${toPay.toFixed(2)} pour $${nominal} de crédit)`;
      }
    });
  });

  rechargeBtn.addEventListener("click", async () => {
    const selected = document.querySelector(".tier-card.selected");
    const amount = selected ? selected.dataset.amount : "50";
    const discount = selected ? (selected.dataset.discount || 0) : 0;
    const nominal = amount === "custom" ? 20.00 : parseFloat(amount);

    rechargeBtn.disabled = true;
    rechargeBtn.textContent = "Génération de la session de paiement sécurisée...";

    try {
      const res = await fetch("/api/pay/create-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: 1, amount: nominal, discount: parseFloat(discount) })
      });
      const data = await res.json();
      if (data.url) {
        if (data.url.startsWith("http")) {
          window.location.href = data.url;
        } else {
          // Validation de la session de paiement
          const confirmRes = await fetch("/api/pay/confirm", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: data.session_id })
          });
          const confirmData = await confirmRes.json();
          APP_STATE.userBalance = confirmData.new_balance || (APP_STATE.userBalance + nominal);
          document.getElementById("user-balance").textContent = `$${APP_STATE.userBalance.toFixed(2)}`;
          alert(`🎉 Paiement validé ! Votre solde Quota.Hub a été crédité de +$${nominal.toFixed(2)}. Nouveau solde : $${APP_STATE.userBalance.toFixed(2)}`);
        }
      } else {
        alert("Erreur lors de la création de la session de paiement.");
      }
    } catch (err) {
      alert("Erreur de connexion au serveur de paiement.");
    } finally {
      rechargeBtn.disabled = false;
      const toPay = nominal * (1 - (discount / 100));
      rechargeBtn.textContent = `Procéder au Rechargement ($${toPay.toFixed(2)} pour $${nominal} de crédit)`;
    }
  });

  // Code de réduction
  document.getElementById("btn-redeem").addEventListener("click", () => {
    const input = document.getElementById("redeem-input");
    const msg = document.getElementById("redeem-msg");
    const val = input.value.trim().toUpperCase();

    if (val === "QUOTA-WELCOME-2026" || val === "A6API-CHALLENGE") {
      msg.textContent = "✓ Code valide ! $5.00 de crédit offert ajouté immédiatement.";
      msg.style.color = "#15803d";
      msg.hidden = false;
      APP_STATE.userBalance += 5.00;
      document.getElementById("user-balance").textContent = `$${APP_STATE.userBalance.toFixed(2)}`;
      input.value = "";
    } else {
      msg.textContent = "✕ Code invalide ou expiré.";
      msg.style.color = "#e11d48";
      msg.hidden = false;
    }
  });

  // Transfert commission parrainage
  document.getElementById("btn-transfer-aff").addEventListener("click", () => {
    APP_STATE.userBalance += 12.50;
    document.getElementById("user-balance").textContent = `$${APP_STATE.userBalance.toFixed(2)}`;
    alert("✓ 12.50$ de commissions parrainage transférés directement vers votre solde de tirage API.");
  });
}

/* =========================================================================
   PLAYGROUND & TESTEUR EN DIRECT
   ========================================================================= */
function initPlayground() {
  const modelSelect = document.getElementById("play-model-select");
  modelSelect.innerHTML = MODELS_CATALOG.map(m => `
    <option value="${m.id}">${m.name} [${m.id}]</option>
  `).join("");

  document.getElementById("btn-run-playground").addEventListener("click", runLivePlayground);
  document.getElementById("btn-reset-playground").addEventListener("click", () => {
    document.getElementById("play-user-prompt").value = "";
    document.getElementById("playground-output").textContent = "Cliquez sur « Exécuter la Requête » pour tester en direct.";
    document.getElementById("response-meta").textContent = "Prêt";
  });

  // Snippets tabs
  const snippetTabs = document.querySelectorAll("#snippet-lang-tabs .mini-tab");
  snippetTabs.forEach(tab => {
    tab.addEventListener("click", () => {
      snippetTabs.forEach(t => t.classList.remove("active"));
      tab.classList.add("active");
      updateSnippetCode(tab.dataset.lang);
    });
  });

  document.getElementById("btn-copy-snippet").addEventListener("click", () => {
    const code = document.getElementById("snippet-code-content").textContent;
    navigator.clipboard.writeText(code);
    const btn = document.getElementById("btn-copy-snippet");
    btn.textContent = "✓ Copié";
    setTimeout(() => btn.textContent = "Copier", 1800);
  });
}

window.selectModelInPlayground = function(modelId) {
  document.querySelector('.nav-tab[data-tab="playground"]').click();
  const select = document.getElementById("play-model-select");
  if (select) {
    select.value = modelId;
    updateSnippetCode("curl");
  }
};

function runLivePlayground() {
  const modelId = document.getElementById("play-model-select").value;
  const prompt = document.getElementById("play-user-prompt").value.trim();
  const meta = document.getElementById("response-meta");
  const output = document.getElementById("playground-output");

  if (!prompt) {
    alert("Veuillez saisir une invite de test.");
    return;
  }

  meta.textContent = "⚡ Routage vers le canal S-Grade en cours...";
  output.textContent = "En attente du premier token...";

  setTimeout(() => {
    const modelObj = MODELS_CATALOG.find(m => m.id === modelId);
    meta.textContent = `200 OK · Latence : ${modelObj ? modelObj.latency : '135ms'} · Coût calculé : $0.000084`;
    output.textContent = `[Réponse simulée de ${modelId}] :\n\n` +
      `Voici les 3 arguments majeurs pour héberger un cluster d'agents IA via une passerelle unifiée comme Quota.Hub :\n\n` +
      `1. Économie d'échelle drastique : Accédez à des remises de gros (-70% à -90%) impossibles à obtenir avec des cartes bancaires individuelles chez chaque fournisseur.\n` +
      `2. Zéro interruption de service : Bascule instantanée en cas de panne d'un canal (Azure -> Spot -> Direct) sans que vos agents ne crashent.\n` +
      `3. Gouvernance unifiée : Une seule clé maîtresse avec plafonds stricts pour surveiller 100% de votre flotte sans disperser vos identifiants.`;
  }, 450);
}

function updateSnippetCode(lang) {
  const modelId = document.getElementById("play-model-select") ? document.getElementById("play-model-select").value : "gpt-6-astra";
  const title = document.getElementById("snippet-header-title");
  const codeBox = document.getElementById("snippet-code-content");

  if (lang === "curl") {
    title.textContent = "Appel cURL direct";
    codeBox.textContent = `curl https://api.quotahub.eu/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer sk-quota-live-prod" \\
  -d '{
    "model": "${modelId}",
    "messages": [{"role": "user", "content": "Bonjour !"}],
    "stream": false
  }'`;
  } else if (lang === "python") {
    title.textContent = "SDK OpenAI Python";
    codeBox.textContent = `from openai import OpenAI

client = OpenAI(
    base_url="https://api.quotahub.eu/v1",
    api_key="sk-quota-live-prod"
)

response = client.chat.completions.create(
    model="${modelId}",
    messages=[{"role": "user", "content": "Bonjour !"}]
)
print(response.choices[0].message.content)`;
  } else if (lang === "node") {
    title.textContent = "SDK OpenAI Node.js / TypeScript";
    codeBox.textContent = `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.quotahub.eu/v1",
  apiKey: "sk-quota-live-prod",
});

const completion = await client.chat.completions.create({
  model: "${modelId}",
  messages: [{ role: "user", content: "Bonjour !" }],
});
console.log(completion.choices[0].message.content);`;
  }
}

/* =========================================================================
   CONTROLEUR D'OPACITÉ DU VERRE (HERITÉ DE QUOTA GLASS)
   ========================================================================= */
function initGlassControl() {
  const slider = document.getElementById("glass-alpha-slider");
  const label = document.getElementById("glass-alpha-label");

  slider.addEventListener("input", (e) => {
    const val = parseFloat(e.target.value);
    APP_STATE.glassAlpha = val;
    document.documentElement.style.setProperty("--glass-alpha", val);
    label.textContent = `${Math.round(val * 100)}%`;
  });
}
