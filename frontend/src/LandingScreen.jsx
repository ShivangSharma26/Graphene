import React from 'react';
import { Code2, Network, Zap, LayoutTemplate, Sun, Moon, LogOut } from 'lucide-react';
import './LandingScreen.css';
import { API_BASE_URL } from './config';

const GithubIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.2c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4"/>
    <path d="M9 18c-4.51 2-5-2-7-2"/>
  </svg>
);

export default function LandingScreen({ onThemeToggle, theme, user, onAnalyze, recentRepos, onLogout }) {
  const [repoInput, setRepoInput] = React.useState('');

  const handleGithubLogin = () => {
    // Redirect to FastAPI backend auth route
    window.location.href = `${API_BASE_URL || 'http://localhost:8000'}/api/auth/login/github`;
  };

  if (user) {
    return (
      <div className="landing-container-logged-in">
        <div className="landing-top-right">
          <button className="theme-toggle-btn" onClick={onThemeToggle} style={{marginRight: '16px'}}>
            {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
          </button>
          <img src={user.avatar} alt="Avatar" className="user-avatar-small" onError={(e) => e.target.style.display = 'none'} />
          <span className="user-name-small" style={{marginRight: '16px'}}>{user.username}</span>
          <button className="logout-btn" onClick={onLogout} title="Logout">
            <LogOut size={16} />
          </button>
        </div>

        <div className="landing-centered-content">
          <img src="/logo.png" alt="Graphene Logo" className="graphene-logo-xl" />
          <h1 className="landing-title">Understand any codebase instantly</h1>
          <p className="landing-subtitle">
            Paste a GitHub repo URL and Graphene builds a live<br/>
            knowledge graph — then answer any question about it.
          </p>

          <div className="input-group-large">
            <input 
              type="text" 
              className="repo-input-main" 
              placeholder="https://github.com/owner/repository"
              value={repoInput}
              onChange={(e) => setRepoInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && onAnalyze(repoInput)}
            />
            <button className="analyze-btn-main" onClick={() => onAnalyze(repoInput)}>
              <Network size={18} /> Analyze repo
            </button>
          </div>

          {recentRepos && recentRepos.length > 0 && (
            <div className="recent-searches-centered">
              <h3 className="recent-title-centered">Recent Searches</h3>
              <div className="recent-pills">
                {recentRepos.map(repo => (
                  <button key={repo} className="recent-pill" onClick={() => onAnalyze(repo)}>
                    {repo}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="landing-split-container">
      {/* Left Panel: Deep Purple/Pink Aesthetic */}
      <div className="landing-left-panel">
        <div className="left-panel-content">
          <div className="landing-logo-container">
            <img src="/logo.png" alt="Graphene Logo" className="graphene-logo-large" onError={(e) => e.target.style.display = 'none'} />
            <div>
              <h1 className="landing-logo-text">Graphene AI</h1>
              <span className="landing-logo-sub">REPO INTELLIGENCE</span>
            </div>
          </div>

          <h2 className="landing-main-headline">
            Code that finally<br />understands you.
          </h2>
          <p className="landing-sub-headline">
            Your personal AI codebase consultant —<br />decoding your repository's DNA, one layer at a time.
          </p>

          <div className="features-grid-vertical">
            <div className="feature-block">
              <div className="feature-icon-box"><Network size={18} /></div>
              <div className="feature-text">
                <h3>Reads your architecture</h3>
                <p>Decodes your code's unique structural blueprint</p>
              </div>
            </div>
            
            <div className="feature-block">
              <div className="feature-icon-box"><Zap size={18} /></div>
              <div className="feature-text">
                <h3>Lightning-fast, 24/7</h3>
                <p>Intelligent analysis you can trust, anytime</p>
              </div>
            </div>

            <div className="feature-block">
              <div className="feature-icon-box"><Code2 size={18} /></div>
              <div className="feature-text">
                <h3>Context that evolves</h3>
                <p>Dynamic understanding that adapts as your code does</p>
              </div>
            </div>

            <div className="feature-block">
              <div className="feature-icon-box"><LayoutTemplate size={18} /></div>
              <div className="feature-text">
                <h3>Expertly trained</h3>
                <p>Built on thousands of real software architectures</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Right Panel: Dark/Login Aesthetic */}
      <div className="landing-right-panel">
        <div className="theme-toggle-container">
          <button className="theme-toggle-btn" onClick={onThemeToggle}>
            {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
          </button>
        </div>
        
        <div className="login-container">
          <h2 className="login-title">Sign in</h2>
          <p className="login-subtitle">Welcome back to Graphene</p>
          
          <button className="github-login-btn" onClick={handleGithubLogin}>
            <GithubIcon />
            Continue with GitHub
          </button>
          
          <p className="login-footer">
            New to Graphene? <a href="#">Sign up for free</a>
          </p>
        </div>
      </div>
    </div>
  );
}
