"""
Symbol Anchor - Determines WHERE to insert new symbols using LLM-based anchoring.

Flow:
1. Use semantic search to find the most relevant file (with proper embeddings)
2. Generate file skeleton for that file
3. Call LLM to determine exact insertion point
4. Return line number and context
"""

import ast
import yaml
from pathlib import Path
from collections import defaultdict
import chromadb
from typing import Dict, List, Optional

from ai_client import AIClient
from file_skeleton import FileSkeletonGenerator
import rays_ui


class SymbolAnchor:
    """Find precise insertion points for new symbols using LLM."""
    
    def __init__(self, codebase_root: Path, rays_dir: Path, config: dict = None, ai_client: AIClient = None):
        self.codebase_root = Path(codebase_root)
        self.rays_dir = Path(rays_dir)
        self.chroma_path = str(rays_dir / "chroma_db")
        
        # Load config if not provided
        if config is None:
            config = self._load_config()
        self.config = config
        
        # Initialize AI client for LLM calls
        if ai_client is None:
            self.ai_client = AIClient({
                'provider': config['llm']['provider'],
                'model': config['llm']['model'],
                'base_url': config['llm']['ollama_endpoint'].replace('/api/generate', '').replace('/api', ''),
                'api_key': config['llm'].get('api_key', ''),
                'delay': 0.1
            })
        else:
            self.ai_client = ai_client
        
        # Initialize embedding client (MUST use same model as chunk_generator)
        self.embedding_client = AIClient({
            'provider': config['llm']['provider'],
            'model': config['embedding']['model'],
            'base_url': config['llm']['ollama_endpoint'].replace('/api/generate', '').replace('/api', ''),
            'api_key': config['llm'].get('api_key', ''),
            'delay': 0.05
        })
        
        # File skeleton generator
        self.skeleton_gen = FileSkeletonGenerator(codebase_root, rays_dir)
    
    def _load_config(self) -> dict:
        """Load config.yaml"""
        config_path = Path("./config.yaml")
        if not config_path.exists():
            config_path = Path(__file__).parent / "config.yaml"
        
        with open(config_path) as f:
            return yaml.safe_load(f)
    
    def resolve_file_path(self, ambiguous_file: str, 
                         previous_edits: List[dict]) -> str:
        """
        Resolve ambiguous file paths using previous edit context.
        """
        if '/' in ambiguous_file and len(ambiguous_file.split('/')) > 2:
            return ambiguous_file
        
        for edit in previous_edits:
            file_path = edit.get('file_path', '')
            if file_path.endswith(ambiguous_file):
                rays_ui.print_step(f"Resolved '{ambiguous_file}' to '{file_path}'")
                return file_path
        
        return ambiguous_file

    def find_insertion_point(self, new_symbol: dict, 
                            previous_edits: List[dict] = None,
                            implementation_plan: dict = None) -> dict:
        """
        Find where to insert a new symbol using LLM-based anchoring.
        
        Flow:
        1. Resolve ambiguous file path from context
        2. Find semantically similar symbols to determine target file
        3. Generate file skeleton for target file
        4. Call LLM to determine exact insertion line
        
        Args:
            new_symbol: From implementation plan
            previous_edits: Previous file edits for path resolution
            implementation_plan: Full plan for context
        
        Returns:
            dict with target_file, insertion_line, context, confidence
        """
        symbol_name = new_symbol['name']
        symbol_type = new_symbol['type']
        
        rays_ui.print_info(f"Anchoring {symbol_type}: {symbol_name}")
        
        # Step 1: Resolve ambiguous file path if provided
        suggested_file = new_symbol.get('file')
        if suggested_file and previous_edits:
            resolved_file = self.resolve_file_path(suggested_file, previous_edits)
            new_symbol['file'] = resolved_file
            suggested_file = resolved_file
        
        # Step 2: Find target file using semantic search
        target_file = self._find_target_file(new_symbol, suggested_file)
        
        if not target_file:
            rays_ui.print_warning(f"Could not determine target file for {symbol_name}, using fallback")
            return self._default_location(new_symbol)
        
        rays_ui.print_step(f"Target file: {target_file}")
        
        # Step 3: Generate file skeleton
        file_skeleton = self.skeleton_gen.get_file_skeleton(target_file)
        
        # Step 4: Call LLM to determine insertion point
        insertion_result = self._llm_find_insertion_point(
            new_symbol,
            target_file,
            file_skeleton,
            implementation_plan
        )
        
        return {
            'target_file': target_file,
            'insertion_line': insertion_result['line'],
            'insertion_type': insertion_result['type'],
            'parent_class': insertion_result.get('parent_class'),
            'context': insertion_result['context'],
            'confidence': insertion_result['confidence'],
            'similar_symbols': []
        }
    
    def _find_target_file(self, new_symbol: dict, suggested_file: str = None) -> Optional[str]:
        """
        Find the best file for inserting the new symbol.
        
        Priority:
        1. Use suggested file if it exists
        2. Use semantic search to find file with similar symbols
        """
        # Check if suggested file exists
        if suggested_file:
            # Try to find the file
            full_path = self.codebase_root / suggested_file
            if full_path.exists():
                return suggested_file
            
            # Try to find by filename
            filename = Path(suggested_file).name
            for path in self.codebase_root.rglob(filename):
                if '.rays' not in str(path) and '__pycache__' not in str(path):
                    return str(path.relative_to(self.codebase_root))
        
        # Use semantic search
        similar_symbols = self._find_similar_symbols(new_symbol)
        
        if not similar_symbols:
            return None
        
        # Group by file and find the best one
        file_counts = defaultdict(int)
        for sym in similar_symbols:
            file_path = sym.get('file_path', '')
            if file_path:
                file_counts[file_path] += 1
        
        if file_counts:
            best_file = max(file_counts.items(), key=lambda x: x[1])[0]
            return best_file
        
        return None
    
    def _find_similar_symbols(self, new_symbol: dict) -> List[dict]:
        """
        Query ChromaDB for semantically similar symbols.
        
        IMPORTANT: Uses the same embedding model as chunk_generator to avoid
        dimension mismatch errors.
        """
        query_text = f"{new_symbol['name']} {new_symbol['type']} {new_symbol.get('purpose', '')}"
        
        try:
            # Get embedding using the SAME model as chunk_generator
            query_embedding = self.embedding_client.get_embedding(query_text)
            
            if not query_embedding:
                rays_ui.print_warning(f"Failed to get embedding for query: {query_text[:50]}...")
                return []
            
            client = chromadb.PersistentClient(path=self.chroma_path)
            collection = client.get_collection("code_chunks")
            
            # Query with embedding (NOT query_texts which uses default embedder)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=15
            )
            
            if not results['metadatas'] or not results['metadatas'][0]:
                return []
            
            similar = []
            for metadata in results['metadatas'][0]:
                similar.append({
                    'symbol_name': metadata.get('symbol_name', ''),
                    'symbol_type': metadata.get('symbol_type', ''),
                    'file_path': metadata.get('file_path', ''),
                    'start_line': metadata.get('start_line', 0),
                    'end_line': metadata.get('end_line', 0),
                    'parent_symbol': metadata.get('parent_symbol')
                })
            
            rays_ui.print_info(f"Found {len(similar)} similar symbols")
            return similar
            
        except Exception as e:
            rays_ui.print_warning(f"Semantic search error: {e}")
            return []
    
    def _llm_find_insertion_point(self, new_symbol: dict, target_file: str,
                                  file_skeleton: str, implementation_plan: dict = None) -> dict:
        """
        Use LLM to determine exact insertion point in the file.
        
        The LLM sees the file skeleton with line numbers and decides
        where to insert the new symbol.
        """
        symbol_name = new_symbol['name']
        symbol_type = new_symbol['type']
        signature = new_symbol.get('signature', '')
        purpose = new_symbol.get('purpose', '')
        
        plan_summary = ""
        if implementation_plan:
            plan_summary = implementation_plan.get('plan_summary', '')
        
        prompt = f"""You are a code placement expert. Determine where to insert a new symbol into a file.

**NEW SYMBOL TO INSERT:**
- Name: {symbol_name}
- Type: {symbol_type}
- Signature: {signature}
- Purpose: {purpose}

**IMPLEMENTATION CONTEXT:**
{plan_summary}

**TARGET FILE SKELETON:**
{file_skeleton}

**YOUR TASK:**
Analyze the file structure and determine the BEST line number to insert this new symbol.

**RULES:**
1. Classes should be inserted after imports, typically after existing classes
2. Functions should be grouped with related functions
3. Methods should be inserted at the end of their parent class
4. Constants should be at the top after imports
5. Maintain logical grouping (auth functions together, helper functions together, etc.)

**RESPOND WITH JSON:**
{{
  "line": <exact line number to insert AT>,
  "type": "<top_level|inside_class|after_imports>",
  "parent_class": "<class name if inserting inside a class, else null>",
  "context": "<brief description of insertion location>",
  "confidence": <0.0-1.0>,
  "reasoning": "<why this location is best>"
}}

IMPORTANT: The line number should be where the NEW code will START.
For example, if inserting after line 45, return line 46.
"""
        
        try:
            result = self.ai_client.generate_json(
                prompt,
                "You are an expert code analyzer. Return valid JSON only."
            )
            
            line = result.get('line', 0)
            insert_type = result.get('type', 'top_level')
            parent_class = result.get('parent_class')
            context = result.get('context', 'end of file')
            confidence = result.get('confidence', 0.5)
            
            rays_ui.print_step(f"Insertion point: line {line} ({insert_type})")
            if parent_class:
                rays_ui.print_info(f"Class context: {parent_class}")
            
            return {
                'line': line,
                'type': insert_type,
                'parent_class': parent_class,
                'context': context,
                'confidence': confidence
            }
            
        except Exception as e:
            rays_ui.print_warning(f"LLM anchoring error: {e}, using AST fallback")
            return self._ast_fallback_insertion(target_file, new_symbol['type'])
    
    def _ast_fallback_insertion(self, file_path: str, symbol_type: str) -> dict:
        """
        Fallback: Use AST to find insertion point if LLM fails.
        """
        full_path = self.codebase_root / file_path
        
        if not full_path.exists():
            return {'line': 0, 'type': 'top_level', 'context': 'end of file', 'confidence': 0.1}
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            # Find last import line
            last_import_line = 0
            last_def_line = 0
            
            for node in tree.body:
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    if hasattr(node, 'end_lineno'):
                        last_import_line = max(last_import_line, node.end_lineno)
                elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                    if hasattr(node, 'end_lineno'):
                        last_def_line = max(last_def_line, node.end_lineno)
            
            # Classes go after imports, functions go at end
            if symbol_type == 'class':
                line = last_import_line + 2 if last_import_line else 1
                return {'line': line, 'type': 'after_imports', 'context': 'after imports', 'confidence': 0.3}
            else:
                line = last_def_line + 2 if last_def_line else last_import_line + 2
                return {'line': line, 'type': 'top_level', 'context': 'end of file', 'confidence': 0.3}
                
        except Exception as e:
            return {'line': 0, 'type': 'top_level', 'context': 'end of file (parse error)', 'confidence': 0.1}
    
    def _default_location(self, new_symbol: dict) -> dict:
        """Fallback location if no similar symbols found."""
        suggested_file = new_symbol.get('file', 'utils/helpers.py')
        
        return {
            'target_file': suggested_file,
            'insertion_line': 0,
            'insertion_type': 'top_level',
            'parent_class': None,
            'context': 'end of file (no similar symbols found)',
            'confidence': 0.1,
            'similar_symbols': []
        }
