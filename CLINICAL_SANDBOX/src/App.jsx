import React, { useState, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './App.css';

const API_BASE = 'http://localhost:8000';
const DEFAULT_TOKEN = 'hcg_maestro_123';

function App() {
  // Navigation State
  const [activeView, setActiveView] = useState('agent'); // 'adm' | 'agent' | 'eval'

  // Evaluation / RLHF State
  const [selectedEvalCase, setSelectedEvalCase] = useState(null);
  const [evalFeedback, setEvalFeedback] = useState({
    status: 'correct', // 'correct' | 'incorrect' | 'gold'
    correctedResponse: '',
    clinicalTags: []
  });

  const [currentToken, setCurrentToken] = useState(DEFAULT_TOKEN);
  const [usageLogs, setUsageLogs] = useState([]);
  const [systemStats, setSystemStats] = useState({ online: true, version: '2.0.0' });

  // Agent Panel State
  const [messages, setMessages] = useState([
    { role: 'ai', text: '¡Bienvenido al **Clinical Testing Sandbox**!\n\nUtiliza el panel de la derecha para configurar el contexto HIS y probar la inyección de prompts XML del cliente.', timestamp: new Date().toLocaleTimeString() }
  ]);
  const [inputText, setInputText] = useState('');
  const [usePromptInjection, setUsePromptInjection] = useState(false);
  const [selectedIAType, setSelectedIAType] = useState('medical');
  const [selectedModule, setSelectedModule] = useState('chat1');
  const [isSending, setIsSending] = useState(false);

  // HIS Context State
  const [hisContext, setHisContext] = useState({
    genero: 'F',
    edad: 20,
    diagnostico: 'DOLOR LOCALIZADO EN OTRAS PARTES INFERIORES DEL ABDOMEN'
  });

  // Technical / Inspector State
  const [activeTab, setActiveTab] = useState('trace');
  const [currentTrace, setCurrentTrace] = useState(null);
  const [technicalSpecs, setTechnicalSpecs] = useState({
    last_payload: null,
    system_prompt: 'Auditor Médico: Capas de Seguridad BioMistral Activas.',
    metrics: { latency: '---', cache: '---' }
  });

  useEffect(() => {
    fetchTokens();
    fetchLogs();
  }, []);

  const fetchTokens = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/tokens`);
      const data = await res.json();
      setTokens(data);
    } catch (e) {
      console.error("Error fetching tokens", e);
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/logs`);
      const data = await res.json();
      setUsageLogs(data);
    } catch (e) {
      console.error("Error fetching logs", e);
    }
  };

  const fetchTrace = async (sessionId) => {
    try {
      const res = await fetch(`${API_BASE}/admin/trace/${sessionId}`);
      const data = await res.json();
      setUsageLogs(prev => prev); // dummy use
      setCurrentTrace(data.trace);
    } catch (e) {
      setCurrentTrace({ error: "No trace found" });
    }
  };

  const createNewUser = async () => {
    const name = prompt("Nombre del nuevo usuario:");
    if (!name) return;
    try {
      await fetch(`${API_BASE}/admin/tokens`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: name, name: `Token para ${name}` })
      });
      fetchTokens();
    } catch (e) {
      alert("Error creando usuario");
    }
  };

  const sendMessage = async () => {
    if (!inputText.trim() || isSending) return;

    let finalMessage = inputText;
    // Simular inyección masiva si está activa
    if (usePromptInjection) {
      finalMessage = `<rol>médico internista</rol><contexto>Soy médico y mi paciente es GENERO:${hisContext.genero}, EDAD:${hisContext.edad} años, DIAGNOSTICO:${hisContext.diagnostico}</contexto><alcance>responde directamente, conciso y claro, no recomiendes nada</alcance><solicitud>${inputText}</solicitud>`;
    }

    const userEntry = { role: 'user', text: inputText, timestamp: new Date().toLocaleTimeString() };
    setMessages(prev => [...prev, userEntry]);
    setInputText('');
    setIsSending(true);

    const payload = {
      message: finalMessage,
      sessionId: `sandbox_${Date.now()}`,
      IAType: selectedIAType,
      context: hisContext
    };
    setTechnicalSpecs(prev => ({ ...prev, last_payload: payload }));

    const startTime = Date.now();
    try {
      const response = await fetch(`${API_BASE}/v1/${selectedModule}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${currentToken}`
        },
        body: JSON.stringify(payload)
      });

      const data = await response.json();
      const endTime = Date.now();

      let responseText = 'Sin respuesta del módulo.';
      if (data.data && data.data.response) responseText = data.data.response;
      else if (data.response) responseText = data.response;
      else if (data.message) responseText = data.message;

      setMessages(prev => [...prev, {
        role: 'ai',
        text: responseText,
        timestamp: new Date().toLocaleTimeString()
      }]);

      setTechnicalSpecs(prev => ({
        ...prev,
        metrics: {
          latency: `${endTime - startTime}ms`,
          cache: (data.data?.auditor_intercept || data.meta?.cached) ? 'HIT' : 'MISS'
        }
      }));

      fetchTrace(data.session_id || payload.sessionId);
      fetchLogs();
    } catch (error) {
      setMessages(prev => [...prev, { role: 'ai', text: 'Error de conexión con el Gateway.', timestamp: new Date().toLocaleTimeString() }]);
    } finally {
      setIsSending(false);
    }
  };

  const clearSession = () => {
    setMessages([{ role: 'ai', text: 'Sesión reiniciada. Memoria limpia.', timestamp: new Date().toLocaleTimeString() }]);
    setCurrentTrace(null);
    setTechnicalSpecs(prev => ({ ...prev, metrics: { latency: '---', cache: '---' } }));
  };

  const revokeToken = async (token) => {
    if (!confirm(`¿Revocar token ${token.slice(0, 8)}...?`)) return;
    // Endpoint placeholder
    alert("Funcionalidad de revocación pendiente de backend.");
  };

  return (
    <div className="sandbox-wrapper">
      {/* NAV RAIL (Fijado a la izquierda) */}
      <nav className="nav-rail glass">
        <div className="nav-logo">G</div>
        <button
          className={`nav-item ${activeView === 'agent' ? 'active' : ''}`}
          onClick={() => setActiveView('agent')}
          title="Agent Testing Suite"
        >
          🤖
        </button>
        <button
          className={`nav-item ${activeView === 'adm' ? 'active' : ''}`}
          onClick={() => setActiveView('adm')}
          title="ADM Management"
        >
          ⚙️
        </button>
        <button
          className={`nav-item ${activeView === 'eval' ? 'active' : ''}`}
          onClick={() => setActiveView('eval')}
          title="Fine-Tuning & Clinical Eval"
        >
          ⚖️
        </button>
      </nav>

      {/* MAIN VIEW AREA */}
      <div className="main-viewport">
        {activeView === 'agent' ? (
          <div className="agent-panels">
            {/* AGENT CHAT AREA */}
            <main className="chat-area">
              <div className="chat-panel glass">
                <div className="panel-header">
                  <span>Agent Intelligence</span>
                  <div className="header-actions">
                    <button className="text-btn" onClick={clearSession}>🗑️ Clear Session</button>
                    <div className="module-info">{selectedModule} / {selectedIAType}</div>
                  </div>
                </div>
                <div className="messages-area">
                  {messages.map((m, i) => (
                    <div key={i} className={`msg-bubble ${m.role}`}>
                      <div className="msg-content">
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
                      </div>
                      <div className="msg-time">{m.timestamp}</div>
                    </div>
                  ))}
                  {isSending && <div className="msg-bubble ai loading">Procesando...</div>}
                </div>
                <div className="input-area">
                  <div className="input-row">
                    <input
                      type="text"
                      className="chat-input glass"
                      placeholder={usePromptInjection ? "Introduce la <solicitud> XML..." : "Pregunta cualquier cosa médica..."}
                      value={inputText}
                      onChange={(e) => setInputText(e.target.value)}
                      onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
                    />
                    <button className="send-btn" onClick={sendMessage} disabled={isSending}>
                      {isSending ? '...' : 'Enviar'}
                    </button>
                  </div>
                  <div className="input-options">
                    <label className="toggle">
                      <input type="checkbox" checked={usePromptInjection} onChange={(e) => setUsePromptInjection(e.target.checked)} />
                      <span>Simular Prompt Injection Cliente</span>
                    </label>
                  </div>
                </div>
              </div>
            </main>

            {/* AGENT INSPECTOR / CONFIG */}
            <aside className="agent-inspector explorer glass">
              <div className="panel-header">Agent Configuration</div>

              <div className="inspector-section config-row">
                <div className="field">
                  <label>IAType (Prompt Mode)</label>
                  <select value={selectedIAType} onChange={e => setSelectedIAType(e.target.value)}>
                    <option value="medical">Medical Agent</option>
                    <option value="pediatric">Pediatric</option>
                    <option value="emergency">Emergency</option>
                    <option value="pharmacy">Pharmacy</option>
                    <option value="general">General Chat</option>
                  </select>
                </div>
                <div className="field">
                  <label>External Tools</label>
                  <select value={selectedModule} onChange={e => setSelectedModule(e.target.value)}>
                    <option value="chat1">No Tools (General)</option>
                    <option value="tools/pubmed">PubMed Search</option>
                    <option value="tools/fda">FDA Drug Search</option>
                    <option value="tools/icd10">ICD-10 Search</option>
                  </select>
                </div>
              </div>

              <div className="inspector-section">
                <h4>Session History</h4>
                <div className="sessions-list glass">
                  <div className="session-item active">Current Session (Last trace)</div>
                  <div className="placeholder-small">History explorer coming soon...</div>
                </div>
              </div>

              <div className="inspector-section">
                <h4>HIS Context (Patient Data)</h4>
                <div className="his-editor glass">
                  <div className="field">
                    <label>Género</label>
                    <select value={hisContext.genero} onChange={e => setHisContext({ ...hisContext, genero: e.target.value })}>
                      <option value="F">Femenino</option>
                      <option value="M">Masculino</option>
                    </select>
                  </div>
                  <div className="field">
                    <label>Edad</label>
                    <input type="number" value={hisContext.edad} onChange={e => setHisContext({ ...hisContext, edad: parseInt(e.target.value) })} />
                  </div>
                  <div className="field full">
                    <label>Diagnóstico Primario</label>
                    <textarea value={hisContext.diagnostico} onChange={e => setHisContext({ ...hisContext, diagnostico: e.target.value })} />
                  </div>
                </div>
              </div>

              <div className="inspector-section tabs-container">
                <div className="tabs">
                  <button className={activeTab === 'trace' ? 'active' : ''} onClick={() => setActiveTab('trace')}>Audit Trace</button>
                  <button className={activeTab === 'payload' ? 'active' : ''} onClick={() => setActiveTab('payload')}>JSON</button>
                </div>
                <div className="tab-content">
                  {activeTab === 'trace' && (
                    <div className="trace-view">
                      {currentTrace ? currentTrace.map((step, idx) => (
                        <div key={idx} className="trace-step">
                          <div className="step-name">{step.step}</div>
                          <pre className="step-data">{JSON.stringify(step.data, null, 2)}</pre>
                        </div>
                      )) : <div className="placeholder">Esperando trazo clínico...</div>}
                    </div>
                  )}
                  {activeTab === 'payload' && (
                    <pre className="code-block glass">
                      {technicalSpecs.last_payload ? JSON.stringify(technicalSpecs.last_payload, null, 2) : '// No data'}
                    </pre>
                  )}
                </div>
              </div>
            </aside>
          </div>
        ) : activeView === 'adm' ? (
          /* ADM MANAGEMENT VIEW */
          <div className="adm-panels">
            <header className="adm-header glass">
              <h1>ADM MODULAR / Gateway Management</h1>
              <div className="system-health">
                <span className="dot"></span> System Online (v{systemStats.version})
              </div>
            </header>

            <div className="adm-grid">
              <section className="adm-card glass info">
                <h3>Token & User Registry</h3>
                <div className="token-list">
                  {tokens.map((t, i) => (
                    <div key={i} className={`token-row ${currentToken === t.token ? 'current' : ''}`} onClick={() => setCurrentToken(t.token)}>
                      <div className="tk-info">
                        <span className="tk-name">{t.name}</span>
                        <span className="tk-user">User: {t.user}</span>
                      </div>
                      <div className="tk-actions">
                        <div className={`tk-role tag ${t.role}`}>{t.role}</div>
                        <button className="icon-btn" onClick={(e) => { e.stopPropagation(); revokeToken(t.token); }}>🚫</button>
                      </div>
                    </div>
                  ))}
                </div>
                <button className="add-btn" onClick={createNewUser}>+ New Test User</button>
              </section>

              <section className="adm-card glass usage">
                <h3>Consumption Monitoring</h3>
                <div className="usage-stats">
                  {usageLogs.map((log, i) => (
                    <div key={i} className="usage-row">
                      <span className="ts">{new Date(log.timestamp).toLocaleTimeString()}</span>
                      <span className="ep">[{log.endpoint}]</span>
                      <span className="tk">{log.total_tokens} tokens</span>
                    </div>
                  ))}
                </div>
              </section>

              <section className="adm-card glass settings">
                <h3>System Integration</h3>
                <div className="settings-form">
                  <div className="field">
                    <label>Active Gateway URL</label>
                    <div className="token-display">http://localhost:8000</div>
                  </div>
                  <div className="field">
                    <label>Current Master Session</label>
                    <div className="token-display">hcg_maestro_session_77</div>
                  </div>
                </div>
              </section>
            </div>
          </div>
        ) : (
          /* EVALUATION & FINE-TUNING VIEW */
          <div className="eval-panels">
            <aside className="case-explorer glass">
              <div className="panel-header">RLHF Case History</div>
              <div className="case-filters">
                <button className="filter-pill active">All</button>
                <button className="filter-pill alert">Alerts</button>
                <button className="filter-pill reject">Rejects</button>
              </div>
              <div className="case-list">
                {[1, 2, 3].map(i => (
                  <div key={i} className="case-item glass" onClick={() => setSelectedEvalCase({ id: i })}>
                    <div className="case-date">Hace {i} horas</div>
                    <div className="case-preview">Consulta médica sobre dolor abdominal...</div>
                    <div className="case-status alert">Veredicto Auditor: ALERT</div>
                  </div>
                ))}
              </div>
            </aside>

            <main className="eval-workview">
              <header className="workview-header">
                <h2>Analysis Workview</h2>
                <div className="case-id">Session ID: sandbox_eval_12345</div>
              </header>

              <div className="analysis-grid">
                <section className="analysis-block glass">
                  <h4>1. Input & Context (Prompt)</h4>
                  <div className="code-block">
                    "Tengo un dolor muy fuerte, ¿puedo tomar algo?"
                    <br /><br />
                    <strong>Context:</strong> F, 20 años, Úlcera Gástrica activa.
                  </div>
                </section>

                <section className="analysis-block glass">
                  <h4>2. AI Raw Response</h4>
                  <div className="code-block">
                    "Para el dolor fuerte puede tomar Aspirina de 500mg cada 8 horas..."
                  </div>
                </section>

                <section className="analysis-block glass warning">
                  <h4>3. Auditor Intervention</h4>
                  <div className="code-block alert-text">
                    [REJECTED] Contraindicación crítica. Aspirina prohibida en úlcera gástrica activa.
                  </div>
                </section>
              </div>
            </main>

            <aside className="expert-panel glass">
              <div className="panel-header">Fine-Tuning ground truth</div>

              <div className="eval-form">
                <div className="field">
                  <label>Auditor Accuracy</label>
                  <div className="rating-toggle">
                    <button className="rate-btn correct selected">✅ Correct</button>
                    <button className="rate-btn incorrect">❌ Failure</button>
                    <button className="rate-btn gold">⭐ Gold Standard</button>
                  </div>
                </div>

                <div className="field">
                  <label>Corrected / Ideal Response (Target)</label>
                  <textarea
                    placeholder="Escribe la respuesta médica perfecta para re-entrenar al modelo..."
                    className="ground-truth-editor"
                  />
                </div>

                <div className="field">
                  <label>Safety Classification</label>
                  <div className="tag-cloud">
                    <span className="eval-tag">Contraindication</span>
                    <span className="eval-tag">Dosage Error</span>
                    <span className="eval-tag">Protocol Breach</span>
                    <span className="eval-tag">+ Add Tag</span>
                  </div>
                </div>

                <button className="save-eval-btn">Save to Fine-Tuning Dataset</button>
                <div className="dataset-progress">
                  <div className="progress-label">Dataset Quality: 85%</div>
                  <div className="progress-bar"><div className="fill" style={{ width: '85%' }}></div></div>
                </div>
              </div>
            </aside>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
