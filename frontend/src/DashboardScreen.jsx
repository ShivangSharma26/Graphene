import React, { useState, useEffect, useRef } from 'react';
import { GitBranch, Plus, Minus, Maximize, RefreshCw, ArrowUp, Bot, Loader2, ChevronDown, ChevronRight } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import KnowledgeGraph from './components/KnowledgeGraph';

export default function DashboardScreen({ repo }) {
  const [graphData, setGraphData] = useState(null);
  const [stats, setStats] = useState({ nodes: 0, edges: 0, langs: 0 });
  const [ingesting, setIngesting] = useState(true);
  const [ingestionStatus, setIngestionStatus] = useState('Cloning repository...');
  
  // Chat state
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [showQuickQueries, setShowQuickQueries] = useState(false);
  
  // Resizable layout state
  const [graphWidth, setGraphWidth] = useState(55); // percentage
  const [isDragging, setIsDragging] = useState(false);

  const chatEndRef = useRef(null);
  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // Drag logic for resizer
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (!isDragging) return;
      const newWidth = (e.clientX / window.innerWidth) * 100;
      if (newWidth > 20 && newWidth < 80) { // Limit between 20% and 80%
        setGraphWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  useEffect(() => {
    let active = true;
    let intervalId = null;

    setIngesting(true);
    setIngestionStatus('Cloning repository...');

    const startIngestion = async () => {
      try {
        const token = localStorage.getItem('graphene_token');
        const payload = { repo_url: repo };
        if (token) {
          payload.token = token;
        }

        const res = await fetch('/api/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        
        if (!res.ok) {
          const errData = await res.json();
          if (active) {
            setIngesting(false);
            setMessages([{
              sender: 'agent',
              text: `❌ **Ingestion failed:** ${errData.detail || 'Could not start ingestion.'}`
            }]);
          }
          return;
        }

        const data = await res.json();
        const jobId = data.job_id;
        
        if (!active) return;
        setIngestionStatus('Parsing source code...');

        intervalId = setInterval(async () => {
          try {
            const statusRes = await fetch(`/api/status/${jobId}`);
            if (!statusRes.ok) return;
            const statusData = await statusRes.json();

            if (!active) return;

            if (statusData.status === 'STARTED') {
              setIngestionStatus('Building knowledge graph...');
            }

            if (statusData.status === 'SUCCESS') {
              if (intervalId) {
                clearInterval(intervalId);
                intervalId = null;
              }
              setIngestionStatus('Loading graph...');
              await loadGraph();
              if (active) {
                setIngesting(false);
                setMessages([{
                  sender: 'agent',
                  text: "✅ **Codebase ingested successfully!**\n\nI've analyzed the repository, built the knowledge graph, and indexed all source code. I can now answer any question about this codebase.\n\nTry asking me:\n- *What's the architecture?*\n- *What does function X do?*\n- *Show dead code*\n- *What are the API endpoints?*"
                }]);
              }
            } else if (statusData.status === 'FAILURE') {
              if (intervalId) {
                clearInterval(intervalId);
                intervalId = null;
              }
              if (active) {
                setIngesting(false);
                setMessages([{
                  sender: 'agent',
                  text: "❌ **Ingestion failed.** Please check if the repository URL is correct and try again."
                }]);
              }
            }
          } catch (err) {
            console.error('Polling error:', err);
          }
        }, 2000);

      } catch (err) {
        if (active) {
          setIngesting(false);
          setMessages([{ sender: 'agent', text: '❌ Failed to connect to the backend.' }]);
        }
      }
    };

    startIngestion();

    return () => {
      active = false;
      if (intervalId) {
        clearInterval(intervalId);
      }
    };
  }, [repo]);

  const loadGraph = async () => {
    try {
      const res = await fetch('/api/graph-data');
      const data = await res.json();
      
      const d3Nodes = data.nodes.map(n => ({
        id: n.id,
        label: n.name,
        type: n.group.toLowerCase(), // File -> file, Class -> class, etc.
      }));

      const seenEdges = new Set();
      const d3Links = [];

      data.links.forEach(l => {
        const edgeKey = `${l.source}-${l.target}`;
        if (!seenEdges.has(edgeKey)) {
          seenEdges.add(edgeKey);
          
          let kind = 'imports';
          if (l.type === 'DEFINED_IN') kind = 'defines';
          if (l.type === 'CALLS') kind = 'calls';
          if (l.type === 'IMPORTS_FILE') kind = 'imports';

          d3Links.push({
            source: l.source,
            target: l.target,
            kind: kind
          });
        }
      });
      
      // Count unique languages from node data
      const langs = new Set(data.nodes.filter(n => n.group === 'File').map(n => {
        const ext = n.name?.split('.').pop();
        return ext;
      }));
      
      setGraphData({ nodes: d3Nodes, links: d3Links });
      setStats({ nodes: data.nodes.length, edges: data.links.length, langs: langs.size || 0 });
    } catch(err) {
      console.error('Graph load error:', err);
    }
  };

  const sendMessage = async (text) => {
    if (!text.trim()) return;
    
    const newMsgs = [...messages, { sender: 'user', text }];
    setMessages(newMsgs);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text })
      });
      const data = await res.json();
      setMessages([...newMsgs, { sender: 'agent', text: data.response }]);
    } catch (err) {
      setMessages([...newMsgs, { sender: 'agent', text: "❌ Error connecting to the AI backend. Make sure the server is running." }]);
    }
    setLoading(false);
  };

  return (
    <div className={`dashboard-layout ${isDragging ? 'dragging' : ''}`}>
      <div className="graph-section" style={{ flex: `0 0 ${graphWidth}%` }}>
        {/* Top Overlay Stats */}
        <div className="graph-top-overlay" style={{zIndex: 10}}>
          <div className="repo-badge">
            <GitBranch size={16} />
            {repo.replace('https://github.com/', '')}
          </div>
          <div className="stats-text">
            <span>{stats.nodes}</span> nodes &nbsp;&nbsp; <span>{stats.edges}</span> edges &nbsp;&nbsp; <span>{stats.langs}</span> langs
          </div>
        </div>

        {/* Loading State or Knowledge Graph */}
        {ingesting ? (
          <div className="graph-loading">
            <Loader2 size={40} className="spinner" />
            <div className="loading-text">{ingestionStatus}</div>
          </div>
        ) : (
          graphData && <KnowledgeGraph data={graphData} />
        )}
      </div>

      {/* Resizable Divider */}
      <div 
        className="layout-resizer" 
        onMouseDown={() => setIsDragging(true)}
        title="Drag to resize"
      >
        <div className="resizer-handle"></div>
      </div>

      {/* RIGHT CHAT PANE */}
      <div className="chat-section" style={{ flex: `0 0 ${100 - graphWidth}%` }}>
        <div className="chat-header">
          <div className="chat-header-title">
            <Bot size={18} color="#FF4081" /> AI Assistant
          </div>
          <div className="agent-badge">Graphene Agent</div>
        </div>

        <div className="chat-messages">
          {messages.map((m, i) => (
            <div key={i} className={`message-bubble ${m.sender === 'user' ? 'message-user' : 'message-agent'}`}>
              {m.sender === 'agent' && <div className="agent-name-small">GRAPHENE AI</div>}
              <ReactMarkdown>{m.text}</ReactMarkdown>
            </div>
          ))}
          {loading && (
            <div className="message-bubble message-agent">
              <div className="agent-name-small">GRAPHENE AI</div>
              <div className="loading-dots">
                <span>Analyzing codebase</span>
                <Loader2 size={14} className="spinner" style={{display: 'inline-block', marginLeft: '8px'}} />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="chat-input-area">
          <div className="quick-queries-dropdown">
            <button 
              className="quick-query-toggle" 
              onClick={() => setShowQuickQueries(!showQuickQueries)}
            >
              ⚡ Quick Queries {showQuickQueries ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
            </button>
            {showQuickQueries && (
              <div className="quick-queries-menu">
                <button className="quick-query-btn" onClick={() => { sendMessage("What's the architecture of this codebase?"); setShowQuickQueries(false); }}>
                  What's the architecture?
                </button>
                <button className="quick-query-btn" onClick={() => { sendMessage("List all API endpoints"); setShowQuickQueries(false); }}>
                  List all API endpoints
                </button>
                <button className="quick-query-btn" onClick={() => { sendMessage("Show dead code"); setShowQuickQueries(false); }}>
                  Show dead code
                </button>
              </div>
            )}
          </div>
          <div className="chat-input-wrapper">
            <input 
              type="text" 
              className="chat-input" 
              placeholder="Ask anything about the codebase..." 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendMessage(input)}
            />
            <button className="chat-send-btn" onClick={() => sendMessage(input)}>
              <ArrowUp size={20} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
