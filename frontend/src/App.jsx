import React, { useState } from 'react';
import LandingScreen from './LandingScreen';
import DashboardScreen from './DashboardScreen';
import './index.css';

export default function App() {
  const [repoUrl, setRepoUrl] = useState(null);

  return (
    <div className="app-container">
      {/* Top Nav Bar for entire app */}
      <div className="top-bar">
        <div className="logo-section">
          <div className="logo-dot"></div>
          Graphene <span className="ai-text">AI</span>
        </div>
        
        <div className="top-nav-buttons">
          {repoUrl ? (
            <>
              <button className="nav-btn active">Graph</button>
              <button className="nav-btn">Files</button>
              <button className="nav-btn">Agents</button>
              <button className="nav-btn">Settings</button>
            </>
          ) : (
            <>
              <button className="nav-btn active">Analyze</button>
              <button className="nav-btn">Docs</button>
              <button className="nav-btn">History</button>
            </>
          )}
        </div>
      </div>

      {repoUrl ? (
        <DashboardScreen repo={repoUrl} />
      ) : (
        <LandingScreen onAnalyze={(url) => setRepoUrl(url)} />
      )}
    </div>
  );
}
