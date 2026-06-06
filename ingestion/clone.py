import os
import shutil
import tempfile
from git import Repo

def clone_repo(repo_url: str, branch: str = "main", dest_dir: str = None) -> str:
    """
    Clones a git repository into a local directory and filters out noise.
    Returns the path to the cloned repository.
    """
    if not dest_dir:
        # Create a temporary directory for the repo
        dest_dir = tempfile.mkdtemp(prefix="graphene_repo_")
    
    print(f"Cloning {repo_url} (branch: {branch}) into {dest_dir}...")
    try:
        Repo.clone_from(repo_url, dest_dir, branch=branch, depth=1)
    except Exception as e:
        raise Exception(f"Failed to clone repository: {e}")
        
    _filter_noise(dest_dir)
    return dest_dir

def _filter_noise(repo_path: str):
    """
    Removes non-source files (binaries, node_modules, build artifacts, .git).
    """
    ignore_dirs = {'.git', 'node_modules', 'venv', 'env', '__pycache__', 'dist', 'build'}
    ignore_extensions = {'.pyc', '.exe', '.dll', '.so', '.dylib', '.png', '.jpg', '.pdf'}
    
    for root, dirs, files in os.walk(repo_path, topdown=True):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in ignore_extensions:
                os.remove(os.path.join(root, file))
