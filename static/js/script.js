/* =============================================
   Agapay AI Studio — Client Application
   ============================================= */

// =============================================
// DOM Cache
// =============================================
const DOM = {
    chatForm: document.getElementById('chat-form'),
    userInput: document.getElementById('user-input'),
    sendBtn: document.getElementById('send-btn'),
    chatMessages: document.getElementById('chat-messages'),
    chatScroll: document.getElementById('chat-scroll'),
    welcomeScreen: document.getElementById('welcome-screen'),
    // Header
    themeBtn: document.getElementById('theme-btn'),
    themeIcon: document.getElementById('theme-icon'),
    sidebarToggle: document.getElementById('sidebar-toggle-btn'),
    panelToggle: document.getElementById('panel-toggle-btn'),
    // Sync
    syncDot: document.getElementById('sync-dot'),
    syncText: document.getElementById('sync-text'),
    syncStatus: document.getElementById('sync-status'),
    // Sidebar
    sidebar: document.getElementById('sidebar'),
    newChatBtn: document.getElementById('new-chat-btn'),
    saveChatBtn: document.getElementById('save-chat-btn'),
    loadFileBtn: document.getElementById('load-file-btn'),
    loadFileInput: document.getElementById('load-file-input'),
    convoList: document.getElementById('conversations-list'),
    // Right Panel
    rightPanel: document.getElementById('right-panel'),
    configPanel: document.getElementById('config-panel'),
    // Config Actions
    saveConfigBtn: document.getElementById('save-config-btn'),
    exportConfigBtn: document.getElementById('export-config-btn'),
    importConfigBtn: document.getElementById('import-config-btn'),
    importConfigInput: document.getElementById('import-config-input'),
    // Logs
    logsContent: document.getElementById('logs-content'),
    logStatusDot: document.getElementById('log-status-dot'),
    logStatusText: document.getElementById('log-status-text'),
    clearLogsBtn: document.getElementById('clear-logs-btn'),
    // Status Bar
    statusSession: document.getElementById('status-session'),
    statusRoute: document.getElementById('status-route'),
    statusMsgCount: document.getElementById('status-msg-count'),
    // Modals
    ragModal: document.getElementById('rag-modal'),
    ragModalBody: document.getElementById('rag-modal-body'),
    detailsModal: document.getElementById('details-modal'),
    detailsModalTitle: document.getElementById('details-modal-title'),
    detailsModalBody: document.getElementById('details-modal-body'),
    instructionsModal: document.getElementById('instructions-modal'),
    instructionsModalTitle: document.getElementById('instructions-modal-title'),
    instructionsModalTextarea: document.getElementById('instructions-modal-textarea'),
    instructionsModalMeta: document.getElementById('instructions-modal-meta'),
    instrModalCharCount: document.getElementById('instr-modal-char-count'),
    // Toast
    toastContainer: document.getElementById('toast-container'),
};

// =============================================
// State
// =============================================
let state = {
    isProcessing: false,
    sessionId: null,
    currentRoute: null,
    messageCount: 0,
    currentRagChunks: [],
    chatHistory: [], // local mirror for save/load (includes full pipeline events)
    // Module enabled states for developer testing
    moduleEnabled: {
        triage: true,
        router: true,
        general: true,
        reasoning: true,
        casual: true,
    },
};

// Active module for instructions modal
let _activeInstrModule = null;

// =============================================
// 1. Theme Manager
// =============================================
const MOON_PATH = "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z";
const SUN_PATH = "M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z";

function initTheme() {
    const saved = localStorage.getItem('theme');
    if (saved === 'light') {
        document.body.setAttribute('data-theme', 'light');
        DOM.themeIcon.setAttribute('d', SUN_PATH);
    }
    // default is dark (no data-theme attr needed)
}

DOM.themeBtn.addEventListener('click', () => {
    if (document.body.getAttribute('data-theme') === 'light') {
        document.body.removeAttribute('data-theme');
        localStorage.setItem('theme', 'dark');
        DOM.themeIcon.setAttribute('d', MOON_PATH);
    } else {
        document.body.setAttribute('data-theme', 'light');
        localStorage.setItem('theme', 'light');
        DOM.themeIcon.setAttribute('d', SUN_PATH);
    }
});

initTheme();

// =============================================
// 2. Panel Manager (sidebar / right panel toggle)
// =============================================
DOM.sidebarToggle.addEventListener('click', () => {
    DOM.sidebar.classList.toggle('force-show');
});

DOM.panelToggle.addEventListener('click', () => {
    DOM.rightPanel.classList.toggle('force-show');
});

// Panel tab switching
document.querySelectorAll('.panel-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.panel-content').forEach(c => c.classList.remove('active'));
        tab.classList.add('active');
        document.getElementById(tab.dataset.tab).classList.add('active');
    });
});

// Config section collapse/expand
window.toggleConfigSection = function(headerEl) {
    headerEl.closest('.config-section').classList.toggle('open');
};

// =============================================
// 3. Sync Status
// =============================================
const SYNC_POLL_INTERVAL = 15000; // 15s

async function updateSyncStatus() {
    try {
        console.log('[Sync] Checking index status...');
        const res = await fetch('/api/sync-status');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        
        const data = await res.json();
        
        if (data.error) {
            console.error('[Sync] Server reported error:', data.error);
            DOM.syncDot.className = 'sync-dot red';
            DOM.syncText.textContent = 'Sync Error';
            DOM.syncStatus.title = `Error: ${data.error}`;
            return;
        }

        if (data.is_synced) {
            DOM.syncDot.className = 'sync-dot green';
            DOM.syncText.textContent = 'Index Synced';
            DOM.syncStatus.title = `Index up to date with ${data.corpus_count} documents.`;
        } else {
            DOM.syncDot.className = 'sync-dot yellow';
            DOM.syncText.textContent = `Out of Sync (${data.missing_count})`;
            DOM.syncStatus.title = `${data.missing_count} documents missing from index.`;
        }
        console.log('[Sync] Status updated:', data.is_synced ? 'Synced' : 'Out of Sync');
    } catch (err) {
        console.error('[Sync] Fetch failed:', err);
        DOM.syncDot.className = 'sync-dot red';
        DOM.syncText.textContent = 'Sync Error';
        DOM.syncStatus.title = `Failed to fetch sync status: ${err.message}`;
    }
}

// Initial check and set up polling
updateSyncStatus();
setInterval(updateSyncStatus, SYNC_POLL_INTERVAL);

// =============================================
// 4. Toast Notifications
// =============================================
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    DOM.toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

// =============================================
// 5. Modal Helpers
// =============================================
window.closeModal = function(id) {
    document.getElementById(id).classList.add('hidden');
};

// Close modals on overlay click
document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
        if (e.target === overlay) overlay.classList.add('hidden');
    });
});

window.openRagModal = function(index) {
    if (!state.currentRagChunks.length) return;
    const frag = document.createDocumentFragment();
    state.currentRagChunks.forEach((chunk, i) => {
        const isHighlight = (index !== undefined && parseInt(index) === (i + 1));
        const card = document.createElement('div');
        card.className = `rag-source${isHighlight ? ' highlight' : ''}`;
        card.innerHTML = `<h4>Source [${i + 1}]</h4><p>${escapeHtml(chunk.text)}</p>`;
        frag.appendChild(card);
    });
    DOM.ragModalBody.innerHTML = '';
    DOM.ragModalBody.appendChild(frag);
    DOM.ragModal.classList.remove('hidden');
};

window.openDetailsModal = function(title, dataStr) {
    const data = JSON.parse(decodeURIComponent(dataStr));
    DOM.detailsModalTitle.textContent = title;
    let html = '<table class="details-table">';
    for (const [key, value] of Object.entries(data)) {
        html += `<tr><th>${escapeHtml(key)}</th><td>${typeof value === 'object' ? escapeHtml(JSON.stringify(value, null, 2)) : escapeHtml(String(value))}</td></tr>`;
    }
    html += '</table>';
    DOM.detailsModalBody.innerHTML = html;
    DOM.detailsModal.classList.remove('hidden');
};

// System Instructions Modal
const MODULE_LABELS = {
    triage: 'Triage Module',
    router: 'Router Module',
    general: 'General Response',
    reasoning: 'Reasoning (Legal Logic)',
    casual: 'Casual Response',
};

window.openInstructionsModal = function(module) {
    _activeInstrModule = module;
    const ta = document.getElementById(`cfg_${module}_instructions`);
    const currentVal = ta ? ta.value : '';
    DOM.instructionsModalTitle.textContent = `Edit System Instructions — ${MODULE_LABELS[module] || module}`;
    DOM.instructionsModalMeta.innerHTML = `<span class="instr-module-badge">${MODULE_LABELS[module] || module}</span> Edit the system prompt used to instruct this module.`;
    DOM.instructionsModalTextarea.value = currentVal;
    DOM.instrModalCharCount.textContent = `${currentVal.length} chars`;
    DOM.instructionsModal.classList.remove('hidden');
    // Focus the textarea
    setTimeout(() => DOM.instructionsModalTextarea.focus(), 80);
};

window.saveInstructionsModal = function() {
    if (!_activeInstrModule) return;
    const ta = document.getElementById(`cfg_${_activeInstrModule}_instructions`);
    const preview = document.getElementById(`preview_${_activeInstrModule}_instructions`);
    const val = DOM.instructionsModalTextarea.value;
    if (ta) ta.value = val;
    if (preview) {
        preview.textContent = val.length > 0 ? val.substring(0, 120) + (val.length > 120 ? '…' : '') : 'No instructions set';
    }
    updateCharCount(_activeInstrModule);
    closeModal('instructions-modal');
    showToast('System instructions updated', 'success');
    _activeInstrModule = null;
};

// Live char count in instructions modal
if (DOM.instructionsModalTextarea) {
    DOM.instructionsModalTextarea.addEventListener('input', () => {
        DOM.instrModalCharCount.textContent = `${DOM.instructionsModalTextarea.value.length} chars`;
    });
}

// =============================================
// 6. Markdown Renderer
// =============================================
function renderMarkdown(text) {
    if (!text) return '';
    let parsed = text;

    // Extract <think> blocks into collapsible details
    parsed = parsed.replace(/<think>([\s\S]*?)<\/think>/gi, (match, inner) => {
        return `<details class="reasoning-block"><summary>💡 View Reasoning / Thought Process</summary><div class="reasoning-content">${inner}</div></details>\n`;
    });

    // Handle streaming case: <think> present but unclosed
    if (parsed.includes('<think>') && !parsed.includes('</think>')) {
        parsed = parsed.replace(/<think>/gi, '<details open class="reasoning-block"><summary>💡 Thinking...</summary><div class="reasoning-content">\n');
        parsed += '\n</div></details>';
    }

    // Convert [n] citations to clickable badges
    parsed = parsed.replace(/\[(\d+)\]/g, '<sup class="citation" data-ref="$1">[$1]</sup>');

    // Parse markdown
    const rawHtml = marked.parse(parsed, { breaks: true, gfm: true });

    // Sanitize with allowed tags
    let clean = DOMPurify.sanitize(rawHtml, {
        ADD_TAGS: ['details', 'summary', 'sup'],
        ADD_ATTR: ['open', 'class', 'data-ref', 'style']
    });

    // Wrap code blocks with copy button
    clean = clean.replace(/<pre><code(.*?)>([\s\S]*?)<\/code><\/pre>/g, (match, attrs, code) => {
        return `<div class="code-block-wrapper"><button class="copy-code-btn" onclick="copyCodeBlock(this)">Copy</button><pre><code${attrs}>${code}</code></pre></div>`;
    });

    return clean;
}

window.copyCodeBlock = function(btn) {
    const code = btn.nextElementSibling.querySelector('code');
    if (code) {
        navigator.clipboard.writeText(code.textContent).then(() => {
            btn.textContent = 'Copied!';
            setTimeout(() => btn.textContent = 'Copy', 1500);
        });
    }
};

function escapeHtml(str) {
    const el = document.createElement('span');
    el.textContent = str;
    return el.innerHTML;
}

// =============================================
// 7. Chat Engine
// =============================================

// Auto-resize textarea
let resizeTimeout;
DOM.userInput.addEventListener('input', function() {
    clearTimeout(resizeTimeout);
    resizeTimeout = setTimeout(() => {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    }, 16);
});

DOM.userInput.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        DOM.chatForm.dispatchEvent(new Event('submit'));
    }
});

// Preset messages
window.sendPreset = function(text) {
    if (state.isProcessing) return;
    DOM.userInput.value = text;
    DOM.chatForm.dispatchEvent(new Event('submit'));
};

function scrollToBottom() {
    requestAnimationFrame(() => {
        DOM.chatScroll.scrollTop = DOM.chatScroll.scrollHeight;
    });
}

function addUserMessage(text) {
    if (DOM.welcomeScreen) {
        DOM.welcomeScreen.style.display = 'none';
    }
    const div = document.createElement('div');
    div.className = 'message user';
    div.innerHTML = `<div class="msg-bubble user-bubble">${escapeHtml(text)}</div>`;
    DOM.chatMessages.appendChild(div);
    
    state.chatHistory.push({ role: 'user', content: text, timestamp: new Date().toISOString() });
    state.messageCount++;
    DOM.statusMsgCount.textContent = state.messageCount;
    scrollToBottom();
}

function updateStatusBar() {
    DOM.statusSession.textContent = state.sessionId ? state.sessionId.substring(0, 8) + '...' : 'None';
    DOM.statusRoute.textContent = state.currentRoute || '—';
    DOM.statusMsgCount.textContent = state.messageCount;
}

// Citation click delegation
DOM.chatMessages.addEventListener('click', (e) => {
    const citation = e.target.closest('.citation');
    if (citation) {
        window.openRagModal(citation.dataset.ref);
    }
});

// Main chat submit handler
DOM.chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = DOM.userInput.value.trim();
    if (!message || state.isProcessing) return;

    addUserMessage(message);
    DOM.userInput.value = '';
    DOM.userInput.style.height = 'auto';
    state.isProcessing = true;
    DOM.sendBtn.disabled = true;

    // Create assistant message container
    const assistantDiv = document.createElement('div');
    assistantDiv.className = 'message assistant';

    const pipelineDiv = document.createElement('div');
    pipelineDiv.className = 'pipeline-container';
    pipelineDiv.innerHTML = `<div class="pipe-step active"><span class="step-icon"><div class="pipe-spinner"></div></span><span class="step-text">Initializing pipeline...</span></div>`;

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'msg-bubble assistant-bubble markdown-body';

    assistantDiv.appendChild(pipelineDiv);
    assistantDiv.appendChild(bubbleDiv);
    DOM.chatMessages.appendChild(assistantDiv);
    scrollToBottom();

    try {
        const payload = { message };
        if (state.sessionId) payload.sessionId = state.sessionId;

        // Send module enabled/disabled state to backend for pipeline control
        payload.moduleEnabled = { ...state.moduleEnabled };

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantText = '';
        let buffer = '';
        // Pipeline event accumulator for history
        const pipelineEvents = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop(); // keep incomplete line in buffer

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const data = JSON.parse(line);
                    handleStreamEvent(data, pipelineDiv, bubbleDiv);
                    
                    if (data.type === 'result') {
                        assistantText = data.content;
                    }
                    // Capture all pipeline events for history
                    if (['step', 'data', 'rag_context', 'result', 'error'].includes(data.type)) {
                        pipelineEvents.push({ ...data, timestamp: new Date().toISOString() });
                    }
                } catch (parseErr) {
                    console.error('Stream parse error:', parseErr);
                }
            }
        }

        // Process remaining buffer
        if (buffer.trim()) {
            try {
                const data = JSON.parse(buffer);
                handleStreamEvent(data, pipelineDiv, bubbleDiv);
                if (data.type === 'result') assistantText = data.content;
                if (['step', 'data', 'rag_context', 'result', 'error'].includes(data.type)) {
                    pipelineEvents.push({ ...data, timestamp: new Date().toISOString() });
                }
            } catch {}
        }

        // Store full pipeline + assistant response in local history
        if (assistantText) {
            // Record a pipeline_trace entry capturing the full process
            if (pipelineEvents.length > 0) {
                const triageEvent = pipelineEvents.find(e => e.type === 'data' && e.title && e.title.includes('Triage'));
                const routingEvent = pipelineEvents.find(e => e.type === 'data' && e.title && e.title.includes('Routing'));
                const ragEvent = pipelineEvents.find(e => e.type === 'rag_context');
                const resultEvent = pipelineEvents.find(e => e.type === 'result');

                state.chatHistory.push({
                    role: 'pipeline_trace',
                    timestamp: new Date().toISOString(),
                    triage_result: triageEvent ? triageEvent.data : null,
                    routing_decision: routingEvent ? routingEvent.data : null,
                    rag_chunks_count: ragEvent ? ragEvent.chunks.length : 0,
                    rag_chunks: ragEvent ? ragEvent.chunks.map(c => ({ 
                        score: c.score, 
                        metadata: c.metadata, 
                        text: c.text,
                        excerpt: (c.text || '').substring(0, 200) // Keep excerpt for backward compat
                    })) : [],
                    llm_response_preview: assistantText.substring(0, 300),
                    route: resultEvent ? resultEvent.route : null,
                });
            }
            state.chatHistory.push({ role: 'assistant', content: assistantText, timestamp: new Date().toISOString() });
            state.messageCount++;
        }

    } catch (err) {
        pipelineDiv.innerHTML += `<div class="pipe-step error"><span class="step-icon">✗</span><span class="step-text">Network error: ${escapeHtml(err.message)}</span></div>`;
    } finally {
        state.isProcessing = false;
        DOM.sendBtn.disabled = false;
        updateStatusBar();
    }
});

function handleStreamEvent(data, pipelineDiv, bubbleDiv) {
    if (data.type === 'meta') {
        state.sessionId = data.sessionId;
        updateStatusBar();
    }
    else if (data.type === 'step' || data.type === 'data') {
        // Mark previous active step as done
        markPreviousStepDone(pipelineDiv);

        let statusText = '';
        if (data.type === 'data') {
            const encodedData = encodeURIComponent(JSON.stringify(data.data));
            const link = `<span class="details-link" onclick="window.openDetailsModal('${escapeHtml(data.title)}', '${encodedData}')">(View details)</span>`;
            
            if (data.title.includes('Routing')) {
                statusText = `Routed via <strong>${escapeHtml(data.data['Selected Route'] || data.data.Route || '')}</strong> ${link}`;
            } else if (data.title.includes('Triage')) {
                statusText = `Triage applied ${link}`;
            } else {
                statusText = `${escapeHtml(data.title)} ${link}`;
            }
        } else {
            statusText = escapeHtml(data.content);
        }

        const step = document.createElement('div');
        step.className = 'pipe-step active';
        step.innerHTML = `<span class="step-icon"><div class="pipe-spinner"></div></span><span class="step-text">${statusText}</span>`;
        pipelineDiv.appendChild(step);
        scrollToBottom();
    }
    else if (data.type === 'rag_context') {
        state.currentRagChunks = data.chunks;
        markPreviousStepDone(pipelineDiv);

        // RAG found step
        const ragStep = document.createElement('div');
        ragStep.className = 'pipe-step done';
        ragStep.style.cursor = 'pointer';
        ragStep.innerHTML = `<span class="step-icon">✓</span><span class="step-text" style="color:var(--accent-primary);text-decoration:underline" onclick="window.openRagModal()">Found ${data.chunks.length} legal sources (click to view)</span>`;
        pipelineDiv.appendChild(ragStep);

        // Add generating step
        const genStep = document.createElement('div');
        genStep.className = 'pipe-step active';
        genStep.innerHTML = `<span class="step-icon"><div class="pipe-spinner"></div></span><span class="step-text">Reading context and generating...</span>`;
        pipelineDiv.appendChild(genStep);
        scrollToBottom();
    }
    else if (data.type === 'result') {
        markPreviousStepDone(pipelineDiv);
        
        // Final completed step
        const doneStep = document.createElement('div');
        doneStep.className = 'pipe-step done';
        doneStep.innerHTML = `<span class="step-icon">✓</span><span class="step-text">Completed</span>`;
        pipelineDiv.appendChild(doneStep);

        bubbleDiv.innerHTML = renderMarkdown(data.content);
        
        if (data.route) {
            state.currentRoute = data.route;
        }
        scrollToBottom();
    }
    else if (data.type === 'error') {
        const errStep = document.createElement('div');
        errStep.className = 'pipe-step error';
        errStep.innerHTML = `<span class="step-icon">✗</span><span class="step-text">${escapeHtml(data.content)}</span>`;
        pipelineDiv.appendChild(errStep);
        
        if (!bubbleDiv.innerHTML) {
            bubbleDiv.innerHTML = `<div style="color:var(--accent-red)">${escapeHtml(data.content)}</div>`;
        }
    }
}

function markPreviousStepDone(pipelineDiv) {
    const active = pipelineDiv.querySelector('.pipe-step.active:last-of-type') || pipelineDiv.querySelector('.pipe-step.active');
    if (active) {
        active.classList.remove('active');
        active.classList.add('done');
        const icon = active.querySelector('.step-icon');
        if (icon) icon.innerHTML = '✓';
    }
}

// =============================================
// 8. Conversation Manager
// =============================================

// New Chat
DOM.newChatBtn.addEventListener('click', () => {
    state.sessionId = null;
    state.currentRoute = null;
    state.messageCount = 0;
    state.chatHistory = [];
    state.currentRagChunks = [];

    DOM.chatMessages.innerHTML = '';
    // Re-add welcome screen
    DOM.chatMessages.innerHTML = `
        <div class="welcome-screen" id="welcome-screen">
            <div class="welcome-icon">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
            </div>
            <h2>Saan ako makakatulong, OFW?</h2>
            <p>Ask me anything about Philippine & Hong Kong labor laws, migrant worker rights, and legal procedures.</p>
            <div class="welcome-hints">
                <button class="hint-chip" onclick="sendPreset('What are my rights as an OFW in Hong Kong?')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3M12 17h.01"/></svg>
                    OFW rights in HK
                </button>
                <button class="hint-chip" onclick="sendPreset('What is the minimum wage for domestic helpers?')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 1v22M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>
                    Minimum wage policies
                </button>
                <button class="hint-chip" onclick="sendPreset('My employer did not pay me for 2 months, what should I do?')">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
                    Unpaid wages dispute
                </button>
            </div>
        </div>`;

    updateStatusBar();
    // Reset inputs
    DOM.userInput.value = '';
    DOM.userInput.style.height = 'auto';
    
    showToast('New chat started', 'info');
});

// Save Conversation
DOM.saveChatBtn.addEventListener('click', async () => {
    if (state.chatHistory.length === 0) {
        showToast('No messages to save', 'error');
        return;
    }

    // Generate title from first user message
    const firstMsg = state.chatHistory.find(m => m.role === 'user');
    const title = firstMsg ? firstMsg.content.substring(0, 60) : 'Untitled';

    try {
        const res = await fetch('/api/chat/save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                sessionId: state.sessionId,
                messages: state.chatHistory,
                title: title
            })
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('Conversation saved!', 'success');
            loadConversationsList();
        } else {
            showToast('Save failed: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch (err) {
        showToast('Network error while saving', 'error');
    }
});

// Load from file upload
DOM.loadFileBtn.addEventListener('click', () => DOM.loadFileInput.click());
DOM.loadFileInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/chat/load', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (data.error) {
            showToast('Load failed: ' + data.error, 'error');
        } else {
            restoreConversation(data);
            showToast('Conversation loaded from file', 'success');
        }
    } catch (err) {
        showToast('Error loading file', 'error');
    }
    e.target.value = '';
});

// List saved conversations
async function loadConversationsList() {
    try {
        const res = await fetch('/api/chat/list');
        const files = await res.json();
        
        const frag = document.createDocumentFragment();
        if (files.length === 0) {
            const empty = document.createElement('div');
            empty.style.cssText = 'padding:16px;text-align:center;color:var(--text-muted);font-size:0.78rem';
            empty.textContent = 'No saved conversations yet';
            frag.appendChild(empty);
        } else {
            files.forEach(f => {
                const item = document.createElement('div');
                item.className = 'convo-item';
                item.innerHTML = `
                    <div class="convo-info">
                        <span class="convo-title">${escapeHtml(f.title)}</span>
                        <span class="convo-meta">${f.message_count} messages · ${formatTimestamp(f.timestamp)}</span>
                    </div>
                    <button class="convo-delete-btn" title="Delete conversation" onclick="event.stopPropagation(); deleteConversation('${f.filename}')">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
                    </button>
                `;
                item.addEventListener('click', () => loadConversation(f.filename));
                frag.appendChild(item);
            });
        }
        DOM.convoList.innerHTML = '';
        DOM.convoList.appendChild(frag);
    } catch {}
}

async function loadConversation(filename) {
    try {
        const res = await fetch('/api/chat/load', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
        const data = await res.json();
        if (data.error) {
            showToast('Load failed: ' + data.error, 'error');
        } else {
            restoreConversation(data);
            showToast('Conversation loaded', 'success');
        }
    } catch {
        showToast('Error loading conversation', 'error');
    }
}

async function deleteConversation(filename) {
    if (!confirm('Are you sure you want to delete this conversation?')) return;
    
    try {
        const res = await fetch('/api/chat/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename })
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast('Conversation deleted', 'success');
            loadConversationsList();
        } else {
            showToast('Delete failed: ' + data.error, 'error');
        }
    } catch {
        showToast('Error deleting conversation', 'error');
    }
}

async function deleteAllConversations() {
    try {
        const res = await fetch('/api/chat/list');
        const files = await res.json();
        
        if (files.length === 0) {
            showToast('No conversations to clear', 'info');
            return;
        }
        
        if (!confirm(`Are you sure you want to delete ALL ${files.length} saved conversations? This cannot be undone.`)) return;
        
        let successCount = 0;
        for (const file of files) {
            const delRes = await fetch('/api/chat/delete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: file.filename })
            });
            if ((await delRes.json()).status === 'success') successCount++;
        }
        
        showToast(`Cleared ${successCount} conversations`, 'success');
        loadConversationsList();
    } catch {
        showToast('Error clearing conversations', 'error');
    }
}

function restoreConversation(data) {
    // Clear current chat
    DOM.chatMessages.innerHTML = '';
    state.sessionId = data.session_id || null;
    state.chatHistory = data.messages || [];
    state.currentRoute = null;
    state.currentRagChunks = [];

    // Group messages into turns: [ {user, trace?, assistant} ]
    // pipeline_trace always sits between a user and assistant entry
    const turns = [];
    let current = null;
    state.chatHistory.forEach(msg => {
        if (msg.role === 'user') {
            current = { user: msg, trace: null, assistant: null };
            turns.push(current);
        } else if (msg.role === 'pipeline_trace' && current) {
            current.trace = msg;
        } else if (msg.role === 'assistant' && current) {
            current.assistant = msg;
            current = null;
        }
    });

    // Count only real message pairs
    state.messageCount = turns.filter(t => t.user || t.assistant).length * 2;

    const frag = document.createDocumentFragment();

    turns.forEach(turn => {
        // --- User bubble ---
        if (turn.user) {
            const userDiv = document.createElement('div');
            userDiv.className = 'message user';
            const userBubble = document.createElement('div');
            userBubble.className = 'msg-bubble user-bubble';
            userBubble.textContent = turn.user.content;
            if (turn.user.timestamp) {
                const ts = document.createElement('div');
                ts.className = 'msg-timestamp';
                ts.textContent = formatTimestamp(turn.user.timestamp);
                userDiv.appendChild(ts);
            }
            userDiv.appendChild(userBubble);
            frag.appendChild(userDiv);
        }

        // --- Assistant message group (trace + bubble) ---
        const assistantDiv = document.createElement('div');
        assistantDiv.className = 'message assistant';

        // Pipeline trace block
        if (turn.trace) {
            const trace = turn.trace;
            const pipelineDiv = document.createElement('div');
            pipelineDiv.className = 'pipeline-container restored-pipeline';

            // Restored badge
            const badge = document.createElement('div');
            badge.className = 'restored-badge';
            badge.innerHTML = `<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg> Restored session — ${formatTimestamp(trace.timestamp)}`;
            pipelineDiv.appendChild(badge);

            // Step: Triage
            if (trace.triage_result) {
                const tr = trace.triage_result;
                const encodedTriage = encodeURIComponent(JSON.stringify(tr));
                const step = document.createElement('div');
                step.className = 'pipe-step done';
                step.innerHTML = `<span class="step-icon">✓</span><span class="step-text">Triage applied <span class="details-link" onclick="window.openDetailsModal('Triage Result', '${encodedTriage}')">(View details)</span></span>`;
                pipelineDiv.appendChild(step);
            }

            // Step: Routing
            if (trace.routing_decision) {
                const rd = trace.routing_decision;
                const encodedRoute = encodeURIComponent(JSON.stringify(rd));
                const step = document.createElement('div');
                step.className = 'pipe-step done';
                step.innerHTML = `<span class="step-icon">✓</span><span class="step-text">Routed via <strong>${escapeHtml(rd['Selected Route'] || '')}</strong> (confidence: ${typeof rd['Confidence Score'] === 'number' ? rd['Confidence Score'].toFixed(2) : rd['Confidence Score']}) <span class="details-link" onclick="window.openDetailsModal('Routing Result', '${encodedRoute}')">(View details)</span></span>`;
                if (trace.route) state.currentRoute = trace.route;
                pipelineDiv.appendChild(step);
            }

            // Step: RAG
            if (trace.rag_chunks_count > 0 && trace.rag_chunks) {
                const ragStep = document.createElement('div');
                ragStep.className = 'pipe-step done';
                ragStep.style.cursor = 'pointer';
                const chunkCount = trace.rag_chunks_count;
                
                // Rebuild chunks for modal (prefer full text)
                const restoredChunks = trace.rag_chunks.map(c => ({
                    text: c.text || c.excerpt || '',
                    metadata: c.metadata || {},
                    score: c.score || 0
                }));
                
                ragStep.innerHTML = `<span class="step-icon">✓</span><span class="step-text" style="color:var(--accent-primary);text-decoration:underline">Found ${chunkCount} legal source${chunkCount !== 1 ? 's' : ''} (click to view)</span>`;
                
                // Fix the "click to view" functionality
                ragStep.addEventListener('click', (e) => {
                    e.stopPropagation();
                    state.currentRagChunks = restoredChunks;
                    window.openRagModal();
                });
                
                pipelineDiv.appendChild(ragStep);
            }

            // Step: LLM response preview
            if (trace.llm_response_preview) {
                const step = document.createElement('div');
                step.className = 'pipe-step done';
                step.innerHTML = `<span class="step-icon">✓</span><span class="step-text">Completed via <strong>${escapeHtml(trace.route || 'LLM')}</strong></span>`;
                pipelineDiv.appendChild(step);
            }

            assistantDiv.appendChild(pipelineDiv);
        }

        // Assistant bubble
        if (turn.assistant) {
            const bubble = document.createElement('div');
            bubble.className = 'msg-bubble assistant-bubble markdown-body';
            bubble.innerHTML = renderMarkdown(turn.assistant.content);
            assistantDiv.appendChild(bubble);
        }

        frag.appendChild(assistantDiv);
    });

    DOM.chatMessages.appendChild(frag);
    updateStatusBar();
    scrollToBottom();
}

function formatTimestamp(ts) {
    if (!ts) return '';
    try {
        const d = new Date(ts);
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch { return ts; }
}

// Load list on startup
loadConversationsList();

// =============================================
// 9. Config Manager
// =============================================

async function loadConfig() {
    try {
        const res = await fetch('/api/config');
        const data = await res.json();

        // API Key
        document.getElementById('cfg_api_key').value = data.api_key || '';

        // Triage
        document.getElementById('cfg_triage_model').value = data.triage_model || '';
        document.getElementById('cfg_triage_temp').value = data.triage_temp ?? 0;
        document.getElementById('cfg_triage_max_tokens').value = data.triage_max_tokens ?? 1000;
        document.getElementById('cfg_triage_use_system').checked = !!data.triage_use_system;
        // reasoning fixed false — hidden input already set
        setInstructionValue('triage', data.triage_instructions || '');

        // Router
        document.getElementById('cfg_router_model').value = data.router_model || '';
        document.getElementById('cfg_router_temp').value = data.router_temp ?? 0;
        document.getElementById('cfg_router_max_tokens').value = data.router_max_tokens ?? 1000;
        document.getElementById('cfg_router_use_system').checked = !!data.router_use_system;
        // reasoning fixed false — hidden input already set

        // General
        document.getElementById('cfg_general_model').value = data.general_model || '';
        document.getElementById('cfg_general_temp').value = data.general_temp ?? 0;
        document.getElementById('cfg_general_max_tokens').value = data.general_max_tokens ?? 1000;
        document.getElementById('cfg_general_use_system').checked = !!data.general_use_system;
        document.getElementById('cfg_general_reasoning').checked = !!data.general_reasoning;
        setInstructionValue('general', data.general_instructions || '');

        // Reasoning
        document.getElementById('cfg_reasoning_model').value = data.reasoning_model || '';
        document.getElementById('cfg_reasoning_temp').value = data.reasoning_temp ?? 0;
        document.getElementById('cfg_reasoning_max_tokens').value = data.reasoning_max_tokens ?? 2000;
        document.getElementById('cfg_reasoning_use_system').checked = !!data.reasoning_use_system;
        document.getElementById('cfg_reasoning_reasoning').checked = !!data.reasoning_reasoning;
        setInstructionValue('reasoning', data.reasoning_instructions || '');

        // Casual
        document.getElementById('cfg_casual_model').value = data.casual_model || '';
        document.getElementById('cfg_casual_temp').value = data.casual_temp ?? 0;
        document.getElementById('cfg_casual_max_tokens').value = data.casual_max_tokens ?? 200;
        document.getElementById('cfg_casual_use_system').checked = !!data.casual_use_system;
        document.getElementById('cfg_casual_reasoning').checked = !!data.casual_reasoning;
        setInstructionValue('casual', data.casual_instructions || '');

    } catch (e) {
        console.error('Failed to load config:', e);
    }
}

/** Set textarea value AND update its preview div, then refresh char count */
function setInstructionValue(module, val) {
    const ta = document.getElementById(`cfg_${module}_instructions`);
    const preview = document.getElementById(`preview_${module}_instructions`);
    if (ta) ta.value = val;
    if (preview) {
        preview.textContent = val.length > 0 ? val.substring(0, 120) + (val.length > 120 ? '…' : '') : 'No instructions set';
    }
    updateCharCount(module);
}

function updateCharCount(module) {
    const textarea = document.getElementById(`cfg_${module}_instructions`);
    const counter = document.getElementById(`cc_${module}`);
    if (textarea && counter) {
        counter.textContent = `${textarea.value.length} chars`;
    }
}

// Attach char counters
['triage', 'general', 'reasoning', 'casual'].forEach(mod => {
    const ta = document.getElementById(`cfg_${mod}_instructions`);
    if (ta) {
        ta.addEventListener('input', () => updateCharCount(mod));
        // Tab support
        ta.addEventListener('keydown', (e) => {
            if (e.key === 'Tab') {
                e.preventDefault();
                const start = ta.selectionStart;
                const end = ta.selectionEnd;
                ta.value = ta.value.substring(0, start) + '    ' + ta.value.substring(end);
                ta.selectionStart = ta.selectionEnd = start + 4;
            }
        });
    }
});

// Save Config
DOM.saveConfigBtn.addEventListener('click', async () => {
    const payload = {
        api_key: document.getElementById('cfg_api_key').value,

        triage_model: document.getElementById('cfg_triage_model').value,
        triage_temp: parseFloat(document.getElementById('cfg_triage_temp').value) || 0,
        triage_max_tokens: parseInt(document.getElementById('cfg_triage_max_tokens').value) || 1000,
        triage_use_system: document.getElementById('cfg_triage_use_system').checked,
        triage_reasoning: false, // Fixed OFF per QA requirement
        triage_instructions: document.getElementById('cfg_triage_instructions').value,

        router_model: document.getElementById('cfg_router_model').value,
        router_temp: parseFloat(document.getElementById('cfg_router_temp').value) || 0,
        router_max_tokens: parseInt(document.getElementById('cfg_router_max_tokens').value) || 1000,
        router_use_system: document.getElementById('cfg_router_use_system').checked,
        router_reasoning: false, // Fixed OFF per QA requirement

        general_model: document.getElementById('cfg_general_model').value,
        general_temp: parseFloat(document.getElementById('cfg_general_temp').value) || 0,
        general_max_tokens: parseInt(document.getElementById('cfg_general_max_tokens').value) || 1000,
        general_use_system: document.getElementById('cfg_general_use_system').checked,
        general_reasoning: document.getElementById('cfg_general_reasoning').checked,
        general_instructions: document.getElementById('cfg_general_instructions').value,

        reasoning_model: document.getElementById('cfg_reasoning_model').value,
        reasoning_temp: parseFloat(document.getElementById('cfg_reasoning_temp').value) || 0,
        reasoning_max_tokens: parseInt(document.getElementById('cfg_reasoning_max_tokens').value) || 2000,
        reasoning_use_system: document.getElementById('cfg_reasoning_use_system').checked,
        reasoning_reasoning: document.getElementById('cfg_reasoning_reasoning').checked,
        reasoning_instructions: document.getElementById('cfg_reasoning_instructions').value,

        casual_model: document.getElementById('cfg_casual_model').value,
        casual_temp: parseFloat(document.getElementById('cfg_casual_temp').value) || 0,
        casual_max_tokens: parseInt(document.getElementById('cfg_casual_max_tokens').value) || 200,
        casual_use_system: document.getElementById('cfg_casual_use_system').checked,
        casual_reasoning: document.getElementById('cfg_casual_reasoning').checked,
        casual_instructions: document.getElementById('cfg_casual_instructions').value,
    };

    DOM.saveConfigBtn.textContent = 'Saving...';
    DOM.saveConfigBtn.disabled = true;

    try {
        await fetch('/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        DOM.saveConfigBtn.textContent = 'Saved!';
        showToast('Configuration saved', 'success');
        setTimeout(() => {
            DOM.saveConfigBtn.textContent = 'Save Config';
            DOM.saveConfigBtn.disabled = false;
        }, 1200);
    } catch {
        showToast('Failed to save config', 'error');
        DOM.saveConfigBtn.textContent = 'Save Config';
        DOM.saveConfigBtn.disabled = false;
    }
});

// Export Config
DOM.exportConfigBtn.addEventListener('click', () => {
    window.location.href = '/api/config/export';
    showToast('Configuration exported', 'success');
});

// Import Config
DOM.importConfigBtn.addEventListener('click', () => DOM.importConfigInput.click());
DOM.importConfigInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/config/import', {
            method: 'POST',
            body: formData
        });
        const data = await res.json();
        if (data.status === 'success') {
            showToast(`Config imported (${data.applied} settings)`, 'success');
            loadConfig(); // Refresh UI
        } else {
            showToast('Import failed: ' + (data.error || 'Unknown error'), 'error');
        }
    } catch {
        showToast('Error importing config', 'error');
    }
    e.target.value = '';
});

// Toggle API key visibility
window.toggleApiKeyVisibility = function() {
    const input = document.getElementById('cfg_api_key');
    input.type = input.type === 'password' ? 'text' : 'password';
};

// Load config on startup
loadConfig();

// =============================================
// 10. Logs Viewer (SSE)
// =============================================
const MAX_LOG_LINES = 500;
let logLineCount = 0;
let logAutoScroll = true;

function connectLogStream() {
    const evtSource = new EventSource('/api/logs');

    evtSource.onopen = () => {
        DOM.logStatusDot.style.background = 'var(--accent-green)';
        DOM.logStatusText.textContent = 'Connected';
    };

    evtSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'connected') return;

            const line = document.createElement('div');
            line.className = 'log-line';

            // Color by level
            const level = (data.level || '').toLowerCase();
            if (level === 'warning') line.classList.add('warning');
            else if (level === 'error' || level === 'critical') line.classList.add('error');
            else if (level === 'debug') line.classList.add('debug');
            else line.classList.add('info');

            line.textContent = data.message || JSON.stringify(data);
            DOM.logsContent.appendChild(line);
            logLineCount++;

            // Trim excess lines
            while (logLineCount > MAX_LOG_LINES) {
                const first = DOM.logsContent.firstChild;
                if (first) {
                    DOM.logsContent.removeChild(first);
                    logLineCount--;
                }
            }

            // Auto-scroll
            if (logAutoScroll) {
                DOM.logsContent.scrollTop = DOM.logsContent.scrollHeight;
            }
        } catch {}
    };

    evtSource.onerror = () => {
        DOM.logStatusDot.style.background = 'var(--accent-red)';
        DOM.logStatusText.textContent = 'Disconnected';
        evtSource.close();
        // Reconnect after 5s
        setTimeout(connectLogStream, 5000);
    };
}

// Detect manual scrolling in logs
DOM.logsContent.addEventListener('scroll', () => {
    const threshold = 30;
    const atBottom = DOM.logsContent.scrollHeight - DOM.logsContent.scrollTop - DOM.logsContent.clientHeight < threshold;
    logAutoScroll = atBottom;
});

DOM.clearLogsBtn.addEventListener('click', () => {
    DOM.logsContent.innerHTML = '';
    logLineCount = 0;
});

connectLogStream();
