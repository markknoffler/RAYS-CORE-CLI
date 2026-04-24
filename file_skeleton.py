"""
File Skeleton Generator - Extracts file structure for LLM-based anchoring.

Provides:
1. File skeleton: imports + class/function signatures with line numbers
2. Directory tree: folder structure with file descriptions
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Optional
import msgpack


class FileSkeletonGenerator:
    """Generate file skeletons for LLM anchoring context."""
    
    def __init__(self, codebase_root: Path, rays_dir: Path):
        self.codebase_root = Path(codebase_root)
        self.rays_dir = Path(rays_dir)
    
    def get_file_skeleton(self, file_path: str, include_docstrings: bool = True) -> str:
        """
        Extract a file skeleton showing structure with line numbers.
        
        Returns format like:
        ```
        # File: src/auth/session.py
        # Total lines: 145
        
        # === IMPORTS (lines 1-8) ===
        1| import jwt
        2| from datetime import datetime, timedelta
        3| from typing import Optional, Dict
        4| 
        5| from models.user import User
        6| from config import SECRET_KEY
        7| 
        8| 
        
        # === SYMBOLS ===
        
        # class SessionManager (lines 9-85)
        9| class SessionManager:
        10|     \"\"\"Manages user sessions with Redis backend.\"\"\"
        11|     
        12|     def __init__(self, redis_client):  # lines 12-18
        ...
        19|     def create_session(self, user: User, remember: bool = False) -> str:  # lines 19-45
        ...
        46|     def validate_session(self, token: str) -> Optional[User]:  # lines 46-72
        ...
        73|     def revoke_session(self, token: str) -> bool:  # lines 73-85
        ...
        
        # function generate_token (lines 87-102)
        87| def generate_token(payload: Dict, expires_in: int = 3600) -> str:
        88|     \"\"\"Generate a JWT token.\"\"\"
        ...
        
        # END OF FILE (line 145)
        # 
        # SUGGESTED INSERTION POINTS:
        # - After imports (line 9): For new top-level classes
        # - End of SessionManager (line 86): For new methods in SessionManager
        # - End of file (line 146): For new top-level functions
        ```
        """
        full_path = self.codebase_root / file_path
        
        if not full_path.exists():
            return f"# File not found: {file_path}"
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
                lines = source.split('\n')
            
            tree = ast.parse(source)
            total_lines = len(lines)
            
            skeleton = []
            skeleton.append(f"# File: {file_path}")
            skeleton.append(f"# Total lines: {total_lines}")
            skeleton.append("")
            
            # Extract imports section
            import_end = 0
            skeleton.append("# === IMPORTS ===")
            
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                    import_end = max(import_end, end_line)
            
            # Show import lines
            if import_end > 0:
                skeleton.append(f"# (lines 1-{import_end})")
                for i in range(min(import_end, len(lines))):
                    skeleton.append(f"{i+1:4d}| {lines[i]}")
                skeleton.append("")
            else:
                skeleton.append("# (no imports)")
                skeleton.append("")
            
            # Extract class and function definitions
            skeleton.append("# === SYMBOLS ===")
            skeleton.append("")
            
            insertion_points = []
            insertion_points.append(f"After imports (line {import_end + 1}): For new top-level classes/functions")
            
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    class_skeleton = self._extract_class_skeleton(node, lines, include_docstrings)
                    skeleton.extend(class_skeleton)
                    skeleton.append("")
                    
                    # Add insertion point for end of class
                    class_end = node.end_lineno if hasattr(node, 'end_lineno') else node.lineno
                    insertion_points.append(f"Inside class {node.name} (line {class_end}): For new methods")
                
                elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    func_skeleton = self._extract_function_skeleton(node, lines, include_docstrings, indent=0)
                    skeleton.extend(func_skeleton)
                    skeleton.append("")
            
            # End of file marker
            skeleton.append(f"# END OF FILE (line {total_lines})")
            skeleton.append("")
            
            # Suggested insertion points
            insertion_points.append(f"End of file (line {total_lines + 1}): For new top-level functions/classes")
            
            skeleton.append("# SUGGESTED INSERTION POINTS:")
            for point in insertion_points:
                skeleton.append(f"# - {point}")
            
            return '\n'.join(skeleton)
            
        except SyntaxError as e:
            return f"# Syntax error parsing {file_path}: {e}"
        except Exception as e:
            return f"# Error extracting skeleton from {file_path}: {e}"
    
    def _extract_class_skeleton(self, node: ast.ClassDef, lines: List[str], 
                                include_docstrings: bool) -> List[str]:
        """Extract class skeleton with method signatures."""
        skeleton = []
        
        start_line = node.lineno
        end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
        
        skeleton.append(f"# class {node.name} (lines {start_line}-{end_line})")
        
        # Class definition line
        skeleton.append(f"{start_line:4d}| {lines[start_line - 1]}")
        
        # Docstring if present
        if include_docstrings and node.body and isinstance(node.body[0], ast.Expr):
            if isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                doc_line = node.body[0].lineno
                skeleton.append(f"{doc_line:4d}| {lines[doc_line - 1]}")
        
        skeleton.append("    ...")
        
        # Method signatures
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_skeleton = self._extract_function_skeleton(item, lines, include_docstrings, indent=4)
                skeleton.extend(method_skeleton)
        
        return skeleton
    
    def _extract_function_skeleton(self, node, lines: List[str], 
                                   include_docstrings: bool, indent: int) -> List[str]:
        """Extract function/method skeleton."""
        skeleton = []
        
        start_line = node.lineno
        end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
        
        prefix = " " * indent
        func_type = "method" if indent > 0 else "function"
        
        skeleton.append(f"{prefix}# {func_type} {node.name} (lines {start_line}-{end_line})")
        skeleton.append(f"{start_line:4d}| {lines[start_line - 1]}")
        
        # Docstring if present
        if include_docstrings and node.body and isinstance(node.body[0], ast.Expr):
            if isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                doc_line = node.body[0].lineno
                if doc_line != start_line:
                    skeleton.append(f"{doc_line:4d}| {lines[doc_line - 1]}")
        
        skeleton.append(f"{prefix}    ...")
        
        return skeleton
    
    def get_directory_tree(self, max_depth: int = 4, include_symbols: bool = True) -> str:
        """
        Generate directory tree structure with file descriptions.
        
        Returns format like:
        ```
        # Codebase Structure: /path/to/codebase
        #
        # src/
        # ├── auth/
        # │   ├── __init__.py
        # │   ├── session.py (SessionManager, create_session, validate_session)
        # │   ├── jwt_handler.py (JWTHandler, encode, decode, verify)
        # │   └── middleware.py (AuthMiddleware, require_auth)
        # ├── models/
        # │   ├── __init__.py
        # │   ├── user.py (User, UserProfile, UserSettings)
        # │   └── base.py (BaseModel, TimestampMixin)
        # ├── api/
        # │   ├── routes/
        # │   │   ├── auth.py (login_route, logout_route, register_route)
        # │   │   └── users.py (get_user, update_user, delete_user)
        # │   └── server.py (create_app, configure_routes)
        # └── utils/
        #     ├── helpers.py (format_date, hash_password, generate_id)
        #     └── validators.py (validate_email, validate_password)
        ```
        """
        # Load symbols if available
        symbols_by_file = {}
        if include_symbols:
            symbols_file = self.rays_dir / "symbols.msgpack"
            if symbols_file.exists():
                try:
                    with open(symbols_file, 'rb') as f:
                        symbols = msgpack.unpackb(f.read(), raw=False)
                    
                    for sym in symbols:
                        file_path = sym.get('file_path', '')
                        sym_name = sym.get('symbol_name', '')
                        sym_type = sym.get('symbol_type', '')
                        
                        if file_path not in symbols_by_file:
                            symbols_by_file[file_path] = []
                        
                        # Only include top-level symbols (no parent)
                        if not sym.get('parent_symbol'):
                            symbols_by_file[file_path].append(sym_name)
                except Exception as e:
                    print(f"Warning: Could not load symbols: {e}")
        
        tree_lines = []
        tree_lines.append(f"# Codebase Structure: {self.codebase_root}")
        tree_lines.append("#")
        
        def build_tree(path: Path, prefix: str = "# ", depth: int = 0):
            if depth > max_depth:
                return
            
            try:
                entries = sorted(path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
            except PermissionError:
                return
            
            # Filter out hidden files/dirs and common ignores
            entries = [e for e in entries if not e.name.startswith('.') 
                      and e.name not in ['__pycache__', 'node_modules', 'venv', '.git', '.rays']]
            
            for i, entry in enumerate(entries):
                is_last = (i == len(entries) - 1)
                connector = "└── " if is_last else "├── "
                
                if entry.is_dir():
                    tree_lines.append(f"{prefix}{connector}{entry.name}/")
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    build_tree(entry, next_prefix, depth + 1)
                else:
                    # Get symbols for this file
                    rel_path = str(entry.relative_to(self.codebase_root))
                    file_symbols = symbols_by_file.get(rel_path, [])
                    
                    if file_symbols:
                        symbols_str = ", ".join(file_symbols[:5])
                        if len(file_symbols) > 5:
                            symbols_str += f", ... (+{len(file_symbols) - 5})"
                        tree_lines.append(f"{prefix}{connector}{entry.name} ({symbols_str})")
                    else:
                        tree_lines.append(f"{prefix}{connector}{entry.name}")
        
        build_tree(self.codebase_root)
        
        return '\n'.join(tree_lines)
    
    def get_file_list_with_purposes(self) -> str:
        """
        Get a simple list of files with their primary symbols.
        Useful for LLM to understand what each file contains.
        """
        # Load symbols
        symbols_file = self.rays_dir / "symbols.msgpack"
        if not symbols_file.exists():
            return "# No symbols.msgpack found"
        
        try:
            with open(symbols_file, 'rb') as f:
                symbols = msgpack.unpackb(f.read(), raw=False)
        except Exception as e:
            return f"# Error loading symbols: {e}"
        
        # Group symbols by file
        files_info = {}
        for sym in symbols:
            file_path = sym.get('file_path', '')
            if not file_path:
                continue
            
            if file_path not in files_info:
                files_info[file_path] = {
                    'classes': [],
                    'functions': [],
                    'other': []
                }
            
            sym_name = sym.get('symbol_name', '')
            sym_type = sym.get('symbol_type', '')
            parent = sym.get('parent_symbol', '')
            
            # Only top-level symbols
            if not parent:
                if sym_type == 'class':
                    files_info[file_path]['classes'].append(sym_name)
                elif sym_type in ['function', 'method']:
                    files_info[file_path]['functions'].append(sym_name)
                else:
                    files_info[file_path]['other'].append(sym_name)
        
        # Format output
        output = ["# File List with Contents:"]
        output.append("#")
        
        for file_path in sorted(files_info.keys()):
            info = files_info[file_path]
            parts = []
            
            if info['classes']:
                parts.append(f"classes: {', '.join(info['classes'][:3])}")
            if info['functions']:
                parts.append(f"functions: {', '.join(info['functions'][:3])}")
            
            if parts:
                output.append(f"# {file_path}")
                output.append(f"#   {'; '.join(parts)}")
            else:
                output.append(f"# {file_path}")
        
        return '\n'.join(output)


def test_skeleton():
    """Test the skeleton generator."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python file_skeleton.py <codebase_path> [file_path]")
        return
    
    codebase = Path(sys.argv[1])
    rays_dir = codebase / ".rays"
    
    gen = FileSkeletonGenerator(codebase, rays_dir)
    
    if len(sys.argv) > 2:
        # Show specific file skeleton
        file_path = sys.argv[2]
        print(gen.get_file_skeleton(file_path))
    else:
        # Show directory tree
        print(gen.get_directory_tree())


if __name__ == "__main__":
    test_skeleton()
