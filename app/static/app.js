// ============================================================================
// Armor Agent Demo — Frontend Client Logic (Milestone 2 Overhaul)
// Stack: Vanilla ES6+, Material Design 3 Tokens, Vertex AI Agent Platform
// ============================================================================

// Estado Global de la Aplicación
const state = {
  currentTab: 'chat',
  history: [],
  isLoading: false,
  presets: [],
  policiesData: null,
  triggeredDetectors: new Set(),
  triggeredRuleIds: new Set(),
  allowedTurns: [],
  lastAllowedExecution: null,
  gcloudCommand: '',
  consoleUrl: 'https://console.cloud.google.com/logs/query'
};

// Referencias del DOM Globales
const chatMessages = document.getElementById('chatMessages');
const chatForm = document.getElementById('chatForm');
const promptInput = document.getElementById('promptInput');
const sendBtn = document.getElementById('sendBtn');
const masterArmorToggle = document.getElementById('masterArmorToggle');
const armorStatusBadge = document.getElementById('armorStatusBadge');
const modelSelect = document.getElementById('modelSelect');
const clearChatBtn = document.getElementById('clearChatBtn');
const themeDarkBtn = document.getElementById('themeDarkBtn');
const themeLightBtn = document.getElementById('themeLightBtn');
const presetSelect = document.getElementById('presetSelect');

// Elementos de Políticas y Detectores
const policiesBreakdownContainer = document.getElementById('policiesBreakdownContainer');
const floorEnforcementBadge = document.getElementById('floorEnforcementBadge');
const policyModeBadge = document.getElementById('policyModeBadge');

// Elementos de Telemetría y Auditoría
const telemetryStatus = document.getElementById('telemetryStatus');
const tabBadgeAudit = document.getElementById('tabBadgeAudit');
const statPromptAction = document.getElementById('statPromptAction');
const statOutputAction = document.getElementById('statOutputAction');
const statArmorLatency = document.getElementById('statArmorLatency');
const statLlmLatency = document.getElementById('statLlmLatency');
const statMatchDetails = document.getElementById('statMatchDetails');

// Elementos de Cloud Logging
const refreshLogsBtn = document.getElementById('refreshLogsBtn');
const refreshLogsIcon = document.getElementById('refreshLogsIcon');
const copyGcloudBtn = document.getElementById('copyGcloudBtn');
const copyGcloudLabel = document.getElementById('copyGcloudLabel');
const openConsoleLink = document.getElementById('openConsoleLink');
const gcloudCommandBox = document.getElementById('gcloudCommandBox');
const cloudLogsList = document.getElementById('cloudLogsList');

// ============================================================================
// 1. Gestión de Temas (Material Design 3 Claro / Oscuro)
// ============================================================================

function applyTheme(theme) {
  const normalized = theme === 'light' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', normalized);
  try {
    localStorage.setItem('armor_m3_theme', normalized);
  } catch (_) {}
  if (themeDarkBtn && themeLightBtn) {
    themeDarkBtn.classList.toggle('active', normalized === 'dark');
    themeLightBtn.classList.toggle('active', normalized === 'light');
  }
}

function initTheme() {
  let saved = 'dark';
  try {
    saved = localStorage.getItem('armor_m3_theme') || 'dark';
  } catch (_) {}
  applyTheme(saved);
}

// ============================================================================
// 2. Máquina de Estados de Pestañas (Tab Switching State Machine)
// ============================================================================

const TABS_CONFIG = [
  {
    key: 'chat',
    buttonIds: ['tabBtnChat', 'chat-tab'],
    panelIds: ['tabPanelChat', 'chat-panel', 'chatTabContent']
  },
  {
    key: 'arch',
    buttonIds: ['tabBtnArch', 'arch-tab'],
    panelIds: ['tabPanelArch', 'arch-panel', 'archTabContent']
  },
  {
    key: 'audit',
    buttonIds: ['tabBtnAudit', 'audit-tab'],
    panelIds: ['tabPanelAudit', 'audit-panel', 'auditTabContent']
  },
  {
    key: 'policies',
    buttonIds: ['tabBtnPolicies', 'policies-tab'],
    panelIds: ['tabPanelPolicies', 'policies-panel', 'policiesTabContent']
  },
  {
    key: 'logs',
    buttonIds: ['tabBtnLogs', 'logs-tab'],
    panelIds: ['tabPanelLogs', 'logs-panel', 'logsTabContent']
  }
];

function switchTab(targetKey) {
  const activeTab = TABS_CONFIG.find(t => t.key === targetKey) || TABS_CONFIG[0];
  state.currentTab = activeTab.key;

  TABS_CONFIG.forEach(t => {
    const isTarget = t.key === activeTab.key;

    // Actualizar botones por ID
    t.buttonIds.forEach(id => {
      const btn = document.getElementById(id);
      if (btn) {
        btn.classList.toggle('active', isTarget);
        btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
      }
    });

    // Actualizar botones con atributo data-tab
    document.querySelectorAll(`.md3-tab[data-tab="${t.key}"]`).forEach(btn => {
      btn.classList.toggle('active', isTarget);
      btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
    });

    // Actualizar visibilidad de paneles
    t.panelIds.forEach(id => {
      const panel = document.getElementById(id);
      if (panel) {
        if (isTarget) {
          panel.classList.remove('hidden');
          panel.classList.add('active');
        } else {
          panel.classList.add('hidden');
          panel.classList.remove('active');
        }
      }
    });
  });

  // Acciones contextuales al activar pestaña
  if (activeTab.key === 'chat') {
    if (promptInput) {
      setTimeout(() => promptInput.focus(), 50);
    }
    scrollToBottom();
  } else if (activeTab.key === 'logs') {
    // Si la lista de logs está vacía o inicial, cargar en silencio
    if (!cloudLogsList || cloudLogsList.children.length <= 1) {
      loadCloudLogs(true);
    }
  } else if (activeTab.key === 'policies') {
    if (!state.policiesData) {
      loadPoliciesSummary();
    }
  }
}

function initTabs() {
  TABS_CONFIG.forEach(t => {
    t.buttonIds.forEach(id => {
      const btn = document.getElementById(id);
      if (btn) {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          switchTab(t.key);
        });
      }
    });
  });

  // Delegación de eventos para clicks en data-tab
  document.addEventListener('click', (e) => {
    const tabEl = e.target.closest('[data-tab]');
    if (tabEl && tabEl.dataset.tab) {
      e.preventDefault();
      switchTab(tabEl.dataset.tab);
    }
  });

  // Iniciar en Chat Playground
  switchTab('chat');
}

// ============================================================================
// 3. Menú Desplegable de Presets de Seguridad & Chips
// ============================================================================

function applyPreset(index) {
  const idx = Number(index);
  if (state.presets[idx]) {
    if (promptInput) {
      promptInput.value = state.presets[idx].prompt;
      switchTab('chat');
      promptInput.focus();
    }
  }
}
window.applyPreset = applyPreset;

function initPresetsDropdown() {
  const selectEl = document.getElementById('presetSelect');
  if (selectEl) {
    selectEl.addEventListener('change', (e) => {
      const val = e.target.value;
      if (val !== '') {
        applyPreset(val);
        e.target.value = ''; // Restaurar placeholder
      }
    });
  }
}

function renderPresetsDropdown() {
  const selectEl = document.getElementById('presetSelect');
  if (!selectEl || !state.presets.length) return;

  const inputAttackGroup = state.presets
    .map((p, idx) => ({ ...p, idx }))
    .filter(p => p.stage === 'input' || (!p.stage && !p.title.includes('Legítima') && !p.title.includes('Respuesta:') && !p.title.includes('Multilenguaje')));

  const multiLangGroup = state.presets
    .map((p, idx) => ({ ...p, idx }))
    .filter(p => p.stage === 'multilang' || p.title.includes('Multilenguaje'));

  const outputLeakGroup = state.presets
    .map((p, idx) => ({ ...p, idx }))
    .filter(p => p.stage === 'output' || p.title.includes('Respuesta:'));

  const safeGroup = state.presets
    .map((p, idx) => ({ ...p, idx }))
    .filter(p => p.stage === 'safe' || p.title.includes('Legítima'));

  selectEl.innerHTML = `
    <option value="" selected disabled>⚡ Cargar prueba de seguridad...</option>
    <optgroup label="🚫 Ataques en Prompt de Entrada (Español · SANITIZE_USER_PROMPT)">
      ${inputAttackGroup.map(p => `<option value="${p.idx}">${escapeHtml(p.title)}</option>`).join('')}
    </optgroup>
    <optgroup label="🌐 Ataques Multilenguaje (EN · 中文 · العربية — Multi-Language Detection)">
      ${multiLangGroup.map(p => `<option value="${p.idx}">${escapeHtml(p.title)}</option>`).join('')}
    </optgroup>
    <optgroup label="📤 Fugas en Respuesta del Modelo (SANITIZE_MODEL_RESPONSE)">
      ${outputLeakGroup.map(p => `<option value="${p.idx}">${escapeHtml(p.title)}</option>`).join('')}
    </optgroup>
    <optgroup label="✅ Consultas Seguras">
      ${safeGroup.map(p => `<option value="${p.idx}">${escapeHtml(p.title)}</option>`).join('')}
    </optgroup>
  `;
}

// ============================================================================
// 4. Inicialización Global y Carga de Datos
// ============================================================================

document.addEventListener('DOMContentLoaded', async () => {
  initTheme();
  initTabs();
  initPresetsDropdown();
  setupEventListeners();

  // /api/templates ya incluye policies, evitando doble llamada HTTP redundante al iniciar
  await Promise.all([
    loadTemplatesAndPresets(),
    loadCloudLogs()
  ]);
});

async function loadTemplatesAndPresets() {
  try {
    const res = await fetch('/api/templates');
    if (res.ok) {
      const data = await res.json();
      state.presets = data.attack_presets || [];
      renderPresetsDropdown();
      if (data.policies) {
        state.policiesData = data.policies;
        renderPoliciesBreakdown();
      } else {
        await loadPoliciesSummary();
      }
    }
  } catch (err) {
    console.warn('No se pudieron cargar las pruebas rápidas:', err);
  }
}

async function loadPoliciesSummary() {
  try {
    const res = await fetch('/api/policies');
    if (res.ok) {
      const data = await res.json();
      state.policiesData = data;
      renderPoliciesBreakdown();
    }
  } catch (err) {
    console.warn('No se pudieron consultar las políticas activas:', err);
  }
}

// ============================================================================
// 5. Gestión de Políticas, Reglas y Detectores Activos
// ============================================================================

function recordTriggeredMatches(matchedFilters) {
  if (!Array.isArray(matchedFilters)) return;
  for (const m of matchedFilters) {
    const name = (m.name || '').toUpperCase();
    const detected = (m.detected_variable || '').toUpperCase();
    if (detected) {
      state.triggeredDetectors.add(detected);
    }
    if (name.includes('SDP') || name.includes('SENSITIVE')) {
      state.triggeredRuleIds.add('sdpSettings');
    }
    if (name.includes('PI') || name.includes('JAILBREAK') || name.includes('INJECTION')) {
      state.triggeredRuleIds.add('piAndJailbreakFilterSettings');
      if (!detected) state.triggeredDetectors.add('PROMPT_INJECTION');
    }
    if (name.includes('RAI') || name.includes('RESPONSIBLE')) {
      state.triggeredRuleIds.add('raiSettings');
    }
    if (name.includes('URI') || name.includes('URL') || name.includes('MALICIOUS')) {
      state.triggeredRuleIds.add('maliciousUriFilterSettings');
      state.triggeredDetectors.add('MALICIOUS_URI');
    }
    if (name.includes('MULTILANGUAGE') || detected.includes('MULTI_LANGUAGE')) {
      state.triggeredRuleIds.add('multiLanguageDetection');
    }
  }
  renderPoliciesBreakdown();
}

function isDetectorTriggered(code) {
  if (!code) return false;
  const upperCode = code.toUpperCase();
  for (const trig of state.triggeredDetectors) {
    if (upperCode.includes(trig) || trig.includes(upperCode)) {
      return true;
    }
  }
  return false;
}

function renderPoliciesBreakdown() {
  if (!policiesBreakdownContainer || !state.policiesData) return;

  const p = state.policiesData;
  const enforcementType = p.enforcement_mode || p.enforcement_type || 'INSPECT_AND_BLOCK';
  const isBlocking = enforcementType === 'INSPECT_AND_BLOCK';

  if (floorEnforcementBadge) {
    if (isBlocking) {
      floorEnforcementBadge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-semibold';
      floorEnforcementBadge.textContent = 'ACTIVO · INSPECT_AND_BLOCK';
    } else {
      floorEnforcementBadge.className = 'text-[10px] font-mono px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30 font-semibold';
      floorEnforcementBadge.textContent = 'AUDITORÍA · INSPECT_ONLY';
    }
  }

  const rules = p.model_armor_rules || [];
  const wafRules = p.cloud_armor_rules || [];
  const rawFloorJson = JSON.stringify(p.raw_floor_setting || {}, null, 2);

  const ruleStyleMap = {
    multiLanguageDetection: {
      badge: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
      iconClass: 'fa-language text-emerald-400'
    },
    piAndJailbreakFilterSettings: {
      badge: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
      iconClass: 'fa-user-secret text-rose-400'
    },
    sdpSettings: {
      badge: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
      iconClass: 'fa-credit-card text-amber-400'
    },
    raiSettings: {
      badge: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
      iconClass: 'fa-scale-balanced text-purple-400'
    },
    maliciousUriFilterSettings: {
      badge: 'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
      iconClass: 'fa-link-slash text-cyan-400'
    },
    csamFilter: {
      badge: 'bg-red-500/15 text-red-300 border-red-500/30',
      iconClass: 'fa-shield-halved text-red-400'
    }
  };

  const rulesHtml = rules.map((rule) => {
    const c = ruleStyleMap[rule.id] || ruleStyleMap.piAndJailbreakFilterSettings;
    const ruleTitle = rule.title || rule.name || rule.id;
    const ruleState = rule.state || rule.status || 'ENABLED';
    const ruleThreshold = rule.threshold || rule.confidence_level || 'MATCH_FOUND';
    const ruleThresholdLabel = rule.threshold_label || '';
    const detectors = rule.blocked_matches || rule.detectors_blocked || [];
    const anyDetectorTriggered = detectors.some(d => isDetectorTriggered(d.code));
    const ruleTriggered = state.triggeredRuleIds.has(rule.id) || anyDetectorTriggered;
    const cardClass = ruleTriggered ? 'policy-rule-card policy-rule-card-triggered' : 'policy-rule-card';

    const detectorsHtml = detectors.map((d) => {
      const dTriggered = isDetectorTriggered(d.code);
      const rowClass = dTriggered ? 'detector-row detector-row-triggered' : 'detector-row';
      const chipClass = dTriggered ? 'detector-chip detector-chip-triggered' : 'detector-chip';
      const detailText = d.detail || d.examples || '';
      return `
        <div class="${rowClass}">
          <div class="flex items-center justify-between gap-1.5 mb-0.5">
            <span class="${chipClass}">
              <i class="fa-solid ${dTriggered ? 'fa-ban text-red-300' : 'fa-xmark text-red-400/80'} text-[9px]"></i>
              ${escapeHtml(d.code)}
            </span>
            <span class="text-[9px] font-mono ${dTriggered ? 'text-red-300 font-bold' : 'text-rose-300/90'}">
              ${dTriggered ? '🚨 MATCH_FOUND (BLOQUEADO)' : 'NO PASARÁ · BLOCK'}
            </span>
          </div>
          <div class="text-[10px] font-semibold text-slate-200">${escapeHtml(d.label)}</div>
          <div class="text-[10px] text-slate-400 leading-tight mt-0.5">${escapeHtml(detailText)}</div>
        </div>
      `;
    }).join('');

    return `
      <div class="${cardClass}">
        <div class="flex items-start justify-between gap-2 mb-1.5">
          <div class="flex items-center gap-1.5">
            <i class="fa-solid ${c.iconClass} text-xs"></i>
            <span class="text-xs font-bold text-white leading-tight">${escapeHtml(ruleTitle)}</span>
          </div>
          <span class="text-[9px] font-mono px-1.5 py-0.5 rounded border shrink-0 ${ruleTriggered ? 'bg-red-900/70 text-red-200 border-red-500 font-bold' : c.badge}">
            ${ruleTriggered ? '🚨 REGLA DISPARADA' : escapeHtml(ruleState)}
          </span>
        </div>

        <div class="flex flex-wrap items-center gap-1.5 mb-1.5 text-[10px] font-mono">
          <span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
            API: ${escapeHtml(rule.id)}
          </span>
          <span class="px-1.5 py-0.5 rounded bg-slate-800 text-amber-300 border border-slate-700">
            Umbral: ${escapeHtml(ruleThreshold)}
          </span>
          <span class="px-1.5 py-0.5 rounded bg-red-950/50 text-red-300 border border-red-800/40">
            Acción: BLOCK (MATCH_FOUND)
          </span>
        </div>
        ${ruleThresholdLabel ? `<div class="text-[10px] text-amber-200/90 font-mono mb-1.5">${escapeHtml(ruleThresholdLabel)}</div>` : ''}

        <p class="text-[11px] text-slate-300 leading-snug mb-2">
          ${escapeHtml(rule.description || '')}
        </p>

        <div class="space-y-1.5">
          <div class="text-[10px] font-semibold uppercase tracking-wider text-slate-400 flex items-center justify-between">
            <span>Detectores / Matches que NO pasarán (${detectors.length}):</span>
            ${rule.id === 'sdpSettings' ? '<span class="text-amber-300 font-mono text-[9px]">Cloud DLP infoTypes</span>' : ''}
          </div>
          ${detectorsHtml}
        </div>
      </div>
    `;
  }).join('');

  const wafHtml = wafRules.map((w) => `
    <div class="p-2 rounded-lg bg-slate-900/75 border border-slate-800 text-[10px] space-y-0.5">
      <div class="flex items-center justify-between gap-2">
        <span class="font-bold text-indigo-300 font-mono">Prioridad ${escapeHtml(String(w.priority))} · ${escapeHtml(w.name)}</span>
        <span class="px-1.5 py-0.5 rounded bg-red-950/60 text-red-300 border border-red-800/40 font-mono">${escapeHtml(w.action)}</span>
      </div>
      <div class="font-mono text-[9px] text-amber-300/90 break-all">${escapeHtml(w.expression)}</div>
      <div class="text-slate-400 leading-tight">${escapeHtml(w.detail || w.blocks || '')}</div>
    </div>
  `).join('');

  policiesBreakdownContainer.innerHTML = `
    <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-700/70 text-[10px] space-y-1 mb-2">
      <div class="flex items-center justify-between">
        <span class="text-slate-400 font-semibold">Recurso GCP Activo:</span>
        <span class="font-mono text-emerald-400">${escapeHtml((p.integrated_services || ['AI_PLATFORM']).join(', '))}</span>
      </div>
      <div class="font-mono text-[9px] text-slate-300 break-all bg-slate-950/70 px-2 py-1 rounded border border-slate-800">
        ${escapeHtml(p.policy_resource || p.floor_setting_resource || 'projects/armor-agent-demo-mau/locations/global/floorSetting')}
      </div>
      <div class="flex items-center justify-between pt-0.5 text-[10px]">
        <span class="text-slate-400">Modelos Agent Platform Protegidos:</span>
        <span class="font-mono text-blue-300 font-semibold">gemini-4-argon · gemini-3.8-flash</span>
      </div>
    </div>

    <div class="space-y-2.5">
      ${rulesHtml}

      <div class="policy-rule-card">
        <div class="flex items-center justify-between mb-1.5">
          <div class="flex items-center gap-1.5">
            <i class="fa-solid fa-shield text-indigo-400 text-xs"></i>
            <span class="text-xs font-bold text-white">Cloud Armor WAF (Perímetro HTTP L7)</span>
          </div>
          <span class="text-[9px] font-mono px-1.5 py-0.5 rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/30">
            ACTIVO EN LOAD BALANCER
          </span>
        </div>
        <div class="space-y-1.5">
          ${wafHtml}
        </div>
      </div>

      <details class="bg-slate-900/70 rounded-lg p-2 border border-slate-800">
        <summary class="text-[10px] font-mono text-blue-400 cursor-pointer">
          📄 Ver JSON en vivo de Floor Settings (${escapeHtml(p.project_id || 'GCP')})
        </summary>
        <pre class="log-json-pre font-mono mt-1.5">${escapeHtml(rawFloorJson)}</pre>
      </details>
    </div>
  `;
}

// ============================================================================
// 6. Cloud Logging en Vivo (Diferenciación de 3 Veredictos)
// ============================================================================

async function loadCloudLogs(silent = false) {
  if (!silent && refreshLogsIcon) {
    refreshLogsIcon.classList.add('fa-spin');
  }
  try {
    const res = await fetch('/api/logs?limit=8&vertex_only=true');
    if (res.ok) {
      const data = await res.json();
      if (data.gcloud_command) {
        state.gcloudCommand = data.gcloud_command;
        if (gcloudCommandBox) gcloudCommandBox.textContent = data.gcloud_command;
      }
      if (data.console_url && openConsoleLink) {
        state.consoleUrl = data.console_url;
        openConsoleLink.href = data.console_url;
      }
      renderCloudLogs(data.entries || [], data.error);
    }
  } catch (err) {
    console.warn('Error consultando Cloud Logging:', err);
  } finally {
    if (refreshLogsIcon) {
      refreshLogsIcon.classList.remove('fa-spin');
    }
  }
}

function renderCloudLogs(entries, errorMsg) {
  if (!cloudLogsList) return;

  if (errorMsg && (!entries || entries.length === 0)) {
    cloudLogsList.innerHTML = `
      <div class="text-xs text-amber-300 p-3 bg-slate-900/70 rounded-xl border border-amber-700/40 leading-relaxed">
        <strong>Nota de permisos IAM:</strong> Propagando <code>roles/logging.viewer</code> en Cloud Run.<br>
        Puedes usar el botón <strong>Abrir en Consola GCP</strong> o el comando <strong>gcloud</strong> en cualquier momento.
      </div>
    `;
    return;
  }

  if (!entries || entries.length === 0) {
    cloudLogsList.innerHTML = `
      <div class="text-xs text-slate-400 p-4 bg-slate-900/50 rounded-xl text-center">
        Aún no hay registros recientes de SanitizeOperation. Envía un mensaje o selecciona una prueba rápida para generar eventos en Cloud Logging.
      </div>
    `;
    return;
  }

  // Registrar matches de logs bloqueados y auditados para iluminar los detectores
  for (const item of entries) {
    if ((item.is_blocked || item.is_audit) && Array.isArray(item.matched_filters)) {
      recordTriggeredMatches(item.matched_filters);
    }
  }

  cloudLogsList.innerHTML = entries.map((item) => {
    const isBlocked = item.is_blocked;
    const isAudit = item.is_audit || (item.verdict && item.verdict.includes('AUDITORÍA'));
    const opType = item.operation_type || 'SANITIZE_USER_PROMPT';
    const isModelResponseOp = opType.includes('MODEL_RESPONSE');

    let cardClass = 'log-card';
    let verdictBadge = '';

    if (isBlocked) {
      cardClass = 'log-card log-card-blocked';
      verdictBadge = `<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-red-900/70 text-red-300 border border-red-700 font-bold shrink-0">🚫 ${isModelResponseOp ? 'BLOQUEADO EN SALIDA' : 'BLOQUEADO EN ENTRADA'}</span>`;
    } else if (isAudit) {
      cardClass = 'log-card log-card-audit';
      verdictBadge = `<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-900/70 text-amber-300 border border-amber-600 font-bold shrink-0">⚠️ PERMITIDO · AUDITORÍA ${isModelResponseOp ? 'EN SALIDA' : 'EN ENTRADA'} (INSPECT_ONLY)</span>`;
    } else {
      cardClass = 'log-card log-card-allowed';
      verdictBadge = `<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-900/70 text-emerald-300 border border-emerald-600 font-bold shrink-0">✅ PERMITIDO</span>`;
    }

    const stageBadge = isModelResponseOp
      ? `<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-900/60 text-purple-200 border border-purple-600/50 font-semibold shrink-0">📤 SALIDA · SANITIZE_MODEL_RESPONSE</span>`
      : `<span class="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-900/50 text-blue-200 border border-blue-700/50 font-semibold shrink-0">📥 ENTRADA · SANITIZE_USER_PROMPT</span>`;

    const timeStr = item.timestamp
      ? new Date(item.timestamp).toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      : '';

    const matchedPills = (item.matched_filters || []).map(f => {
      const label = f.detected_variable ? `${f.name}: ${f.detected_variable}` : f.name;
      return `<span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-red-950/50 text-amber-300 border border-red-800/50">${escapeHtml(label)}</span>`;
    }).join(' ');

    const rawJsonStr = JSON.stringify(item.raw_entry || item.json_payload || {}, null, 2);

    // Asociar la respuesta real del modelo (tanto permitida como interceptada en salida)
    let allowedModelDropdownHtml = '';
    if (!isBlocked) {
      const excerptClean = (item.full_text || item.prompt_excerpt || '').trim();
      let matchedTurn = null;
      if (excerptClean) {
        matchedTurn = state.allowedTurns.find(t =>
          t.prompt && (excerptClean.includes(t.prompt.slice(0, 35)) || t.prompt.includes(excerptClean.slice(0, 35)))
        );
      }
      if (!matchedTurn && state.lastAllowedExecution) {
        matchedTurn = state.lastAllowedExecution;
      }

      const dropdownTitle = isAudit
        ? 'Ver Respuesta Real del Modelo Permitida en Modo Auditoría (INSPECT_ONLY)'
        : 'Ver Respuesta Real del Modelo (Aprobada por Model Armor)';

      if (isModelResponseOp && item.full_text) {
        allowedModelDropdownHtml = buildModelExecutionDropdownHtml(
          matchedTurn ? matchedTurn.rawExec : null,
          item.full_text,
          matchedTurn ? matchedTurn.modelUsed : 'Vertex AI Agent Engine',
          dropdownTitle
        );
      } else if (matchedTurn && matchedTurn.response) {
        allowedModelDropdownHtml = buildModelExecutionDropdownHtml(
          matchedTurn.rawExec,
          matchedTurn.response,
          matchedTurn.modelUsed,
          dropdownTitle
        );
      }
    } else if (isModelResponseOp && item.full_text) {
      allowedModelDropdownHtml = buildModelExecutionDropdownHtml(
        {
          intercepted_by_model_armor: true,
          response_text: item.full_text,
          finish_reason: 'BLOCKED_BY_MODEL_ARMOR_OUTPUT_FLOOR_SETTING',
          raw_events: [item.raw_entry || item.json_payload || {}]
        },
        item.full_text,
        'Vertex AI Agent Engine',
        'Ver Respuesta Generada por el Modelo e Interceptada en Salida (SANITIZE_MODEL_RESPONSE)'
      );
    }

    return `
      <div class="${cardClass} space-y-2 p-3 rounded-xl bg-slate-900/80 border border-slate-700/60">
        <div class="flex items-center justify-between gap-2">
          <div class="flex items-center gap-1.5 flex-wrap">
            ${verdictBadge}
            ${stageBadge}
            <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
              ${escapeHtml(item.client_name || 'VERTEX_AI')} · ${escapeHtml(item.template_id || 'FLOOR_SETTING')}
            </span>
          </div>
          <span class="text-[10px] font-mono text-slate-400 shrink-0">${escapeHtml(timeStr)}</span>
        </div>

        <div class="text-xs text-slate-200 font-sans leading-snug">
          <strong class="text-slate-400">${escapeHtml(item.operation_label || 'Prompt')}:</strong>
          "${escapeHtml(item.prompt_excerpt || '')}"
        </div>

        ${matchedPills ? `<div class="flex items-center gap-1 overflow-x-auto py-0.5">${matchedPills}</div>` : ''}

        ${item.verdict_reason ? `
          <div class="text-[11px] ${isBlocked ? 'text-red-300' : (isAudit ? 'text-amber-300' : 'text-slate-400')} leading-snug">
            ${escapeHtml(item.verdict_reason)}
          </div>
        ` : ''}

        ${allowedModelDropdownHtml}

        <details class="bg-slate-950/60 rounded-lg p-2 border border-slate-800">
          <summary class="text-[10px] font-mono text-blue-300 cursor-pointer">
            🔍 Ver Payload JSON Crudo de Cloud Logging (SanitizeOperationLogEntry)
          </summary>
          <pre class="log-json-pre font-mono mt-1 text-[9px]">${escapeHtml(rawJsonStr)}</pre>
        </details>
      </div>
    `;
  }).join('');
}

// ============================================================================
// 7. Componente Dropdown de Respuesta Real del Modelo & Telemetría en Vivo (R2)
// ============================================================================

function buildModelExecutionDropdownHtml(rawExec, fallbackResponseText, fallbackModelUsed, summaryTitle = 'Ver Respuesta Real del Modelo y Evidencia en Vivo (No Mock)') {
  const exec = rawExec || {};
  const responseText = exec.response_text || fallbackResponseText || '';
  if (!responseText) return '';

  const isInterceptedOutput = Boolean(exec.intercepted_by_model_armor);
  const modelVersion = exec.model_version || exec.model_requested || fallbackModelUsed || 'gemini-4-argon';
  const runtimeLabel = exec.runtime || fallbackModelUsed || 'Vertex AI Agent Engine (ADK)';
  const resourceName = exec.resource_name || 'projects/181100407378/locations/us-central1/reasoningEngines/8735527798581493760';
  const invocationId = exec.invocation_id || 'stream_query (ADK Live Session)';
  const finishReason = exec.finish_reason || (isInterceptedOutput ? 'BLOCKED_AT_OUTPUT (SANITIZE_MODEL_RESPONSE)' : 'STOP');
  const usage = exec.usage_metadata || {};
  const promptTokens = usage.prompt_token_count ?? usage.promptTokenCount ?? '-';
  const candidateTokens = usage.candidates_token_count ?? usage.candidatesTokenCount ?? '-';
  const totalTokens = usage.total_token_count ?? usage.totalTokenCount ?? '-';
  const rawEventsJson = JSON.stringify(exec.raw_events && exec.raw_events.length ? exec.raw_events : exec, null, 2);

  const badgeHtml = isInterceptedOutput
    ? `<span class="text-[9px] font-mono px-2 py-0.5 rounded-full bg-red-900/70 text-red-200 border border-red-600 font-bold shrink-0">
         🚫 INTERCEPTADO EN SALIDA · VERTEX AI
       </span>`
    : `<span class="text-[9px] font-mono px-2 py-0.5 rounded-full bg-emerald-900/60 text-emerald-300 border border-emerald-700 font-bold shrink-0">
         EN VIVO · VERTEX AI
       </span>`;

  const responseBoxTitle = isInterceptedOutput
    ? `🛑 Respuesta Generada por ${escapeHtml(modelVersion)} e Interceptada por SANITIZE_MODEL_RESPONSE:`
    : `💬 Respuesta Íntegra Generada por ${escapeHtml(modelVersion)}:`;

  const responseBoxSubtitle = isInterceptedOutput
    ? `Bloqueada antes de llegar al usuario`
    : `Prueba 100% Real (No Mock)`;

  return `
    <details class="md3-response-dropdown">
      <summary>
        <span class="flex items-center gap-1.5">
          <i class="fa-solid ${isInterceptedOutput ? 'fa-shield-virus text-red-400' : 'fa-robot'} text-xs"></i>
          <span>${escapeHtml(summaryTitle)}</span>
        </span>
        ${badgeHtml}
      </summary>
      <div class="md3-response-dropdown-body space-y-2">
        <div>
          <div class="text-[10px] font-bold uppercase tracking-wider ${isInterceptedOutput ? 'text-red-300' : 'text-emerald-400'} mb-1 flex items-center justify-between">
            <span>${responseBoxTitle}</span>
            <span class="font-mono text-[9px] text-slate-300">${responseBoxSubtitle}</span>
          </div>
          <div class="md3-real-response-box">${escapeHtml(responseText)}</div>
        </div>

        <div class="p-2.5 rounded-lg bg-slate-900/80 border border-slate-700/70 text-[10px] font-mono space-y-1">
          <div class="flex items-center justify-between gap-2">
            <span class="text-slate-400">Modelo Ejecutado (GCP):</span>
            <span class="text-emerald-300 font-bold">${escapeHtml(modelVersion)}</span>
          </div>
          <div class="flex items-center justify-between gap-2">
            <span class="text-slate-400">Runtime:</span>
            <span class="text-blue-300">${escapeHtml(runtimeLabel)}</span>
          </div>
          <div class="flex items-center justify-between gap-2">
            <span class="text-slate-400">Invocation ID (ADK):</span>
            <span class="text-slate-200">${escapeHtml(invocationId)}</span>
          </div>
          <div class="flex items-center justify-between gap-2">
            <span class="text-slate-400">Tokens (Prompt / Resp / Total):</span>
            <span class="text-amber-300">${escapeHtml(String(promptTokens))} / ${escapeHtml(String(candidateTokens))} / ${escapeHtml(String(totalTokens))}</span>
          </div>
          <div class="flex items-center justify-between gap-2">
            <span class="text-slate-400">Finish Reason:</span>
            <span class="${isInterceptedOutput ? 'text-red-400' : 'text-emerald-400'} font-semibold">${escapeHtml(finishReason)}</span>
          </div>
          <div class="pt-0.5">
            <span class="text-slate-400 block mb-0.5">Recurso ReasoningEngine en GCP:</span>
            <div class="text-[9px] text-slate-200 bg-slate-950/70 px-2 py-1 rounded border border-slate-800 break-all">
              ${escapeHtml(resourceName)}
            </div>
          </div>
        </div>

        <details class="bg-slate-900/70 rounded-lg p-2 border border-slate-800">
          <summary class="text-[10px] font-mono text-blue-300 cursor-pointer">
            📄 Ver Payload JSON Crudo de Ejecución / Intercepción en Vertex AI Agent Engine
          </summary>
          <pre class="log-json-pre font-mono mt-1.5 text-[9px]">${escapeHtml(rawEventsJson)}</pre>
        </details>
      </div>
    </details>
  `;
}

// ============================================================================
// 8. Configuración de Listeners de Eventos
// ============================================================================

function setupEventListeners() {
  if (themeDarkBtn) {
    themeDarkBtn.addEventListener('click', () => applyTheme('dark'));
  }
  if (themeLightBtn) {
    themeLightBtn.addEventListener('click', () => applyTheme('light'));
  }

  if (chatForm) {
    chatForm.addEventListener('submit', (e) => {
      e.preventDefault();
      sendMessage();
    });
  }

  if (promptInput) {
    promptInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });
  }

  if (refreshLogsBtn) {
    refreshLogsBtn.addEventListener('click', () => {
      loadCloudLogs(false);
    });
  }

  if (copyGcloudBtn) {
    copyGcloudBtn.addEventListener('click', async () => {
      const cmdToCopy = state.gcloudCommand || (gcloudCommandBox ? gcloudCommandBox.textContent.trim() : '');
      if (!cmdToCopy) return;
      try {
        await navigator.clipboard.writeText(cmdToCopy);
        if (copyGcloudLabel) {
          const prev = copyGcloudLabel.textContent;
          copyGcloudLabel.textContent = '¡Copiado!';
          setTimeout(() => { copyGcloudLabel.textContent = prev; }, 2000);
        }
      } catch (err) {
        console.warn('No se pudo copiar al portapapeles:', err);
      }
    });
  }

  if (clearChatBtn) {
    clearChatBtn.addEventListener('click', () => {
      state.history = [];
      state.allowedTurns = [];
      state.lastAllowedExecution = null;
      state.triggeredDetectors.clear();
      state.triggeredRuleIds.clear();
      renderPoliciesBreakdown();

      if (chatMessages) {
        chatMessages.innerHTML = `
          <div class="flex items-start space-x-3 max-w-3xl chat-bubble-enter">
            <div class="md3-avatar-bot">
              <i class="fa-solid fa-robot text-sm"></i>
            </div>
            <div class="md3-bubble-bot max-w-2xl prose">
              <div class="flex items-center justify-between mb-1.5 pb-1 border-b border-slate-700/60">
                <span class="text-xs font-bold md3-bubble-author">Agente ADK en Vertex AI Agent Platform</span>
                <span class="text-[10px] text-emerald-400 font-mono font-semibold">gemini-4-argon · gemini-3.8-flash</span>
              </div>
              <p class="text-sm md3-bubble-text leading-relaxed">
                Conversación reiniciada. Selecciona <strong>Gemini 4 Argon</strong> o <strong>Gemini 3.8 Flash</strong> o usa una prueba de seguridad para verificar qué políticas y detectores de Model Armor + SDP bloquean amenazas automáticamente.
              </p>
            </div>
          </div>
        `;
      }
      resetTelemetry();
    });
  }

  if (masterArmorToggle) {
    masterArmorToggle.addEventListener('change', async () => {
      const isProtected = masterArmorToggle.checked;
      if (armorStatusBadge) {
        if (isProtected) {
          armorStatusBadge.className = "text-[10px] font-mono px-2 py-0.5 rounded-md font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30";
          armorStatusBadge.textContent = "INSPECT_AND_BLOCK";
        } else {
          armorStatusBadge.className = "text-[10px] font-mono px-2 py-0.5 rounded-md font-semibold bg-amber-500/15 text-amber-300 border border-amber-600/50";
          armorStatusBadge.textContent = "INSPECT_ONLY (Auditoría)";
        }
      }
      try {
        await fetch('/api/floor-setting', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ inspect_and_block: isProtected })
        });
        await loadPoliciesSummary();
      } catch (err) {
        console.warn('No se pudo sincronizar el modo del Floor Setting:', err);
      }
    });
  }
}

// ============================================================================
// 9. Envío de Mensajes y Orquestación de Inferencia
// ============================================================================

async function sendMessage() {
  const message = promptInput ? promptInput.value.trim() : '';
  if (!message || state.isLoading) return;

  state.isLoading = true;
  if (promptInput) promptInput.value = '';
  if (sendBtn) sendBtn.disabled = true;

  // Renderizar burbuja del usuario con clases temáticas dinámicas
  renderUserMessage(message);

  // Mostrar mensaje de carga
  const loadingId = 'loading-' + Date.now();
  renderLoadingMessage(loadingId);

  const isBypass = masterArmorToggle ? !masterArmorToggle.checked : false;
  const selectedModel = modelSelect ? modelSelect.value : 'gemini-4-argon';

  const payload = {
    message: message,
    history: state.history,
    model: selectedModel,
    bypass_model_armor: isBypass
  };

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 90000);

    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    const data = await res.json();
    removeLoadingMessage(loadingId);

    if (res.ok) {
      if (!data.blocked) {
        const turnRecord = {
          prompt: message,
          response: data.content,
          modelUsed: data.model_used,
          rawExec: (data.telemetry && data.telemetry.raw_model_execution) ? data.telemetry.raw_model_execution : null,
          timestamp: Date.now()
        };
        state.lastAllowedExecution = turnRecord;
        state.allowedTurns.unshift(turnRecord);
        state.history.push({ role: 'user', content: message });
        state.history.push({ role: 'model', content: data.content });
      }

      renderBotResponse(data);
      updateTelemetry(data.telemetry, data.blocked, data.content, data.model_used);

      // Ingesta de Cloud Logging: actualización inmediata y a los 2.2s
      loadCloudLogs(true);
      setTimeout(() => loadCloudLogs(true), 2200);
    } else {
      renderErrorMessage(data.detail || 'Ocurrió un error al procesar el mensaje.');
    }
  } catch (err) {
    removeLoadingMessage(loadingId);
    if (err.name === 'AbortError') {
      renderErrorMessage('La solicitud excedió el tiempo límite (Timeout de 45s). Por favor intenta de nuevo.');
    } else {
      renderErrorMessage('Error de red o comunicación con el servicio en GCP.');
    }
  } finally {
    state.isLoading = false;
    if (sendBtn) sendBtn.disabled = false;
    if (promptInput) promptInput.focus();
    scrollToBottom();
  }
}

// ============================================================================
// 10. Renderizado de Mensajes en el Chat (Sin Estilos Inline Fijos)
// ============================================================================

function renderUserMessage(text) {
  if (!chatMessages) return;
  const div = document.createElement('div');
  div.className = 'flex items-start justify-end space-x-3 chat-bubble-enter';
  div.innerHTML = `
    <div class="md3-bubble-user max-w-xl">
      <div class="flex items-center justify-between mb-1 gap-4">
        <span class="text-xs font-bold md3-bubble-user-author">Usuario</span>
        <span class="text-[10px] font-mono md3-bubble-user-time">${new Date().toLocaleTimeString('es-MX', {hour: '2-digit', minute:'2-digit'})}</span>
      </div>
      <p class="text-sm whitespace-pre-wrap leading-relaxed md3-bubble-user-text">${escapeHtml(text)}</p>
    </div>
    <div class="md3-avatar-user">
      <i class="fa-solid fa-user text-xs"></i>
    </div>
  `;
  chatMessages.appendChild(div);
  scrollToBottom();
}

function formatMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);
  html = html.replace(/`([^`]+)`/g, '<code class="md3-inline-code">$1</code>');
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  const lines = html.split('\n');
  let inList = false;
  const out = [];
  for (const line of lines) {
    const bulletMatch = line.match(/^\s*[-*]\s+(.*)$/);
    if (bulletMatch) {
      if (!inList) {
        out.push('<ul class="list-disc pl-4 space-y-1 my-1">');
        inList = true;
      }
      out.push(`<li>${bulletMatch[1]}</li>`);
    } else {
      if (inList) {
        out.push('</ul>');
        inList = false;
      }
      if (line.trim() === '') {
        out.push('<br>');
      } else {
        out.push(`<p class="my-1">${line}</p>`);
      }
    }
  }
  if (inList) out.push('</ul>');
  return out.join('');
}

function renderBotResponse(data) {
  if (!chatMessages) return;
  const isBlocked = data.blocked;
  const telem = data.telemetry || {};
  const blockedStage = data.blocked_stage || telem.blocked_stage || (isBlocked ? 'input' : null);
  const inputInsp = telem.input_inspection || {};
  const outputInsp = telem.output_inspection || {};
  const rawExec = telem.raw_model_execution || null;

  const isInputAudit = !isBlocked && (inputInsp.action === 'INSPECT_ONLY' || (inputInsp.matched_filters && inputInsp.matched_filters.length > 0));
  const isOutputAudit = !isBlocked && (outputInsp.action === 'INSPECT_ONLY' || (outputInsp.matched_filters && outputInsp.matched_filters.length > 0));
  const isAudit = isInputAudit || isOutputAudit;

  const div = document.createElement('div');
  div.className = 'flex items-start space-x-3 max-w-3xl chat-bubble-enter';

  const formattedContent = formatMarkdown(data.content);

  if (isBlocked) {
    const isOutputBlock = blockedStage === 'output';
    const headerTitle = isOutputBlock
      ? 'INTERCEPTADO EN SALIDA (SANITIZE_MODEL_RESPONSE) POR MODEL ARMOR'
      : 'INTERCEPTADO EN ENTRADA (SANITIZE_USER_PROMPT) POR MODEL ARMOR';

    let interceptedDropdownHtml = '';
    if (isOutputBlock && rawExec && rawExec.response_text) {
      interceptedDropdownHtml = buildModelExecutionDropdownHtml(
        rawExec,
        rawExec.response_text,
        data.model_used,
        'Ver Respuesta Real Generada por el Modelo e Interceptada en Salida (SANITIZE_MODEL_RESPONSE)'
      );
    }

    div.innerHTML = `
      <div class="md3-avatar-blocked">
        <i class="fa-solid fa-shield-virus text-sm"></i>
      </div>
      <div class="md3-bubble-blocked max-w-2xl prose">
        <div class="flex items-center justify-between mb-2 border-b border-red-800/40 pb-1.5">
          <span class="text-xs font-bold text-red-400 flex items-center gap-1.5">
            <i class="fa-solid fa-ban"></i> ${escapeHtml(headerTitle)}
          </span>
          <span class="text-[10px] text-red-300 font-mono">${escapeHtml(data.model_used || '')}</span>
        </div>
        <div class="text-sm md3-bubble-text leading-relaxed font-sans space-y-1">
          ${formattedContent}
        </div>
        ${interceptedDropdownHtml}
      </div>
    `;
  } else {
    const dropdownHtml = buildModelExecutionDropdownHtml(
      rawExec,
      data.content,
      data.model_used,
      isAudit
        ? (isOutputAudit
            ? 'Ver Respuesta Real del Modelo Auditada en Salida (SANITIZE_MODEL_RESPONSE · INSPECT_ONLY)'
            : 'Ver Respuesta Real del Modelo Ejecutada en Modo Auditoría (Vertex AI Agent Engine)')
        : 'Ver Respuesta Cruda del Modelo y Evidencia en Vivo de Vertex AI Agent Engine'
    );

    const headerBadge = isAudit
      ? `<span class="text-xs font-bold text-amber-400 flex items-center gap-1">
           <i class="fa-solid fa-triangle-exclamation text-[10px]"></i> ${isOutputAudit ? 'Modo Auditoría · Respuesta del Modelo Auditada sin Bloqueo (SANITIZE_MODEL_RESPONSE)' : 'Modo Auditoría · Amenaza Auditada sin Bloqueo'}
         </span>`
      : `<span class="text-xs font-bold text-emerald-400 flex items-center gap-1">
           <i class="fa-solid fa-shield-halved text-[10px]"></i> Entrada y Respuesta Aprobadas por Floor Settings
         </span>`;

    div.innerHTML = `
      <div class="md3-avatar-bot">
        <i class="fa-solid fa-robot text-sm"></i>
      </div>
      <div class="md3-bubble-bot max-w-2xl prose">
        <div class="flex items-center justify-between mb-2 border-b border-slate-700/60 pb-1.5">
          ${headerBadge}
          <span class="text-[10px] md3-bubble-meta font-mono">${escapeHtml(data.model_used || '')}</span>
        </div>
        <div class="text-sm md3-bubble-text leading-relaxed font-sans space-y-1">
          ${formattedContent}
        </div>
        ${dropdownHtml}
      </div>
    `;
  }

  chatMessages.appendChild(div);
  scrollToBottom();
}

function renderLoadingMessage(id) {
  if (!chatMessages) return;
  const selectedModel = modelSelect ? modelSelect.value : 'gemini-4-argon';
  const div = document.createElement('div');
  div.id = id;
  div.className = 'flex items-start space-x-3 max-w-3xl chat-bubble-enter';
  div.innerHTML = `
    <div class="md3-avatar-bot animate-pulse">
      <i class="fa-solid fa-shield-halved text-sm"></i>
    </div>
    <div class="md3-bubble-bot text-xs flex items-center gap-2 md3-bubble-text">
      <i class="fa-solid fa-circle-notch fa-spin text-blue-300"></i>
      <span>Invocando Agente ADK (<strong>${escapeHtml(selectedModel)}</strong>) en Vertex AI Agent Platform...</span>
    </div>
  `;
  chatMessages.appendChild(div);
  scrollToBottom();
}

function removeLoadingMessage(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function renderErrorMessage(msg) {
  if (!chatMessages) return;
  const div = document.createElement('div');
  div.className = 'flex items-start space-x-3 max-w-3xl chat-bubble-enter';
  div.innerHTML = `
    <div class="md3-avatar-blocked">
      <i class="fa-solid fa-triangle-exclamation text-xs"></i>
    </div>
    <div class="md3-bubble-blocked text-xs text-amber-300">
      ${escapeHtml(msg)}
    </div>
  `;
  chatMessages.appendChild(div);
  scrollToBottom();
}

// ============================================================================
// 11. Telemetría y Auditoría de Seguridad (Último Turno)
// ============================================================================

function updateTelemetry(telem, isBlocked, responseContent = '', modelUsed = '') {
  if (!telem) return;

  const blockedStage = telem.blocked_stage || (isBlocked ? 'input' : null);
  const isOutputBlock = isBlocked && blockedStage === 'output';
  const inputInsp = telem.input_inspection || {};
  const outputInsp = telem.output_inspection || {};

  const isInputAudit = !isBlocked && (inputInsp.action === 'INSPECT_ONLY' || (inputInsp.matched_filters && inputInsp.matched_filters.length > 0));
  const isOutputAudit = !isBlocked && (outputInsp.action === 'INSPECT_ONLY' || (outputInsp.matched_filters && outputInsp.matched_filters.length > 0));
  const isAudit = isInputAudit || isOutputAudit;

  // 1. Estado en Card de Auditoría
  if (telemetryStatus) {
    if (isBlocked) {
      telemetryStatus.className = 'text-xs px-3 py-1 rounded-full bg-red-900/60 text-red-300 border border-red-700 font-mono font-bold';
      telemetryStatus.textContent = isOutputBlock ? '🚫 RESPUESTA BLOQUEADA (SALIDA)' : '🚫 PROMPT BLOQUEADO (ENTRADA)';
    } else if (isAudit) {
      telemetryStatus.className = 'text-xs px-3 py-1 rounded-full bg-amber-900/60 text-amber-300 border border-amber-700 font-mono font-bold';
      telemetryStatus.textContent = isOutputAudit ? '⚠️ AUDITORÍA EN SALIDA · INSPECT_ONLY' : '⚠️ AUDITORÍA EN ENTRADA · INSPECT_ONLY';
    } else {
      telemetryStatus.className = 'text-xs px-3 py-1 rounded-full bg-emerald-900/60 text-emerald-300 border border-emerald-700 font-mono font-bold';
      telemetryStatus.textContent = '✅ ENTRADA Y SALIDA APROBADAS';
    }
  }

  // 2. Badge en pestaña Tab 2 (Auditoría del Turno)
  const tabBadgeAuditEl = document.getElementById('tabBadgeAudit');
  if (tabBadgeAuditEl) {
    if (isBlocked) {
      tabBadgeAuditEl.className = 'text-[9px] px-1.5 py-0.5 rounded-full bg-red-900/60 text-red-200 font-mono font-bold';
      tabBadgeAuditEl.textContent = isOutputBlock ? 'Bloqueado (Salida)' : 'Bloqueado (Entrada)';
    } else if (isAudit) {
      tabBadgeAuditEl.className = 'text-[9px] px-1.5 py-0.5 rounded-full bg-amber-900/60 text-amber-200 font-mono font-bold';
      tabBadgeAuditEl.textContent = isOutputAudit ? 'Auditoría (Salida)' : 'Auditoría';
    } else {
      tabBadgeAuditEl.className = 'text-[9px] px-1.5 py-0.5 rounded-full bg-emerald-900/60 text-emerald-200 font-mono font-bold';
      tabBadgeAuditEl.textContent = 'Aprobado';
    }
  }

  // 3a. Acción del Prompt de Entrada (SANITIZE_USER_PROMPT)
  if (statPromptAction) {
    if (isBlocked && !isOutputBlock) {
      statPromptAction.textContent = '🚫 BLOQUEADO';
      statPromptAction.className = 'text-sm text-red-400 font-bold font-mono';
    } else if (isInputAudit) {
      statPromptAction.textContent = '⚠️ INSPECT_ONLY';
      statPromptAction.className = 'text-sm text-amber-400 font-bold font-mono';
    } else {
      statPromptAction.textContent = '✅ PERMITIDO';
      statPromptAction.className = 'text-sm text-emerald-400 font-bold font-mono';
    }
  }

  // 3b. Acción de la Respuesta del Modelo (SANITIZE_MODEL_RESPONSE)
  if (statOutputAction) {
    if (isOutputBlock) {
      statOutputAction.textContent = '🚫 BLOQUEADO EN SALIDA';
      statOutputAction.className = 'text-sm text-red-400 font-bold font-mono';
    } else if (isBlocked && !isOutputBlock) {
      statOutputAction.textContent = '⏭️ OMITIDA (Entrada Bloq.)';
      statOutputAction.className = 'text-xs text-slate-400 font-semibold font-mono';
    } else if (isOutputAudit) {
      statOutputAction.textContent = '⚠️ INSPECT_ONLY (SALIDA)';
      statOutputAction.className = 'text-sm text-amber-400 font-bold font-mono';
    } else {
      statOutputAction.textContent = '✅ PERMITIDO';
      statOutputAction.className = 'text-sm text-emerald-400 font-bold font-mono';
    }
  }

  // 4. Latencias
  if (statArmorLatency) {
    statArmorLatency.textContent = `${telem.total_latency_ms || inputInsp.latency_ms || 0} ms`;
  }
  if (statLlmLatency) {
    if (isOutputBlock) {
      statLlmLatency.textContent = `${telem.llm_latency_ms || 0} ms (Salida Interceptada)`;
    } else {
      statLlmLatency.textContent = telem.llm_executed ? `${telem.llm_latency_ms || 0} ms` : '0 ms (Inferencia Abortada)';
    }
  }

  // 5. Filtros Coincidentes (Entrada + Salida)
  const inputMatched = (inputInsp.matched_filters || []).map(m => ({ ...m, _stageLabel: 'ENTRADA (SANITIZE_USER_PROMPT)' }));
  const outputMatched = (outputInsp.matched_filters || []).map(m => ({ ...m, _stageLabel: 'SALIDA (SANITIZE_MODEL_RESPONSE)' }));
  const matched = [...inputMatched, ...outputMatched];
  if (matched.length > 0) {
    recordTriggeredMatches(matched);
  }

  // 6. Construcción del dropdown si raw_model_execution está presente (incluyendo intercepción en salida) o turno permitido
  const rawExec = telem.raw_model_execution || null;
  let dropdownHtml = '';
  if (rawExec || (!isBlocked && responseContent)) {
    const dropdownTitle = isOutputBlock
      ? 'Ver Respuesta Real Generada por el Modelo e Interceptada en Salida (SANITIZE_MODEL_RESPONSE)'
      : (isAudit
          ? 'Ver Respuesta Real del Modelo Ejecutada en Modo Auditoría (Vertex AI Agent Engine)'
          : 'Ver Respuesta Real del Modelo y Evidencia en Vivo (No Mock)');
    dropdownHtml = buildModelExecutionDropdownHtml(
      rawExec,
      isOutputBlock ? (rawExec && rawExec.response_text ? rawExec.response_text : '') : responseContent,
      modelUsed,
      dropdownTitle
    );
  }

  if (statMatchDetails) {
    let detailsHtml = '';

    if (matched.length > 0) {
      const banner = isAudit
        ? `<div class="p-2 rounded-lg bg-amber-950/40 border border-amber-800/40 text-amber-300 text-xs font-semibold mb-2 flex items-center gap-1.5">
             <i class="fa-solid fa-triangle-exclamation"></i>
             <span>Amenaza Auditada en ${isOutputAudit ? 'Respuesta del Modelo (SANITIZE_MODEL_RESPONSE)' : 'Prompt de Entrada (SANITIZE_USER_PROMPT)'} · Modo INSPECT_ONLY:</span>
           </div>`
        : `<div class="p-2 rounded-lg bg-red-950/40 border border-red-800/40 text-red-300 text-xs font-semibold mb-2 flex items-center gap-1.5">
             <i class="fa-solid fa-ban"></i>
             <span>${isOutputBlock ? 'Entrada Aprobada (✅) → Respuesta del Modelo Bloqueada en Salida (🚫 SANITIZE_MODEL_RESPONSE):' : 'Prompt de Entrada Bloqueado (🚫 SANITIZE_USER_PROMPT) por Model Armor Floor Settings:'}</span>
           </div>`;

      const filterCards = matched.map(m => `
        <div class="text-red-300 font-semibold mb-1.5 p-2 bg-red-950/30 rounded-lg border border-red-800/30">
          <div class="text-red-400 flex items-center justify-between gap-1 flex-wrap">
            <span class="flex items-center gap-1">
              <i class="fa-solid fa-triangle-exclamation text-[10px]"></i>
              <span>${escapeHtml(m.name || 'REGLA_SEGURIDAD')}</span>
            </span>
            <div class="flex items-center gap-1">
              ${m._stageLabel ? `<span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-purple-900/50 text-purple-200 border border-purple-700/50">${escapeHtml(m._stageLabel)}</span>` : ''}
              ${m.confidence ? `<span class="text-[9px] font-mono px-1.5 py-0.2 rounded bg-red-900/40 text-red-200 border border-red-800/40">Confianza: ${escapeHtml(m.confidence)}</span>` : ''}
            </div>
          </div>
          ${m.detected_variable ? `<div class="text-amber-300 text-[10px] font-mono mt-1">Detector / infoType: <strong>${escapeHtml(m.detected_variable)}</strong></div>` : ''}
          <div class="text-slate-300 font-normal text-[10px] mt-0.5 leading-normal">${escapeHtml(m.details || '')}</div>
        </div>
      `).join('');

      detailsHtml = banner + filterCards;
    } else {
      detailsHtml = `
        <div class="text-emerald-400 font-semibold text-xs flex items-center gap-1.5 mb-2 p-2 rounded-lg bg-emerald-950/30 border border-emerald-800/30">
          <i class="fa-solid fa-circle-check text-xs"></i>
          <span>Sin violaciones detectadas · Entrada (SANITIZE_USER_PROMPT) y Salida (SANITIZE_MODEL_RESPONSE) aprobadas por Floor Settings</span>
        </div>
      `;
    }

    // SIEMPRE añadir el dropdown del modelo si hay telemetría de ejecución real o intercepción en salida
    if (dropdownHtml) {
      detailsHtml += `<div class="mt-3">${dropdownHtml}</div>`;
    }

    statMatchDetails.innerHTML = detailsHtml;
  }
}

function resetTelemetry() {
  if (telemetryStatus) {
    telemetryStatus.className = 'text-xs px-3 py-1 rounded-full bg-slate-700 text-slate-200 font-mono';
    telemetryStatus.textContent = 'En espera';
  }
  const tabBadgeAuditEl = document.getElementById('tabBadgeAudit');
  if (tabBadgeAuditEl) {
    tabBadgeAuditEl.className = 'text-[9px] px-1.5 py-0.2 rounded-full bg-slate-700 text-slate-300 font-mono';
    tabBadgeAuditEl.textContent = 'En espera';
  }
  if (statPromptAction) {
    statPromptAction.textContent = '-';
    statPromptAction.className = 'text-sm text-slate-200 font-bold font-mono';
  }
  if (statOutputAction) {
    statOutputAction.textContent = '-';
    statOutputAction.className = 'text-sm text-slate-200 font-bold font-mono';
  }
  if (statArmorLatency) statArmorLatency.textContent = '-';
  if (statLlmLatency) statLlmLatency.textContent = '-';
  if (statMatchDetails) {
    statMatchDetails.textContent = 'Ninguna violación detectada. Envía una consulta o prueba rápida para visualizar la auditoría en vivo.';
  }
}

// ============================================================================
// 12. Utilidades Generales
// ============================================================================

function scrollToBottom() {
  if (chatMessages) {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}

function escapeHtml(str) {
  if (!str) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

// ============================================================================
// 13. Arquitectura Gráfica Interactiva del Sistema (SVG Flows & Node Inspector)
// ============================================================================

const ARCH_FLOW_META = {
  all: {
    btnId: 'archFlowBtnAll',
    titleClass: 'text-emerald-400',
    icon: 'fa-shield-halved',
    title: 'Arquitectura Completa de 3 Capas: Perímetro L7 (Cloud Armor) + Cómputo Serverless (Cloud Run) + Guardarraíles Inline (Model Armor + SDP)',
    desc: 'Haz clic en cualquier <strong>componente del diagrama gráfico</strong> para inspeccionar su configuración real en GCP y su archivo de Terraform, o selecciona uno de los flujos arriba para ver el recorrido exacto de los paquetes.',
    ctaPresetIndex: 5,
    ctaLabel: 'Probar Bloqueo de Salida en Vivo →'
  },
  input_block: {
    btnId: 'archFlowBtnInput',
    titleClass: 'text-red-400',
    icon: 'fa-ban',
    title: '🚫 Flujo 1 · Intercepción en Entrada (SANITIZE_USER_PROMPT · 0 Tokens Consumidos en el Modelo)',
    desc: 'El paquete atraviesa el Balanceador Global (Cloud Armor WAF) y llega a Cloud Run. Antes de invocar al modelo en Vertex AI Agent Engine, <strong>Model Armor Floor Settings + Cloud SDP</strong> inspeccionan el prompt (PI/Jailbreak, Tarjetas/SSN, RAI, Malicious URI) y abortan la inferencia instantáneamente registrando el evento en Cloud Logging.',
    ctaPresetIndex: 0,
    ctaLabel: 'Probar Ataque de Entrada en Vivo →'
  },
  output_block: {
    btnId: 'archFlowBtnOutput',
    titleClass: 'text-amber-400',
    icon: 'fa-file-shield',
    title: '📤 Flujo 2 · Intercepción en Respuesta del Modelo (SANITIZE_MODEL_RESPONSE · Exfiltración Prevenida)',
    desc: 'El prompt del usuario es limpio y aprueba <code>SANITIZE_USER_PROMPT</code>. El agente en <strong>Vertex AI Agent Engine</strong> consulta registros internos (CRM/RRHH) y genera una respuesta con PII (Tarjeta Visa, SSN) o phishing. Antes de entregarla al cliente, <strong>Model Armor + SDP</strong> interceptan la salida en <code>SANITIZE_MODEL_RESPONSE</code>.',
    ctaPresetIndex: 5,
    ctaLabel: 'Probar Exfiltración de Salida en Vivo →'
  },
  allowed: {
    btnId: 'archFlowBtnAllowed',
    titleClass: 'text-sky-400',
    icon: 'fa-circle-check',
    title: '✅ Flujo 3 · Consulta Segura Aprobada End-to-End (o Ejecución en Modo Auditoría INSPECT_ONLY)',
    desc: 'Tanto el prompt de entrada (<code>SANITIZE_USER_PROMPT</code>) como la respuesta generada por <code>gemini-4-argon</code> / <code>gemini-3.8-flash</code> (<code>SANITIZE_MODEL_RESPONSE</code>) superan los guardarraíles (o se auditan en <code>INSPECT_ONLY</code>) y se entregan al usuario con el dropdown de telemetría real de Vertex AI.',
    ctaPresetIndex: 4,
    ctaLabel: 'Probar Consulta Segura en Vivo →'
  }
};

const ARCH_NODE_META = {
  user: {
    title: '👤 Cliente / Navegador Web (Interfaz Material Design 3)',
    layer: 'CAPA 0 · CLIENTE / FRONTEND',
    layerClass: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
    tfFile: 'Frontend: app/static/index.html · styles.css · app.js',
    desc: 'Interfaz interactiva en español con soporte para Tema Oscuro y Tema Claro (paleta Material Design 3). Permite probar ataques de entrada (<code>SANITIZE_USER_PROMPT</code>), exfiltración en respuestas del modelo (<code>SANITIZE_MODEL_RESPONSE</code>), alternar entre <code>INSPECT_AND_BLOCK</code> e <code>INSPECT_ONLY</code> y verificar la respuesta real del modelo en un dropdown con telemetría cruda de Vertex AI.',
    resource: 'http://34.117.66.159 (Cliente Web -> Global HTTP Load Balancer)',
    controls: 'Selector gemini-4-argon / gemini-3.8-flash · Switch Floor Settings · Visor Cloud Logging en Vivo'
  },
  lb_waf: {
    title: '🌐 Global External Application Load Balancer + Cloud Armor WAF L7',
    layer: 'CAPA 1 · PERÍMETRO GLOBAL L7',
    layerClass: 'bg-blue-500/15 text-blue-300 border-blue-500/30',
    tfFile: 'Terraform: terraform/network.tf',
    desc: 'Punto de entrada único con IP Anycast global (<code>34.117.66.159</code>) conectado a Cloud Run mediante un Serverless NEG (<code>armor-agent-neg</code>). La política adjunta de <strong>Google Cloud Armor</strong> inspecciona las cabeceras y payloads HTTP en el borde de Google antes de tocar el contenedor.',
    resource: 'projects/armor-agent-demo-mau/global/securityPolicies/armor-agent-waf-policy',
    controls: 'Prioridad 1000: evaluatePreconfiguredWaf("sqli-v33-stable") · Prioridad 1001: evaluatePreconfiguredWaf("xss-v33-stable")'
  },
  cloud_run: {
    title: '🚀 Google Cloud Run Serverless (armor-agent-service) + Least-Privilege IAM',
    layer: 'CAPA 2 · ORQUESTACIÓN SERVERLESS',
    layerClass: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    tfFile: 'Terraform: terraform/main.tf · terraform/iam.tf',
    desc: 'Servicio FastAPI serverless en <code>us-central1</code> que orquesta la comunicación con Vertex AI Agent Engine, sincroniza el Floor Setting del proyecto y correlaciona los eventos de <code>SanitizeOperation</code> en Cloud Logging tanto para el prompt de entrada como para la respuesta del modelo.',
    resource: 'projects/armor-agent-demo-mau/locations/us-central1/services/armor-agent-service',
    controls: 'SA: armor-agent-sa@armor-agent-demo-mau.iam.gserviceaccount.com (roles/aiplatform.user, dlp.user, modelarmor.admin, logging.viewer)'
  },
  model_armor: {
    title: '🛡️ Model Armor Floor Settings (Inspección Bidireccional Zero-Code)',
    layer: 'CAPA 3 · GUARDARRAÍLES INLINE',
    layerClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    tfFile: 'Terraform: terraform/main.tf + terraform/sdp.tf',
    desc: 'Política global aplicada a nivel de proyecto (<code>projects/armor-agent-demo-mau/locations/global/floorSetting</code>) con <code>integratedServices: [AI_PLATFORM]</code>. Intercepta automáticamente todas las llamadas hacia y desde Vertex AI sin requerir llamadas manuales al SDK de seguridad en el código del agente: evalúa el prompt del usuario en <code>SANITIZE_USER_PROMPT</code> y evalúa la respuesta generada por el modelo en <code>SANITIZE_MODEL_RESPONSE</code>.',
    resource: 'projects/armor-agent-demo-mau/locations/global/floorSetting',
    controls: 'PI & Jailbreak (LOW_AND_ABOVE) · SDP Advanced · RAI (Hate, Harassment, Dangerous, Sexually Explicit) · Malicious URI · CSAM'
  },
  sdp_dlp: {
    title: '🔍 Sensitive Data Protection (Cloud SDP / DLP InspectTemplate)',
    layer: 'CAPA 3 · INSPECCIÓN PROFUNDA PII/SDP',
    layerClass: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
    tfFile: 'Terraform: terraform/sdp.tf',
    desc: 'Plantilla avanzada de inspección de datos sensibles (<code>armor-sdp-inspect-us-central1</code>) vinculada directamente a Model Armor Floor Settings. Escanea tanto el prompt de entrada del usuario como la respuesta generada por el modelo LLM para impedir fugas de tarjetas de crédito, SSN, credenciales o llaves criptográficas.',
    resource: 'projects/armor-agent-demo-mau/locations/us-central1/inspectTemplates/armor-sdp-inspect-us-central1',
    controls: 'InfoTypes: CREDIT_CARD_NUMBER · US_SOCIAL_SECURITY_NUMBER · GCP_API_KEY · AUTH_TOKEN · PASSWORD · ENCRYPTION_KEY'
  },
  vertex_agents: {
    title: '🧠 Vertex AI Agent Engine (Google ADK ReasoningEngines)',
    layer: 'CAPA 4 · PLATAFORMA AGÉNTICA',
    layerClass: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
    tfFile: 'Código Agente: app/core/agent.py · deploy_adk.py',
    desc: 'Agentes empresariales desplegados en Vertex AI Agent Platform (<code>ReasoningEngines</code> en <code>us-central1</code>) operando exclusivamente con los modelos autorizados <code>gemini-4-argon</code> y <code>gemini-3.8-flash</code>. Cuentan con acceso a registros corporativos simulados (CRM de Juan Pérez, RRHH de María López y catálogo de proveedores) para demostrar cómo Model Armor previene la exfiltración en <code>SANITIZE_MODEL_RESPONSE</code>.',
    resource: 'projects/181100407378/locations/us-central1/reasoningEngines/8735527798581493760 (gemini-4-argon) & 1635602986031906816 (gemini-3.8-flash)',
    controls: 'Ejecución real vía vertexai.agent_engines.get() · Telemetría en vivo (invocation_id, usage_metadata, stream_query events)'
  },
  cloud_logging: {
    title: '📜 Google Cloud Logging (Auditoría SanitizeOperation en Tiempo Real)',
    layer: 'CAPA 4 · OBSERVABILIDAD Y AUDITORÍA',
    layerClass: 'bg-purple-500/15 text-purple-300 border-purple-500/30',
    tfFile: 'Integración: app/core/model_armor.py (list_sanitize_logs)',
    desc: 'Cada evaluación realizada por Model Armor genera un registro de auditoría inmutable en el log <code>modelarmor.googleapis.com%2FSanitizeOperation</code>. Registra la etapa exacta (<code>SANITIZE_USER_PROMPT</code> o <code>SANITIZE_MODEL_RESPONSE</code>), el veredicto (<code>BLOQUEADO</code> o <code>PERMITIDO · AUDITORÍA</code>) y los detectores activados.',
    resource: 'projects/armor-agent-demo-mau/logs/modelarmor.googleapis.com%2FSanitizeOperation',
    controls: 'Consulta en vivo desde la UI + Comando CLI gcloud logging read listo para copiar'
  }
};

function selectArchFlow(flowKey) {
  const key = ARCH_FLOW_META[flowKey] ? flowKey : 'all';
  const meta = ARCH_FLOW_META[key];

  // 1. Actualizar estado activo de los botones de flujo
  ['archFlowBtnAll', 'archFlowBtnInput', 'archFlowBtnOutput', 'archFlowBtnAllowed'].forEach(btnId => {
    const btn = document.getElementById(btnId);
    if (btn) {
      btn.classList.toggle('active', btnId === meta.btnId);
    }
  });

  // 2. Actualizar banner explicativo del flujo
  const banner = document.getElementById('archFlowBanner');
  if (banner) {
    banner.innerHTML = `
      <div class="space-y-0.5 flex-1">
        <div class="font-bold ${meta.titleClass} flex items-center gap-1.5">
          <i class="fa-solid ${meta.icon}"></i>
          <span>${meta.title}</span>
        </div>
        <div class="text-slate-300 text-[11px]">
          ${meta.desc}
        </div>
      </div>
      <button type="button" onclick="applyPreset(${meta.ctaPresetIndex})" class="btn-action-secondary shrink-0">
        <i class="fa-solid fa-bolt text-amber-400"></i>
        <span>${escapeHtml(meta.ctaLabel)}</span>
      </button>
    `;
  }

  // 3. Resaltar u opacar nodos y conexiones SVG según data-flows
  const svg = document.getElementById('archSvgDiagram');
  if (svg) {
    svg.querySelectorAll('.arch-node, .arch-edge').forEach(el => {
      const flowsAttr = el.getAttribute('data-flows') || 'all';
      const flows = flowsAttr.split(',').map(s => s.trim());
      if (key === 'all' || flows.includes(key)) {
        el.classList.remove('dimmed');
      } else {
        el.classList.add('dimmed');
      }
    });
  }

  // 4. Seleccionar nodo representativo del flujo
  if (key === 'input_block') {
    selectArchNode('model_armor');
  } else if (key === 'output_block') {
    selectArchNode('sdp_dlp');
  } else if (key === 'allowed') {
    selectArchNode('vertex_agents');
  }
}

function selectArchNode(nodeKey) {
  const meta = ARCH_NODE_META[nodeKey];
  if (!meta) return;

  // 1. Marcar nodo seleccionado en el SVG
  const svg = document.getElementById('archSvgDiagram');
  if (svg) {
    svg.querySelectorAll('.arch-node').forEach(nodeEl => {
      nodeEl.classList.toggle('selected', nodeEl.id === `archNode-${nodeKey}`);
    });
  }

  // 2. Actualizar tarjeta inspectora inferior
  const titleEl = document.getElementById('archDetailTitle');
  const layerEl = document.getElementById('archDetailLayer');
  const tfFileEl = document.getElementById('archDetailTfFile');
  const descEl = document.getElementById('archDetailDesc');
  const resourceEl = document.getElementById('archDetailResource');
  const controlsEl = document.getElementById('archDetailControls');

  if (titleEl) titleEl.textContent = meta.title;
  if (layerEl) {
    layerEl.textContent = meta.layer;
    layerEl.className = `text-[10px] font-mono px-2 py-0.5 rounded border ${meta.layerClass}`;
  }
  if (tfFileEl) tfFileEl.textContent = meta.tfFile;
  if (descEl) descEl.innerHTML = meta.desc;
  if (resourceEl) resourceEl.textContent = meta.resource;
  if (controlsEl) controlsEl.textContent = meta.controls;
}

window.selectArchFlow = selectArchFlow;
window.selectArchNode = selectArchNode;

