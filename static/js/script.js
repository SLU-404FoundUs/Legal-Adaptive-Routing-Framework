/* =============================================
   Agapay AI — Perplexity-Style Client Script
   ============================================= */

// DOM Elements
const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const chatHistory = document.getElementById('chat-history');
const settingsBtn = document.getElementById('settings-btn');
const configModal = document.getElementById('config-modal');
const closeConfigBtn = document.getElementById('close-config-btn');
const configForm = document.getElementById('config-form');

let isProcessing = false;
let currentSessionId = null;
window.currentRagChunks = []; // Global to store chunks for the modal

/**
 * Update the UI to reflect the current sync status of the legal index.
 */
async function updateSyncStatus() {
    const container = document.getElementById('sync-status-container');
    const dot = container.querySelector('.status-dot');
    const text = container.querySelector('.status-text');

    try {
        const res = await fetch('/api/sync-status');
        const data = await res.json();

        if (data.is_synced) {
            dot.className = 'status-dot green';
            text.innerText = 'Index Synced';
            container.title = `Index is up to date with ${data.corpus_count} documents.`;
        } else {
            dot.className = 'status-dot yellow';
            text.innerText = `Out of Sync (${data.missing_count})`;
            container.title = `${data.missing_count} documents are missing from the index. Run -reindex in CLI.`;
        }
    } catch (e) {
        dot.className = 'status-dot red';
        text.innerText = 'Sync Error';
        container.title = 'Failed to fetch index sync status.';
    }
}

// Initial check
updateSyncStatus();

// =============================================
// Settings Modal & Theme Logic
// =============================================
const themeBtn = document.getElementById('theme-btn');
const moonIconPath = "M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"; // Moon
const sunIconPath = "M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"; // Sun

// Initialize theme from storage
if(localStorage.getItem('theme') === 'dark') {
    document.body.setAttribute('data-theme', 'dark');
    themeBtn.querySelector('path').setAttribute('d', sunIconPath);
}

themeBtn.addEventListener('click', () => {
    if(document.body.getAttribute('data-theme') === 'dark') {
        document.body.removeAttribute('data-theme');
        localStorage.setItem('theme', 'light');
        themeBtn.querySelector('path').setAttribute('d', moonIconPath);
    } else {
        document.body.setAttribute('data-theme', 'dark');
        localStorage.setItem('theme', 'dark');
        themeBtn.querySelector('path').setAttribute('d', sunIconPath);
    }
});

settingsBtn.addEventListener('click', async () => {
    configModal.classList.remove('hidden');
    // Fetch current settings
    try {
        const res = await fetch('/api/config');
        const data = await res.json();
        document.getElementById('input_api_key').value = data.api_key || '';

        // Triage
        document.getElementById('input_triage_model').value = data.triage_model || '';
        document.getElementById('input_triage_temp').value = data.triage_temp || 0;
        document.getElementById('input_triage_max_tokens').value = data.triage_max_tokens || 1000;
        document.getElementById('input_triage_use_system').value = data.triage_use_system ? "true" : "false";
        document.getElementById('input_triage_reasoning').value = data.triage_reasoning ? "true" : "false";
        
        // Router
        document.getElementById('input_router_model').value = data.router_model || '';
        document.getElementById('input_router_temp').value = data.router_temp || 0;
        document.getElementById('input_router_max_tokens').value = data.router_max_tokens || 1000;
        document.getElementById('input_router_use_system').value = data.router_use_system ? "true" : "false";
        document.getElementById('input_router_reasoning').value = data.router_reasoning ? "true" : "false";

        // Reasoning
        document.getElementById('input_reasoning_model').value = data.reasoning_model || '';
        document.getElementById('input_reasoning_temp').value = data.reasoning_temp || 0;
        document.getElementById('input_reasoning_max_tokens').value = data.reasoning_max_tokens || 2000;
        document.getElementById('input_reasoning_use_system').value = data.reasoning_use_system ? "true" : "false";
        document.getElementById('input_reasoning_reasoning').value = data.reasoning_reasoning ? "true" : "false";
        document.getElementById('input_reasoning_instructions').value = data.reasoning_instructions || '';
        
        // General
        document.getElementById('input_general_model').value = data.general_model || '';
        document.getElementById('input_general_temp').value = data.general_temp || 0;
        document.getElementById('input_general_max_tokens').value = data.general_max_tokens || 1000;
        document.getElementById('input_general_use_system').value = data.general_use_system ? "true" : "false";
        document.getElementById('input_general_reasoning').value = data.general_reasoning ? "true" : "false";
        document.getElementById('input_general_instructions').value = data.general_instructions || '';

        // Casual
        document.getElementById('input_casual_model').value = data.casual_model || '';
        document.getElementById('input_casual_temp').value = data.casual_temp || 0;
        document.getElementById('input_casual_max_tokens').value = data.casual_max_tokens || 200;
        document.getElementById('input_casual_use_system').value = data.casual_use_system ? "true" : "false";
        document.getElementById('input_casual_reasoning').value = data.casual_reasoning ? "true" : "false";
        document.getElementById('input_casual_instructions').value = data.casual_instructions || '';
    } catch (e) {
        console.error("Failed to load config", e);
    }
});

closeConfigBtn.addEventListener('click', () => configModal.classList.add('hidden'));

configForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const payload = {
        api_key: document.getElementById('input_api_key').value,
        
        triage_model: document.getElementById('input_triage_model').value,
        triage_temp: parseFloat(document.getElementById('input_triage_temp').value),
        triage_max_tokens: parseInt(document.getElementById('input_triage_max_tokens').value) || 1000,
        triage_use_system: document.getElementById('input_triage_use_system').value === "true",
        triage_reasoning: document.getElementById('input_triage_reasoning').value === "true",
        
        router_model: document.getElementById('input_router_model').value,
        router_temp: parseFloat(document.getElementById('input_router_temp').value),
        router_max_tokens: parseInt(document.getElementById('input_router_max_tokens').value) || 1000,
        router_use_system: document.getElementById('input_router_use_system').value === "true",
        router_reasoning: document.getElementById('input_router_reasoning').value === "true",
        
        reasoning_model: document.getElementById('input_reasoning_model').value,
        reasoning_temp: parseFloat(document.getElementById('input_reasoning_temp').value),
        reasoning_max_tokens: parseInt(document.getElementById('input_reasoning_max_tokens').value) || 2000,
        reasoning_use_system: document.getElementById('input_reasoning_use_system').value === "true",
        reasoning_reasoning: document.getElementById('input_reasoning_reasoning').value === "true",
        reasoning_instructions: document.getElementById('input_reasoning_instructions').value,
        
        general_model: document.getElementById('input_general_model').value,
        general_temp: parseFloat(document.getElementById('input_general_temp').value),
        general_max_tokens: parseInt(document.getElementById('input_general_max_tokens').value) || 1000,
        general_use_system: document.getElementById('input_general_use_system').value === "true",
        general_reasoning: document.getElementById('input_general_reasoning').value === "true",
        general_instructions: document.getElementById('input_general_instructions').value,
        
        casual_model: document.getElementById('input_casual_model').value,
        casual_temp: parseFloat(document.getElementById('input_casual_temp').value),
        casual_max_tokens: parseInt(document.getElementById('input_casual_max_tokens').value) || 200,
        casual_use_system: document.getElementById('input_casual_use_system').value === "true",
        casual_reasoning: document.getElementById('input_casual_reasoning').value === "true",
        casual_instructions: document.getElementById('input_casual_instructions').value,
    };

    const submitBtn = configForm.querySelector('button[type="submit"]');
    const ogText = submitBtn.innerText;
    submitBtn.innerText = "Saving...";
    
    try {
        await fetch('/api/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        setTimeout(() => {
            submitBtn.innerText = "Saved!";
            setTimeout(() => {
                submitBtn.innerText = ogText;
                configModal.classList.add('hidden');
            }, 1000);
        }, 500);
    } catch (e) {
        console.error("Save config failed", e);
        submitBtn.innerText = ogText;
    }
});

// =============================================
// RAG Modal & Citations Logic
// =============================================
const ragModal = document.getElementById('rag-modal');
const closeRagBtn = document.getElementById('close-rag-btn');
const modalRagContent = document.getElementById('modal-rag-content');

window.openRagModal = function(index = null) {
    if (!ragModal || !window.currentRagChunks) return;
    
    // Build content
    let html = '';
    window.currentRagChunks.forEach((chunk, i) => {
        // If an index was provided by citation click, highlight it
        const isHighlight = (index !== null && parseInt(index) === (i + 1));
        html += `
        <div style="padding: 12px; margin-bottom: 12px; border: 1px solid ${isHighlight ? 'var(--accent-blue)' : 'var(--border-subtle)'}; border-radius: var(--radius-sm); background: ${isHighlight ? 'rgba(37,99,235,0.05)' : 'var(--chat-bg)'}">
            <h4 style="margin-bottom: 6px; font-size: 0.95rem;">Source [${i + 1}]</h4>
            <p style="font-size: 0.85rem; color: var(--text-secondary); white-space: pre-wrap;">${chunk.text}</p>
        </div>`;
    });
    
    if(html === '') html = '<p>No legal sources were retrieved for this query.</p>';
    modalRagContent.innerHTML = html;
    ragModal.classList.remove('hidden');
};

if(closeRagBtn) {
    closeRagBtn.addEventListener('click', () => ragModal.classList.add('hidden'));
}

// =============================================
// Module Details Modal Logic
// =============================================
const detailsModal = document.getElementById('details-modal');
const closeDetailsBtn = document.getElementById('close-details-btn');
const modalDetailsContent = document.getElementById('details-modal-content');
const modalDetailsTitle = document.getElementById('details-modal-title');

window.openDetailsModal = function(title, dataStr) {
    if (!detailsModal) return;
    const data = JSON.parse(decodeURIComponent(dataStr));
    
    modalDetailsTitle.innerText = title;
    
    let html = '<table class="details-table">';
    for (const [key, value] of Object.entries(data)) {
        html += `
        <tr>
            <th>${key}</th>
            <td>${typeof value === 'object' ? JSON.stringify(value, null, 2) : value}</td>
        </tr>`;
    }
    html += '</table>';
    
    modalDetailsContent.innerHTML = html;
    detailsModal.classList.remove('hidden');
};

if(closeDetailsBtn) {
    closeDetailsBtn.addEventListener('click', () => detailsModal.classList.add('hidden'));
}

// Delegate listener for citation clicks
chatHistory.addEventListener('click', (e) => {
    if (e.target.closest('.citation')) {
        const ref = e.target.closest('.citation').getAttribute('data-ref');
        window.openRagModal(ref);
    }
});

// =============================================
// Helper: Auto-resize textarea
// =============================================
userInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});
userInput.addEventListener('keydown', function(e) {
    if(e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
});

// Preset Messages
function sendPreset(text) {
    if (isProcessing) return;
    userInput.value = text;
    chatForm.dispatchEvent(new Event('submit'));
}

// =============================================
// Chat Form Handler
// =============================================
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message || isProcessing) return;

    // Clear welcome hints
    const welcome = document.querySelector('.welcome-section');
    if (welcome) welcome.style.display = 'none';

    // Add user message
    addMessage(message, 'user');
    userInput.value = '';
    userInput.style.height = 'auto';
    isProcessing = true;

    // Add system placeholder
    const assistantContainer = document.createElement('div');
    assistantContainer.className = 'message system';
    
    // Create inline pipeline container inside the assistant bubble
    const pipelineDiv = document.createElement('div');
    pipelineDiv.className = 'pipeline-inline';
    // We will keep the spinner loosely coupled so we can move it
    pipelineDiv.innerHTML = `<div class="pipeline-step active" id="current-step"><span class="step-icon"><div class="spinner-icon"></div></span><span class="step-text">Initializing Process...</span></div>`;
    
    const bubble = document.createElement('div');
    bubble.className = 'bubble markdown-body';
    
    assistantContainer.appendChild(pipelineDiv);
    assistantContainer.appendChild(bubble);
    chatHistory.appendChild(assistantContainer);
    scrollToBottom();

    try {
        const payload = { message };
        if (currentSessionId) payload.sessionId = currentSessionId;

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let assistantText = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (!line.trim()) continue;
                try {
                    const data = JSON.parse(line);

                    if (data.type === 'meta') {
                        currentSessionId = data.sessionId;
                    } 
                    else if (data.type === 'step' || data.type === 'data') {
                        // Mark previous step as done (replace spinner with check)
                        const currentActive = pipelineDiv.querySelector('.pipeline-step.active');
                        if (currentActive) {
                            currentActive.classList.remove('active');
                            const iconSpan = currentActive.querySelector('.step-icon');
                            if (iconSpan) iconSpan.innerHTML = '✓';
                        }

                        // Update Pipeline
                        let statusText = data.content;
                        if(data.type === 'data') {
                           const encodedData = encodeURIComponent(JSON.stringify(data.data));
                           const detailsLink = `<span class="details-link" onclick="window.openDetailsModal('${data.title}', '${encodedData}')">(View details)</span>`;
                           
                           if(data.title.includes("Routing")) {
                               statusText = `Routed via <strong>${data.data.Route || data.data["Selected Route"]}</strong> ${detailsLink}`;
                           } else if(data.title.includes("Triage")) {
                               statusText = `Triage applied. ${detailsLink}`;
                           } else {
                               statusText = `${data.title} ${detailsLink}`;
                           }
                        }
                        
                        pipelineDiv.innerHTML += `<div class="pipeline-step active"><span class="step-icon"><div class="spinner-icon"></div></span><span class="step-text">${statusText}</span></div>`;
                        scrollToBottom();
                    }
                    else if (data.type === 'rag_context') {
                        window.currentRagChunks = data.chunks;
                        // Mark previous active as done
                        const currentActive = pipelineDiv.querySelector('.pipeline-step.active');
                        if (currentActive) {
                            currentActive.classList.remove('active');
                            const iconSpan = currentActive.querySelector('.step-icon');
                            if (iconSpan) iconSpan.innerHTML = '✓';
                        }
                        
                        pipelineDiv.innerHTML += `<div class="pipeline-step" style="color:var(--accent-blue); cursor:pointer; text-decoration:underline;" onclick="window.openRagModal()">✓ <span class="step-text">Found ${data.chunks.length} legal sources. (Click to view)</span></div>`;
                        // Re-add a loading step since generating is next
                        pipelineDiv.innerHTML += `<div class="pipeline-step active"><span class="step-icon"><div class="spinner-icon"></div></span><span class="step-text">Reading context and generating...</span></div>`;
                        scrollToBottom();
                    }
                    else if (data.type === 'result') {
                        // Mark pipeline as complete
                        const currentActive = pipelineDiv.querySelector('.pipeline-step.active');
                        if (currentActive) {
                            currentActive.classList.remove('active');
                            const iconSpan = currentActive.querySelector('.step-icon');
                            if (iconSpan) iconSpan.innerHTML = '✓';
                            const textSpan = currentActive.querySelector('.step-text');
                            if (textSpan) textSpan.innerHTML = 'Completed';
                        }
                        
                        assistantText = data.content;
                        bubble.innerHTML = renderMarkdown(assistantText);
                        scrollToBottom();
                    }
                    else if (data.type === 'error') {
                        pipelineDiv.innerHTML += `<div class="pipeline-step" style="color:red">✗ <span class="step-text">Error: ${data.content}</span></div>`;
                        if(assistantText === '') bubble.innerHTML = `<div style="color:red">${data.content}</div>`;
                    }
                } catch (e) {
                    console.error("SSE Parse Error", e);
                }
            }
        }
    } catch (e) {
        pipelineDiv.innerHTML += `<div class="pipeline-step" style="color:red">✗ Critical Network Error.</div>`;
    } finally {
        isProcessing = false;
    }
});

// =============================================
// Render Markdown with <think> Tag Extraction
// =============================================
function renderMarkdown(text) {
    if(!text) return '';
    let parsedText = text;

    // Fix <think> tags. Sometimes models use <think> \n content \n </think> or just <think>content</think>.
    // Using a more robust regex that ignores case and matches universally.
    parsedText = parsedText.replace(/<think>([\s\S]*?)<\/think>/gi, function(match, inner) {
        return `<details class="reasoning-block"><summary>Thought Process</summary><div class="reasoning-content">${inner}</div></details>\n`;
    });
    
    // Handle streaming case where <think> is present but not closed
    if (parsedText.includes('<think>') && !parsedText.includes('</think>')) {
        parsedText = parsedText.replace(/<think>/gi, '<details open class="reasoning-block"><summary>Thought Process</summary><div class="reasoning-content">\n');
        parsedText += '\n</div></details>';
    } 

    // Convert Citations [1], [2], etc into clickable badges
    parsedText = parsedText.replace(/\[(\d+)\]/g, '<sup class="citation" data-ref="$1" style="cursor:pointer; color:var(--accent-blue); font-weight:bold; padding: 0 2px;">[$1]</sup>');

    // Configure marked for proper HTML support
    const rawHtml = marked.parse(parsedText, { breaks: true, gfm: true });
    
    // Purify with exceptions for details, summary, and citations
    return DOMPurify.sanitize(rawHtml, {
        ADD_TAGS: ['details', 'summary', 'sup'],
        ADD_ATTR: ['open', 'class', 'data-ref', 'style']
    });
}

function addMessage(text, sender) {
    const div = document.createElement('div');
    div.className = `message ${sender}`;
    const bubble = document.createElement('div');
    bubble.className = 'bubble';
    
    // User messages are safe text
    if(sender === 'user') {
        bubble.innerText = text;
    } else {
        bubble.innerHTML = renderMarkdown(text);
    }
    
    div.appendChild(bubble);
    chatHistory.appendChild(div);
    scrollToBottom();
}

function scrollToBottom() {
    const container = document.querySelector('.chat-history-container');
    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });
}
