/* =============================================
   Agapay AI Studio — Module Test Harness JS
   static/js/test.js
   ============================================= */

// =============================================
// Module Metadata
// =============================================
const MODULE_META = {
    triage: {
        label: 'Triage Module',
        desc: 'Normalizes multilingual input into formal English and detects the source language',
        badgeClass: 'badge-triage',
        icon: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>`,
        configKeys: [],
    },
    router: {
        label: 'Router Module',
        desc: 'Classifies normalized text and determines the legal routing path (General / Reasoning / Casual)',
        badgeClass: 'badge-router',
        icon: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="16 3 21 3 21 8"/><line x1="4" y1="20" x2="21" y2="3"/><polyline points="21 16 21 21 16 21"/><line x1="15" y1="15" x2="21" y2="21"/><line x1="4" y1="4" x2="9" y2="9"/></svg>`,
        configKeys: ['router_model'],
    },
    general: {
        label: 'General LLM',
        desc: 'Generates accessible legal information responses, optionally augmented with RAG context',
        badgeClass: 'badge-general',
        icon: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`,
        configKeys: ['general_model', 'general_instructions'],
        instrKey: 'general_instructions',
        instrEl: 'general-system-instructions',
    },
    reasoning: {
        label: 'Reasoning LLM',
        desc: 'Produces detailed legal analysis using the ALAC-style format, with optional RAG context',
        badgeClass: 'badge-reasoning',
        icon: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 1 1 7.072 0l-.548.547A3.374 3.374 0 0 0 14 18.469V19a2 2 0 1 1-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"/></svg>`,
        configKeys: ['reasoning_model', 'reasoning_instructions'],
        instrKey: 'reasoning_instructions',
        instrEl: 'reasoning-system-instructions',
    },
    casual: {
        label: 'Casual LLM',
        desc: 'Handles greetings and off-topic queries with friendly redirection — no RAG context used',
        badgeClass: 'badge-casual',
        icon: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
        configKeys: ['casual_model', 'casual_instructions'],
        instrKey: 'casual_instructions',
        instrEl: 'casual-system-instructions',
    },
    retrieval: {
        label: 'Legal Retrieval (RAG)',
        desc: 'Searches the FAISS index using hybrid BM25 + semantic search to retrieve relevant legal document chunks',
        badgeClass: 'badge-retrieval',
        icon: `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>`,
        configKeys: [],
    },
};

// =============================================
// State
// =============================================
const MODULE   = window.TEST_MODULE;
const meta     = MODULE_META[MODULE] || {};
let isRunning  = false;
let startTime  = null;
let timerInterval = null;
let logSource  = null;

// =============================================
// Init
// =============================================
document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    applyModuleMeta();
    showModuleInputs();
    loadConfig();
    initSliders();
    initLogDrawer();
    initButtons();
});

function applyModuleMeta() {
    const badge = document.getElementById('module-badge');
    const desc  = document.getElementById('module-desc');
    if (badge) {
        badge.className = `test-module-badge ${meta.badgeClass || ''}`;
        badge.innerHTML = `${meta.icon || ''} ${meta.label || MODULE}`;
    }
    if (desc) desc.textContent = meta.desc || '';
    document.title = `Test — ${meta.label || MODULE} — Agapay AI Studio`;
}

function showModuleInputs() {
    document.querySelectorAll('.module-inputs').forEach(el => el.style.display = 'none');
    const panel = document.getElementById(`inputs-${MODULE}`);
    if (panel) panel.style.display = 'flex';
}

async function loadConfig() {
    if (!meta.instrKey) return; // only load for LLM modules
    try {
        const res  = await fetch('/api/config');
        const cfg  = await res.json();
        
        // 1. System Instructions
        const instrEl = document.getElementById(meta.instrEl);
        if (instrEl && cfg[meta.instrKey]) {
            instrEl.value = cfg[meta.instrKey];
        }
        
        // 2. Hyperparameters
        const tempKey = `${MODULE}_temp`;
        const maxTokensKey = `${MODULE}_max_tokens`;
        
        const tempEl = document.getElementById(`${MODULE}-temp`);
        const tempValEl = document.getElementById(`${MODULE}-temp-val`);
        const maxTokensEl = document.getElementById(`${MODULE}-max-tokens`);
        
        if (tempEl && cfg[tempKey] !== undefined) {
            tempEl.value = cfg[tempKey];
            if (tempValEl) tempValEl.textContent = parseFloat(cfg[tempKey]).toFixed(2);
        }
        if (maxTokensEl && cfg[maxTokensKey] !== undefined) {
            maxTokensEl.value = cfg[maxTokensKey];
        }

        // Show model in footer
        const modelKey = `${MODULE}_model`;
        const footerModel = document.getElementById('footer-model');
        if (footerModel && cfg[modelKey]) {
            footerModel.textContent = `Model: ${cfg[modelKey]}`;
        }
    } catch (err) {
        console.warn('Config load failed:', err);
    }
}

window.resetToDefaults = async function(moduleName) {
    if (!confirm('Reset all overrides to current framework defaults?')) return;
    await loadConfig();
    showToast('Restored defaults from framework config', 'success');
};

// =============================================
// Theme (mirrors main app)
// =============================================
const MOON_PATH = 'M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z';
const SUN_PATH  = 'M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z';

function initTheme() {
    const saved = localStorage.getItem('theme');
    const icon  = document.getElementById('theme-icon');
    if (saved === 'light') {
        document.body.setAttribute('data-theme', 'light');
        if (icon) icon.setAttribute('d', SUN_PATH);
    }
    document.getElementById('theme-btn').addEventListener('click', () => {
        if (document.body.getAttribute('data-theme') === 'light') {
            document.body.removeAttribute('data-theme');
            localStorage.setItem('theme', 'dark');
            if (icon) icon.setAttribute('d', MOON_PATH);
        } else {
            document.body.setAttribute('data-theme', 'light');
            localStorage.setItem('theme', 'light');
            if (icon) icon.setAttribute('d', SUN_PATH);
        }
    });
}

// =============================================
// Slider init
// =============================================
function initSliders() {
    const threshold = document.getElementById('router-threshold');
    const threshVal = document.getElementById('router-threshold-val');
    if (threshold && threshVal) {
        threshold.addEventListener('input', () => {
            threshVal.textContent = parseFloat(threshold.value).toFixed(2);
        });
    }

    // Module specific temperature sliders
    ['general', 'reasoning', 'casual'].forEach(m => {
        const slider = document.getElementById(`${m}-temp`);
        const val    = document.getElementById(`${m}-temp-val`);
        if (slider && val) {
            slider.addEventListener('input', () => {
                val.textContent = parseFloat(slider.value).toFixed(2);
            });
        }
    });

    const topK    = document.getElementById('retrieval-top-k');
    const topKVal = document.getElementById('retrieval-top-k-val');
    if (topK && topKVal) {
        topK.addEventListener('input', () => { topKVal.textContent = topK.value; });
    }
}

// =============================================
// Expander toggle
// =============================================
window.toggleExpander = function(id) {
    document.getElementById(id).classList.toggle('open');
};

// =============================================
// Buttons
// =============================================
function initButtons() {
    document.getElementById('run-btn').addEventListener('click', runTest);
    document.getElementById('reset-btn').addEventListener('click', resetForm);
    document.getElementById('clear-output-btn').addEventListener('click', clearOutput);
    document.getElementById('clear-logs-btn').addEventListener('click', () => {
        document.getElementById('log-entries').innerHTML = '';
    });
}

// =============================================
// Log Drawer
// =============================================
function initLogDrawer() {
    const toggleBtn  = document.getElementById('log-toggle-btn');
    const drawer     = document.getElementById('log-drawer');
    const toggleText = document.getElementById('log-toggle-text');

    toggleBtn.addEventListener('click', () => {
        const open = drawer.classList.toggle('open');
        toggleText.textContent = open ? 'Hide Logs' : 'Show Logs';
        if (open && !logSource) startLogSSE();
    });
}

function startLogSSE() {
    logSource = new EventSource('/api/logs');
    logSource.onmessage = (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data.type === 'connected') return;
            appendLog(data);
        } catch {}
    };
    logSource.onerror = () => {
        // SSE connection lost — it will retry automatically
    };
}

function appendLog(entry) {
    const container = document.getElementById('log-entries');
    if (!container) return;
    const line = document.createElement('div');
    line.className = `test-log-entry ${entry.level || 'INFO'}`;
    line.textContent = entry.message || JSON.stringify(entry);
    container.appendChild(line);
    container.scrollTop = container.scrollHeight;
}

// =============================================
// Output helpers
// =============================================
function clearOutput() {
    const area = document.getElementById('output-area');
    area.innerHTML = `
        <div class="test-output-empty" id="output-empty">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                <polygon points="5 3 19 12 5 21 5 3"/>
            </svg>
            <p>Fill in the inputs on the left and click <strong>Run Test</strong> to see the module output here.</p>
        </div>`;
    setFooterStatus('Ready');
    stopTimer();
}

function setFooterStatus(text) {
    const el = document.getElementById('footer-status');
    if (el) el.textContent = text;
}

function startTimer() {
    startTime = Date.now();
    const timerEl = document.getElementById('run-timer');
    timerInterval = setInterval(() => {
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
        if (timerEl) timerEl.textContent = `${elapsed}s`;
    }, 100);
}

function stopTimer() {
    clearInterval(timerInterval);
    const timerEl = document.getElementById('run-timer');
    if (timerEl && startTime) {
        const elapsed = ((Date.now() - startTime) / 1000).toFixed(2);
        timerEl.textContent = `Completed in ${elapsed}s`;
    }
    startTime = null;
}

function setRunning(flag) {
    isRunning = flag;
    const btn = document.getElementById('run-btn');
    if (!btn) return;
    btn.disabled = flag;
    if (flag) {
        btn.classList.add('running');
    } else {
        btn.classList.remove('running');
    }
}

function getOutputArea() {
    const area = document.getElementById('output-area');
    // Remove empty state if present
    const empty = area.querySelector('.test-output-empty');
    if (empty) empty.remove();
    return area;
}

function escapeHtml(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
}

function renderMarkdown(text) {
    if (!text) return '';
    let parsed = text;
    parsed = parsed.replace(/<think>([\s\S]*?)<\/think>/gi, (match, inner) => {
        return `<details class="reasoning-block"><summary>💡 View Reasoning / Thought Process</summary><div class="reasoning-content">${inner}</div></details>\n`;
    });
    if (parsed.includes('<think>') && !parsed.includes('</think>')) {
        parsed = parsed.replace(/<think>/gi, '<details open class="reasoning-block"><summary>💡 Thinking...</summary><div class="reasoning-content">\n');
        parsed += '\n</div></details>';
    }
    const rawHtml = marked.parse(parsed, { breaks: true, gfm: true });
    return DOMPurify.sanitize(rawHtml, {
        ADD_TAGS: ['details', 'summary', 'sup'],
        ADD_ATTR: ['open', 'class', 'data-ref', 'style']
    });
}

// =============================================
// Toast
// =============================================
function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 3200);
}

// =============================================
// Pipeline step builder (shared for LLM modules)
// =============================================
function createPipelineEl() {
    const pipeline = document.createElement('div');
    pipeline.className = 'test-pipeline';
    pipeline.innerHTML = `<div class="test-pipe-step active"><span class="step-icon"><div class="pipe-spinner"></div></span><span>Initializing...</span></div>`;
    return pipeline;
}

function addPipeStep(pipeline, text, state = 'active') {
    // Mark previous active as done
    const prev = pipeline.querySelector('.test-pipe-step.active');
    if (prev) {
        prev.classList.remove('active');
        prev.classList.add('done');
        const icon = prev.querySelector('.step-icon');
        if (icon) icon.textContent = '✓';
    }
    const step = document.createElement('div');
    step.className = `test-pipe-step ${state}`;
    if (state === 'active') {
        step.innerHTML = `<span class="step-icon"><div class="pipe-spinner"></div></span><span>${escapeHtml(text)}</span>`;
    } else if (state === 'done') {
        step.innerHTML = `<span class="step-icon">✓</span><span>${escapeHtml(text)}</span>`;
    } else {
        step.innerHTML = `<span class="step-icon">✗</span><span>${escapeHtml(text)}</span>`;
    }
    pipeline.appendChild(step);
}

function finalizePipeline(pipeline) {
    const active = pipeline.querySelector('.test-pipe-step.active');
    if (active) {
        active.classList.remove('active');
        active.classList.add('done');
        const icon = active.querySelector('.step-icon');
        if (icon) icon.textContent = '✓';
    }
}

// =============================================
// Reset Form
// =============================================
function resetForm() {
    const textareas = document.querySelectorAll(`#inputs-${MODULE} textarea, #inputs-${MODULE} input[type="text"]`);
    textareas.forEach(ta => {
        if (!ta.id.includes('system-instructions')) ta.value = '';
    });
    clearOutput();
    showToast('Form reset', 'info');
}

// =============================================
// Run Test Router
// =============================================
async function runTest() {
    if (isRunning) return;
    clearOutput();
    setRunning(true);
    setFooterStatus('Running…');
    startTimer();

    try {
        switch (MODULE) {
            case 'triage':    await runTriage();    break;
            case 'router':    await runRouter();    break;
            case 'general':   await runLLM('general');   break;
            case 'reasoning': await runLLM('reasoning'); break;
            case 'casual':    await runLLM('casual');    break;
            case 'retrieval': await runRetrieval(); break;
            default:
                showToast('Unknown module', 'error');
        }
    } catch (err) {
        const area = getOutputArea();
        area.innerHTML += `
            <div class="test-error-card">
                <span class="test-error-icon">⚠️</span>
                <span class="test-error-message">Network or unexpected error: ${escapeHtml(err.message)}</span>
            </div>`;
        setFooterStatus('Error');
    } finally {
        setRunning(false);
        stopTimer();
    }
}

// =============================================
// Triage Test
// =============================================
async function runTriage() {
    const raw = document.getElementById('triage-raw-input').value.trim();
    if (!raw) { showToast('Raw input is required', 'error'); setRunning(false); stopTimer(); return; }

    setFooterStatus('Normalizing…');
    const res  = await fetch('/api/test/triage', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_input: raw })
    });
    const data = await res.json();
    const area = getOutputArea();

    if (data.error) {
        area.innerHTML += `
            <div class="test-error-card">
                <span class="test-error-icon">⚠️</span>
                <span class="test-error-message"><strong>Error:</strong> ${escapeHtml(data.error)}</span>
            </div>`;
        setFooterStatus('Error');
        return;
    }

    area.innerHTML += `
        <div class="triage-result-card">
            <div class="triage-result-header">
                <div class="triage-status-icon">✓</div>
                <span class="triage-result-title">Triage Complete</span>
            </div>
            <div class="triage-result-body">
                <div>
                    <div class="triage-field-label">Detected Language</div>
                    <span class="triage-language-badge">🌐 ${escapeHtml(data.detected_language || 'Unknown')}</span>
                </div>
                <div>
                    <div class="triage-field-label">Original Input</div>
                    <div class="triage-normalized-text">${escapeHtml(data.original_prompt || raw)}</div>
                </div>
                <div>
                    <div class="triage-field-label">Normalized English Output</div>
                    <div class="triage-normalized-text" style="color:var(--accent-green);border-color:rgba(16,185,129,0.3);">${escapeHtml(data.normalized_text || '(empty)')}</div>
                </div>
            </div>
        </div>`;
    setFooterStatus('Done');
}

// =============================================
// Router Test
// =============================================
async function runRouter() {
    const text      = document.getElementById('router-normalized-text').value.trim();
    const threshold = parseFloat(document.getElementById('router-threshold').value);
    if (!text) { showToast('Normalized text is required', 'error'); setRunning(false); stopTimer(); return; }

    setFooterStatus('Classifying…');
    const res  = await fetch('/api/test/router', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ normalized_text: text, threshold })
    });
    const data = await res.json();
    const area = getOutputArea();

    if (data.error) {
        area.innerHTML += `
            <div class="test-error-card">
                <span class="test-error-icon">⚠️</span>
                <span class="test-error-message"><strong>Error:</strong> ${escapeHtml(data.error)}</span>
            </div>`;
        setFooterStatus('Error');
        return;
    }

    const route      = data.route || 'null';
    const confidence = Math.min(1, Math.max(0, parseFloat(data.confidence || 0)));
    const signals    = Array.isArray(data.search_signals) ? data.search_signals : [];
    const pct        = Math.round(confidence * 100);
    const routeClass = `route-${route.replace(/[^a-zA-Z-]/g,'') || 'null'}`;

    const signalsHtml = signals.length > 0
        ? signals.map(s => `<span class="signal-chip">${escapeHtml(s)}</span>`).join('')
        : '<span class="no-signals">No search signals returned (non-legal query or below threshold)</span>';

    const errorBanner = data.error
        ? `<div style="padding:8px 0;"><span style="color:var(--accent-red);font-size:0.8rem;">⚠ ${escapeHtml(data.error)}</span></div>`
        : '';

    area.innerHTML += `
        <div class="router-result-card">
            <div class="router-result-header">
                <div class="route-badge ${routeClass}">
                    🔀 ${escapeHtml(route)}
                </div>
                <div class="confidence-bar-wrap">
                    <div class="confidence-bar-track">
                        <div class="confidence-bar-fill" style="width:${pct}%"></div>
                    </div>
                    <span class="confidence-value">${pct}%</span>
                </div>
            </div>
            <div class="router-result-body">
                ${errorBanner}
                <div>
                    <div class="triage-field-label" style="margin-bottom:8px;">Search Signals (RAG Keywords)</div>
                    <div class="signals-list">${signalsHtml}</div>
                </div>
                <div style="padding-top:8px;border-top:1px solid var(--border-subtle);">
                    <div class="triage-field-label" style="margin-bottom:4px;">Interpretation</div>
                    <div style="font-size:0.8rem;color:var(--text-secondary);line-height:1.6;">
                        ${getRouteInterpretation(route, confidence, threshold)}
                    </div>
                </div>
            </div>
        </div>`;
    setFooterStatus('Done');
}

function getRouteInterpretation(route, confidence, threshold) {
    const pct = Math.round(confidence * 100);
    const map = {
        'General-LLM': `Query routed to the <strong>General LLM</strong> for accessible legal information. Confidence: <strong>${pct}%</strong>.`,
        'Reasoning-LLM':   `Query routed to the <strong>Reasoning LLM</strong> for detailed legal analysis. Confidence: <strong>${pct}%</strong>.`,
        'Casual-LLM':  `Query identified as <strong>casual / off-topic</strong> — will be handled with a friendly redirect. Confidence: <strong>${pct}%</strong>.`,
        'null':         `Classification failed — confidence (${pct}%) was persistently below threshold (${Math.round(threshold*100)}%). The pipeline would fall back to General-LLM.`,
    };
    return map[route] || `Route: ${route} (${pct}%)`;
}

// =============================================
// LLM Module Test (General / Reasoning / Casual)
// =============================================
async function runLLM(moduleName) {
    const msgEl  = document.getElementById(`${moduleName}-user-message`);
    const instrEl = document.getElementById(`${moduleName}-system-instructions`);
    const ragEl  = moduleName !== 'casual' ? document.getElementById(`${moduleName}-rag-context`) : null;
    
    // Hyperparameters
    const tempEl = document.getElementById(`${moduleName}-temp`);
    const maxTokensEl = document.getElementById(`${moduleName}-max-tokens`);

    const userMessage = msgEl ? msgEl.value.trim() : '';
    if (!userMessage) { showToast('User message is required', 'error'); setRunning(false); stopTimer(); return; }

    const systemInstructions = instrEl ? instrEl.value.trim() || null : null;
    const ragContext          = ragEl   ? ragEl.value.trim()   || null : null;
    
    const temperature = tempEl ? parseFloat(tempEl.value) : null;
    const maxTokens   = maxTokensEl ? parseInt(maxTokensEl.value) : null;

    const area     = getOutputArea();
    const pipeline = createPipelineEl();
    area.appendChild(pipeline);

    const responseCard = document.createElement('div');
    responseCard.className = 'llm-response-card';

    const routeLabels = { general: 'General-LLM', reasoning: 'Reasoning-LLM', casual: 'Casual-LLM' };
    const routeLabel  = routeLabels[moduleName] || moduleName;
    const routeChipClass = { 'General-LLM': 'route-General-LLM', 'Reasoning-LLM': 'route-Reasoning-LLM', 'Casual-LLM': 'route-Casual-LLM' }[routeLabel] || '';

    responseCard.innerHTML = `
        <div class="llm-response-header">
            <span class="llm-response-route-chip ${routeChipClass}">${escapeHtml(routeLabel)}</span>
            <span style="font-size:0.72rem;color:var(--text-muted);margin-left:auto;">Response</span>
        </div>
        <div class="llm-response-body markdown-body" id="llm-response-body"></div>`;

    setFooterStatus('Generating…');

    try {
        const res = await fetch(`/api/test/${moduleName}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                user_message: userMessage,
                system_instructions: systemInstructions,
                rag_context: ragContext,
                temperature: temperature,
                max_tokens: maxTokens
            })
        });

        const reader  = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer    = '';
        let gotResult = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop();

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const event = JSON.parse(line);
                    if (event.type === 'step') {
                        addPipeStep(pipeline, event.content, 'active');
                    } else if (event.type === 'result') {
                        finalizePipeline(pipeline);
                        area.appendChild(responseCard);
                        const bodyEl = document.getElementById('llm-response-body');
                        if (bodyEl) bodyEl.innerHTML = renderMarkdown(event.content);
                        gotResult = true;
                        setFooterStatus('Done');
                    } else if (event.type === 'error') {
                        addPipeStep(pipeline, event.content, 'error');
                        area.innerHTML += `
                            <div class="test-error-card">
                                <span class="test-error-icon">⚠️</span>
                                <span class="test-error-message">${escapeHtml(event.content)}</span>
                            </div>`;
                        setFooterStatus('Error');
                    }
                } catch {}
            }
        }

        // Process remaining buffer
        if (buffer.trim()) {
            try {
                const event = JSON.parse(buffer);
                if (event.type === 'result' && !gotResult) {
                    finalizePipeline(pipeline);
                    area.appendChild(responseCard);
                    const bodyEl = document.getElementById('llm-response-body');
                    if (bodyEl) bodyEl.innerHTML = renderMarkdown(event.content);
                }
            } catch {}
        }

    } catch (err) {
        addPipeStep(pipeline, `Network error: ${err.message}`, 'error');
        setFooterStatus('Error');
    }
}

// =============================================
// Retrieval Test
// =============================================
async function runRetrieval() {
    const query   = document.getElementById('retrieval-query').value.trim();
    const signals = document.getElementById('retrieval-signals').value.trim();
    const topK    = parseInt(document.getElementById('retrieval-top-k').value, 10);

    if (!query) { showToast('Search query is required', 'error'); setRunning(false); stopTimer(); return; }

    setFooterStatus('Retrieving…');
    const res  = await fetch('/api/test/retrieval', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, signals, top_k: topK })
    });
    const data = await res.json();
    const area = getOutputArea();

    if (data.error) {
        area.innerHTML += `
            <div class="test-error-card">
                <span class="test-error-icon">⚠️</span>
                <span class="test-error-message"><strong>Error:</strong> ${escapeHtml(data.error)}</span>
            </div>`;
        setFooterStatus('Error');
        return;
    }

    const chunks = data.chunks || [];
    const countBadge = `<span class="retrieval-count-badge">📚 ${chunks.length} chunk${chunks.length !== 1 ? 's' : ''} retrieved</span>`;

    area.innerHTML += `
        <div class="retrieval-summary">
            ${countBadge}
            <span style="font-size:0.72rem;color:var(--text-muted);">Combined query: <em>${escapeHtml(data.combined_query || query)}</em></span>
        </div>`;

    if (chunks.length === 0) {
        area.innerHTML += `
            <div style="text-align:center;padding:32px;color:var(--text-muted);font-size:0.82rem;">
                No relevant chunks found in the index for this query.
            </div>`;
        setFooterStatus('Done — 0 chunks');
        return;
    }

    chunks.forEach((chunk, i) => {
        const meta = chunk.metadata || {};
        const score = (typeof chunk.score === 'number') ? chunk.score.toFixed(4) : 'N/A';

        // Build metadata tags
        const metaTags = Object.entries(meta)
            .filter(([k, v]) => v && typeof v === 'string' && k !== 'chunk_index')
            .map(([k, v]) => `<span class="chunk-meta-tag">${escapeHtml(k)}: ${escapeHtml(v)}</span>`)
            .join('');

        area.innerHTML += `
            <div class="chunk-card">
                <div class="chunk-card-header">
                    <span class="chunk-source-label">Source [${i + 1}]</span>
                    <span class="chunk-score-badge">Score: ${score}</span>
                </div>
                ${metaTags ? `<div class="chunk-meta">${metaTags}</div>` : ''}
                <div class="chunk-text">${escapeHtml(chunk.text || '')}</div>
            </div>`;
    });

    setFooterStatus(`Done — ${chunks.length} chunks`);
}
