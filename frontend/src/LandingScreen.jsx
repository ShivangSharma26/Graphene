import React, { useState } from 'react';
import { GitBranch, Activity, Code, Map } from 'lucide-react';

export default function LandingScreen({ onAnalyze }) {
  const [repo, setRepo] = useState('');

  const handleAnalyze = () => {
    if (repo) onAnalyze(repo);
  };

  return (
    <div className="landing-container">
      <div className="landing-icon">
        <GitBranch size={32} />
      </div>
      
      <h1 className="landing-title">Understand any codebase instantly</h1>
      <p className="landing-subtitle">
        Paste a GitHub repo URL and Graphene builds a live<br/>
        knowledge graph — then answer any question about it.
      </p>

      <div className="input-group">
        <input 
          type="text" 
          className="repo-input" 
          placeholder="https://github.com/owner/repository"
          value={repo}
          onChange={(e) => setRepo(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAnalyze()}
        />
        <button className="analyze-btn" onClick={handleAnalyze}>
          <GitBranch size={18} /> Analyze repo
        </button>
      </div>

      <div className="example-repos">
        <button className="example-pill" onClick={() => setRepo('github.com/vercel/next.js')}>
          github.com/vercel/next.js
        </button>
        <button className="example-pill" onClick={() => setRepo('github.com/fastapi/fastapi')}>
          github.com/fastapi/fastapi
        </button>
        <button className="example-pill" onClick={() => setRepo('github.com/langchain-ai/langchain')}>
          github.com/langchain-ai/langchain
        </button>
      </div>

      <div className="features-row">
        <div className="feature-item">
          <Activity size={16} /> Impact analysis
        </div>
        <div className="feature-item">
          <Code size={16} /> Dead code detection
        </div>
        <div className="feature-item">
          <Map size={16} /> Architecture map
        </div>
      </div>
    </div>
  );
}
