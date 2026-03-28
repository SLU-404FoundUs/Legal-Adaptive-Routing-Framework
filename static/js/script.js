/* =============================================
   Agapay AI — Client Script
   SLU Legal Adaptive Routing Framework
   ============================================= */

const chatForm = document.getElementById('chat-form');
const userInput = document.getElementById('user-input');
const chatHistory = document.getElementById('chat-history');
const processLog = document.getElementById('process-log');
const statusIndicator = document.getElementById('status-indicator');
const emptyState = document.getElementById('empty-state');
const routeBadgeContainer = document.getElementById('route-badge-container');
const routeBadgeValue = document.getElementById('route-badge-value');
const routeBadgeConfidence = document.getElementById('route-badge-confidence');
const mobilePanelBtn = document.getElementById('mobile-panel-btn');
const processPanel = document.getElementById('process-panel');

let isProcessing = false;
let currentSessionId = null;

// =============================================
// Preset Messages (Welcome Hints)
// =============================================
function sendPreset(text) {
    if (isProcessing) return;
    userInput.value = text;
    chatForm.dispatchEvent(new Event('submit'));
}

// =============================================
// Mobile Panel Toggle
// =============================================
if (mobilePanelBtn) {
    mobilePanelBtn.addEventListener('click', () => {
        processPanel.classList.toggle('open');
    });
}

// Close panel when clicking outside on mobile
document.addEventListener('click', (e) => {
    if (processPanel.classList.contains('open') &&
        !processPanel.contains(e.target) &&
        e.target !== mobilePanelBtn) {
        processPanel.classList.remove('open');
    }
});

// =============================================
// Chat Form Handler
// =============================================
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = userInput.value.trim();
    if (!message || isProcessing) return;

    // Clear welcome hints after first message
    const welcomeHints = document.querySelector('.welcome-hints');
    if (welcomeHints) welcomeHints.remove();

    addMessage(message, 'user');
    userInput.value = '';
    isProcessing = true;

    // Update status
    setStatus('processing', 'Processing...');

    // Clear process log
    processLog.innerHTML = '';
    if (emptyState) emptyState.style.display = 'none';

    // Reset route badge
    routeBadgeContainer.style.display = 'none';

    // Create assistant placeholder
    const assistantMessageDiv = createMessageElement('system');
    chatHistory.appendChild(assistantMessageDiv);
    const bubble = assistantMessageDiv.querySelector('.bubble');
    bubble.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
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
        let currentRagChunks = [];

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value, { stream: true });
            const lines = chunk.split('\n');

            for (const line of lines) {
                if (!line.trim()) continue;

                try {
                    const data = JSON.parse(line);

                    switch (data.type) {
                        case 'meta':
                            currentSessionId = data.sessionId;
                            break;

                        case 'step':
                            addProcessStep(data.content);
                            break;

                        case 'data':
                            addProcessData(data.title, data.data);
                            // Update route badge if this is routing data
                            if (data.title === 'Routing Result') {
                                updateRouteBadge(data.data.Route, data.data.Confidence);
                            }
                            break;

                        case 'rag_context':
                            currentRagChunks = data.chunks;
                            window.currentRagChunks = data.chunks;
                            addProcessRagContext(data.title, data.chunks);
                            break;

                        case 'result':
                            if (assistantText === '') bubble.innerHTML = '';
                            assistantText = data.content;
                            bubble.innerHTML = formatResponse(assistantText);
                            // If there were RAG chunks, add inline reference
                            if (currentRagChunks.length > 0) {
                                addInlineRagReference(bubble, currentRagChunks);
                            }
                            scrollToBottom();
                            break;

                        case 'error':
                            addProcessStep(data.content, 'error');
                            if (assistantText === '') {
                                bubble.innerHTML = `<div class="error-message">${data.content}</div>`;
                            }
                            break;
                    }
                } catch (jsonError) {
                    console.error('Error parsing SSE chunk:', jsonError);
                }
            }
        }

    } catch (error) {
        console.error('Fetch error:', error);
        addProcessStep('Network error — check your connection.', 'error');
        bubble.innerHTML = '<div class="error-message">Failed to send message. Please check your connection.</div>';
    } finally {
        isProcessing = false;
        setStatus('ready', 'Ready');
    }
});

// =============================================
// UI Helpers
// =============================================
function setStatus(state, text) {
    statusIndicator.className = `status-indicator ${state === 'processing' ? 'processing' : ''}`;
    statusIndicator.querySelector('.status-text').textContent = text;
}

function createMessageElement(sender) {
    const div = document.createElement('div');
    div.classList.add('message', sender);

    const avatar = document.createElement('div');
    avatar.classList.add('avatar');

    if (sender === 'system') {
        avatar.classList.add('system-avatar');
        avatar.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
        </svg>`;
    } else {
        avatar.classList.add('user-avatar');
        avatar.innerText = 'U';
    }

    const bubble = document.createElement('div');
    bubble.classList.add('bubble');

    div.appendChild(avatar);
    div.appendChild(bubble);
    return div;
}

function addMessage(text, sender) {
    const div = createMessageElement(sender);
    div.querySelector('.bubble').innerText = text;
    chatHistory.appendChild(div);
    scrollToBottom();
}

function scrollToBottom() {
    const container = document.querySelector('.chat-history-container');
    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });
}

// =============================================
// Route Badge
// =============================================
function updateRouteBadge(route, confidence) {
    routeBadgeContainer.style.display = 'block';

    // Clean class
    routeBadgeValue.className = 'route-badge-value';

    if (route === 'Casual-LLM') {
        routeBadgeValue.classList.add('casual');
        routeBadgeValue.textContent = '💬 Casual';
    } else if (route === 'General-LLM') {
        routeBadgeValue.classList.add('general');
        routeBadgeValue.textContent = '📘 General';
    } else if (route === 'Reasoning-LLM') {
        routeBadgeValue.classList.add('reasoning');
        routeBadgeValue.textContent = '⚖️ Reasoning';
    } else {
        routeBadgeValue.classList.add('error');
        routeBadgeValue.textContent = route || 'Unknown';
    }

    if (confidence) {
        routeBadgeConfidence.textContent = `${(confidence * 100).toFixed(0)}%`;
    } else {
        routeBadgeConfidence.textContent = '';
    }
}

// =============================================
// Process Log Steps
// =============================================
function addProcessStep(text, type = 'normal') {
    const step = document.createElement('div');
    step.classList.add('step-item');
    if (type === 'error') step.classList.add('error');
    if (text.includes('Casual')) step.classList.add('casual');
    step.textContent = text;
    processLog.appendChild(step);
    scrollProcessLog();
}

function addProcessData(title, dataObj) {
    const container = document.createElement('div');
    container.classList.add('step-data');

    const header = document.createElement('strong');
    header.textContent = title;
    container.appendChild(header);

    for (const [key, value] of Object.entries(dataObj)) {
        const row = document.createElement('div');
        row.classList.add('data-row');

        let displayValue = value;
        if (typeof value === 'number' && key.toLowerCase().includes('confidence')) {
            displayValue = `${(value * 100).toFixed(1)}%`;
        }

        row.innerHTML = `<span class="data-label">${key}</span><span class="data-value">${displayValue}</span>`;
        container.appendChild(row);
    }

    const lastStep = processLog.lastElementChild;
    if (lastStep && lastStep.classList.contains('step-item')) {
        lastStep.appendChild(container);
        lastStep.classList.add('active');
    } else {
        processLog.appendChild(container);
    }
    scrollProcessLog();
}

// =============================================
// RAG Context Display (Sidebar)
// =============================================
function addProcessRagContext(title, chunks) {
    const container = document.createElement('div');
    container.classList.add('step-data', 'rag-container');

    const header = document.createElement('strong');
    header.textContent = `📚 ${title} (${chunks.length} sources)`;
    container.appendChild(header);

    window.currentRagChunks = chunks;

    chunks.forEach((chunk, index) => {
        const sourceCard = document.createElement('div');
        sourceCard.classList.add('rag-source-card');

        const scorePercent = Math.min((chunk.score || 0) * 100, 100);

        let metaHtml = '';
        if (chunk.metadata && Object.keys(chunk.metadata).length > 0) {
            metaHtml = `
                <div class="rag-metadata-tags">
                    <span class="rag-tag jurisdiction-tag">${chunk.metadata.jurisdiction || 'Unknown'}</span>
                    <span class="rag-tag category-tag">${chunk.metadata.category || 'Law'}</span>
                </div>
                <div class="rag-law-title">${escapeHtml(chunk.metadata.title || '')}</div>
                <div class="rag-law-source">Source: ${escapeHtml(chunk.metadata.source_file || 'Unknown')}</div>
            `;
        }

        const previewText = chunk.text ? chunk.text.substring(0, 150).replace(/\n/g, ' ') + '...' : '';

        sourceCard.innerHTML = `
            <div class="rag-source-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="rag-source-title">
                    Source ${index + 1} — Score: ${(chunk.score || 0).toFixed(3)}
                </span>
                <span class="toggle-icon">▼</span>
            </div>
            <div class="rag-source-content">
                ${metaHtml}
                <div class="rag-score-bar"><div class="rag-score-fill" style="width: ${scorePercent}%"></div></div>
                <div class="rag-text-preview" style="margin-top: 10px;">${escapeHtml(chunk.text || '')}</div>
            </div>
        `;
        container.appendChild(sourceCard);
    });

    // View in modal button
    const viewBtnDiv = document.createElement('div');
    viewBtnDiv.classList.add('rag-source-card-actions');
    viewBtnDiv.innerHTML = `<button class="rag-view-btn" onclick="openRagModal()">📖 View Full Legal Sources</button>`;
    container.appendChild(viewBtnDiv);

    const lastStep = processLog.lastElementChild;
    if (lastStep && lastStep.classList.contains('step-item')) {
        lastStep.appendChild(container);
    } else {
        processLog.appendChild(container);
    }
    scrollProcessLog();
}

// =============================================
// Inline RAG Reference (in chat bubble)
// =============================================
function addInlineRagReference(bubble, chunks) {
    const ragInline = document.createElement('div');
    ragInline.classList.add('chat-rag-inline');

    let chipsHtml = '';
    chunks.slice(0, 3).forEach((chunk, i) => {
        const title = chunk.metadata?.title || `Source ${i + 1}`;
        const shortTitle = title.length > 35 ? title.substring(0, 35) + '...' : title;
        chipsHtml += `<span class="chat-rag-chip" onclick="openRagModal()" title="${escapeHtml(title)}">📄 ${escapeHtml(shortTitle)}</span>`;
    });

    ragInline.innerHTML = `
        <div class="chat-rag-header">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
            </svg>
            Legal Sources Referenced
        </div>
        <div>${chipsHtml}</div>
    `;

    bubble.appendChild(ragInline);
}

function scrollProcessLog() {
    if (processLog.parentElement) {
        processLog.parentElement.scrollTop = processLog.parentElement.scrollHeight;
    }
}

// =============================================
// Markdown Formatter
// =============================================
function formatResponse(text) {
    if (!text) return '';

    let html = escapeHtml(text);

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h4 style="color:var(--accent-blue);margin:12px 0 6px;font-size:0.9rem;">$1</h4>');
    html = html.replace(/^## (.+)$/gm, '<h3 style="color:var(--accent-blue);margin:14px 0 6px;font-size:1rem;">$1</h3>');
    html = html.replace(/^# (.+)$/gm, '<h2 style="color:var(--accent-blue);margin:16px 0 8px;font-size:1.1rem;">$1</h2>');

    // Bold + Italic
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Numbered lists
    html = html.replace(/^(\d+)\.\s+(.+)$/gm, '<div style="padding-left:16px;margin:4px 0;"><span style="color:var(--accent-blue);font-weight:600;">$1.</span> $2</div>');

    // Bullet lists
    html = html.replace(/^[-•]\s+(.+)$/gm, '<div style="padding-left:16px;margin:3px 0;">• $1</div>');

    // Line breaks
    html = html.replace(/\n/g, '<br>');

    // Clean up excessive breaks
    html = html.replace(/(<br>){3,}/g, '<br><br>');

    return html;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// =============================================
// RAG Modal
// =============================================
const ragModal = document.getElementById('rag-modal');
const closeModalBtn = document.getElementById('close-modal-btn');
const modalRagContent = document.getElementById('modal-rag-content');

if (closeModalBtn) {
    closeModalBtn.addEventListener('click', () => {
        ragModal.classList.add('hidden');
    });
}

if (ragModal) {
    ragModal.addEventListener('click', (e) => {
        if (e.target === ragModal) {
            ragModal.classList.add('hidden');
        }
    });
}

// Close modal with Escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && ragModal && !ragModal.classList.contains('hidden')) {
        ragModal.classList.add('hidden');
    }
});

function openRagModal() {
    if (!window.currentRagChunks || window.currentRagChunks.length === 0) return;

    modalRagContent.innerHTML = '';

    window.currentRagChunks.forEach((chunk, i) => {
        const div = document.createElement('div');
        div.classList.add('modal-rag-item');

        const scorePercent = Math.min((chunk.score || 0) * 100, 100);

        let metaHtml = '';
        if (chunk.metadata && Object.keys(chunk.metadata).length > 0) {
            metaHtml = `
                <div class="modal-metadata-header">
                    <div class="rag-metadata-tags">
                        <span class="rag-tag jurisdiction-tag">${escapeHtml(chunk.metadata.jurisdiction || 'Unknown')}</span>
                        <span class="rag-tag category-tag">${escapeHtml(chunk.metadata.category || 'Law')}</span>
                    </div>
                    <div class="rag-law-title">${escapeHtml(chunk.metadata.title || 'Untitled')}</div>
                    <div class="rag-law-source">Source: ${escapeHtml(chunk.metadata.source_file || 'Unknown')}</div>
                    <div class="rag-score-bar" style="margin-top:8px;"><div class="rag-score-fill" style="width: ${scorePercent}%"></div></div>
                </div>
            `;
        }

        div.innerHTML = `
            <div class="modal-rag-score">
                <span>Source ${i + 1}</span>
                <span class="score-value">Similarity: ${(chunk.score || 0).toFixed(4)}</span>
            </div>
            ${metaHtml}
            <div class="modal-rag-text">${escapeHtml(chunk.text || '')}</div>
        `;
        modalRagContent.appendChild(div);
    });

    ragModal.classList.remove('hidden');
}
