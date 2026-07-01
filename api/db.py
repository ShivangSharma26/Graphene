import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'graphene.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            github_id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            avatar_url TEXT
        )
    ''')
    
    # Recent searches table
    c.execute('''
        CREATE TABLE IF NOT EXISTS recent_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            github_id TEXT NOT NULL,
            repo_url TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (github_id) REFERENCES users (github_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Initialize tables on import
init_db()

def get_or_create_user(github_id: str, username: str, avatar_url: str):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM users WHERE github_id = ?', (github_id,))
    user = c.fetchone()
    
    if not user:
        c.execute('INSERT INTO users (github_id, username, avatar_url) VALUES (?, ?, ?)',
                  (github_id, username, avatar_url))
    else:
        c.execute('UPDATE users SET username = ?, avatar_url = ? WHERE github_id = ?',
                  (username, avatar_url, github_id))
    
    conn.commit()
    conn.close()

def add_recent_search(github_id: str, repo_url: str):
    conn = get_db()
    c = conn.cursor()
    
    # Only keep the last 5 searches, prevent duplicates by deleting old one first
    c.execute('DELETE FROM recent_searches WHERE github_id = ? AND repo_url = ?', (github_id, repo_url))
    
    c.execute('INSERT INTO recent_searches (github_id, repo_url) VALUES (?, ?)', (github_id, repo_url))
    
    # Prune old searches
    c.execute('''
        DELETE FROM recent_searches 
        WHERE github_id = ? AND id NOT IN (
            SELECT id FROM recent_searches WHERE github_id = ? ORDER BY timestamp DESC LIMIT 5
        )
    ''', (github_id, github_id))
    
    conn.commit()
    conn.close()

def get_recent_searches(github_id: str):
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT repo_url FROM recent_searches WHERE github_id = ? ORDER BY timestamp DESC', (github_id,))
    rows = c.fetchall()
    conn.close()
    return [row['repo_url'] for row in rows]
