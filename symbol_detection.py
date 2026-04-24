import msgpack
import chromadb
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set, Any
from ai_client import AIClient
import rays_ui

class SymbolDetector:
    def __init__(self, rays_dir: Path, ai_client: AIClient, config: dict, codebase_root: Path = None):
        self.rays_dir = rays_dir
        self.codebase_root = codebase_root or rays_dir.parent
        self.ai_client = ai_client
        self.config = config
        self._all_symbols_cache = None

    def _get_all_symbols(self) -> list:
        """Lazy load all symbols from msgpack"""
        if self._all_symbols_cache is not None:
            return self._all_symbols_cache
            
        symbols_file = self.rays_dir / "symbols.msgpack"
        if not symbols_file.exists():
            return []
            
        with open(symbols_file, 'rb') as f:
            self._all_symbols_cache = msgpack.unpackb(f.read(), raw=False)
        return self._all_symbols_cache

    def _get_symbols_in_file(self, file_path: str) -> list:
        """Get all symbols belonging to a specific file"""
        all_syms = self._get_all_symbols()
        # Handle both exact and partial matches if needed, but preference is for exact
        matches = [s for s in all_syms if s.get('file_path') == file_path]
        if not matches:
            # Try partial match if no exact match
            matches = [s for s in all_syms if file_path in s.get('file_path', '')]
        
        # UI: If we are in symbols detection phase, show the file being scanned
        if matches:
            pass # We'll show the tree in detect_affected_symbols
        return matches

    def _get_symbol_at_line(self, file_path: str, line_num: int) -> Optional[dict]:
        """Find the symbol (function/class) that contains a specific line number"""
        file_symbols = self._get_symbols_in_file(file_path)
        for sym in file_symbols:
            start = sym.get('start_line', 0)
            end = sym.get('end_line', 0)
            if start <= line_num <= end:
                return sym
        return None

    def _get_symbols_by_name(self, name: str, file_hint: str = None) -> list:
        """Find symbols by name, optionally filtered by file"""
        all_syms = self._get_all_symbols()
        matches = [s for s in all_syms if s.get('symbol_name') == name]
        if file_hint:
            matches = [s for s in matches if file_hint in s.get('file_path', '')]
        return matches

    def extract_symbol_types_from_codebase(self) -> set:
        """
        Extract all unique symbol types from .rays/symbols.msgpack
        
        Returns:
            Set of symbol types found in the codebase
        """
        
        symbols_file = self.rays_dir / "symbols.msgpack"
        if not symbols_file.exists():
            return set()
        
        with open(symbols_file, 'rb') as f:
            symbols = msgpack.unpackb(f.read(), raw=False)
        
        # Extract unique symbol types
        symbol_types = set()
        for symbol in symbols:
            sym_type = symbol.get('symbol_type', 'unknown')
            symbol_types.add(sym_type)
        
        return symbol_types

    def map_keywords_to_symbol_types(self, user_prompt: str, keywords: list, 
                                    available_symbol_types: set) -> dict:
        """
        Use AI to map each keyword to possible symbol types from the codebase.
        
        Args:
            user_prompt: Original user prompt
            keywords: Extracted keywords
            available_symbol_types: Symbol types available in the codebase
        
        Returns:
            Dict mapping keyword -> list of possible symbol types
        """
        
        prompt_template = self.config['symbol_detection_prompts']['keyword_to_symbol_type_mapping']
        prompt = prompt_template.format(
            user_prompt=user_prompt,
            keywords=keywords,
            available_symbol_types=sorted(available_symbol_types)
        )
        
        system_prompt = self.config['task_analysis_prompts']['system_instructions']
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            keyword_mapping = result.get('keyword_to_types', {})
            return keyword_mapping
        except Exception as e:
            # Fallback: assign all types to all keywords
            return {kw: list(available_symbol_types) for kw in keywords}

    def query_vector_database(self, keywords: list, symbol_names: list, top_k: int = 100) -> list:
        """
        Query ChromaDB with keywords to get candidate symbols.
        
        Args:
            keywords: Keywords to search for
            symbol_names: Explicit symbol names
            top_k: Number of results to retrieve
        
        Returns:
            List of symbol metadata dicts
        """
        
        chroma_path = str(self.rays_dir / "chroma_db")
        client = chromadb.PersistentClient(path=chroma_path)
        collection = client.get_collection("code_chunks")
        
        # Create search query from keywords and symbol names
        search_query = " ".join(keywords + symbol_names)
        
        # Get embedding for query using embedding client
        from ai_client import AIClient
        embedding_cfg = self.config.get('embedding', {})
        embedding_provider = embedding_cfg.get('provider', self.config['llm']['provider'])
        embedding_endpoint = embedding_cfg.get('ollama_endpoint', self.config['llm'].get('ollama_endpoint', 'http://localhost:11434/api/generate'))
        embedding_api_key = embedding_cfg.get('api_key', self.config['llm'].get('api_key', ''))
        embedding_client = AIClient({
            'provider': embedding_provider,
            'model': self.config['embedding']['model'],
            'base_url': embedding_endpoint.replace('/api/generate', '').replace('/api/embeddings', '').replace('/api', ''),
            'api_key': embedding_api_key,
            'delay': 0.05
        })
        
        try:
            query_embedding = embedding_client.get_embedding(search_query)
            if not query_embedding:
                return []
            
            # Search vector DB
            search_results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k
            )
            
            # Extract metadata
            candidate_symbols = []
            if search_results['metadatas'] and search_results['metadatas'][0]:
                candidate_symbols = search_results['metadatas'][0]
            
            return candidate_symbols
        except Exception as e:
            return []
    
    def filter_symbols_by_type(self, candidate_symbols: list, 
                               keyword_mapping: dict) -> list:
        """
        Filter candidate symbols by matching their types with keyword mappings.
        Filter candidate symbols by matching their types with keyword mappings.
        
        Args:
            candidate_symbols: Symbols from vector DB
            keyword_mapping: Keyword -> types mapping
        
        Returns:
            Filtered list of relevant symbols
        """
        
        # Collect all allowed types
        allowed_types = set()
        for types_list in keyword_mapping.values():
            allowed_types.update(types_list)
        
        
        # Filter symbols
        filtered_symbols = []
        for symbol in candidate_symbols:
            symbol_type = symbol.get('symbol_type', 'unknown')
            if symbol_type in allowed_types:
                filtered_symbols.append(symbol)
        
        return filtered_symbols

    def extract_explicit_mentions(self, user_prompt: str) -> dict:
        """
        Extract explicit mentions of files, symbols, lines from user prompt.
        
        Args:
            user_prompt: User's request
        
        Returns:
            Organized JSON with explicit mentions
        """
        
        prompt_template = self.config['symbol_detection_prompts']['explicit_mentions_extraction']
        prompt = prompt_template.format(user_prompt=user_prompt)
        
        system_prompt = self.config['task_analysis_prompts']['system_instructions']
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            
            
            return result
        except Exception as e:
            return {
                'explicit_line_edits': [],
                'explicit_symbol_edits': [],
                'explicit_file_edits': [],
                'new_creations': [],
                'implicit_request': {
                    'is_implicit': True,
                    'intent': user_prompt
                }
            }
    
    def detect_affected_symbols(self, user_prompt: str, analysis: dict, memory_symbols: List[Dict[str, Any]] = []) -> dict:
        """
        Step 4: Symbol Detection - Find symbols affected by user's request.
        
        Args:
            user_prompt: User's request
            analysis: Task analysis results
            memory_symbols: Symbols retrieved and filtered from memory
        """
        
        # Extract symbol types from .rays/symbols.msgpack
        available_symbol_types = self.extract_symbol_types_from_codebase()
        
        # Map keywords to possible symbol types using AI
        keyword_mapping = self.map_keywords_to_symbol_types(
            user_prompt,
            analysis['keywords'],
            available_symbol_types
        )
        
        # Query vector database with keywords (get 100+ candidates)
        candidate_symbols = self.query_vector_database(
            analysis['keywords'],
            analysis['symbol_names'],
            top_k=100
        )
        
        # Filter candidates by symbol types
        filtered_symbols = self.filter_symbols_by_type(
            candidate_symbols,
            keyword_mapping
        )

        # Merge in memory symbols (mark them as from_memory)
        for ms in memory_symbols:
            # Check if already present
            exists = False
            for fs in filtered_symbols:
                if fs.get('symbol_name') == ms.get('name') and fs.get('file_path') == ms.get('file_path'):
                    fs['from_memory'] = True
                    fs['relevance_explanation'] = ms.get('relevance_explanation')
                    exists = True
                    break
            if not exists:
                filtered_symbols.append({
                    'symbol_name': ms.get('name'),
                    'file_path': ms.get('file_path'),
                    'from_memory': True,
                    'relevance_explanation': ms.get('relevance_explanation'),
                    'symbol_type': ms.get('symbol_type', 'unknown') # Type might be missing in summary
                })
        
        # Extract explicit mentions from prompt
        explicit_mentions = self.extract_explicit_mentions(user_prompt)
        
        # UI Feedback for symbol detection
        rays_ui.print_phase("Scanning Codebase")
        
        all_files = sorted(list(set(s.get('file_path') for s in candidate_symbols if s.get('file_path'))))
        selected_files = sorted(list(set(s.get('file_path') for s in filtered_symbols if s.get('file_path'))))
        
        # Show animated file tree of candidate area
        rays_ui.print_file_tree(all_files, selected_files, "Locating relevant symbols")
        
        # Combine results
        result = {
            'available_symbol_types': sorted(available_symbol_types),
            'keyword_to_types_mapping': keyword_mapping,
            'candidate_symbols_count': len(candidate_symbols),
            'filtered_symbols_count': len(filtered_symbols),
            'affected_symbols': filtered_symbols,
            'explicit_mentions': explicit_mentions
        }
        
        explicit_count = (len(explicit_mentions.get('explicit_line_edits', [])) + 
                         len(explicit_mentions.get('explicit_symbol_edits', [])) +
                         len(explicit_mentions.get('explicit_file_edits', [])))
        
        return result

    def retrieve_code_chunks(self, filtered_symbols: list) -> list:
        """
        Retrieve actual code content for filtered symbols from ChromaDB.
        
        Args:
            filtered_symbols: List of symbol metadata from vector DB
        
        Returns:
            List of symbols with full code content
        """
        
        chroma_path = str(self.rays_dir / "chroma_db")
        client = chromadb.PersistentClient(path=chroma_path)
        collection = client.get_collection("code_chunks")
        
        symbols_with_code = []
        
        for symbol in filtered_symbols:
            chunk_id = symbol.get('chunk_id')
            if not chunk_id:
                continue
            
            try:
                # Get full chunk data from ChromaDB
                result = collection.get(
                    ids=[chunk_id],
                    include=['metadatas', 'documents']
                )
                
                if result['metadatas'] and result['metadatas'][0]:
                    metadata = result['metadatas'][0]
                    code = result['documents'][0] if result['documents'] else metadata.get('code_content', '')
                    
                    symbols_with_code.append({
                        'chunk_id': chunk_id,
                        'symbol_name': metadata.get('symbol_name', 'unknown'),
                        'symbol_type': symbol.get('symbol_type', 'unknown'),
                        'file_path': metadata.get('file_path', ''),
                        'start_line': metadata.get('start_line', 0),
                        'end_line': metadata.get('end_line', 0),
                        'code': code,
                        'context_tags': metadata.get('context_tags', ''),
                        'is_explicit': symbol.get('is_explicit', False)
                    })
            except Exception as e:
                continue
        
        return symbols_with_code

    def select_final_affected_symbols(self, user_prompt: str, analysis: dict, 
                                      symbols_with_code: list, explicit_mentions: dict,
                                      memory_summaries: str = "") -> dict:
        """
        Step 5: Use AI to select final list of symbols that will actually be affected.
        Step 5: Use AI to select final list of symbols that will actually be affected.
        
        Args:
            user_prompt: User's request
            analysis: Task analysis results
            symbols_with_code: Symbols with full code content
            explicit_mentions: Explicit mentions from user
            memory_summaries: Textual summaries of relevant memories
        
        Returns:
            Dict with final affected symbols and analysis
        """
        
        # Format explicit mentions summary
        explicit_summary = "None"
        if explicit_mentions.get('explicit_line_edits') or \
        explicit_mentions.get('explicit_symbol_edits') or \
        explicit_mentions.get('explicit_file_edits'):
            parts = []
            if explicit_mentions.get('explicit_line_edits'):
                parts.append(f"Line edits: {len(explicit_mentions['explicit_line_edits'])}")
            if explicit_mentions.get('explicit_symbol_edits'):
                parts.append(f"Symbol edits: {len(explicit_mentions['explicit_symbol_edits'])}")
            if explicit_mentions.get('explicit_file_edits'):
                parts.append(f"File edits: {len(explicit_mentions['explicit_file_edits'])}")
            explicit_summary = ", ".join(parts)
        
        # Format ALL symbols with FULL code for prompt
        symbols_text = ""
        for idx, symbol in enumerate(symbols_with_code, 1):
            symbols_text += f"\n--- Symbol {idx} ---\n"
            symbols_text += f"Name: {symbol['symbol_name']}\n"
            symbols_text += f"Type: {symbol['symbol_type']}\n"
            symbols_text += f"File: {symbol['file_path']} (lines {symbol['start_line']}-{symbol['end_line']})\n"
            symbols_text += f"Chunk ID: {symbol['chunk_id']}\n"
            if symbol.get('context_tags'):
                symbols_text += f"Context: {symbol['context_tags']}\n"
            if symbol.get('relevance_explanation'):
                symbols_text += f"Memory Relevance: {symbol['relevance_explanation']}\n"
            symbols_text += f"Code:\n```\n{symbol['code']}\n```\n"
        
        # Build prompt
        prompt_template = self.config['final_symbol_selection_prompts']['analyze_and_select_symbols']
        prompt = prompt_template.format(
            user_prompt=user_prompt,
            task_type=analysis.get('task_type', 'unknown'),
            sds_score=analysis.get('sds_score', 0.0),
            ies_score=analysis.get('ies_score', 0.0),
            keywords=", ".join(analysis.get('keywords', [])),
            explicit_mentions_summary=explicit_summary,
            memory_context=memory_summaries,
            num_symbols=len(symbols_with_code),
            symbols_with_code=symbols_text
        )
        
        system_prompt = self.config['task_analysis_prompts']['system_instructions']
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            
            affected = result.get('affected_symbols', [])
            unrelated = result.get('unrelated_symbols', [])
            summary = result.get('analysis_summary', '')
            
            
            return {
                'affected_symbols': affected,
                'unrelated_symbols': unrelated,
                'analysis_summary': summary,
                'total_candidates': len(symbols_with_code)
            }
        except Exception as e:
            # Fallback: return all symbols
            return {
                'affected_symbols': [
                    {
                        'symbol_name': s['symbol_name'],
                        'file_path': s['file_path'],
                        'chunk_id': s['chunk_id'],
                        'reason': 'Fallback - AI selection failed',
                        'change_type': 'modify',
                        'priority': 'medium'
                    }
                    for s in symbols_with_code
                ],
                'unrelated_symbols': [],
                'analysis_summary': 'AI selection failed, returning all candidates',
                'total_candidates': len(symbols_with_code)
            }

    def finalize_symbol_selection(self, user_prompt: str, analysis: dict, 
                                  symbol_detection: dict, memory_summaries: str = "") -> dict:
        """
        Step 5: Retrieve code and finalize symbol selection using AI.
        Step 5: Retrieve code and finalize symbol selection using AI.
        
        Args:
            user_prompt: User's request
            analysis: Task analysis results
            symbol_detection: Symbol detection results
            memory_summaries: Text summarized memories for the prompt
        
        Returns:
            Dict with final symbol selection
        """
        
        explicit = symbol_detection.get('explicit_mentions', {})
        resolved_explicit_symbols = []
        
        # 1. Resolve explicit file mentions -> get all symbols in that file
        for file_edit in explicit.get('explicit_file_edits', []):
            file_path = file_edit.get('file')
            if file_path:
                file_syms = self._get_symbols_in_file(file_path)
                for s in file_syms:
                    s['is_explicit'] = True
                    resolved_explicit_symbols.append(s)
        
        # 2. Resolve explicit symbol mentions
        for sym_edit in explicit.get('explicit_symbol_edits', []):
            name = sym_edit.get('symbol_name')
            file_hint = sym_edit.get('file')
            if name:
                found = self._get_symbols_by_name(name, file_hint)
                for s in found:
                    s['is_explicit'] = True
                    resolved_explicit_symbols.append(s)
                    
        # 3. Resolve explicit line mentions -> get symbol at that line
        for line_edit in explicit.get('explicit_line_edits', []):
            file_path = line_edit.get('file')
            line_num = line_edit.get('line')
            if file_path and line_num:
                sym = self._get_symbol_at_line(file_path, line_num)
                if sym:
                    sym['is_explicit'] = True
                    resolved_explicit_symbols.append(sym)

        # Merge with detected symbols (avoid duplicates)
        detected_symbols = symbol_detection.get('affected_symbols', [])
        all_candidate_symbols = list(detected_symbols)
        
        # Mapping for easy duplicate check
        existing_ids = { (s.get('file_path'), s.get('symbol_name'), s.get('start_line')) for s in all_candidate_symbols }
        
        for exp_sym in resolved_explicit_symbols:
            key = (exp_sym.get('file_path'), exp_sym.get('symbol_name'), exp_sym.get('start_line'))
            if key not in existing_ids:
                all_candidate_symbols.append(exp_sym)
                existing_ids.add(key)
            else:
                # Update existing one to be explicit
                for s in all_candidate_symbols:
                    if (s.get('file_path'), s.get('symbol_name'), s.get('start_line')) == key:
                        s['is_explicit'] = True

        # Retrieve code chunks for ALL candidates (detected + resolved explicit)
        symbols_with_code = self.retrieve_code_chunks(all_candidate_symbols)
        
        # Use AI to select final affected symbols
        final_selection = self.select_final_affected_symbols(
            user_prompt,
            analysis,
            symbols_with_code,
            explicit,
            memory_summaries
        )
        
        # Force inclusion of explicit symbols if they weren't selected by AI
        # (AI might filter them out if it thinks they're irrelevant, but we want a dump)
        current_affected_names = { (s['symbol_name'], s['file_path']) for s in final_selection['affected_symbols'] }
        
        for code_sym in symbols_with_code:
            if code_sym.get('is_explicit'):
                key = (code_sym['symbol_name'], code_sym['file_path'])
                if key not in current_affected_names:
                    final_selection['affected_symbols'].append({
                        'symbol_name': code_sym['symbol_name'],
                        'file_path': code_sym['file_path'],
                        'chunk_id': code_sym.get('chunk_id'),
                        'reason': 'Explicitly mentioned by user',
                        'change_type': 'modify',
                        'priority': 'high',
                        'is_explicit': True
                    })
        
        
        return final_selection

    # ═══════════════════════════════════════════════════════════════════
    #                  V16: DEEP SCAN PIPELINE BRANCH
    # ═══════════════════════════════════════════════════════════════════

    def _classify_prompt_openness(self, user_prompt: str, explicit_mentions: dict) -> bool:
        """
        Determine if the user prompt is "open-ended" (no specific targets).
        Returns True if open-ended, False if specific.
        """
        # Check if explicit mentions are all empty
        has_explicit = (
            bool(explicit_mentions.get('explicit_line_edits')) or
            bool(explicit_mentions.get('explicit_symbol_edits')) or
            bool(explicit_mentions.get('explicit_file_edits'))
        )
        if has_explicit:
            return False

        # Check for open-ended keywords in prompt
        open_ended_keywords = [
            'find', 'search', 'explain', 'bug', 'review', 'audit',
            'check', 'analyze', 'look for', 'investigate', 'scan',
            'debug', 'inspect', 'tell me', 'show me', 'what are',
            'are there', 'is there', 'any issues', 'any bugs',
            'any problems', 'possible bugs', 'possible issues'
        ]
        prompt_lower = user_prompt.lower()
        for kw in open_ended_keywords:
            if kw in prompt_lower:
                return True

        return False

    def _get_all_codebase_files(self) -> List[str]:
        """Walk codebase and return all relevant file paths (relative)."""
        all_files = []
        for root, dirs, files in os.walk(self.codebase_root):
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in [
                'node_modules', 'venv', '__pycache__', '.rays', 'dist', 'build', '.git'
            ]]
            for f in files:
                if f.startswith('.') or f.endswith((
                    '.pyc', '.msgpack', '.png', '.jpg', '.jpeg', '.gif',
                    '.ico', '.pdf', '.woff', '.woff2', '.ttf', '.eot',
                    '.svg', '.lock', '.map'
                )):
                    continue
                rel_path = os.path.relpath(os.path.join(root, f), self.codebase_root)
                all_files.append(rel_path)
        return sorted(all_files)

    def _skeleton_batch_scan(self, user_prompt: str, analysis: dict,
                              all_files: List[str]) -> List[Dict[str, Any]]:
        """
        Path A: Skeleton-based batch scan (15 files/batch).
        For specific prompts with targeted intent.
        """
        from file_skeleton import FileSkeletonGenerator
        skeleton_gen = FileSkeletonGenerator(self.codebase_root, self.rays_dir)

        batch_size = 15
        candidates = []
        system_prompt = self.config['task_analysis_prompts']['system_instructions']

        with rays_ui.cool_thinking(
            title="Deep Scan (Architecture)",
            sub_messages=[
                "Scanning file structures...",
                "Mapping symbol signatures...",
                "Tracing import chains...",
                "Analyzing function boundaries...",
                "Detecting cross-module links..."
            ]
        ) as spinner:
            for i in range(0, len(all_files), batch_size):
                batch = all_files[i:i + batch_size]
                batch_num = i // batch_size + 1

                # Generate skeletons
                file_skeletons = ""
                for fp in batch:
                    file_skeletons += f"\n{'='*60}\n"
                    file_skeletons += f"FILE: {fp}\n"
                    file_skeletons += f"{'='*60}\n"
                    file_skeletons += skeleton_gen.get_file_skeleton(fp, include_docstrings=False)
                    file_skeletons += "\n"

                # Build prompt
                prompt_template = self.config['deep_scan_prompts']['skeleton_batch_scan']
                prompt = prompt_template.format(
                    user_prompt=user_prompt,
                    task_type=analysis.get('task_type', 'unknown'),
                    keywords=", ".join(analysis.get('keywords', [])),
                    num_files=len(batch),
                    file_skeletons=file_skeletons
                )

                try:
                    rays_ui.log_model_interaction(
                        "Deep Scan",
                        f"Skeleton batch {batch_num} ({len(batch)} files)"
                    )
                    if spinner:
                        spinner.set_sub_message(f"Batch {batch_num}: {len(batch)} files")
                    result = self.ai_client.generate_json(prompt, system_prompt)
                    batch_affected = result.get('affected_symbols', [])
                    if batch_affected:
                        candidates.extend(batch_affected)
                        rays_ui.log_model_interaction(
                            "Deep Scan Result",
                            f"Found {len(batch_affected)} symbols in batch {batch_num}"
                        )
                except Exception as e:
                    rays_ui.log_model_interaction("Deep Scan Error", str(e)[:80])
                    continue

        return candidates

    def _full_code_batch_scan(self, user_prompt: str, analysis: dict,
                               all_files: List[str]) -> List[Dict[str, Any]]:
        """
        Path B: Full-code batch scan (5 files/batch).
        For open-ended prompts (find bugs, review, etc.).
        """
        batch_size = 5
        candidates = []
        system_prompt = self.config['task_analysis_prompts']['system_instructions']

        with rays_ui.cool_thinking(
            title="Deep Scan (Full Analysis)",
            sub_messages=[
                "Reading file contents...",
                "Analyzing code logic...",
                "Checking for issues...",
                "Evaluating symbol behavior...",
                "Cross-referencing patterns..."
            ]
        ) as spinner:
            for i in range(0, len(all_files), batch_size):
                batch = all_files[i:i + batch_size]
                batch_num = i // batch_size + 1

                # Read full file contents
                file_contents = ""
                for fp in batch:
                    full_path = self.codebase_root / fp
                    try:
                        with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                            code = f.read()
                        file_contents += f"\n{'='*60}\n"
                        file_contents += f"FILE: {fp}\n"
                        file_contents += f"{'='*60}\n"
                        file_contents += code
                        file_contents += "\n"
                    except Exception:
                        continue

                if not file_contents.strip():
                    continue

                # Build prompt
                prompt_template = self.config['deep_scan_prompts']['full_code_batch_scan']
                prompt = prompt_template.format(
                    user_prompt=user_prompt,
                    task_type=analysis.get('task_type', 'unknown'),
                    keywords=", ".join(analysis.get('keywords', [])),
                    num_files=len(batch),
                    file_contents=file_contents
                )

                try:
                    rays_ui.log_model_interaction(
                        "Deep Scan (Full)",
                        f"Code batch {batch_num} ({len(batch)} files)"
                    )
                    if spinner:
                        spinner.set_sub_message(f"Batch {batch_num}: reading {len(batch)} files")
                    result = self.ai_client.generate_json(prompt, system_prompt)
                    batch_affected = result.get('affected_symbols', [])
                    if batch_affected:
                        candidates.extend(batch_affected)
                        rays_ui.log_model_interaction(
                            "Deep Scan Result",
                            f"Found {len(batch_affected)} symbols in batch {batch_num}"
                        )
                except Exception as e:
                    rays_ui.log_model_interaction("Deep Scan Error", str(e)[:80])
                    continue

        return candidates

    def _verify_deep_candidates(self, user_prompt: str, analysis: dict,
                                 candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Final verification: resolve candidates to full code and ask model to confirm.
        Returns symbols in the standard pipeline format with chunk_id.
        """
        if not candidates:
            return []

        # Deduplicate candidates first
        unique_candidates = []
        seen = set()
        for c in candidates:
            key = (c.get('symbol_name'), c.get('file_path'))
            if key not in seen and c.get('symbol_name') and c.get('file_path'):
                unique_candidates.append(c)
                seen.add(key)

        # Resolve to full symbol metadata (with chunk_id)
        resolved = []
        for candidate in unique_candidates:
            found = self._get_symbols_by_name(candidate['symbol_name'], candidate.get('file_path'))
            if found:
                sym = found[0]
                sym['reason'] = candidate.get('reason', 'Deep scan match')
                sym['priority'] = candidate.get('priority', 'medium')
                sym['change_type'] = candidate.get('change_type', 'modify')
                resolved.append(sym)

        if not resolved:
            return []

        # Retrieve full code chunks
        symbols_with_code = self.retrieve_code_chunks(resolved)

        if not symbols_with_code:
            return []

        # Format for verification prompt
        symbols_text = ""
        for idx, symbol in enumerate(symbols_with_code, 1):
            symbols_text += f"\n--- Candidate {idx} ---\n"
            symbols_text += f"Name: {symbol['symbol_name']}\n"
            symbols_text += f"Type: {symbol.get('symbol_type', 'unknown')}\n"
            symbols_text += f"File: {symbol['file_path']} (lines {symbol.get('start_line', '?')}-{symbol.get('end_line', '?')})\n"
            symbols_text += f"Chunk ID: {symbol.get('chunk_id', 'N/A')}\n"
            symbols_text += f"Initial Reason: {symbol.get('reason', 'N/A')}\n"
            symbols_text += f"Code:\n```\n{symbol.get('code', 'N/A')}\n```\n"

        # Build verification prompt
        prompt_template = self.config['deep_scan_prompts']['verify_deep_candidates']
        prompt = prompt_template.format(
            user_prompt=user_prompt,
            task_type=analysis.get('task_type', 'unknown'),
            keywords=", ".join(analysis.get('keywords', [])),
            num_symbols=len(symbols_with_code),
            symbols_with_code=symbols_text
        )
        system_prompt = self.config['task_analysis_prompts']['system_instructions']

        try:
            with rays_ui.cool_thinking(
                title="Verifying Deep Scan",
                sub_messages=[
                    "Cross-checking candidates...",
                    "Validating code relevance...",
                    "Confirming affected symbols..."
                ]
            ):
                rays_ui.log_model_interaction(
                    "Verification",
                    f"Verifying {len(symbols_with_code)} candidates with full code"
                )
                result = self.ai_client.generate_json(prompt, system_prompt)

            verified = result.get('verified_symbols', [])

            # Map verified back to full symbol format with code (for downstream)
            verified_full = []
            code_lookup = {(s['symbol_name'], s['file_path']): s for s in symbols_with_code}
            for v in verified:
                key = (v.get('symbol_name'), v.get('file_path'))
                if key in code_lookup:
                    full_sym = code_lookup[key].copy()
                    full_sym['reason'] = v.get('reason', full_sym.get('reason', ''))
                    full_sym['change_type'] = v.get('change_type', 'modify')
                    full_sym['priority'] = v.get('priority', 'medium')
                    full_sym['deep_scan'] = True
                    verified_full.append(full_sym)
                else:
                    # Symbol was verified but we couldn't resolve it — include metadata only
                    verified_full.append({
                        'symbol_name': v.get('symbol_name'),
                        'file_path': v.get('file_path'),
                        'chunk_id': v.get('chunk_id', ''),
                        'reason': v.get('reason', 'Deep scan verified'),
                        'change_type': v.get('change_type', 'modify'),
                        'priority': v.get('priority', 'medium'),
                        'deep_scan': True
                    })

            rays_ui.log_model_interaction(
                "Verification Complete",
                f"{len(verified_full)} of {len(symbols_with_code)} candidates confirmed"
            )
            return verified_full

        except Exception as e:
            rays_ui.log_model_interaction("Verification Error", str(e)[:80])
            # Fallback: return all resolved candidates with their chunk_ids
            for s in symbols_with_code:
                s['deep_scan'] = True
            return symbols_with_code

    def deep_scan_symbols(self, user_prompt: str, analysis: dict,
                          explicit_mentions: dict,
                          final_selection: dict) -> List[Dict[str, Any]]:
        """
        V16 Deep Scan Pipeline Branch.
        Runs AFTER finalize_symbol_selection. Uses RAW user prompt.

        Two conditional paths:
        - Skeleton batch (15 files/batch) for specific prompts
        - Full code batch (5 files/batch) for open-ended prompts

        Returns list of verified symbols in standard pipeline format.
        """
        rays_ui.print_phase("Deep Scan Branch")

        # Classify prompt openness
        is_open_ended = self._classify_prompt_openness(user_prompt, explicit_mentions)

        scan_type = "Full Analysis" if is_open_ended else "Architecture"
        rays_ui.log_model_interaction(
            "Deep Scan",
            f"Mode: {scan_type} | Open-ended: {is_open_ended}"
        )

        # Get all codebase files
        all_files = self._get_all_codebase_files()
        if not all_files:
            rays_ui.log_model_interaction("Deep Scan", "No files found in codebase")
            return []

        rays_ui.log_model_interaction("Deep Scan", f"Scanning {len(all_files)} files")

        # Route to appropriate batch scan
        if is_open_ended:
            candidates = self._full_code_batch_scan(user_prompt, analysis, all_files)
        else:
            candidates = self._skeleton_batch_scan(user_prompt, analysis, all_files)

        if not candidates:
            rays_ui.log_model_interaction("Deep Scan", "No additional symbols found")
            return []

        rays_ui.log_model_interaction(
            "Deep Scan",
            f"Found {len(candidates)} candidates — starting verification"
        )

        # Final verification with full code
        verified = self._verify_deep_candidates(user_prompt, analysis, candidates)

        return verified
