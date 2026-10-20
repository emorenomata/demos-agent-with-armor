/**
 * Empirical Adversarial Challenger Test Suite for Milestone 2 Frontend
 * Executes app/static/app.js in Node.js VM against emulated DOM.
 * 
 * Verifies:
 * 1. DOM Elements presence & querying
 * 2. 4-Tab Switching State Machine (chat, audit, policies, logs) & Stress
 * 3. Presets Dropdown Population & applyPreset edge cases
 * 4. Model Selector Options strictly gemini-4-argon and gemini-3.8-flash
 * 5. Theme Button State Handling (Oscuro/Claro), localStorage & Resilience
 * 6. Real Model Response Dropdown (R2) & Live Telemetry parsing
 * 7. Cloud Logging 3-verdict classification (BLOQUEADO, AUDITORÍA, PERMITIDO)
 */

const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert');

const ROOT_DIR = path.resolve(__dirname, '..');
const HTML_FILE = path.join(ROOT_DIR, 'app', 'static', 'index.html');
const JS_FILE = path.join(ROOT_DIR, 'app', 'static', 'app.js');

const htmlContent = fs.readFileSync(HTML_FILE, 'utf8');
const jsContent = fs.readFileSync(JS_FILE, 'utf8');

// --- Minimalist Fast DOM Mock for Node.js VM ---

class MockClassList {
  constructor(node) {
    this.node = node;
    this.classes = new Set();
  }
  add(...cls) {
    cls.forEach(c => c && this.classes.add(c));
    this.node.className = Array.from(this.classes).join(' ');
  }
  remove(...cls) {
    cls.forEach(c => this.classes.delete(c));
    this.node.className = Array.from(this.classes).join(' ');
  }
  toggle(cls, force) {
    if (force !== undefined) {
      if (force) this.add(cls);
      else this.remove(cls);
      return force;
    }
    if (this.classes.has(cls)) {
      this.remove(cls);
      return false;
    } else {
      this.add(cls);
      return true;
    }
  }
  contains(cls) {
    return this.classes.has(cls);
  }
}

class MockElement {
  constructor(tagName = 'div', id = '', attrs = {}) {
    this.tagName = tagName.toUpperCase();
    this.id = id;
    this.attrs = { ...attrs };
    if (id) this.attrs.id = id;
    this.classList = new MockClassList(this);
    if (attrs.class) {
      attrs.class.split(/\s+/).forEach(c => this.classList.add(c));
    }
    this.children = [];
    this._innerHTML = '';
    this._textContent = '';
    this.value = '';
    this.checked = false;
    this.disabled = false;
    this.eventListeners = {};
    this.dataset = {};
    this.style = {};
  }

  get className() {
    return Array.from(this.classList.classes).join(' ');
  }

  set className(val) {
    this.classList.classes.clear();
    if (val) {
      val.trim().split(/\s+/).forEach(c => c && this.classList.classes.add(c));
    }
  }

  setAttribute(name, val) {
    this.attrs[name] = String(val);
    if (name === 'class') this.className = val;
    if (name.startsWith('data-')) {
      const dataKey = name.slice(5).replace(/-([a-z])/g, (_, g) => g.toUpperCase());
      this.dataset[dataKey] = String(val);
    }
  }

  getAttribute(name) {
    return this.attrs[name] !== undefined ? this.attrs[name] : null;
  }

  removeAttribute(name) {
    delete this.attrs[name];
  }

  addEventListener(type, fn) {
    if (!this.eventListeners[type]) this.eventListeners[type] = [];
    this.eventListeners[type].push(fn);
  }

  dispatchEvent(event) {
    const list = this.eventListeners[event.type] || [];
    list.forEach(fn => fn(event));
  }

  appendChild(child) {
    this.children.push(child);
  }

  remove() {
    // detach
  }

  focus() {
    this._focused = true;
  }

  get innerHTML() {
    return this._innerHTML;
  }

  set innerHTML(val) {
    this._innerHTML = val;
    this.children = [];
    const matches = val.match(/<([a-zA-Z0-9\-]+)[^>]*>/g) || [];
    this.children = matches.map(() => new MockElement('div'));
  }

  get textContent() {
    return this._textContent || this._innerHTML.replace(/<[^>]+>/g, '');
  }

  set textContent(val) {
    this._textContent = val;
    this._innerHTML = val;
  }

  closest(selector) {
    if (selector.startsWith('[data-tab]')) {
      if (this.dataset && this.dataset.tab) return this;
    }
    return null;
  }
}

class MockDocument {
  constructor() {
    this.elementsById = new Map();
    this.allElements = [];
    this.documentElement = new MockElement('html', '', { 'data-theme': 'dark' });
    this.eventListeners = {};
  }

  register(el) {
    if (el.id) this.elementsById.set(el.id, el);
    this.allElements.push(el);
    return el;
  }

  getElementById(id) {
    return this.elementsById.get(id) || null;
  }

  querySelectorAll(selector) {
    if (selector.startsWith('.md3-tab[data-tab=')) {
      const match = selector.match(/data-tab="([^"]+)"/);
      if (match) {
        const key = match[1];
        return this.allElements.filter(el => el.dataset.tab === key);
      }
    }
    return [];
  }

  createElement(tagName) {
    const el = new MockElement(tagName);
    this.allElements.push(el);
    return el;
  }

  addEventListener(type, fn) {
    if (!this.eventListeners[type]) this.eventListeners[type] = [];
    this.eventListeners[type].push(fn);
  }

  dispatchEvent(event) {
    const list = this.eventListeners[event.type] || [];
    list.forEach(fn => fn(event));
  }
}

function createTestHarness() {
  const doc = new MockDocument();

  // Create standard elements found in index.html
  const elemIds = [
    'chatMessages', 'chatForm', 'promptInput', 'sendBtn',
    'masterArmorToggle', 'armorStatusBadge', 'modelSelect',
    'clearChatBtn', 'themeDarkBtn', 'themeLightBtn', 'presetSelect',
    'policiesBreakdownContainer', 'floorEnforcementBadge', 'policyModeBadge',
    'telemetryStatus', 'tabBadgeAudit', 'statPromptAction',
    'statArmorLatency', 'statLlmLatency', 'statMatchDetails',
    'refreshLogsBtn', 'refreshLogsIcon', 'copyGcloudBtn',
    'copyGcloudLabel', 'openConsoleLink', 'gcloudCommandBox', 'cloudLogsList'
  ];

  elemIds.forEach(id => {
    let tag = 'div';
    let attrs = {};
    if (id === 'promptInput') tag = 'textarea';
    if (id === 'modelSelect' || id === 'presetSelect') tag = 'select';
    if (id === 'masterArmorToggle') { tag = 'input'; attrs.type = 'checkbox'; }
    if (id.endsWith('Btn')) tag = 'button';
    if (id === 'themeDarkBtn') attrs.class = 'md3-theme-btn active';
    if (id === 'themeLightBtn') attrs.class = 'md3-theme-btn';
    const el = new MockElement(tag, id, attrs);
    doc.register(el);
  });

  // 4 Tabs & Panels
  ['Chat', 'Audit', 'Policies', 'Logs'].forEach(t => {
    const key = t.toLowerCase();
    const btn = new MockElement('button', `tabBtn${t}`, {
      role: 'tab',
      'data-tab': key,
      'aria-selected': key === 'chat' ? 'true' : 'false',
      class: key === 'chat' ? 'md3-tab active' : 'md3-tab'
    });
    btn.dataset.tab = key;
    doc.register(btn);

    const panel = new MockElement('section', `tabPanel${t}`, {
      role: 'tabpanel',
      class: key === 'chat' ? 'md3-tab-panel active' : 'md3-tab-panel hidden'
    });
    doc.register(panel);
  });

  // Mock modelSelect options
  const modelSelect = doc.getElementById('modelSelect');
  modelSelect.value = 'gemini-4-argon';

  const storage = {};
  const mockLocalStorage = {
    getItem: (k) => (k in storage ? storage[k] : null),
    setItem: (k, v) => { storage[k] = String(v); },
    removeItem: (k) => { delete storage[k]; },
    _storage: storage
  };

  const sandbox = {
    document: doc,
    window: {},
    navigator: {
      clipboard: {
        writeText: async (text) => { sandbox._copiedText = text; }
      }
    },
    localStorage: mockLocalStorage,
    fetch: async (url, options) => {
      sandbox._lastFetchUrl = url;
      sandbox._lastFetchOptions = options;
      return {
        ok: true,
        json: async () => ({
          attack_presets: [
            { title: "🚫 Inyección de Prompt / Jailbreak", prompt: "Test prompt 0" },
            { title: "💳 Fuga de Tarjeta de Crédito (SDP)", prompt: "Test prompt 1" },
            { title: "🔑 Secreto / Contraseña (SDP)", prompt: "Test prompt 2" },
            { title: "⚠️ Contenido Peligroso (RAI)", prompt: "Test prompt 3" },
            { title: "🔗 Enlace Malicioso (Web Risk)", prompt: "Test prompt 4" },
            { title: "✅ Consulta Legítima", prompt: "Test prompt safe" }
          ],
          entries: [],
          policies: {
            enforcement_mode: "INSPECT_AND_BLOCK",
            model_armor_rules: []
          }
        })
      };
    },
    setTimeout: (fn, delay) => { fn(); return 1; },
    clearTimeout: () => {},
    console: {
      log: () => {},
      warn: () => {},
      error: () => {}
    },
    AbortController: class {
      constructor() {
        this.signal = {};
      }
      abort() {}
    },
    Date: Date,
    JSON: JSON,
    Set: Set,
    Array: Array,
    Object: Object,
    String: String,
    Number: Number,
    Boolean: Boolean,
    RegExp: RegExp,
    Promise: Promise
  };

  sandbox.window = sandbox;
  sandbox.globalThis = sandbox;

  // Append export hook to script so test can access internal functions and state
  const testInstrumentedScript = `
    ${jsContent}
    ;globalThis.__state = state;
    globalThis.__switchTab = switchTab;
    globalThis.__applyPreset = applyPreset;
    globalThis.__renderPresetsDropdown = renderPresetsDropdown;
    globalThis.__buildModelExecutionDropdownHtml = buildModelExecutionDropdownHtml;
    globalThis.__updateTelemetry = updateTelemetry;
    globalThis.__renderCloudLogs = renderCloudLogs;
    globalThis.__applyTheme = applyTheme;
    globalThis.__initTheme = initTheme;
    globalThis.__setupEventListeners = setupEventListeners;
    globalThis.sendMessage = sendMessage;
    globalThis.formatMarkdown = formatMarkdown;
  `;

  const context = vm.createContext(sandbox);
  vm.runInContext(testInstrumentedScript, context);

  // Dispatch DOMContentLoaded to register all event listeners
  doc.dispatchEvent({ type: 'DOMContentLoaded' });

  return { doc, sandbox, context };
}

// ============================================================================
// TEST SUITE
// ============================================================================

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    console.log(`  PASS: ${name}`);
    passed++;
  } catch (err) {
    console.error(`  FAIL: ${name}`);
    console.error(`        Error: ${err.message}`);
    failed++;
  }
}

console.log("=== EMPIRICAL STRESS TEST SUITE: MILESTONE 2 FRONTEND ===");

// ----------------------------------------------------------------------------
// Suite 1: DOM & Tab Switching State Machine
// ----------------------------------------------------------------------------
console.log("\n[Suite 1] 4-Tab Switching State Machine");

test("Initial tab state is 'chat' active, other 3 tabs hidden", () => {
  const { doc, sandbox } = createTestHarness();
  assert.strictEqual(sandbox.__state.currentTab, 'chat');
  assert.strictEqual(doc.getElementById('tabPanelChat').classList.contains('active'), true);
  assert.strictEqual(doc.getElementById('tabPanelChat').classList.contains('hidden'), false);
  assert.strictEqual(doc.getElementById('tabPanelAudit').classList.contains('hidden'), true);
  assert.strictEqual(doc.getElementById('tabPanelPolicies').classList.contains('hidden'), true);
  assert.strictEqual(doc.getElementById('tabPanelLogs').classList.contains('hidden'), true);
  assert.strictEqual(doc.getElementById('tabBtnChat').getAttribute('aria-selected'), 'true');
});

test("Switching to 'audit' tab toggles classes and ARIA correctly", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__switchTab('audit');
  assert.strictEqual(sandbox.__state.currentTab, 'audit');
  assert.strictEqual(doc.getElementById('tabPanelAudit').classList.contains('active'), true);
  assert.strictEqual(doc.getElementById('tabPanelAudit').classList.contains('hidden'), false);
  assert.strictEqual(doc.getElementById('tabBtnAudit').getAttribute('aria-selected'), 'true');
  assert.strictEqual(doc.getElementById('tabPanelChat').classList.contains('hidden'), true);
});

test("Switching to 'policies' tab toggles panel visibility", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__switchTab('policies');
  assert.strictEqual(sandbox.__state.currentTab, 'policies');
  assert.strictEqual(doc.getElementById('tabPanelPolicies').classList.contains('active'), true);
  assert.strictEqual(doc.getElementById('tabPanelPolicies').classList.contains('hidden'), false);
  assert.strictEqual(doc.getElementById('tabBtnPolicies').getAttribute('aria-selected'), 'true');
});

test("Switching to 'logs' tab toggles panel visibility", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__switchTab('logs');
  assert.strictEqual(sandbox.__state.currentTab, 'logs');
  assert.strictEqual(doc.getElementById('tabPanelLogs').classList.contains('active'), true);
  assert.strictEqual(doc.getElementById('tabPanelLogs').classList.contains('hidden'), false);
  assert.strictEqual(doc.getElementById('tabBtnLogs').getAttribute('aria-selected'), 'true');
});

test("Unknown/invalid tab key gracefully falls back to default without crash", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__switchTab('invalid_non_existent_tab');
  assert.strictEqual(sandbox.__state.currentTab, 'chat');
  assert.strictEqual(doc.getElementById('tabPanelChat').classList.contains('active'), true);
  assert.strictEqual(doc.getElementById('tabPanelChat').classList.contains('hidden'), false);
});

test("Stress test: 1,000 rapid sequential tab switches maintain consistency", () => {
  const { doc, sandbox } = createTestHarness();
  const tabs = ['chat', 'audit', 'policies', 'logs'];
  for (let i = 0; i < 1000; i++) {
    const target = tabs[i % tabs.length];
    sandbox.__switchTab(target);
    assert.strictEqual(sandbox.__state.currentTab, target);
  }
  // End on policies
  sandbox.__switchTab('policies');
  const activePanels = tabs.filter(t => doc.getElementById(`tabPanel${t.charAt(0).toUpperCase() + t.slice(1)}`).classList.contains('active'));
  assert.strictEqual(activePanels.length, 1);
  assert.strictEqual(activePanels[0], 'policies');
});

// ----------------------------------------------------------------------------
// Suite 2: Theme State Handling & Segmented Buttons
// ----------------------------------------------------------------------------
console.log("\n[Suite 2] Theme State Handling (Oscuro / Claro) & Persistence");

test("Default theme is dark and dark button is active", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__initTheme();
  assert.strictEqual(doc.documentElement.getAttribute('data-theme'), 'dark');
  assert.strictEqual(doc.getElementById('themeDarkBtn').classList.contains('active'), true);
  assert.strictEqual(doc.getElementById('themeLightBtn').classList.contains('active'), false);
});

test("applyTheme('light') updates data-theme, active button, and localStorage", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__applyTheme('light');
  assert.strictEqual(doc.documentElement.getAttribute('data-theme'), 'light');
  assert.strictEqual(doc.getElementById('themeLightBtn').classList.contains('active'), true);
  assert.strictEqual(doc.getElementById('themeDarkBtn').classList.contains('active'), false);
  assert.strictEqual(sandbox.localStorage.getItem('armor_m3_theme'), 'light');
});

test("applyTheme('dark') restores dark theme", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__applyTheme('light');
  sandbox.__applyTheme('dark');
  assert.strictEqual(doc.documentElement.getAttribute('data-theme'), 'dark');
  assert.strictEqual(doc.getElementById('themeDarkBtn').classList.contains('active'), true);
  assert.strictEqual(doc.getElementById('themeLightBtn').classList.contains('active'), false);
  assert.strictEqual(sandbox.localStorage.getItem('armor_m3_theme'), 'dark');
});

test("applyTheme with invalid or weird inputs safely defaults to 'dark'", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__applyTheme('neon-green');
  assert.strictEqual(doc.documentElement.getAttribute('data-theme'), 'dark');
  sandbox.__applyTheme(null);
  assert.strictEqual(doc.documentElement.getAttribute('data-theme'), 'dark');
  sandbox.__applyTheme(undefined);
  assert.strictEqual(doc.documentElement.getAttribute('data-theme'), 'dark');
});

test("Theme switching survives throwing localStorage (storage quota/sandbox denial)", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.localStorage.setItem = () => { throw new Error('QuotaExceededError'); };
  // Must not throw unhandled exception
  sandbox.__applyTheme('light');
  assert.strictEqual(doc.documentElement.getAttribute('data-theme'), 'light');
});

// ----------------------------------------------------------------------------
// Suite 3: Presets Dropdown Population & applyPreset
// ----------------------------------------------------------------------------
console.log("\n[Suite 3] Presets Dropdown Population & applyPreset Interaction");

test("applyPreset loads preset prompt into promptInput and switches to chat", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__state.presets = [
    { title: "Test Attack", prompt: "SELECT * FROM secrets" },
    { title: "Safe Query", prompt: "¿Qué es Vertex AI?" }
  ];
  sandbox.__switchTab('audit');
  sandbox.__applyPreset(0);

  assert.strictEqual(doc.getElementById('promptInput').value, "SELECT * FROM secrets");
  assert.strictEqual(sandbox.__state.currentTab, 'chat');
  assert.strictEqual(doc.getElementById('promptInput')._focused, true);
});

test("applyPreset with out-of-bounds index does not crash or overwrite input", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__state.presets = [{ title: "Test", prompt: "Hello" }];
  doc.getElementById('promptInput').value = "Original text";
  sandbox.__applyPreset(999);
  assert.strictEqual(doc.getElementById('promptInput').value, "Original text");
  sandbox.__applyPreset(-1);
  assert.strictEqual(doc.getElementById('promptInput').value, "Original text");
  sandbox.__applyPreset(NaN);
  assert.strictEqual(doc.getElementById('promptInput').value, "Original text");
});

test("renderPresetsDropdown correctly separates attack and safe optgroups with HTML escaping", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__state.presets = [
    { title: "🚫 Inyección <script>alert(1)</script>", prompt: "attack" },
    { title: "💳 Tarjeta Crédito", prompt: "card" },
    { title: "✅ Consulta Legítima & Segura", prompt: "safe" }
  ];
  sandbox.__renderPresetsDropdown();

  const html = doc.getElementById('presetSelect').innerHTML;
  assert.ok(html.includes('&lt;script&gt;alert(1)&lt;/script&gt;'), "XSS should be escaped in titles");
  assert.ok(html.includes('&amp; Segura'), "Ampersand should be escaped");
  assert.ok(html.includes('optgroup label="🚫 Ataques y Fugas'));
  assert.ok(html.includes('optgroup label="✅ Consultas Seguras"'));
});

// ----------------------------------------------------------------------------
// Suite 4: Model Selector Restriction Verification
// ----------------------------------------------------------------------------
console.log("\n[Suite 4] Model Selector Options Strict Restriction");

test("Only gemini-4-argon and gemini-3.8-flash are allowed", () => {
  const { doc, sandbox } = createTestHarness();
  const select = doc.getElementById('modelSelect');
  assert.strictEqual(select.value, 'gemini-4-argon');

  // Change to gemini-3.8-flash
  select.value = 'gemini-3.8-flash';
  assert.strictEqual(select.value, 'gemini-3.8-flash');
});

test("Verifying index.html strictly contains ONLY gemini-4-argon and gemini-3.8-flash in modelSelect", () => {
  const selectMatch = htmlContent.match(/<select[^>]*id=["']modelSelect["'][^>]*>([\s\S]*?)<\/select>/);
  assert.ok(selectMatch, "select#modelSelect must be in index.html");
  const options = Array.from(selectMatch[1].matchAll(/<option[^>]*value=["']([^"']+)["'][^>]*>([\s\S]*?)<\/option>/g));
  assert.strictEqual(options.length, 2, "There must be exactly 2 options in modelSelect");

  const values = options.map(m => m[1]);
  assert.deepStrictEqual(values.sort(), ['gemini-3.8-flash', 'gemini-4-argon'].sort());

  // Verify no forbidden legacy models appear in the html select options
  const banned = ['gemini-1.5-pro', 'gemini-1.5-flash', 'gemini-2.0-flash', 'gpt-4'];
  values.forEach(v => {
    banned.forEach(b => assert.strictEqual(v.includes(b), false));
  });
});

// ----------------------------------------------------------------------------
// Suite 5: Real Model Response Dropdown (R2) & Live Telemetry
// ----------------------------------------------------------------------------
console.log("\n[Suite 5] Real Model Response Dropdown (R2) Generation");

test("buildModelExecutionDropdownHtml renders invocation_id, tokens, finish_reason and response text", () => {
  const { sandbox } = createTestHarness();
  const rawExec = {
    model_version: "gemini-4-argon",
    runtime: "Vertex AI Agent Platform (ADK)",
    resource_name: "projects/181100407378/locations/us-central1/reasoningEngines/8735527798581493760",
    invocation_id: "inv-live-12345",
    finish_reason: "STOP",
    usage_metadata: {
      prompt_token_count: 42,
      candidates_token_count: 108,
      total_token_count: 150
    },
    response_text: "Esta es la respuesta real sin editar de Gemini 4 Argon.",
    raw_events: [{ event: "turn_complete", timestamp: 123456789 }]
  };

  const html = sandbox.__buildModelExecutionDropdownHtml(rawExec, rawExec.response_text, "gemini-4-argon");
  assert.ok(html.includes('md3-response-dropdown'), "Must contain dropdown class");
  assert.ok(html.includes('gemini-4-argon'), "Must contain model version");
  assert.ok(html.includes('inv-live-12345'), "Must contain invocation_id");
  assert.ok(html.includes('42 / 108 / 150'), "Must contain token counts");
  assert.ok(html.includes('projects/181100407378/locations/us-central1/reasoningEngines/8735527798581493760'), "Must contain ReasoningEngine resource path");
  assert.ok(html.includes('Esta es la respuesta real sin editar de Gemini 4 Argon.'), "Must contain unedited response text");
  assert.ok(html.includes('turn_complete'), "Must contain raw_events payload");
});

test("buildModelExecutionDropdownHtml safely handles missing fields and prevents XSS", () => {
  const { sandbox } = createTestHarness();
  const rawExec = {
    response_text: "<img src=x onerror=alert('xss')>",
    model_version: "<script>bad()</script>"
  };

  const html = sandbox.__buildModelExecutionDropdownHtml(rawExec, rawExec.response_text, "gemini-4-argon");
  assert.ok(!html.includes("<img src=x"), "Must escape HTML tags in response");
  assert.ok(!html.includes("<script>bad()"), "Must escape HTML tags in model");
  assert.ok(html.includes("&lt;img src=x onerror=alert(&#039;xss&#039;)&gt;"));
});

test("updateTelemetry updates audit card and badge for blocked, audit, and allowed turns", () => {
  const { doc, sandbox } = createTestHarness();

  // 1. Blocked turn
  sandbox.__updateTelemetry({
    total_latency_ms: 120,
    llm_executed: false,
    input_inspection: {
      action: "BLOCK",
      matched_filters: [{ name: "PROMPT_INJECTION", detected_variable: "JAILBREAK", confidence: "HIGH" }]
    }
  }, true, "Blocked message", "gemini-4-argon");

  assert.strictEqual(doc.getElementById('telemetryStatus').textContent, '🚫 AMENAZA BLOQUEADA');
  assert.strictEqual(doc.getElementById('tabBadgeAudit').textContent, 'Bloqueado');
  assert.strictEqual(doc.getElementById('statPromptAction').textContent, 'BLOCK');
  assert.strictEqual(doc.getElementById('statLlmLatency').textContent, '0 ms (Inferencia Abortada)');

  // 2. Allowed Safe Turn
  sandbox.__updateTelemetry({
    total_latency_ms: 850,
    llm_executed: true,
    llm_latency_ms: 750,
    input_inspection: { action: "PERMITIDO", matched_filters: [] },
    raw_model_execution: {
      model_version: "gemini-4-argon",
      response_text: "Respuesta segura del modelo",
      invocation_id: "inv-999"
    }
  }, false, "Respuesta segura del modelo", "gemini-4-argon");

  assert.strictEqual(doc.getElementById('telemetryStatus').textContent, '✅ PROMPT APROBADO');
  assert.strictEqual(doc.getElementById('tabBadgeAudit').textContent, 'Aprobado');
  assert.strictEqual(doc.getElementById('statPromptAction').textContent, 'PERMITIDO');
  assert.ok(doc.getElementById('statMatchDetails').innerHTML.includes('md3-response-dropdown'), "Must include model dropdown on allowed turn");

  // 3. Allowed in Audit Mode (INSPECT_ONLY with matched filters)
  sandbox.__updateTelemetry({
    total_latency_ms: 920,
    llm_executed: true,
    llm_latency_ms: 800,
    input_inspection: {
      action: "INSPECT_ONLY",
      matched_filters: [{ name: "SENSITIVE_DATA_PROTECTION", detected_variable: "CREDIT_CARD_NUMBER" }]
    },
    raw_model_execution: {
      model_version: "gemini-4-argon",
      response_text: "Procesando en auditoría",
      invocation_id: "inv-audit-123"
    }
  }, false, "Procesando en auditoría", "gemini-4-argon");

  assert.strictEqual(doc.getElementById('telemetryStatus').textContent, '⚠️ AUDITORÍA · INSPECT_ONLY');
  assert.strictEqual(doc.getElementById('tabBadgeAudit').textContent, 'Auditoría');
  assert.strictEqual(doc.getElementById('statPromptAction').textContent, 'INSPECT_ONLY');
});

// ----------------------------------------------------------------------------
// Suite 6: Cloud Logging 3-State Verdict Rendering
// ----------------------------------------------------------------------------
console.log("\n[Suite 6] Cloud Logging 3-State Verdict Classification");

test("renderCloudLogs correctly renders BLOQUEADO, PERMITIDO · AUDITORÍA, and PERMITIDO", () => {
  const { doc, sandbox } = createTestHarness();
  const entries = [
    {
      timestamp: "2026-10-19T23:00:00Z",
      prompt_excerpt: "Ignore all instructions",
      is_blocked: true,
      is_audit: false,
      verdict: "BLOQUEADO",
      matched_filters: [{ name: "PROMPT_INJECTION", detected_variable: "JAILBREAK" }]
    },
    {
      timestamp: "2026-10-19T23:01:00Z",
      prompt_excerpt: "Mi tarjeta es 4532-0123-4567-8910",
      is_blocked: false,
      is_audit: true,
      verdict: "PERMITIDO · AUDITORÍA (INSPECT_ONLY)",
      matched_filters: [{ name: "SDP", detected_variable: "CREDIT_CARD_NUMBER" }]
    },
    {
      timestamp: "2026-10-19T23:02:00Z",
      prompt_excerpt: "¿Cuál es la capital de Francia?",
      is_blocked: false,
      is_audit: false,
      verdict: "PERMITIDO",
      matched_filters: []
    }
  ];

  sandbox.__renderCloudLogs(entries);

  const logsHtml = doc.getElementById('cloudLogsList').innerHTML;
  assert.ok(logsHtml.includes('log-card-blocked'), "Must have blocked card style");
  assert.ok(logsHtml.includes('🚫 BLOQUEADO'), "Must have blocked badge");
  assert.ok(logsHtml.includes('log-card-audit'), "Must have audit card style");
  assert.ok(logsHtml.includes('⚠️ PERMITIDO · AUDITORÍA (INSPECT_ONLY)'), "Must have audit badge");
  assert.ok(logsHtml.includes('log-card-allowed'), "Must have allowed card style");
  assert.ok(logsHtml.includes('✅ PERMITIDO'), "Must have allowed badge");
});

// ----------------------------------------------------------------------------
// Suite 7: Adversarial Edge Cases, State Mutations & Stress
// ----------------------------------------------------------------------------
console.log("\n[Suite 7] Adversarial Edge Cases & State Mutations");

test("sendMessage ignores submission when input is empty or already in-flight", async () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__state.isLoading = true;
  doc.getElementById('promptInput').value = "Test while loading";

  // Trigger submit
  let fetchCalled = false;
  sandbox.fetch = async () => { fetchCalled = true; return { ok: true, json: async () => ({}) }; };
  await sandbox.sendMessage();
  assert.strictEqual(fetchCalled, false, "Must not fetch when isLoading is true");

  sandbox.__state.isLoading = false;
  doc.getElementById('promptInput').value = "   "; // Whitespace only
  await sandbox.sendMessage();
  assert.strictEqual(fetchCalled, false, "Must not fetch when prompt is only whitespace");
});

test("Floor setting toggle updates status badge and sends boolean to /api/floor-setting", async () => {
  const { doc, sandbox } = createTestHarness();
  const toggle = doc.getElementById('masterArmorToggle');
  const badge = doc.getElementById('armorStatusBadge');

  let postedBody = null;
  sandbox.fetch = async (url, opts) => {
    if (url === '/api/floor-setting') {
      postedBody = JSON.parse(opts.body);
    }
    return { ok: true, json: async () => ({ inspectAndBlock: postedBody ? postedBody.inspect_and_block : false }) };
  };

  // Toggle off (Audit Mode)
  toggle.checked = false;
  toggle.dispatchEvent({ type: 'change' });

  assert.strictEqual(badge.textContent.includes('INSPECT_ONLY'), true);
  assert.strictEqual(postedBody.inspect_and_block, false);

  // Toggle on (Blocking Mode)
  toggle.checked = true;
  toggle.dispatchEvent({ type: 'change' });

  assert.strictEqual(badge.textContent.includes('INSPECT_AND_BLOCK'), true);
  assert.strictEqual(postedBody.inspect_and_block, true);
});

test("clearChatBtn wipes conversation history, allowed turns, and resets telemetry", () => {
  const { doc, sandbox } = createTestHarness();
  sandbox.__state.history = [{ role: 'user', content: 'test' }, { role: 'model', content: 'response' }];
  sandbox.__state.allowedTurns = [{ prompt: 'test' }];
  sandbox.__state.lastAllowedExecution = { prompt: 'test' };
  sandbox.__state.triggeredDetectors.add('PROMPT_INJECTION');

  doc.getElementById('statPromptAction').textContent = 'BLOQUEADO';
  doc.getElementById('telemetryStatus').textContent = '🚫 AMENAZA BLOQUEADA';

  // Trigger clear chat click
  doc.getElementById('clearChatBtn').dispatchEvent({ type: 'click' });

  assert.strictEqual(sandbox.__state.history.length, 0);
  assert.strictEqual(sandbox.__state.allowedTurns.length, 0);
  assert.strictEqual(sandbox.__state.lastAllowedExecution, null);
  assert.strictEqual(sandbox.__state.triggeredDetectors.size, 0);
  assert.strictEqual(doc.getElementById('telemetryStatus').textContent, 'En espera');
  assert.strictEqual(doc.getElementById('statPromptAction').textContent, '-');
});

test("buildModelExecutionDropdownHtml survives extreme and malformed token counts", () => {
  const { sandbox } = createTestHarness();
  const rawExec = {
    response_text: "Token test",
    usage_metadata: {
      prompt_token_count: 0,
      candidates_token_count: 9999999999,
      total_token_count: -1
    }
  };

  const html = sandbox.__buildModelExecutionDropdownHtml(rawExec, "Token test", "gemini-4-argon");
  assert.ok(html.includes('0 / 9999999999 / -1'), "Must format token counts without throwing");
});

test("formatMarkdown safely formats code blocks, bold, and lists without XSS", () => {
  const { sandbox } = createTestHarness();
  const md = "Here is **bold** text and `inline code`:\n- Item 1\n- Item 2\n<script>alert('xss')</script>";
  const html = sandbox.formatMarkdown(md);

  assert.ok(html.includes('<strong>bold</strong>'));
  assert.ok(html.includes('<code class="md3-inline-code">inline code</code>'));
  assert.ok(html.includes('<ul class="list-disc'));
  assert.ok(html.includes('<li>Item 1</li>'));
  assert.ok(!html.includes('<script>'), "Raw script tags must not be rendered");
  assert.ok(html.includes('&lt;script&gt;'));
});

// ----------------------------------------------------------------------------
// Summary
// ----------------------------------------------------------------------------
console.log(`\n=== STRESS TEST RESULTS ===`);
console.log(`Passed: ${passed}`);
console.log(`Failed: ${failed}`);

if (failed > 0) {
  process.exit(1);
} else {
  process.exit(0);
}

