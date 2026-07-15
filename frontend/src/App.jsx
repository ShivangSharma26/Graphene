import React, { useState, useEffect } from 'react';
import LandingScreen from './LandingScreen';
import DashboardScreen from './DashboardScreen';
import { API_BASE_URL } from './config';
import FilesScreen from './FilesScreen';
import HistoryModal from './components/HistoryModal';
import './index.css';
import './App.css';

function AuthCallback({ onLogin }) {
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    if (token) {
      localStorage.setItem('graphene_token', token);
      onLogin(token);
    }
  }, []);
  
  return <div style={{color: 'white', padding: 20}}>Logging you in...</div>;
}

export default function App() {
  const [repoUrl, setRepoUrl] = useState(null);
  const [activeTab, setActiveTab] = useState('graph');
  const [theme, setTheme] = useState('dark');
  const [user, setUser] = useState(null);
  const [recentRepos, setRecentRepos] = useState([]);
  const [showHistory, setShowHistory] = useState(false);

  // Theme management
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => prev === 'light' ? 'dark' : 'light');
  };

  // Auth management
  useEffect(() => {
    const token = localStorage.getItem('graphene_token');
    if (token) {
      handleLoginSuccess(token);
    }
  }, []);

  const handleLoginSuccess = async (token) => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/auth/me?token=${token}`);
      if (res.ok) {
        const data = await res.json();
        setUser(data.user);
        setRecentRepos(data.recent_searches || []);
        // Clean URL if we came from callback
        if (window.location.pathname === '/auth/callback') {
          window.history.replaceState({}, document.title, '/');
        }
      } else {
        localStorage.removeItem('graphene_token');
      }
    } catch (err) {
      console.error("Auth error", err);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('graphene_token');
    setUser(null);
    setRecentRepos([]);
  };

  const handleAnalyze = (url) => {
    if (!url) return;
    setRepoUrl(url);
    setActiveTab('graph');
    
    // Update recent repos (keep max 10, remove duplicates, push to top)
    const filtered = recentRepos.filter(r => r !== url);
    const updated = [url, ...filtered].slice(0, 10);
    setRecentRepos(updated);
    localStorage.setItem('graphene_recent_repos', JSON.stringify(updated));
  };

  if (window.location.pathname === '/auth/callback') {
    return <AuthCallback onLogin={handleLoginSuccess} />;
  }

  return (
    <div className="app-container">
      {/* Top Nav Bar for entire app */}
      <div className="top-bar glass-bar">
        <div className="logo-section" onClick={() => setRepoUrl(null)} style={{cursor: 'pointer'}}>
          <div className="logo-dot"></div>
          Graphene <span className="ai-text">AI</span>
        </div>
        
        <div className="top-nav-buttons">
          {repoUrl ? (
            <>
              <button 
                className={`nav-btn ${activeTab === 'graph' ? 'active' : ''}`}
                onClick={() => setActiveTab('graph')}
              >
                Graph
              </button>
              <button 
                className={`nav-btn ${activeTab === 'files' ? 'active' : ''}`}
                onClick={() => setActiveTab('files')}
              >
                Files
              </button>
            </>
          ) : (
            <>
              <button className="nav-btn active">Analyze</button>
              <button className="nav-btn" onClick={() => setShowHistory(true)}>History</button>
            </>
          )}
        </div>
      </div>

      <HistoryModal 
        isOpen={showHistory} 
        onClose={() => setShowHistory(false)} 
        recentRepos={recentRepos}
        onSelectRepo={handleAnalyze}
      />

      {repoUrl ? (
        <>
          <div style={{ display: activeTab === 'graph' ? 'block' : 'none', width: '100%', height: '100%' }}>
            <DashboardScreen repo={repoUrl} />
          </div>
          <div style={{ display: activeTab === 'files' ? 'block' : 'none', width: '100%', height: '100%' }}>
            <FilesScreen isActive={activeTab === 'files'} />
          </div>
        </>
      ) : (
        <LandingScreen 
          onThemeToggle={toggleTheme}
          theme={theme}
          user={user}
          onAnalyze={handleAnalyze}
          recentRepos={recentRepos}
          onLogout={handleLogout}
        />
      )}
    </div>
  );
}
