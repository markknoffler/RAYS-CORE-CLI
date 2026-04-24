# planning.py
import msgpack
import chromadb
import copy
from pathlib import Path
from ai_client import AIClient
import rays_ui

class Planner:
    def __init__(self, codebase_root: Path, rays_dir: Path, ai_client: AIClient, config: dict):
        self.codebase_root = codebase_root
        self.rays_dir = rays_dir
        self.ai_client = ai_client
        self.config = config    

    def generate_implementation_plan(self, user_prompt: str, analysis: dict,
                                    approved_permissions: dict, symbols_with_code: list,
                                    max_attempts: int = 3) -> dict:
        """
        Generate detailed implementation plan within approved permissions.
        Generate detailed implementation plan within approved permissions.
        
        Args:
            user_prompt: User's request
            analysis: Task analysis
            approved_permissions: Final approved permission slip
            symbols_with_code: Affected symbols with code
            max_attempts: Maximum attempts if plan exceeds permissions
        
        Returns:
            Implementation plan
        """
        
        # Format task summary
        task_summary = (
            f"Type: {analysis.get('task_type', 'unknown')}, "
            f"SDS: {analysis.get('sds_score', 0):.2f}, "
            f"IES: {analysis.get('ies_score', 0):.2f}, "
            f"Keywords: {', '.join(analysis.get('keywords', []))}"
        )
        
        # Format affected symbols with FULL code
        symbols_text = ""
        for idx, symbol in enumerate(symbols_with_code, 1):
            is_explicit = symbol.get('is_explicit', False)
            explicit_label = " [EXPLICITLY REQUESTED BY USER]" if is_explicit else ""
            
            symbols_text += f"\n{'='*50}\n"
            symbols_text += f"Symbol {idx}: {symbol['symbol_name']}{explicit_label}\n"
            symbols_text += f"{'='*50}\n"
            symbols_text += f"Type: {symbol['symbol_type']}\n"
            symbols_text += f"File: {symbol['file_path']}\n"
            symbols_text += f"Lines: {symbol['start_line']}-{symbol['end_line']}\n"
            symbols_text += f"Chunk ID: {symbol['chunk_id']}\n\n"
            
            if is_explicit:
                symbols_text += "!!! IMPORTANT: The user specifically mentioned this symbol/file. It MUST be addressed or used as primary context in your plan. !!!\n\n"
            
            symbols_text += f"Full Code:\n```\n{symbol['code']}\n```\n"
            if symbol.get('context_tags'):
                symbols_text += f"\nContext:\n{symbol['context_tags']}\n"
        
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            
            # Build prompt
            prompt_template = self.config['permission_planning_prompts']['generate_implementation_plan']
            prompt = prompt_template.format(
                user_prompt=user_prompt,
                task_summary=task_summary,
                previous_summaries="None (placeholder)",
                num_symbols_to_edit=approved_permissions['num_symbols_to_edit'],
                num_files_to_edit=approved_permissions['num_files_to_edit'],
                num_files_to_create=approved_permissions['num_files_to_create'],
                num_symbols_to_create=approved_permissions['num_symbols_to_create'],
                max_lines_to_edit=approved_permissions['max_lines_to_edit'],
                affected_symbols_code=symbols_text
            )
            
            system_prompt = self.config['task_analysis_prompts']['system_instructions']
            
            try:
                result = self.ai_client.generate_json(prompt, system_prompt)
                
                # Validate plan
                total_counts = result.get('total_counts', {})
                validation = result.get('validation', {})
                
                
                within_permissions = validation.get('within_permissions', True)
                
                if not within_permissions:
                    violations = validation.get('permission_violations', [])
                    for v in violations:
                        pass
                    if attempt < max_attempts:
                        continue
                    else:
                        pass
                # Success
                
                
                return result
                
            except Exception as e:
                if attempt < max_attempts:
                    continue
                else:
                    return {
                        'plan_summary': 'Error generating plan',
                        'new_files': [],
                        'new_symbols': [],
                        'existing_symbol_edits': [],
                        'files_to_edit': [],
                        'total_counts': {
                            'new_files': 0,
                            'new_symbols': 0,
                            'edited_symbols': 0,
                            'edited_files': 0,
                            'estimated_total_lines_changed': 0
                        },
                        'validation': {
                            'within_permissions': False,
                            'permission_violations': ['Error during generation']
                        }
                    }
        
        # Should not reach here
        return {}

    def predict_blocking_symbols(self, implementation_plan: dict, 
                                 symbols_with_code: list) -> dict:
        """
        Step 9.1: Predict which symbols might block implementation.
        
        Args:
            implementation_plan: Generated implementation plan
            symbols_with_code: Affected symbols with code
        
        Returns:
            Predicted blocking symbols
        """
        
        # Format implementation plan summary
        plan_summary = implementation_plan.get('plan_summary', '')
        
        # Format planned edits - INCLUDING NEW FILES
        planned_edits = ""
        
        # New files
        for new_file in implementation_plan.get('new_files', []):
            planned_edits += f"\n- New File: {new_file['name']}\n"
            planned_edits += f"  Path: {new_file.get('path', 'N/A')}\n"
            planned_edits += f"  Purpose: {new_file['purpose']}\n"
        
        # New symbols
        for new_sym in implementation_plan.get('new_symbols', []):
            planned_edits += f"\n- New Symbol: {new_sym['name']} ({new_sym['type']})\n"
            planned_edits += f"  File: {new_sym.get('file', 'N/A')}\n"
            planned_edits += f"  Purpose: {new_sym['purpose']}\n"
        
        # Existing symbol edits
        for edit in implementation_plan.get('existing_symbol_edits', []):
            planned_edits += f"\n- Edit Symbol: {edit['symbol_name']} ({edit['file_path']})\n"
            planned_edits += f"  Edit Type: {edit['edit_type']}\n"
            for change in edit.get('changes', []):
                planned_edits += f"  Change: {change.get('reason', 'N/A')}\n"
        
        # Format affected symbols code WITH DEPENDENCIES
        symbols_text = ""
        for symbol in symbols_with_code:
            symbols_text += f"\n{'='*60}\n"
            symbols_text += f"Symbol: {symbol['symbol_name']}\n"
            symbols_text += f"File: {symbol['file_path']}\n"
            symbols_text += f"{'='*60}\n"
            
            # Include context/dependencies if available
            if symbol.get('context_tags'):
                symbols_text += f"\nDependencies & Context:\n{symbol['context_tags']}\n"
            
            symbols_text += f"\nCode:\n```\n{symbol['code']}\n```\n"
        
        # Load relationships to show what these symbols depend on
        relationships_file = self.rays_dir / "relationships.msgpack"
        dependency_context = ""
        
        if relationships_file.exists():
            try:
                import msgpack
                with open(relationships_file, 'rb') as f:
                    relationships = msgpack.unpackb(f.read(), raw=False)
                
                # Find relationships for affected symbols
                affected_names = {s['symbol_name'] for s in symbols_with_code}
                
                relevant_deps = []
                for rel in relationships:
                    src = rel.get('source_symbol', '')
                    tgt = rel.get('target_symbol', '')
                    
                    # If affected symbol depends on something
                    if src in affected_names:
                        relevant_deps.append(f"{src} → {tgt} (type: {rel.get('relationship_type', 'unknown')})")
                
                if relevant_deps:
                    dependency_context = "\n**DEPENDENCY GRAPH:**\n"
                    dependency_context += "\n".join(relevant_deps[:50])  # Limit to 50 deps
                    dependency_context += "\n\n(These are symbols that the affected code calls/imports/uses)"
                
            except Exception as e:
                pass
        
        # Build prompt
        prompt_template = self.config['blocking_symbol_detection_prompts']['predict_blocking_symbols']
        prompt = prompt_template.format(
            implementation_plan_summary=plan_summary,
            planned_edits=planned_edits,
            affected_symbols_code=symbols_text + dependency_context
        )
        
        system_prompt = self.config['task_analysis_prompts']['system_instructions']
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            
            predicted = result.get('predicted_blocking_symbols', [])
            
            for blocker in predicted:
                pass
            
            return result
            
        except Exception as e:
            return {
                'predicted_blocking_symbols': [],
                'analysis': 'Error during prediction'
            }

    def smart_retrieve_blocking_symbol(self, blocker_name: str, affected_symbols: list, 
                                       predicted_type: str = None) -> dict:
        """
        Smart retrieval of blocking symbol using dependency graph and context.
        
        Handles name collisions by:
        1. Checking if blocker is in affected symbols' dependency graph
        2. Filtering by symbol type if provided
        3. Using file proximity as tiebreaker
        
        Args:
            blocker_name: Name of blocking symbol to retrieve
            affected_symbols: List of affected symbols (with names and file paths)
            predicted_type: Predicted symbol type (function, class, etc.)
        
        Returns:
            Dict with symbol metadata, code, and confidence score
        """
        # Load symbols and relationships
        symbols_file = self.rays_dir / "symbols.msgpack"
        relationships_file = self.rays_dir / "relationships.msgpack"
        
        if not symbols_file.exists() or not relationships_file.exists():
            return None
        
        import msgpack
        
        with open(symbols_file, 'rb') as f:
            all_symbols = msgpack.unpackb(f.read(), raw=False)
        
        with open(relationships_file, 'rb') as f:
            relationships = msgpack.unpackb(f.read(), raw=False)
        
        # Find all symbols matching the name
        candidates = [s for s in all_symbols if s.get('symbol_name') == blocker_name]
        
        if not candidates:
            return None
        
        if len(candidates) == 1:
            return self._enrich_symbol_data(candidates[0])
        
        # Multiple candidates - disambiguate
        
        # Strategy 1: Check dependency graph
        affected_names = {s.get('symbol_name') for s in affected_symbols}
        
        # Build dependency map: which symbols do affected symbols depend on?
        dependencies_of_affected = set()
        for rel in relationships:
            src = rel.get('source_symbol', '')
            tgt = rel.get('target_symbol', '')
            
            if src in affected_names:
                dependencies_of_affected.add(tgt)
        
        # Check if any candidate is in the dependency graph
        in_dep_graph = []
        for candidate in candidates:
            # Check direct name match in dependencies
            if blocker_name in dependencies_of_affected:
                in_dep_graph.append(candidate)
        
        if len(in_dep_graph) == 1:
            return self._enrich_symbol_data(in_dep_graph[0])
        
        # Strategy 2: Filter by symbol type
        if predicted_type:
            type_matches = [c for c in (in_dep_graph if in_dep_graph else candidates) 
                          if c.get('symbol_type') == predicted_type]
            
            if len(type_matches) == 1:
                return self._enrich_symbol_data(type_matches[0])
            
            if type_matches:
                candidates = type_matches
        
        # Strategy 3: File proximity - prefer symbols in same/related directories
        affected_files = {s.get('file_path', '').split('/')[0] for s in affected_symbols}
        
        proximity_scores = []
        for candidate in (in_dep_graph if in_dep_graph else candidates):
            file_path = candidate.get('file_path', '')
            score = 0
            
            # Check if in same top-level directory
            if file_path.split('/')[0] in affected_files:
                score += 10
            
            # Check for common patterns (auth/, models/, utils/)
            for affected_path in [s.get('file_path', '') for s in affected_symbols]:
                if any(part in file_path for part in affected_path.split('/')):
                    score += 5
            
            proximity_scores.append((candidate, score))
        
        # Sort by proximity score
        proximity_scores.sort(key=lambda x: x[1], reverse=True)
        
        if proximity_scores and proximity_scores[0][1] > 0:
            best_match = proximity_scores[0][0]
            return self._enrich_symbol_data(best_match)
        
        # Fallback: Return first candidate with warning
        return self._enrich_symbol_data(candidates[0])
    
    def _enrich_symbol_data(self, symbol: dict) -> dict:
        """
        Enrich symbol data by reading actual code from file.
        
        Args:
            symbol: Symbol metadata from symbols.msgpack
        
        Returns:
            Enriched symbol with code content
        """
        file_path = symbol.get('file_path', '')
        start_line = symbol.get('start_line', 0)
        end_line = symbol.get('end_line', 0)
        
        # Read actual code
        full_path = self.codebase_root / file_path
        code = ""
        
        if full_path.exists():
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    if start_line > 0 and end_line >= start_line:
                        code = ''.join(lines[start_line-1:end_line])
            except Exception as e:
                pass
        
        return {
            'symbol_name': symbol.get('symbol_name', ''),
            'symbol_type': symbol.get('symbol_type', 'unknown'),
            'file_path': file_path,
            'start_line': start_line,
            'end_line': end_line,
            'code': code,
            'chunk_id': f"{file_path}:{start_line}:{symbol.get('symbol_name', '')}"
        }

    def validate_blocking_symbols(self, implementation_plan: dict, predicted_blockers: list, symbols_with_code: list) -> dict:
        """
        Step 9.2: Validate predicted blocking symbols with actual code.
        
        Args:
            implementation_plan: Implementation plan
            predicted_blockers: Predicted blocking symbols
        
        Returns:
            Confirmed blocking symbols with ACTUAL file paths and chunk IDs from vector DB
        """
        
        if not predicted_blockers:
            return {
                'confirmed_blocking_symbols': [],
                'rejected_predictions': [],
                'validation_summary': 'No blockers predicted'
            }
        
        # Retrieve code for predicted blockers from vector DB
        
        chroma_path = str(self.rays_dir / "chroma_db")
        client = chromadb.PersistentClient(path=chroma_path)
        collection = client.get_collection("code_chunks")
        
        blocking_symbols_code = ""
        retrieved_blockers = []  # Store with ACTUAL metadata

        for blocker in predicted_blockers:
            symbol_name = blocker['symbol_name']
            predicted_type = blocker.get('blocking_type')  # May help with filtering
            
            
            # Use SMART retrieval with dependency graph
            retrieved = self.smart_retrieve_blocking_symbol(
                symbol_name,
                symbols_with_code,  # Pass affected symbols for context
                predicted_type
            )
            
            if retrieved:
                actual_file_path = retrieved['file_path']
                actual_chunk_id = retrieved['chunk_id']
                code = retrieved['code']
                
                # Format for prompt with ACTUAL file path
                blocking_symbols_code += f"\n{'='*50}\n"
                blocking_symbols_code += f"Symbol: {symbol_name}\n"
                blocking_symbols_code += f"Type: {retrieved['symbol_type']}\n"
                blocking_symbols_code += f"File: {actual_file_path}\n"
                blocking_symbols_code += f"Lines: {retrieved['start_line']}-{retrieved['end_line']}\n"
                blocking_symbols_code += f"Chunk ID: {actual_chunk_id}\n"
                blocking_symbols_code += f"{'='*50}\n"
                blocking_symbols_code += f"Code:\n```\n{code}\n```\n"
                
                # Store with ACTUAL metadata for later use
                retrieved_blockers.append({
                    'symbol_name': symbol_name,
                    'symbol_type': retrieved['symbol_type'],
                    'file_path': actual_file_path,
                    'chunk_id': actual_chunk_id,
                    'code': code,
                    'original_prediction': blocker
                })
            else:
                pass
        

        if not retrieved_blockers:
            return {
                'confirmed_blocking_symbols': [],
                'rejected_predictions': predicted_blockers,
                'validation_summary': 'Could not retrieve any blocker code'
            }

        # Format plan summary
        plan_summary = implementation_plan.get('plan_summary', '')
        
        # Format planned edits WITH DETAILS
        planned_edits = ""
        for edit in implementation_plan.get('existing_symbol_edits', []):
            planned_edits += f"\n- {edit['symbol_name']} ({edit['file_path']})\n"
            planned_edits += f"  Edit Type: {edit['edit_type']}\n"
            for change in edit.get('changes', []):
                planned_edits += f"  • {change.get('location', 'N/A')}: {change.get('reason', 'N/A')}\n"
        
        for new_sym in implementation_plan.get('new_symbols', []):
            planned_edits += f"\n- NEW SYMBOL: {new_sym['name']} ({new_sym['type']})\n"
            planned_edits += f"  Purpose: {new_sym.get('purpose', 'N/A')}\n"
            planned_edits += f"  Implementation: {new_sym.get('implementation_logic', 'N/A')[:200]}...\n"
        
        # Format AFFECTED SYMBOLS CODE (the symbols that will be changed)
        affected_symbols_code = ""
        for symbol in symbols_with_code:
            affected_symbols_code += f"\n{'='*60}\n"
            affected_symbols_code += f"AFFECTED SYMBOL: {symbol['symbol_name']}\n"
            affected_symbols_code += f"File: {symbol['file_path']}\n"
            affected_symbols_code += f"Lines: {symbol['start_line']}-{symbol['end_line']}\n"
            affected_symbols_code += f"{'='*60}\n"
            if symbol.get('context_tags'):
                affected_symbols_code += f"Context:\n{symbol['context_tags']}\n\n"
            affected_symbols_code += f"Current Code:\n```\n{symbol['code']}\n```\n"
        
        # Format predicted blockers with their reasons
        predicted_text = ""
        for blocker in predicted_blockers:
            predicted_text += f"\n- {blocker['symbol_name']}\n"
            predicted_text += f"  Predicted Reason: {blocker.get('blocking_reason', 'N/A')}\n"
            predicted_text += f"  Type: {blocker.get('blocking_type', 'N/A')}\n"
            predicted_text += f"  Blocks: {', '.join(blocker.get('blocks_which_edits', []))}\n"
            predicted_text += f"  Evidence: {blocker.get('evidence', 'N/A')}\n"
        
        # Build prompt - NOW WITH BOTH AFFECTED AND BLOCKING CODE
        prompt_template = self.config['blocking_symbol_detection_prompts']['validate_blocking_symbols']
        prompt = prompt_template.format(
            implementation_plan_summary=plan_summary,
            planned_edits=planned_edits,
            affected_symbols_code=affected_symbols_code,  # ← NEW: Show what will be changed
            predicted_blockers=predicted_text,
            blocking_symbols_code=blocking_symbols_code   # ← Show potential blockers
        )
        
        system_prompt = self.config['task_analysis_prompts']['system_instructions']
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            
            confirmed = result.get('confirmed_blocking_symbols', [])
            rejected = result.get('rejected_predictions', [])
            
            # IMPORTANT: Enrich confirmed blockers with ACTUAL metadata from DB
            enriched_confirmed = []
            for conf in confirmed:
                symbol_name = conf['symbol_name']
                # Find the actual metadata we retrieved
                actual_data = next((r for r in retrieved_blockers if r['symbol_name'] == symbol_name), None)
                
                if actual_data:
                    conf['file_path'] = actual_data['file_path']  # ← ACTUAL path
                    conf['chunk_id'] = actual_data['chunk_id']    # ← ACTUAL chunk_id
                    enriched_confirmed.append(conf)
                else:
                    # Fallback: keep as is but mark as unverified
                    conf['file_path'] = 'unverified'
                    conf['chunk_id'] = None
                    enriched_confirmed.append(conf)
            
            
            for blocker in enriched_confirmed:
                pass
            
            for reject in rejected:
                pass
            
            return {
                'confirmed_blocking_symbols': enriched_confirmed,
                'rejected_predictions': rejected,
                'validation_summary': result.get('validation_summary', '')
            }
            
        except Exception as e:
            # Fallback: use retrieved blockers with actual metadata
            fallback_confirmed = []
            for r in retrieved_blockers:
                fallback_confirmed.append({
                    'symbol_name': r['symbol_name'],
                    'file_path': r['file_path'],  # ← ACTUAL
                    'chunk_id': r['chunk_id'],    # ← ACTUAL
                    'blocking_reason': r['original_prediction'].get('blocking_reason', 'Validation failed'),
                    'blocking_type': r['original_prediction'].get('blocking_type', 'unknown'),
                    'requires_change': True,
                    'change_complexity': 'moderate'
                })
            
            return {
                'confirmed_blocking_symbols': fallback_confirmed,
                'rejected_predictions': [],
                'validation_summary': 'Validation failed, accepting all retrieved symbols'
            }

    def analyze_blocker_resolution(self, blocker: dict, implementation_plan: dict, symbols_with_code: list) -> dict:
        """
        Analyze how to resolve a single blocking symbol.
        
        This prompts the AI with:
            pass
        - The original implementation plan
        - Code of affected symbols (being blocked)
        - Code of blocking symbol
        - How the blocking occurs
        
        Args:
            blocker: Blocking symbol details with 'blocks_which_edits'
            implementation_plan: Original implementation plan
            symbols_with_code: Affected symbols with their code
        
        Returns:
            Resolution strategy with detailed changes needed
        """
        
        # Get the blocking symbol's code
        blocker_code = blocker.get('code', '')
        
        if not blocker_code:
            # Try to retrieve from chunk_id
            chunk_id = blocker.get('chunk_id')
            if chunk_id:
                try:
                    chroma_path = str(self.rays_dir / "chroma_db")
                    client = chromadb.PersistentClient(path=chroma_path)
                    collection = client.get_collection("code_chunks")
                    
                    result = collection.get(
                        ids=[chunk_id],
                        include=['documents']
                    )
                    if result['documents']:
                        blocker_code = result['documents'][0]
                except Exception as e:
                    pass
        
        if not blocker_code:
            blocker_code = "// Code not available"
        
        # Get the affected symbols that this blocker blocks
        blocked_edit_names = blocker.get('blocks_which_edits', [])
        
        if not blocked_edit_names:
            return {
                'resolution_strategy': 'skip',
                'required_changes': [],
                'introduces_new_blockers': False,
                'new_blocker_candidates': []
            }
        
        # Find the affected symbols' code and planned changes
        affected_symbols_detail = ""
        planned_changes_detail = ""
        
        for edit_name in blocked_edit_names:
            # Find in implementation plan
            for edit in implementation_plan.get('existing_symbol_edits', []):
                if edit['symbol_name'] == edit_name or edit_name in edit.get('file_path', ''):
                    # Found the planned edit
                    planned_changes_detail += f"\n{'='*50}\n"
                    planned_changes_detail += f"PLANNED EDIT: {edit['symbol_name']}\n"
                    planned_changes_detail += f"File: {edit.get('file_path', 'unknown')}\n"
                    planned_changes_detail += f"Edit Type: {edit['edit_type']}\n"
                    planned_changes_detail += f"{'='*50}\n"
                    
                    for change in edit.get('changes', []):
                        planned_changes_detail += f"- Location: {change.get('location', 'N/A')}\n"
                        planned_changes_detail += f"  Current: {change.get('current', 'N/A')}\n"
                        planned_changes_detail += f"  New: {change.get('new', 'N/A')}\n"
                        planned_changes_detail += f"  Reason: {change.get('reason', 'N/A')}\n\n"
                    
                    # Find the symbol's current code
                    symbol_code = next(
                        (s for s in symbols_with_code if s['symbol_name'] == edit['symbol_name']),
                        None
                    )
                    
                    if symbol_code:
                        affected_symbols_detail += f"\n{'='*50}\n"
                        affected_symbols_detail += f"AFFECTED SYMBOL CODE: {symbol_code['symbol_name']}\n"
                        affected_symbols_detail += f"File: {symbol_code['file_path']}\n"
                        affected_symbols_detail += f"Lines: {symbol_code['start_line']}-{symbol_code['end_line']}\n"
                        affected_symbols_detail += f"{'='*50}\n"
                        affected_symbols_detail += f"Current Code:\n```\n{symbol_code['code']}\n```\n\n"
                    
                    break
        
        if not affected_symbols_detail:
            affected_symbols_detail = "// Affected symbol code not found"
        
        if not planned_changes_detail:
            planned_changes_detail = f"Changes to: {', '.join(blocked_edit_names)}"
        
        # Format the blocking symbol code
        blocking_symbol_detail = f"\n{'='*50}\n"
        blocking_symbol_detail += f"BLOCKING SYMBOL: {blocker['symbol_name']}\n"
        blocking_symbol_detail += f"File: {blocker.get('file_path', 'unknown')}\n"
        blocking_symbol_detail += f"Type: {blocker.get('symbol_type', 'unknown')}\n"
        blocking_symbol_detail += f"{'='*50}\n"
        blocking_symbol_detail += f"Blocking Reason: {blocker.get('blocking_reason', 'N/A')}\n"
        blocking_symbol_detail += f"Blocking Type: {blocker.get('blocking_type', 'unknown')}\n\n"
        blocking_symbol_detail += f"Blocker Code:\n```\n{blocker_code}\n```\n"
        
        # Build prompt with ALL context
        prompt_template = self.config['blocking_symbol_detection_prompts']['analyze_blocker_resolution']
        prompt = prompt_template.format(
            implementation_plan_summary=implementation_plan.get('plan_summary', ''),
            planned_changes=planned_changes_detail,
            affected_symbols_code=affected_symbols_detail,
            blocking_symbol_code=blocking_symbol_detail,
            blocking_relationship=f"{blocker['symbol_name']} blocks {', '.join(blocked_edit_names)} because: {blocker.get('blocking_reason', 'unknown')}"
        )
        
        system_prompt = self.config['task_analysis_prompts']['system_instructions']
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            
            strategy = result.get('resolution_strategy', 'unknown')
            changes_count = len(result.get('required_changes', []))
            introduces_blockers = result.get('introduces_new_blockers', False)
            
            
            return result
            
        except Exception as e:
            return {
                'resolution_strategy': 'unknown',
                'required_changes': [],
                'introduces_new_blockers': False,
                'new_blocker_candidates': []
            }



#            
#            if architectural_boundary:
#                print(f"\n⚠ Architectural boundary reached at hop {current_hop}")
#                print("  This requires architectural change - escalating")
#                break
#            
#            # Prepare for next hop
#            print(f"\n  Expanding to hop {current_hop + 1} with {len(new_blocker_candidates)} candidates...")
#            
#            # Update plan to focus on blocker resolutions
#            # (In reality, you'd reformulate the plan, but for now we'll use same plan)
#            
#        print("\n" + "="*60)
#        print("BLOCKING SYMBOL DETECTION COMPLETE")
#        print("="*60)
#        print(f"Total Hops: {current_hop}")
#        print(f"Total Blockers Found: {len(all_blockers)}")
#        
#        # Group by hop
#        by_hop = {}
#        for blocker in all_blockers:
#            hop = blocker['discovery_hop']
#            if hop not in by_hop:
#                by_hop[hop] = []
#            by_hop[hop].append(blocker['symbol_name'])
#        
#        for hop, symbols in sorted(by_hop.items()):
#            print(f"  Hop {hop}: {len(symbols)} blockers - {', '.join(symbols)}")
#        
#        print("="*60)
#        
#        return {
#            'all_blocking_symbols': all_blockers,
#            'total_hops': current_hop,
#            'blocker_count': len(all_blockers),
#            'blockers_by_hop': by_hop
#        }


    def merge_blocker_resolutions_into_plan(self, implementation_plan: dict, 
                                           blocking_analysis: dict,
                                           permission_slip: dict) -> tuple:
        """
        Step 10: Merge blocking symbol resolutions into the implementation plan.
        
        This updates:
        1. Implementation plan - adds blocker edits to existing_symbol_edits
        2. Permission slip - increases counts to accommodate blocker changes
        
        Args:
            implementation_plan: Original implementation plan
            blocking_analysis: Result from detect_blocking_symbols_multihop
            permission_slip: Current permission slip
        
        Returns:
            Tuple of (updated_plan, updated_permissions)
        """
        
        all_blockers = blocking_analysis.get('all_blocking_symbols', [])
        
        if not all_blockers:
            return implementation_plan, permission_slip
        
        # Deep copy to avoid mutations
        import copy
        updated_plan = copy.deepcopy(implementation_plan)
        updated_permissions = copy.deepcopy(permission_slip)
        
        # Track what we're adding
        added_edits = 0
        added_lines = 0
        
        for blocker in all_blockers:
            resolution = blocker.get('resolution')
            
            if not resolution:
                continue
            
            requires_change = blocker.get('requires_change', True)
            complexity = blocker.get('change_complexity', 'moderate')
            
            if not requires_change or complexity == 'trivial':
                continue
            
            # Build blocker edit entry
            blocker_edit = {
                'symbol_name': blocker['symbol_name'],
                'file_path': blocker.get('file_path', 'unknown'),
                'chunk_id': blocker.get('chunk_id'),
                'edit_type': resolution.get('resolution_strategy', 'modify'),
                'is_blocker_resolution': True,  # Mark as blocker resolution
                'discovery_hop': blocker.get('discovery_hop', 1),
                'changes': []
            }
            
            # Add resolution changes
            for change in resolution.get('required_changes', []):
                blocker_edit['changes'].append({
                    'location': change.get('location', 'unknown'),
                    'current': change.get('current', ''),
                    'new': change.get('new', ''),
                    'reason': f"BLOCKER RESOLUTION: {change.get('reason', 'N/A')}"
                })
            
            # Estimate lines changed
            estimated_lines = len(resolution.get('required_changes', [])) * 5  # Rough estimate
            blocker_edit['estimated_lines_changed'] = estimated_lines
            
            # Add to plan
            updated_plan['existing_symbol_edits'].append(blocker_edit)
            added_edits += 1
            added_lines += estimated_lines
            
        
        # Update totals in plan
        if 'total_counts' in updated_plan:
            updated_plan['total_counts']['edited_symbols'] += added_edits
            updated_plan['total_counts']['estimated_total_lines_changed'] += added_lines
        
        # Update permissions to accommodate blocker changes
        updated_permissions['num_symbols_to_edit'] += added_edits
        updated_permissions['max_lines_to_edit'] += added_lines
        
        # Add to symbols_allowed_to_edit
        for blocker in all_blockers:
            if blocker.get('requires_change', True):
                updated_permissions['symbols_allowed_to_edit'].append({
                    'symbol_name': blocker['symbol_name'],
                    'file_path': blocker.get('file_path', 'unknown'),
                    'chunk_id': blocker.get('chunk_id'),
                    'reason': 'Blocking symbol resolution',
                    'change_type': 'modify',
                    'priority': 'high'
                })
        
        
        return updated_plan, updated_permissions

    def generate_new_codebase_plan(self, user_prompt: str, allowed_files: int, allowed_symbols: int, directory_tree: str) -> dict:
        """
        Generate a hierarchical implementation plan for a new codebase.
        """
        
        prompt = self.config['new_codebase_prompts']['generate_plan'].format(
            user_prompt=user_prompt,
            allowed_files=allowed_files,
            allowed_symbols=allowed_symbols,
            directory_tree=directory_tree
        )
        system_prompt = self.config.get('task_analysis_prompts', {}).get('system_instructions', '')
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            return result
        except Exception as e:
            return {"summary": "Error generating plan", "files": []}

