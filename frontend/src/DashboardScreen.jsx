import React, { useState, useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import CytoscapeComponent from 'react-cytoscapejs';
import { GitBranch, Plus, Minus, Maximize, RefreshCw, ArrowUp, Bot } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

// Helper to assign Figma colors based on heuristics
const getNodeColor = (name) => {
  const n = name.toLowerCase();
  if (n.includes('main') || n.includes('index') || n.includes('app') || n.includes('server')) return '#1D9E75'; // Entry
  if (n.includes('auth') || n.includes('login') || n.includes('token') || n.includes('user')) return '#7F77DD'; // Auth
  if (n.includes('pay') || n.includes('order') || n.includes('cart')) return '#D85A30'; // Critical
  if (n.includes('test') || n.includes('util') || n.includes('helper') || n.includes('common')) return '#888780'; // Utility
  return '#7F77DD'; // Default primary
};

export default function DashboardScreen({ repo }) {
  const [elements, setElements] = useState([]);
  const [stats, setStats] = useState({ nodes: 0, edges: 0 });
  const [selectedNode, setSelectedNode] = useState(null);
  
  // Chat state
  const [messages, setMessages] = useState([{
    sender: 'agent',
    text: "Codebase ingested successfully. How can I help you understand this architecture?"
  }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const cyRef = useRef(null);

  useEffect(() => {
    // 1. Trigger ingestion API
    fetch('/api/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: repo })
    }).then(res => res.json()).then(data => {
      const jobId = data.job_id;
      
      // 2. Poll for completion
      const interval = setInterval(async () => {
        try {
          const statusRes = await fetch(`/status/${jobId}`);
          const statusData = await statusRes.json();
          if (statusData.status === 'SUCCESS' || statusData.status === 'FAILURE') {
            clearInterval(interval);
            if (statusData.status === 'SUCCESS') loadGraph();
          }
        } catch (err) {
          console.error(err);
        }
      }, 2000);
    });
  }, [repo]);

  const loadGraph = async () => {
    try {
      const res = await fetch('/api/graph-data');
      const data = await res.json();
      
      const cyElements = [];
      data.nodes.forEach(n => {
        cyElements.push({
          data: { id: n.id, label: n.name, group: n.group, color: getNodeColor(n.name) }
        });
      });
      data.links.forEach(l => {
        cyElements.push({
          data: { source: l.source, target: l.target, label: l.type || 'CALLS' }
        });
      });
      
      setElements(cyElements);
      setStats({ nodes: data.nodes.length, edges: data.links.length });
    } catch(err) {
      console.error(err);
    }
  };

  const handleNodeClick = (event) => {
    const node = event.target;
    setSelectedNode({
      name: node.data('label'),
      type: node.data('group'),
      impact: 'Critical' // Mocked for UI, ideally comes from API
    });
  };

  const sendMessage = async (text) => {
    if (!text.trim()) return;
    
    const newMsgs = [...messages, { sender: 'user', text }];
    setMessages(newMsgs);
    setInput('');
    setLoading(true);

    try {
      const res = await fetch('/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: text })
      });
      const data = await res.json();
      setMessages([...newMsgs, { sender: 'agent', text: data.response }]);
    } catch (err) {
      setMessages([...newMsgs, { sender: 'agent', text: "Error connecting to AI." }]);
    }
    setLoading(false);
  };

  const handleQuickQuery = (q) => sendMessage(q);

  return (
    <div className="dashboard-layout">
      {/* LEFT GRAPH PANE */}
      <div className="graph-section">
        
        {/* Top Overlay Stats */}
        <div className="graph-top-overlay">
          <div className="repo-badge">
            <GitBranch size={16} />
            {repo.replace('https://github.com/', '')}
          </div>
          <div className="stats-text">
            <span>{stats.nodes}</span> nodes &nbsp;&nbsp; <span>{stats.edges}</span> edges &nbsp;&nbsp; <span>3</span> langs
          </div>
        </div>

        {/* Floating Controls */}
        <div className="floating-controls">
          <div className="control-btn" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() + 0.2)}><Plus size={18} /></div>
          <div className="control-btn" onClick={() => cyRef.current?.zoom(cyRef.current.zoom() - 0.2)}><Minus size={18} /></div>
          <div className="control-btn" onClick={() => cyRef.current?.fit()}><Maximize size={18} /></div>
          <div className="control-btn" onClick={loadGraph}><RefreshCw size={18} /></div>
        </div>

        {/* Node Detail Card */}
        {selectedNode && (
          <div className="node-detail-card">
            <div className="node-card-header">
              <div className="node-card-title">{selectedNode.name}</div>
              <div className="risk-badge">High risk</div>
            </div>
            <div className="node-card-row">
              <div className="node-card-label">Type</div>
              <div className="node-card-value">{selectedNode.type}</div>
            </div>
            <div className="node-card-row">
              <div className="node-card-label">Callers</div>
              <div className="node-card-value">Unknown</div>
            </div>
            <div className="node-card-row">
              <div className="node-card-label">Impact</div>
              <div className="node-card-value value-critical">{selectedNode.impact}</div>
            </div>
          </div>
        )}

        {/* Filter Chips */}
        <div className="filter-chips">
          <div className="filter-chip active">All</div>
          <div className="filter-chip">Services</div>
          <div className="filter-chip">Functions</div>
          <div className="filter-chip">Dead code</div>
          <div className="filter-chip">Imports</div>
        </div>

        <CytoscapeComponent 
          elements={elements} 
          style={{ width: '100%', height: '100%' }}
          cy={(cy) => {
            cyRef.current = cy;
            cy.on('tap', 'node', handleNodeClick);
            cy.on('mouseover', 'node', (e) => {
              e.target.style({ 'label': e.target.data('label'), 'font-size': '12px', 'text-background-opacity': 0.8, 'text-background-color': '#000', 'z-index': 100 });
            });
            cy.on('mouseout', 'node', (e) => {
              e.target.style({ 'label': '' });
            });
          }}
          layout={{ 
            name: 'cose', 
            padding: 50,
            nodeRepulsion: 400000,
            idealEdgeLength: 100,
            gravity: 0.1
          }}
          stylesheet={[
            {
              selector: 'node',
              style: {
                'background-color': 'data(color)',
                'label': '', /* Hide labels to stop the massive text overlap */
                'width': 16,
                'height': 16,
                'border-width': 2,
                'border-color': '#fff'
              }
            },
            {
              selector: 'edge',
              style: {
                'width': 2,
                'line-color': '#333',
                'target-arrow-color': '#333',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier',
                'label': 'data(label)',
                'font-size': '8px',
                'color': '#888',
                'text-background-opacity': 1,
                'text-background-color': '#111'
              }
            }
          ]}
        />
      </div>

      {/* RIGHT CHAT PANE */}
      <div className="chat-section">
        <div className="chat-header">
          <div className="chat-header-title">
            <Bot size={18} color="#7F77DD" /> Agent chat
          </div>
          <div className="agent-badge">Impact agent</div>
        </div>

        <div className="chat-messages">
          {messages.map((m, i) => (
            <div key={i} className={`message-bubble ${m.sender === 'user' ? 'message-user' : 'message-agent'}`}>
              {m.sender === 'agent' && <div className="agent-name-small">GRAPHENE AGENT</div>}
              {/* If it's a blast radius response, style it like the impact box in figma */}
              {m.sender === 'agent' && m.text.includes('Blast Radius') ? (
                <div className="impact-box">
                  <ReactMarkdown>{m.text}</ReactMarkdown>
                </div>
              ) : (
                <ReactMarkdown>{m.text}</ReactMarkdown>
              )}
            </div>
          ))}
          {loading && (
            <div className="message-bubble message-agent">
              <div className="agent-name-small">GRAPHENE AGENT</div>
              <div>Scanning deeper...</div>
            </div>
          )}
        </div>

        <div className="chat-input-area">
          <div className="quick-queries">
            <div className="quick-query-label">QUICK QUERIES</div>
            <button className="quick-query-btn" onClick={() => handleQuickQuery("What's the architecture?")}>
              What's the architecture?
            </button>
            <button className="quick-query-btn" onClick={() => handleQuickQuery("Show dead code")}>
              Show dead code
            </button>
          </div>
          <br/>
          <div className="chat-input-wrapper">
            <input 
              type="text" 
              className="chat-input" 
              placeholder="Ask about the repo..." 
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
