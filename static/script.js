const chatBox = document.getElementById('chatBox');
const userInput = document.getElementById('userInput');
const sendBtn = document.getElementById('sendBtn');
const pdfUpload = document.getElementById('pdfUpload');
const uploadStatus = document.getElementById('uploadStatus');
const historyList = document.getElementById('historyList');
const workspacePill = document.getElementById('workspacePill');
const notificationsBtn = document.getElementById('notificationsBtn');
const settingsBtn = document.getElementById('settingsBtn');
const newConversationBtn = document.getElementById('newConversationBtn');
const exploreAgentsBtn = document.getElementById('exploreAgentsBtn');
const viewAllBtn = document.getElementById('viewAllBtn');
const suggestedPromptsBtn = document.getElementById('suggestedPromptsBtn');
const voiceToggleBtn = document.getElementById('voiceToggleBtn');
const toastContainer = document.getElementById('toastContainer');

let voiceEnabled = false;
let currentThreadId = 'thread_' + Date.now();

// 1. Fetch and render sidebar threads immediately when webpage loads
async function loadSidebarThreads() {
    try {
        const response = await fetch('/get-threads');
        const threads = await response.json();
        historyList.innerHTML = ''; // Clear layout

        threads.forEach(t => {
            const li = document.createElement('li');
            li.className = 'history-item';
            li.innerText = `💬 ${t.title}`;
            li.setAttribute('data-id', t.id);
            
            // If it matches what we are looking at, add highlight class style
            if(t.id === currentThreadId) li.style.background = "#212121";

            // Click listener to load thread history cleanly
            li.addEventListener('click', () => switchThread(t.id));
            historyList.appendChild(li);
        });
    } catch (err) {
        console.error("Failed to render chat links:", err);
    }
}

// 2. Switch thread channel view
async function switchThread(threadId) {
    currentThreadId = threadId;
    loadSidebarThreads(); // Refresh selection shadows

    chatBox.innerHTML = ''; // Clear old visible elements
    appendSystemMessage("Loading historical session parameters...");

    try {
        const response = await fetch(`/get-messages/${threadId}`);
        const history = await response.json();
        chatBox.innerHTML = ''; // Reset loading text

        if(history.length === 0) {
            appendSystemMessage("Fresh workspace loaded. Send a prompt to begin tracking metrics.");
        } else {
            history.forEach(msg => {
                appendMessage(msg.content, msg.role, msg.role === 'user' ? '' : 'DATABASE_HISTORICAL');
            });
        }
    } catch (err) {
        appendSystemMessage("Error reloading database data.");
    }
}

// 3. Input pipeline execution message trigger
async function sendMessage() {
    const text = userInput.value.trim();
    if (!text) return;

    appendMessage(text, 'user', '');
    userInput.value = '';

    const loadingId = appendMessage('Consulting hybrid graph parameters...', 'assistant', 'LOG ROUTING');

    try {
        const response = await fetch('/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text, thread_id: currentThreadId })
        });
        const data = await response.json();

        document.getElementById(loadingId).remove();

        if (data.error) {
            appendMessage(`Error: ${data.error}`, 'assistant', 'CRITICAL_ERROR');
        } else {
            appendMessage(data.answer, 'assistant', data.source);
            loadSidebarThreads(); // Reload sidebar to capture newly generated conversation titles!
        }
    } catch (err) {
        document.getElementById(loadingId).remove();
        appendMessage('Connection broken with agent routing framework.', 'assistant', 'NETWORK_ERROR');
    }
}

// 5. Dynamic PDF Upload Flow Handler
pdfUpload.addEventListener('change', async () => {
    const file = pdfUpload.files[0];
    if (!file) return;

    uploadStatus.innerText = "⏳ Vectorizing Document...";
    uploadStatus.style.color = "#ffc107";

    const formData = new FormData();
    formData.append('pdf_file', file);

    try {
        const response = await fetch('/upload-pdf', { method: 'POST', body: formData });
        const data = await response.json();

        if (data.success) {
            uploadStatus.innerText = `✅ Active: ${data.filename}`;
            uploadStatus.style.color = "#10a37f";
            appendSystemMessage(`System established dynamic vector context matching: ${data.filename}`);
        } else {
            uploadStatus.innerText = "❌ Upload Failed";
            uploadStatus.style.color = "#dc3545";
            alert(data.error);
        }
    } catch (err) {
        uploadStatus.innerText = "❌ Network Error";
        uploadStatus.style.color = "#dc3545";
    }
});

// 6. Element Builder Utilities
function appendMessage(text, sender, sourceTag) {
    const uniqueId = 'msg-' + Date.now();
    const msgDiv = document.createElement('div');
    msgDiv.id = uniqueId;
    msgDiv.className = `message ${sender}`;

    const bubbleDiv = document.createElement('div');
    bubbleDiv.className = 'bubble';
    bubbleDiv.innerText = text;

    msgDiv.appendChild(bubbleDiv);

    if (sourceTag) {
        const spanTag = document.createElement('span');
        spanTag.className = 'source-tag';
        spanTag.innerText = `FOUND VIA: ${sourceTag.toUpperCase()}`;
        msgDiv.appendChild(spanTag);
    }

    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
    return uniqueId;
}

function appendSystemMessage(text) {
    const msgDiv = document.createElement('div');
    msgDiv.className = 'message assistant';
    msgDiv.innerHTML = `<div class="bubble" style="color: #10a37f; font-style: italic; font-size:0.85rem;">${text}</div>`;
    chatBox.appendChild(msgDiv);
    chatBox.scrollTop = chatBox.scrollHeight;
}

function showToast(message, type = 'info', duration = 3000) {
    if (!toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerText = message;
    toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(12px)';
        setTimeout(() => toast.remove(), 240);
    }, duration);
}

function bindUiActions() {
    sendBtn?.addEventListener('click', sendMessage);
    userInput?.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendMessage(); });

    workspacePill?.addEventListener('click', () => showToast('Workspace menu opened.', 'info'));
    notificationsBtn?.addEventListener('click', () => showToast('Notifications panel opened.', 'info'));
    settingsBtn?.addEventListener('click', () => showToast('Settings opened.', 'info'));

    newConversationBtn?.addEventListener('click', () => {
        currentThreadId = 'thread_' + Date.now();
        chatBox.innerHTML = `
            <div class="message assistant">
                <div class="bubble">Initialized a blank canvas thread channel. Awaiting operational inputs...</div>
            </div>
        `;
        loadSidebarThreads();
        showToast('Created a new conversation.', 'success');
    });

    exploreAgentsBtn?.addEventListener('click', () => showToast('Opening agent directory.', 'info'));
    viewAllBtn?.addEventListener('click', () => showToast('Showing all history items.', 'info'));
    suggestedPromptsBtn?.addEventListener('click', () => showToast('Suggested prompts are loaded.', 'info'));
    voiceToggleBtn?.addEventListener('click', () => {
        voiceEnabled = !voiceEnabled;
        voiceToggleBtn.innerText = voiceEnabled ? 'Disable' : 'Enable';
        showToast(voiceEnabled ? 'Voice input enabled.' : 'Voice input disabled.', 'success');
    });

    historyList?.addEventListener('click', (event) => {
        if (event.target.matches('.history-item')) {
            showToast(`Switched to ${event.target.textContent.trim()}`, 'info');
        }
    });

    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (event) => {
            event.preventDefault();
            document.querySelectorAll('.nav-link').forEach(item => item.classList.remove('active'));
            event.currentTarget.classList.add('active');
            showToast(`${event.currentTarget.textContent.trim()} opened`, 'success');
        });
    });
}

// Bind active triggers and initialize
bindUiActions();
window.addEventListener('DOMContentLoaded', loadSidebarThreads); // Load logs automatically on window launch!
