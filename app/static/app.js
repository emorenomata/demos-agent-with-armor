// Client state and logic for Model Armor Demo
const state = {
  history: [],
  isLoading: false,
  presets: []
};

// DOM Elements
const chatMessages = document.getElementById('chatMessages');
const chatForm = document.getElementById('chatForm');
const promptInput = document.getElementById('promptInput');
const sendBtn = document.getElementById('sendBtn');
const masterArmorToggle = document.getElementById('masterArmorToggle');
const armorStatusBadge = document.getElementById('armorStatusBadge');
const modelSelect = document.getElementById('modelSelect');
const clearChatBtn = document.getElementById('clearChatBtn');

// Telemetry Elements
const telemetryStatus = document.getElementById('telemetryStatus');
const statPromptAction = document.getElementById('statPromptAction');
const statArmorLatency = document.getElementById('statArmorLatency');
const statLlmLatency = document.getElementById('statLlmLatency');
const statMatchDetails = document.getElementById('statMatchDetails');

// Initialize
document.addEventListener('DOMContentLoaded', async () => {
  await loadTemplatesAndPresets();
  setupEventListeners();
});

async function loadTemplatesAndPresets() {
  try {
    const res = await fetch('/api/templates');
    if (res.ok) {
      const data = await res.json();
      state.presets = data.attack_presets || [];
    }
  } catch (err) {
    console.warn('Could not load presets:', err);
  }
}

function setupEventListeners() {
  chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    sendMessage();
  });

  promptInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  clearChatBtn.addEventListener('click', () => {
    state.history = [];
    chatMessages.innerHTML = `
      <div class="flex items-start space-x-3 max-w-3xl chat-bubble-enter">
        <div class="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shrink-0 shadow">
          <i class="fa-solid fa-robot text-sm"></i>
        </div>
        <div class="bg-slate-800 border border-slate-700/80 rounded-2xl rounded-tl-sm px-4 py-3 shadow-md max-w-2xl">
          <div class="flex items-center justify-between mb-1">
            <span class="text-xs font-semibold text-blue-400">Asistente Protegido</span>
            <span class="text-[10px] text-slate-400">Sistema Seguro</span>
          </div>
          <p class="text-sm text-slate-200 leading-relaxed">
            Chat reiniciado. Puedes realizar una consulta o probar un ataque de seguridad.
          </p>
        </div>
      </div>
    `;
    resetTelemetry();
  });

  masterArmorToggle.addEventListener('change', () => {
    const isProtected = masterArmorToggle.checked;
    if (isProtected) {
      armorStatusBadge.className = "mt-3 flex items-center gap-2 text-xs font-medium text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-lg border border-emerald-500/20";
      armorStatusBadge.innerHTML = `<i class="fa-solid fa-circle-check"></i><span>PROTEGIDO: Prompts y Respuestas sanitizadas</span>`;
    } else {
      armorStatusBadge.className = "mt-3 flex items-center gap-2 text-xs font-medium text-red-400 bg-red-500/10 px-3 py-1.5 rounded-lg border border-red-500/20";
      armorStatusBadge.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i><span>BYPASS: Model Armor DESACTIVADO (Peligro)</span>`;
    }
  });
}

function applyPreset(index) {
  if (state.presets[index]) {
    promptInput.value = state.presets[index].prompt;
    promptInput.focus();
  }
}

async function sendMessage() {
  const message = promptInput.value.trim();
  if (!message || state.isLoading) return;

  state.isLoading = true;
  promptInput.value = '';
  sendBtn.disabled = true;

  // Render User Message
  renderUserMessage(message);

  // Render Skeleton / Loading Message
  const loadingId = 'loading-' + Date.now();
  renderLoadingMessage(loadingId);

  // Payload preparation
  const isBypass = !masterArmorToggle.checked;
  const payload = {
    message: message,
    history: state.history,
    model: modelSelect.value,
    bypass_model_armor: isBypass
  };

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 25000);

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
      renderBotResponse(data);
      updateTelemetry(data.telemetry, data.blocked);

      // Save to conversation history
      state.history.push({ role: 'user', content: message });
      state.history.push({ role: 'model', content: data.content });
    } else {
      renderErrorMessage(data.detail || 'Ocurrió un error al procesar el mensaje.');
    }
  } catch (err) {
    removeLoadingMessage(loadingId);
    if (err.name === 'AbortError') {
      renderErrorMessage('La solicitud excedió el tiempo límite (Timeout). Por favor intenta de nuevo.');
    } else {
      renderErrorMessage('Error de red o comunicación con el servicio.');
    }
  } finally {
    state.isLoading = false;
    sendBtn.disabled = false;
    promptInput.focus();
    scrollToBottom();
  }
}

function renderUserMessage(text) {
  const div = document.createElement('div');
  div.className = 'flex items-start justify-end space-x-3 chat-bubble-enter';
  div.innerHTML = `
    <div class="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 shadow-md max-w-xl">
      <div class="flex items-center justify-between mb-1 gap-4">
        <span class="text-xs font-semibold text-blue-100">Usuario</span>
        <span class="text-[10px] text-blue-200">${new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
      </div>
      <p class="text-sm whitespace-pre-wrap leading-relaxed">${escapeHtml(text)}</p>
    </div>
    <div class="w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center text-slate-200 shrink-0 shadow">
      <i class="fa-solid fa-user text-xs"></i>
    </div>
  `;
  chatMessages.appendChild(div);
  scrollToBottom();
}

function formatMarkdown(text) {
  if (!text) return '';
  let html = escapeHtml(text);
  // Inline code `code`
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Bold **text**
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Convert bullet lines (- or *) into list items
  const lines = html.split('\n');
  let inList = false;
  const out = [];
  for (const line of lines) {
    const bulletMatch = line.match(/^\s*[-*]\s+(.*)$/);
    if (bulletMatch) {
      if (!inList) {
        out.push('<ul>');
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
        out.push(`<p>${line}</p>`);
      }
    }
  }
  if (inList) out.push('</ul>');
  return out.join('');
}

function renderBotResponse(data) {
  const isBlocked = data.blocked;
  const div = document.createElement('div');
  div.className = 'flex items-start space-x-3 max-w-3xl chat-bubble-enter';

  const formattedContent = formatMarkdown(data.content);

  if (isBlocked) {
    div.innerHTML = `
      <div class="w-8 h-8 rounded-lg bg-red-600 flex items-center justify-center text-white shrink-0 shadow shadow-red-500/20">
        <i class="fa-solid fa-shield-virus text-sm"></i>
      </div>
      <div class="bg-red-950/40 border border-red-700/60 rounded-2xl rounded-tl-sm px-4 py-3 shadow-lg max-w-2xl prose prose-invert prose-sm">
        <div class="flex items-center justify-between mb-2 not-prose border-b border-red-800/40 pb-1.5">
          <span class="text-xs font-bold text-red-400 flex items-center gap-1.5">
            <i class="fa-solid fa-ban"></i> INTERCEPTADO POR MODEL ARMOR
          </span>
          <span class="text-[10px] text-red-300 font-mono">${data.model_used || ''}</span>
        </div>
        <div class="text-sm text-red-100 leading-relaxed font-sans space-y-1">
          ${formattedContent}
        </div>
      </div>
    `;
  } else {
    div.innerHTML = `
      <div class="w-8 h-8 rounded-lg bg-emerald-600 flex items-center justify-center text-white shrink-0 shadow shadow-emerald-500/20">
        <i class="fa-solid fa-robot text-sm"></i>
      </div>
      <div class="bg-slate-800 border border-slate-700/80 rounded-2xl rounded-tl-sm px-4 py-3 shadow-md max-w-2xl prose prose-invert prose-sm">
        <div class="flex items-center justify-between mb-2 not-prose border-b border-slate-700/40 pb-1.5">
          <span class="text-xs font-semibold text-emerald-400 flex items-center gap-1">
            <i class="fa-solid fa-shield-halved text-[10px]"></i> Respuesta Aprobada
          </span>
          <span class="text-[10px] text-slate-400 font-mono">${data.model_used || ''}</span>
        </div>
        <div class="text-sm text-slate-200 leading-relaxed font-sans space-y-1">
          ${formattedContent}
        </div>
      </div>
    `;
  }

  chatMessages.appendChild(div);
  scrollToBottom();
}

function renderLoadingMessage(id) {
  const div = document.createElement('div');
  div.id = id;
  div.className = 'flex items-start space-x-3 max-w-3xl chat-bubble-enter';
  div.innerHTML = `
    <div class="w-8 h-8 rounded-lg bg-slate-700 flex items-center justify-center text-slate-300 shrink-0 animate-pulse">
      <i class="fa-solid fa-shield-halved text-sm"></i>
    </div>
    <div class="bg-slate-800/60 border border-slate-700/40 rounded-2xl px-4 py-3 text-xs text-slate-400 flex items-center gap-2">
      <i class="fa-solid fa-circle-notch fa-spin text-blue-400"></i>
      <span>Inspeccionando con Model Armor y consultando Gemini...</span>
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
  const div = document.createElement('div');
  div.className = 'flex items-start space-x-3 max-w-3xl chat-bubble-enter';
  div.innerHTML = `
    <div class="w-8 h-8 rounded-lg bg-amber-600 flex items-center justify-center text-white shrink-0">
      <i class="fa-solid fa-triangle-exclamation text-xs"></i>
    </div>
    <div class="bg-slate-800 border border-amber-600/50 rounded-2xl px-4 py-3 text-xs text-amber-200">
      ${escapeHtml(msg)}
    </div>
  `;
  chatMessages.appendChild(div);
  scrollToBottom();
}

function updateTelemetry(telem, isBlocked) {
  if (!telem) return;

  if (isBlocked) {
    telemetryStatus.className = 'text-[10px] px-2 py-0.5 rounded bg-red-900/60 text-red-300 border border-red-700 font-bold';
    telemetryStatus.textContent = '🚫 AMENAZA BLOQUEADA';
  } else {
    telemetryStatus.className = 'text-[10px] px-2 py-0.5 rounded bg-emerald-900/60 text-emerald-300 border border-emerald-700 font-bold';
    telemetryStatus.textContent = '✅ PROMPT APROBADO';
  }

  const inputInsp = telem.input_inspection || {};
  statPromptAction.textContent = inputInsp.action || 'ALLOWED';
  statPromptAction.className = inputInsp.action === 'BLOCKED' ? 'text-red-400 font-bold' : 'text-emerald-400 font-bold';

  statArmorLatency.textContent = `${inputInsp.latency_ms || 0} ms`;
  statLlmLatency.textContent = telem.llm_executed ? `${telem.llm_latency_ms || 0} ms` : '0 ms (Evitado)';

  const matched = inputInsp.matched_filters || [];
  if (matched.length > 0) {
    statMatchDetails.innerHTML = matched.map(m => `
      <div class="text-red-300 font-semibold mb-1.5 p-1.5 bg-red-950/30 rounded border border-red-800/30">
        <div class="text-red-400 flex items-center gap-1">
          <i class="fa-solid fa-triangle-exclamation text-[10px]"></i>
          <span>${escapeHtml(m.name || 'VIOLATION')}</span>
        </div>
        ${m.detected_variable ? `<div class="text-amber-300 text-[10px] font-mono mt-0.5">Variable: ${escapeHtml(m.detected_variable)}</div>` : ''}
        <div class="text-slate-300 font-normal text-[10px] mt-0.5">${escapeHtml(m.details || '')}</div>
      </div>
    `).join('');
  } else {
    statMatchDetails.innerHTML = `<span class="text-slate-400">Sin violaciones detectadas (Tráfico limpio).</span>`;
  }
}

function resetTelemetry() {
  telemetryStatus.className = 'text-[10px] px-2 py-0.5 rounded bg-slate-700 text-slate-300';
  telemetryStatus.textContent = 'En espera';
  statPromptAction.textContent = '-';
  statPromptAction.className = 'text-slate-300 font-bold';
  statArmorLatency.textContent = '-';
  statLlmLatency.textContent = '-';
  statMatchDetails.textContent = 'Ninguna violación detectada.';
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHtml(str) {
  if (!str) return '';
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
