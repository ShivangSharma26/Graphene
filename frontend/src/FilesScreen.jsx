import React, { useState, useEffect } from 'react';
import { Folder, File, ChevronRight, ChevronDown, FileCode, Search, Terminal, RefreshCw } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import './FilesScreen.css';

// Recursive File Tree Node
const FileTreeNode = ({ node, onSelectFile, selectedFile }) => {
  const [isOpen, setIsOpen] = useState(false);
  const isDir = node.type === 'directory';

  return (
    <div className="tree-node-wrapper">
      <div 
        className={`tree-node ${isDir ? 'is-dir' : 'is-file'} ${selectedFile === node.path ? 'selected' : ''}`}
        onClick={() => {
          if (isDir) {
            setIsOpen(!isOpen);
          } else {
            onSelectFile(node.path);
          }
        }}
      >
        <span className="tree-icon">
          {isDir ? (
            isOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : (
            <span style={{ width: 14, display: 'inline-block' }}></span>
          )}
          {isDir ? <Folder size={14} className="folder-icon" /> : <File size={14} className="file-icon" />}
        </span>
        <span className="tree-name">{node.name}</span>
      </div>

      {isDir && isOpen && node.children && (
        <div className="tree-children">
          {node.children.map((child, i) => (
            <FileTreeNode key={i} node={child} onSelectFile={onSelectFile} selectedFile={selectedFile} />
          ))}
        </div>
      )}
    </div>
  );
};

export default function FilesScreen({ isActive }) {
  const [tree, setTree] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState('');
  const [loadingContent, setLoadingContent] = useState(false);
  const [loadingTree, setLoadingTree] = useState(false);

  const fetchTree = () => {
    setLoadingTree(true);
    fetch('/api/files')
      .then(res => {
        if (!res.ok) throw new Error('Not found');
        return res.json();
      })
      .then(data => {
        if (data.tree) setTree(data.tree);
        setLoadingTree(false);
      })
      .catch(err => {
        console.error("Failed to load file tree", err);
        setLoadingTree(false);
      });
  };

  useEffect(() => {
    if (isActive && tree.length === 0) {
      fetchTree();
    }
  }, [isActive]);

  const handleSelectFile = (path) => {
    setSelectedFile(path);
    setLoadingContent(true);
    fetch(`/api/files/content?file_path=${encodeURIComponent(path)}`)
      .then(res => res.json())
      .then(data => {
        setFileContent(data.content || 'Error loading file.');
        setLoadingContent(false);
      })
      .catch(err => {
        setFileContent('Error loading file.');
        setLoadingContent(false);
      });
  };

  return (
    <div className="files-screen">
      <div className="files-sidebar">
        <div className="files-sidebar-header">
          <Search size={14} />
          <input type="text" placeholder="Search files..." className="files-search-input" />
          <button className="refresh-tree-btn" onClick={fetchTree} title="Refresh File Tree">
            <RefreshCw size={14} className={loadingTree ? 'spinning' : ''} />
          </button>
        </div>
        <div className="files-tree">
          {tree.length === 0 ? (
            <div className="loading-tree">
              {loadingTree ? 'Loading repository...' : 'No files found. Try refreshing.'}
            </div>
          ) : (
            tree.map((node, i) => (
              <FileTreeNode 
                key={i} 
                node={node} 
                onSelectFile={handleSelectFile} 
                selectedFile={selectedFile} 
              />
            ))
          )}
        </div>
      </div>
      
      <div className="files-content">
        {selectedFile ? (
          <div className="file-viewer-glass">
            <div className="file-viewer-header">
              <FileCode size={16} className="file-icon" />
              <span>{selectedFile}</span>
            </div>
            <div className="file-viewer-body">
              {loadingContent ? (
                <div className="loading-content">Loading {selectedFile}...</div>
              ) : (
                <SyntaxHighlighter 
                  language={selectedFile.split('.').pop() === 'js' || selectedFile.split('.').pop() === 'jsx' ? 'javascript' : selectedFile.split('.').pop() === 'py' ? 'python' : 'typescript'} 
                  style={vscDarkPlus}
                  customStyle={{ margin: 0, background: 'transparent', fontSize: '13px', padding: 0 }}
                  showLineNumbers={true}
                >
                  {fileContent}
                </SyntaxHighlighter>
              )}
            </div>
          </div>
        ) : (
          <div className="empty-file-state">
            <Terminal size={48} className="empty-icon" />
            <p>Select a file from the sidebar to view its code.</p>
          </div>
        )}
      </div>
    </div>
  );
}
