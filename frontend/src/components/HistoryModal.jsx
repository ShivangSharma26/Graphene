import React, { useState, useEffect } from 'react';
import { X, Clock, GitBranch } from 'lucide-react';

export default function HistoryModal({ isOpen, onClose, recentRepos, onSelectRepo }) {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content glass-panel" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            <Clock size={18} /> Recent Repositories
          </div>
          <button className="icon-btn" onClick={onClose}>
            <X size={18} />
          </button>
        </div>
        
        <div className="modal-body">
          {recentRepos.length === 0 ? (
            <div className="empty-state">
              You haven't analyzed any repositories yet.
            </div>
          ) : (
            <div className="repo-list">
              {recentRepos.map((r, i) => (
                <button 
                  key={i} 
                  className="repo-list-item"
                  onClick={() => {
                    onSelectRepo(r);
                    onClose();
                  }}
                >
                  <GitBranch size={16} />
                  <span>{r.replace('https://github.com/', '')}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
