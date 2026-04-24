"""
File Anchor - Determines WHERE to create new files using LLM-based anchoring.

Flow:
1. Generate directory structure of codebase
2. Call LLM to determine best directory for new file
3. Return full path
"""

import yaml
from pathlib import Path
from collections import defaultdict
import chromadb
from typing import Dict, List, Optional

from ai_client import AIClient
from file_skeleton import FileSkeletonGenerator
import rays_ui


class FileAnchor:
    """Find best directory for new files using LLM."""
    
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
        
        # File skeleton generator for directory tree
        self.skeleton_gen = FileSkeletonGenerator(codebase_root, rays_dir)
    
    def _load_config(self) -> dict:
        """Load config.yaml"""
        config_path = Path("./config.yaml")
        if not config_path.exists():
            config_path = Path(__file__).parent / "config.yaml"
        
        with open(config_path) as f:
            return yaml.safe_load(f)
    
    def find_directory_for_new_file(self, new_file: dict, 
                                    implementation_plan: dict = None) -> dict:
        """
        Find which directory to create a new file in using LLM.
        
        Flow:
        1. If explicit path provided, use it
        2. Generate directory structure
        3. Call LLM to determine best directory
        
        Args:
            new_file: From implementation plan
                {
                    'name': 'jwt_middleware.py',
                    'path': 'suggested/path/',  (optional)
                    'purpose': 'JWT authentication middleware',
                    'structure': '...'
                }
            implementation_plan: Full plan for context
        
        Returns:
            {
                'target_directory': 'src/auth/',
                'full_path': 'src/auth/jwt_middleware.py',
                'related_files': ['session.py', 'validators.py'],
                'confidence': 0.9,
                'reasoning': 'Best fit based on directory structure'
            }
        """
        file_name = new_file['name']
        rays_ui.print_info(f"Anchoring new file: {file_name}")
        
        # Step 1: If explicit path provided, use it
        if new_file.get('path'):
            explicit_path = new_file['path']
            rays_ui.print_step(f"Using explicit path: {explicit_path}")
            return {
                'target_directory': explicit_path,
                'full_path': str(Path(explicit_path) / file_name),
                'related_files': [],
                'confidence': 1.0,
                'reasoning': 'Explicit path from implementation plan'
            }
        
        # Step 2: Generate directory structure
        directory_tree = self.skeleton_gen.get_directory_tree(max_depth=4, include_symbols=True)
        
        # Step 3: Get file purposes for additional context
        file_list = self.skeleton_gen.get_file_list_with_purposes()
        
        # Step 4: Find related symbols using semantic search (for additional hints)
        related_files = self._find_related_files(new_file)
        
        # Step 5: Call LLM to determine best directory
        result = self._llm_find_directory(
            new_file,
            directory_tree,
            file_list,
            related_files,
            implementation_plan
        )
        
        return result
    
    def _find_related_files(self, new_file: dict) -> List[str]:
        """
        Find files related to the new file using semantic search.
        
        IMPORTANT: Uses the same embedding model as chunk_generator.
        """
        query_text = f"{new_file['name']} {new_file.get('purpose', '')} {new_file.get('structure', '')}"
        
        try:
            # Get embedding using the SAME model as chunk_generator
            query_embedding = self.embedding_client.get_embedding(query_text)
            
            if not query_embedding:
                return []
            
            client = chromadb.PersistentClient(path=self.chroma_path)
            collection = client.get_collection("code_chunks")
            
            # Query with embedding (NOT query_texts)
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=20
            )
            
            if not results['metadatas'] or not results['metadatas'][0]:
                return []
            
            # Extract unique file paths
            files = set()
            for metadata in results['metadatas'][0]:
                file_path = metadata.get('file_path', '')
                if file_path:
                    files.add(file_path)
            
            rays_ui.print_info(f"Found {len(files)} related files via semantic search")
            return list(files)
            
        except Exception as e:
            rays_ui.print_warning(f"Semantic search error for related files: {e}")
            return []
    
    def _llm_find_directory(self, new_file: dict, directory_tree: str,
                           file_list: str, related_files: List[str],
                           implementation_plan: dict = None) -> dict:
        """
        Use LLM to determine the best directory for the new file.
        """
        file_name = new_file['name']
        purpose = new_file.get('purpose', '')
        structure = new_file.get('structure', '')
        
        symbols_to_create = new_file.get('symbols_to_create', [])
        symbols_info = ""
        if symbols_to_create:
            symbols_info = "\n".join([
                f"- {s.get('name', 'unknown')} ({s.get('type', 'unknown')}): {s.get('purpose', '')[:50]}"
                for s in symbols_to_create[:5]
            ])
        
        plan_summary = ""
        if implementation_plan:
            plan_summary = implementation_plan.get('plan_summary', '')
        
        related_files_str = "\n".join([f"- {f}" for f in related_files[:10]]) if related_files else "None found"
        
        prompt = f"""You are a code organization expert. Determine where to create a new file in a codebase.

**NEW FILE TO CREATE:**
- Filename: {file_name}
- Purpose: {purpose}
- Structure: {structure}
- Symbols it will contain:
{symbols_info}

**IMPLEMENTATION CONTEXT:**
{plan_summary}

**CODEBASE DIRECTORY STRUCTURE:**
{directory_tree}

**EXISTING FILES (with contents):**
{file_list[:3000]}

**SEMANTICALLY RELATED FILES:**
{related_files_str}

**YOUR TASK:**
Analyze the codebase structure and determine the BEST directory to place this new file.

**RULES:**
1. Follow existing project conventions (e.g., if auth code is in src/auth/, new auth files go there)
2. Group related functionality together
3. Don't create new directories unless absolutely necessary
4. Consider where similar files already exist
5. Return a RELATIVE path from the codebase root

**RESPOND WITH JSON:**
{{
  "target_directory": "<relative path to directory, e.g., 'src/auth/' or 'alphafold/model/'>",
  "full_path": "<complete relative path including filename, e.g., 'src/auth/jwt_middleware.py'>",
  "related_files": ["<list of similar files in that directory>"],
  "confidence": <0.0-1.0>,
  "reasoning": "<why this directory is the best fit>"
}}

IMPORTANT: 
- Use forward slashes (/) for paths
- Directory paths should end with /
- Return paths relative to codebase root
"""
        
        try:
            result = self.ai_client.generate_json(
                prompt,
                "You are an expert code organization specialist. Return valid JSON only."
            )
            
            target_dir = result.get('target_directory', 'src/')
            full_path = result.get('full_path', f"src/{file_name}")
            related = result.get('related_files', [])
            confidence = result.get('confidence', 0.5)
            reasoning = result.get('reasoning', 'LLM-based placement')
            
            if not full_path.endswith(file_name):
                full_path = str(Path(target_dir) / file_name)
            
            rays_ui.print_step(f"Target path: {full_path}")
            
            return {
                'target_directory': target_dir,
                'full_path': full_path,
                'related_files': related,
                'confidence': confidence,
                'reasoning': reasoning
            }
            
        except Exception as e:
            rays_ui.print_warning(f"LLM placement error: {e}, using fallback heuristics")
            return self._fallback_directory(new_file, related_files)
    
    def _fallback_directory(self, new_file: dict, related_files: List[str]) -> dict:
        """
        Fallback: Use heuristics if LLM fails.
        """
        file_name = new_file['name']
        
        # If we have related files, use their most common directory
        if related_files:
            dir_counts = defaultdict(int)
            for f in related_files:
                dir_path = str(Path(f).parent)
                dir_counts[dir_path] += 1
            
            if dir_counts:
                best_dir = max(dir_counts.items(), key=lambda x: x[1])[0]
                return {
                    'target_directory': best_dir + '/',
                    'full_path': str(Path(best_dir) / file_name),
                    'related_files': related_files[:5],
                    'confidence': 0.4,
                    'reasoning': 'Fallback: Most common directory of related files'
                }
        
        # Simple heuristics based on filename
        if 'test' in file_name.lower():
            default_dir = 'tests/'
        elif 'util' in file_name.lower() or 'helper' in file_name.lower():
            default_dir = 'utils/'
        elif 'model' in file_name.lower():
            default_dir = 'models/'
        elif 'middleware' in file_name.lower() or 'auth' in file_name.lower():
            default_dir = 'src/auth/'
        else:
            default_dir = 'src/'
        
        return {
            'target_directory': default_dir,
            'full_path': str(Path(default_dir) / file_name),
            'related_files': [],
            'confidence': 0.2,
            'reasoning': f'Fallback: Heuristic based on filename'
        }
