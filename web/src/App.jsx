import React, { useState } from 'react';

export default function App() {
  const [prompt, setPrompt] = useState('');
  const [topk, setTopk] = useState('');
  const [answer, setAnswer] = useState('');
  const [context, setContext] = useState('');
  const [runId, setRunId] = useState('');
  const [loading, setLoading] = useState(false);
  const [showContext, setShowContext] = useState(false);

  // Page fills width. Card centers. No horizontal overflow.
  const pageStyle = {
    minHeight: '100vh',
    width: '100%',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    background: '#1f1f1f',
    color: '#fff',
    padding: '24px',
    overflowX: 'hidden',
    boxSizing: 'border-box',
  };

  const cardStyle = {
    width: '100%',
    maxWidth: '900px',
    background: '#2a2a2a',
    borderRadius: '14px',
    padding: '24px',
    boxShadow: '0 10px 30px rgba(0,0,0,0.35)',
    margin: '0 auto',
    boxSizing: 'border-box',
  };

  const titleStyle = {
    margin: 0,
    marginBottom: '16px',
    fontSize: 'clamp(24px, 5vw, 32px)',
    textAlign: 'center',
    letterSpacing: '0.5px',
    lineHeight: '1.2',
  };

  const subtitleStyle = {
    textAlign: 'center',
    marginTop: '-8px',
    color: '#a1a1a1',
    fontSize: 'clamp(12px, 2.5vw, 14px)',
    lineHeight: '1.4',
    padding: '0 16px',
  };

  const textareaStyle = {
    width: '100%',
    height: 'clamp(120px, 25vh, 160px)',
    boxSizing: 'border-box',
    display: 'block',
    resize: 'none',
    borderRadius: '10px',
    border: '1px solid #3a3a3a',
    background: '#151515',
    color: '#fff',
    padding: 'clamp(12px, 3vw, 14px)',
    fontSize: 'clamp(14px, 3.5vw, 16px)',
    outline: 'none',
    lineHeight: '1.4',
  };

  const rowStyle = {
    display: 'flex',
    alignItems: 'center',
    gap: '6px',
    flexWrap: 'wrap',
    marginTop: '14px',
    marginBottom: '6px',
  };

  const inputStyle = {
    flex: '0 0 200px',
    minWidth: '150px',
    borderRadius: '8px',
    border: '1px solid #3a3a3a',
    background: '#151515',
    color: '#fff',
    padding: 'clamp(8px, 2.5vw, 10px) clamp(10px, 3vw, 12px)',
    fontSize: 'clamp(14px, 3.5vw, 15px)',
    outline: 'none',
    boxSizing: 'border-box',
  };

  const labelStyle = {
    whiteSpace: 'nowrap',
    fontSize: 'clamp(13px, 3.5vw, 14px)',
    minWidth: 'fit-content',
  };

  const buttonStyle = {
    marginTop: '12px',
    padding: 'clamp(10px, 3vw, 12px) clamp(16px, 4vw, 18px)',
    borderRadius: '10px',
    border: '1px solid transparent',
    background: '#2563eb',
    color: '#fff',
    fontSize: 'clamp(14px, 3.5vw, 16px)',
    cursor: 'pointer',
    display: 'inline-flex',
    alignItems: 'center',
    gap: '10px',
    justifyContent: 'center',
    minHeight: '44px', 
  };

  const subtleText = { 
    marginTop: '10px', 
    fontSize: 'clamp(11px, 2.5vw, 12px)', 
    color: '#a1a1a1',
    wordBreak: 'break-word',
  };

  const answerSectionStyle = {
    marginTop: '18px',
  };

  const answerTitleStyle = {
    margin: '0 0 10px 0',
    fontSize: 'clamp(16px, 4vw, 18px)',
  };

  const answerTextStyle = {
    whiteSpace: 'pre-wrap',
    margin: 0,
    fontSize: 'clamp(14px, 3.5vw, 16px)',
    lineHeight: '1.5',
  };

  const contextButtonStyle = {
    ...buttonStyle,
    background: '#374151',
    padding: 'clamp(6px, 2vw, 8px) clamp(10px, 3vw, 12px)',
    fontSize: 'clamp(12px, 3vw, 14px)',
    width: 'auto',
    minHeight: '36px',
  };

  const contextPreStyle = {
    marginTop: '12px',
    padding: 'clamp(10px, 3vw, 14px)',
    background: '#151515',
    border: '1px solid #333',
    borderRadius: '10px',
    maxHeight: 'clamp(200px, 40vh, 360px)',
    overflow: 'auto',
    whiteSpace: 'pre-wrap',
    wordBreak: 'break-word',
    marginLeft: '8px',
    fontSize: 'clamp(12px, 3vw, 14px)',
    lineHeight: '1.4',
  };

  async function handleAsk() {
    if (!prompt.trim()) return;
    setLoading(true);
    setAnswer('');
    setContext('');
    setRunId('');

    try {
      const body = { prompt };
      if (topk && !Number.isNaN(Number(topk))) body.top_k = Number(topk);

      const res = await fetch(`${import.meta.env.VITE_API_BASE_URL}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text);
      }

      const data = await res.json();
      setAnswer(data.answer || '');
      setContext(data.context || '');
      setRunId(data.run_id || data.runId || '');
    } catch (err) {
      setAnswer('Error: ' + err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={pageStyle}>
      {}
      <style>{`
        html, body, #root { height: 100%; width: 100%; }
        body { display: block !important; place-items: unset !important; overflow-x: hidden; }
        *, *::before, *::after { box-sizing: border-box; }
        @keyframes spin { to { transform: rotate(360deg); } }
        .spinner {
          width: 14px; height: 14px;
          border: 2px solid rgba(255,255,255,0.35);
          border-top-color: #fff;
          border-radius: 50%;
          animation: spin 0.8s linear infinite;
        }
        .repo-link { color: #93c5fd; text-decoration: none; }
        .repo-link:hover { color: #60a5fa; }
        
        /* Responsive breakpoints */
        @media (max-width: 768px) {
          .page-container { padding: 16px; }
          .card-container { padding: 20px; border-radius: 12px; }
        }
        
        @media (max-width: 480px) {
          .page-container { padding: 12px; }
          .card-container { padding: 16px; border-radius: 10px; }
        }
        
        @media (max-width: 360px) {
          .page-container { padding: 8px; }
          .card-container { padding: 12px; }
        }
        
        /* Ensure proper touch targets on mobile */
        @media (hover: none) and (pointer: coarse) {
          button { min-height: 44px; }
          input, textarea { min-height: 44px; }
        }
      `}</style>

      <div style={cardStyle} className="card-container">
        <h1 style={titleStyle}>NYC ACRIS Property Deeds Information</h1>
        <div style={{ height: '10px' }} />
        <p style={subtitleStyle}>
          <i>Served by DuckDB, powered by Gemini 1.5 Flash, handled by Apache Airflow, and deployed on Google Cloud Platform.
          </i>
        </p>
        <p style={subtitleStyle}>
          <a href="https://github.com/a-partha/real-estate-ai-qa" target="_blank" rel="noopener noreferrer" className="repo-link">GitHub repository</a>
        </p>


        <textarea
          style={textareaStyle}
          placeholder="What would you like to know?

Example questions:
- What is this dataset about?
- Which area has the most properties?"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
        />

        <div style={rowStyle}>
          <label htmlFor="topk" style={labelStyle}>
            Number of top ranked matches to assess:
          </label>
          <input
            id="topk"
            type="number"
            min="1"
            placeholder="Default = 50"
            value={topk}
            onChange={(e) => setTopk(e.target.value)}
            style={inputStyle}
          />
        </div>

        <button onClick={handleAsk} disabled={loading} style={buttonStyle}>
          {loading ? (
            <>
              Asking...
              <span className="spinner" />
            </>
          ) : (
            'Ask'
          )}
        </button>

        <div style={{ height: '10px' }} />
        <p style={labelStyle}>
        <span style={{ ...subtitleStyle, fontStyle: 'normal', display: 'block', textAlign: 'left', marginLeft: -18 }}>
          Note: Please allow about 25 seconds for an answer to be generated, as it's a large dataset.
        </span>
        </p>

        {answer && (
          <div style={answerSectionStyle}>
            <h2 style={answerTitleStyle}>Answer:</h2>
            <p style={answerTextStyle}>{answer}</p>

            {context && (
              <div style={{ marginTop: '12px' }}>
                <button
                  onClick={() => setShowContext(!showContext)}
                  style={contextButtonStyle}
                >
                  {showContext ? 'Hide context' : 'Show context'}
                </button>

                {showContext && (
                  <pre style={contextPreStyle}>
                    {context}
                  </pre>
                )}
              </div>
            )}

            {runId && <p style={subtleText}>Run ID: {runId}</p>}
          </div>
        )}
      </div>
    </div>
  );
}


