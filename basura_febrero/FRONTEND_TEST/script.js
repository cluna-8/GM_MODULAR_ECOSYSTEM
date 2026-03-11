// API Configuration
let API_BASE_URL = 'http://localhost:7005';
let currentSessionId = '';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    // Load saved API URL
    const savedUrl = localStorage.getItem('apiUrl');
    if (savedUrl) {
        document.getElementById('apiUrl').value = savedUrl;
        API_BASE_URL = savedUrl;
    }

    // Load saved session
    const savedSession = localStorage.getItem('sessionId');
    if (savedSession) {
        document.getElementById('sessionId').value = savedSession;
        currentSessionId = savedSession;
    } else {
        generateSessionId();
    }

    // Check API health
    checkApiHealth();

    // Setup event listeners
    document.getElementById('apiUrl').addEventListener('change', (e) => {
        API_BASE_URL = e.target.value;
        localStorage.setItem('apiUrl', API_BASE_URL);
        checkApiHealth();
    });

    document.getElementById('sessionId').addEventListener('change', (e) => {
        currentSessionId = e.target.value;
        localStorage.setItem('sessionId', currentSessionId);
    });

    // Enter key to send message
    document.getElementById('messageInput').addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
});

// Generate new session ID
function generateSessionId() {
    currentSessionId = `chat_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    document.getElementById('sessionId').value = currentSessionId;
    localStorage.setItem('sessionId', currentSessionId);
    addSystemMessage(`Nueva sesión creada: ${currentSessionId}`);
}

// Check API Health
async function checkApiHealth() {
    const statusIndicator = document.getElementById('apiStatus');
    const statusDot = statusIndicator.querySelector('.status-dot');
    const statusText = statusIndicator.querySelector('.status-text');

    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();

        if (response.ok && data.status === 'healthy') {
            statusIndicator.classList.add('online');
            statusIndicator.classList.remove('offline');
            statusText.textContent = 'API Online';

            // Update response panel with health data
            updateResponsePanel(data, 'Health Check');
        } else {
            throw new Error('API unhealthy');
        }
    } catch (error) {
        statusIndicator.classList.add('offline');
        statusIndicator.classList.remove('online');
        statusText.textContent = 'API Offline';
        console.error('Health check failed:', error);
    }
}

// Send Chat Message
async function sendMessage() {
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();

    if (!message) return;

    const promptMode = document.getElementById('promptMode').value;
    const toolType = document.getElementById('toolType').value;
    const sendBtn = document.getElementById('sendBtn');

    // Add user message to chat
    addMessage(message, 'user', { promptMode, toolType });

    // Clear input
    messageInput.value = '';

    // Disable send button
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<div class="loading"></div> Enviando...';

    try {
        const requestBody = {
            message: message,
            session: currentSessionId,
            prompt_mode: promptMode
        };

        // Add tool if selected
        if (toolType) {
            requestBody.tools = toolType;
        }

        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(requestBody)
        });

        const data = await response.json();

        // Update response panel
        updateResponsePanel(data, 'Chat Response');

        // Add assistant response to chat
        if (data.status === 'success' && data.data && data.data.response) {
            addMessage(data.data.response, 'assistant', {
                provider: data.provider,
                toolUsed: data.tool_used,
                language: data.language_detected,
                conversationCount: data.conversation_count,
                promptMode: data.prompt_mode_used
            });
        } else {
            addMessage(`Error: ${data.message || 'Unknown error'}`, 'assistant', { error: true });
        }

    } catch (error) {
        console.error('Send message error:', error);
        addMessage(`Error de conexión: ${error.message}`, 'assistant', { error: true });
        updateResponsePanel({ error: error.message }, 'Error');
    } finally {
        // Re-enable send button
        sendBtn.disabled = false;
        sendBtn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                <path d="M2 10L18 2L10 18L8 11L2 10Z" fill="currentColor"/>
            </svg>
            Enviar
        `;
    }
}

// Add message to chat
function addMessage(text, sender, metadata = {}) {
    const chatMessages = document.getElementById('chatMessages');

    // Remove welcome message if exists
    const welcomeMsg = chatMessages.querySelector('.welcome-message');
    if (welcomeMsg) {
        welcomeMsg.remove();
    }

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = sender === 'user' ? '👤' : '🤖';

    const content = document.createElement('div');
    content.className = 'message-content';

    const messageText = document.createElement('div');
    messageText.className = 'message-text';
    messageText.textContent = text;

    const messageMeta = document.createElement('div');
    messageMeta.className = 'message-meta';

    // Add metadata badges
    if (metadata.promptMode) {
        const badge = document.createElement('span');
        badge.className = 'meta-badge';
        badge.textContent = `📝 ${metadata.promptMode}`;
        messageMeta.appendChild(badge);
    }

    if (metadata.toolUsed) {
        const badge = document.createElement('span');
        badge.className = 'meta-badge';
        badge.textContent = `🔧 ${metadata.toolUsed}`;
        messageMeta.appendChild(badge);
    }

    if (metadata.provider) {
        const badge = document.createElement('span');
        badge.className = 'meta-badge';
        badge.textContent = `⚡ ${metadata.provider}`;
        messageMeta.appendChild(badge);
    }

    if (metadata.language) {
        const badge = document.createElement('span');
        badge.className = 'meta-badge';
        badge.textContent = `🌐 ${metadata.language}`;
        messageMeta.appendChild(badge);
    }

    if (metadata.conversationCount) {
        const badge = document.createElement('span');
        badge.className = 'meta-badge';
        badge.textContent = `💬 ${metadata.conversationCount}`;
        messageMeta.appendChild(badge);
    }

    // Add timestamp
    const timestamp = document.createElement('span');
    timestamp.textContent = new Date().toLocaleTimeString();
    messageMeta.appendChild(timestamp);

    content.appendChild(messageText);
    content.appendChild(messageMeta);

    messageDiv.appendChild(avatar);
    messageDiv.appendChild(content);

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Add system message
function addSystemMessage(text) {
    const chatMessages = document.getElementById('chatMessages');

    const messageDiv = document.createElement('div');
    messageDiv.style.cssText = `
        text-align: center;
        padding: 0.5rem;
        color: var(--text-muted);
        font-size: 0.875rem;
        font-style: italic;
    `;
    messageDiv.textContent = text;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Update response panel
function updateResponsePanel(data, title = 'Response') {
    const responseJson = document.getElementById('responseJson');
    responseJson.textContent = JSON.stringify(data, null, 2);

    // Syntax highlighting (simple)
    highlightJson(responseJson);
}

// Simple JSON syntax highlighting
function highlightJson(element) {
    let json = element.textContent;

    // Color coding
    json = json.replace(/"([^"]+)":/g, '<span style="color: #a78bfa">"$1"</span>:');
    json = json.replace(/: "([^"]+)"/g, ': <span style="color: #34d399">"$1"</span>');
    json = json.replace(/: (\d+)/g, ': <span style="color: #fbbf24">$1</span>');
    json = json.replace(/: (true|false|null)/g, ': <span style="color: #f472b6">$1</span>');

    element.innerHTML = json;
}

// Copy response to clipboard
function copyResponse() {
    const responseJson = document.getElementById('responseJson');
    const text = responseJson.textContent;

    navigator.clipboard.writeText(text).then(() => {
        // Show feedback
        const btn = event.target.closest('.btn-icon');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<span style="color: #10b981">✓</span>';

        setTimeout(() => {
            btn.innerHTML = originalHTML;
        }, 2000);
    }).catch(err => {
        console.error('Copy failed:', err);
    });
}

// Clear chat
function clearChat() {
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = `
        <div class="welcome-message">
            <h3>👋 Bienvenido al API Tester de GOMedisys</h3>
            <p>Prueba la API de chat médico con diferentes modos y herramientas.</p>
            <ul>
                <li>Selecciona un modo de prompt (Medical, Pediatric, Emergency, etc.)</li>
                <li>Opcionalmente, elige una herramienta médica (FDA, PubMed, ICD-10, etc.)</li>
                <li>Escribe tu mensaje y envía</li>
            </ul>
        </div>
    `;
}

// Test Health Endpoint
async function testHealth() {
    try {
        const response = await fetch(`${API_BASE_URL}/health`);
        const data = await response.json();
        updateResponsePanel(data, 'Health Check');
        addSystemMessage('✅ Health check completado');
    } catch (error) {
        updateResponsePanel({ error: error.message }, 'Health Check Error');
        addSystemMessage('❌ Health check falló');
    }
}

// Test Providers Endpoint
async function testProviders() {
    try {
        const response = await fetch(`${API_BASE_URL}/providers`);
        const data = await response.json();
        updateResponsePanel(data, 'Providers List');
        addSystemMessage('✅ Providers listados');
    } catch (error) {
        updateResponsePanel({ error: error.message }, 'Providers Error');
        addSystemMessage('❌ Error al listar providers');
    }
}

// Test Prompts Endpoint
async function testPrompts() {
    try {
        const response = await fetch(`${API_BASE_URL}/prompts`);
        const data = await response.json();
        updateResponsePanel(data, 'Prompts List');
        addSystemMessage('✅ Prompts listados');
    } catch (error) {
        updateResponsePanel({ error: error.message }, 'Prompts Error');
        addSystemMessage('❌ Error al listar prompts');
    }
}
