"""
Code Generator - Executes implementation plan by generating actual code edits.

Processing order:
1. Blocking symbols (5 at a time)
2. Existing symbol edits (5 at a time)  
3. New symbols in existing files (5 at a time)
4. New files with symbols (1 at a time)
"""

from pathlib import Path
from typing import Dict, List, Tuple
import re
import rays_ui


class CodeGenerator:
    """Generate code edits from implementation plan."""
    
    def __init__(self, codebase_root: Path, rays_dir: Path, ai_client):
        self.codebase_root = Path(codebase_root)
        self.rays_dir = Path(rays_dir)
        self.ai_client = ai_client
        
        # Track all edits made (for context in later batches)
        self.edit_history = []
    
    def execute_implementation_plan(self, implementation_plan: dict,
                                   blocking_analysis: dict,
                                   anchoring_results: dict,
                                   config: dict) -> dict:
        """
        Main entry point - execute entire implementation plan.
        
        Order:
        1. Edit blocking symbols (5 at a time)
        2. Edit existing symbols (5 at a time)
        3. Create new symbols in existing files (5 at a time)
        4. Create new files with symbols (1 at a time)
        
        Returns:
            Execution results with all file changes
        """
        rays_ui.print_phase("Generating Code")
        
        results = {
            'blocking_edits': [],
            'symbol_edits': [],
            'new_symbol_creations': [],
            'new_file_creations': [],
            'errors': []
        }
        
        # PHASE 1: Edit blocking symbols
        blocking_symbols = blocking_analysis.get('all_blocking_symbols', [])
        if blocking_symbols:
            rays_ui.print_sub_phase(f"Editing {len(blocking_symbols)} dependency symbols")
            blocking_edits = self._edit_blocking_symbols(
                blocking_symbols,
                implementation_plan,
                config
            )
            results['blocking_edits'] = blocking_edits
        
        # PHASE 2: Edit existing symbols
        existing_edits = implementation_plan.get('existing_symbol_edits', [])
        if existing_edits:
            rays_ui.print_sub_phase(f"Editing {len(existing_edits)} existing symbols")
            symbol_edits = self._edit_existing_symbols(
                existing_edits,
                implementation_plan,
                config
            )
            results['symbol_edits'] = symbol_edits
        
        # PHASE 3: Create new symbols in existing files
        new_symbols = implementation_plan.get('new_symbols', [])
        if new_symbols:
            rays_ui.print_sub_phase(f"Creating {len(new_symbols)} new symbols")
            new_symbol_results = self._create_new_symbols(
                new_symbols,
                implementation_plan,
                config
            )
            results['new_symbol_creations'] = new_symbol_results
        
        # PHASE 4: Create new files
        new_files = implementation_plan.get('new_files', [])
        if new_files:
            rays_ui.print_sub_phase(f"Creating {len(new_files)} new files")
            new_file_results = self._create_new_files(
                new_files,
                anchoring_results,
                implementation_plan,
                config
            )
            results['new_file_creations'] = new_file_results
        
        rays_ui.print_step("Code generation phase finished")
        
        return results
    
    def _edit_blocking_symbols(self, blocking_symbols: List[dict],
                               implementation_plan: dict,
                               config: dict) -> List[dict]:
        """
        Phase 1: Edit blocking symbols in batches of 5.
        """
        BATCH_SIZE = 5
        all_edits = []
        
        for i in range(0, len(blocking_symbols), BATCH_SIZE):
            batch = blocking_symbols[i:i+BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            rays_ui.print_info(f"Processing batch {batch_num} of dependency edits")
            
            # Generate edits for this batch
            batch_edits = self._generate_blocker_edits(
                batch,
                implementation_plan,
                config
            )
            
            all_edits.extend(batch_edits)
            
            # Add to edit history for next batch context
            for edit in batch_edits:
                self.edit_history.append({
                    'type': 'blocking_symbol',
                    'symbol_name': edit['symbol_name'],
                    'file': edit['file'],
                    'edit': edit
                })
        
        return all_edits
    
    def _generate_blocker_edits(self, blockers: List[dict],
                                implementation_plan: dict,
                                config: dict) -> List[dict]:
        """
        Generate code edits for a batch of blocking symbols.
        """
        edits = []
        
        for blocker in blockers:
            symbol_name = blocker['symbol_name']
            file_path = blocker.get('file_path', 'unknown')
            resolution = blocker.get('resolution', {})
            rays_ui.print_info(f"Generating edit for: {symbol_name}")
            
            # Get current code with line numbers
            code_with_lines = self._get_code_with_line_numbers(
                file_path,
                blocker.get('start_line'),
                blocker.get('end_line')
            )
            
            if not code_with_lines:
                rays_ui.print_warning(f"Could not read code for {symbol_name}")
                continue
            
            # Build prompt for AI
            prompt = self._build_blocker_edit_prompt(
                blocker,
                code_with_lines,
                resolution,
                implementation_plan,
                config
            )
            
            # Get edit from AI
            try:
                edit_result = self.ai_client.generate_json(
                    prompt,
                    config['task_analysis_prompts']['system_instructions']
                )
                
                edit_result['symbol_name'] = symbol_name
                edit_result['file'] = file_path
                edits.append(edit_result)
                
                rays_ui.print_step(f"Generated edit for {symbol_name} ({len(edit_result.get('edits', []))} changes)")
                
            except Exception as e:
                rays_ui.print_error(f"Error generating edit for {symbol_name}: {e}")
                continue
        
        return edits
    
    def _get_code_with_line_numbers(self, file_path: str,
                                    start_line: int = None,
                                    end_line: int = None) -> str:
        """
        Read code from file and format with line numbers.
        
        Returns:
            String with format:
            45 | def validate_jwt(token):
            46 |     if not token:
            47 |         return None
        """
        full_path = self.codebase_root / file_path
        
        if not full_path.exists():
            return ""
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            # If start/end specified, extract that range
            if start_line and end_line:
                selected_lines = lines[start_line-1:end_line]
                start_num = start_line
            else:
                selected_lines = lines
                start_num = 1
            
            # Format with line numbers
            formatted = []
            for i, line in enumerate(selected_lines):
                line_num = start_num + i
                formatted.append(f"{line_num:4d} | {line.rstrip()}")
            
            return "\n".join(formatted)
            
        except Exception as e:
            rays_ui.print_error(f"Error reading {file_path}: {e}")
            return ""
    
    def _build_blocker_edit_prompt(self, blocker: dict,
                                   code_with_lines: str,
                                   resolution: dict,
                                   implementation_plan: dict,
                                   config: dict) -> str:
        """Build prompt for generating blocker edits."""
        
        # Get the prompt template
        prompt_template = config['code_generation_prompts']['generate_blocker_edit']
        
        # Format edit history
        previous_edits_text = self._format_edit_history()
        
        prompt = prompt_template.format(
            blocker_name=blocker['symbol_name'],
            blocker_file=blocker.get('file_path', 'unknown'),
            blocking_reason=blocker.get('blocking_reason', 'N/A'),
            resolution_strategy=resolution.get('resolution_strategy', 'modify'),
            resolution_changes=self._format_resolution_changes(resolution),
            current_code_with_lines=code_with_lines,
            implementation_plan_summary=implementation_plan.get('plan_summary', ''),
            previous_edits=previous_edits_text
        )
        
        return prompt
    
    def _format_resolution_changes(self, resolution: dict) -> str:
        """Format resolution changes for prompt."""
        changes = resolution.get('required_changes', [])
        
        if not changes:
            return "No specific changes defined"
        
        text = ""
        for i, change in enumerate(changes, 1):
            text += f"\n{i}. {change.get('location', 'N/A')}:\n"
            text += f"   Type: {change.get('change_type', 'modify')}\n"
            text += f"   Reason: {change.get('reason', 'N/A')}\n"
        
        return text
    
    def _format_edit_history(self) -> str:
        """Format previous edits for context."""
        if not self.edit_history:
            return "No previous edits yet."
        
        text = ""
        for edit in self.edit_history[-10:]:  # Last 10 edits
            text += f"\n- {edit['type']}: {edit['symbol_name']} in {edit['file']}\n"
        
        return text
    
    def _edit_existing_symbols(self, existing_edits: List[dict],
                               implementation_plan: dict,
                               config: dict) -> List[dict]:
        """
        Phase 2: Edit existing symbols in batches of 5.
        """
        BATCH_SIZE = 5
        all_edits = []
        
        for i in range(0, len(existing_edits), BATCH_SIZE):
            batch = existing_edits[i:i+BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            rays_ui.print_info(f"Processing batch {batch_num} of symbol edits")
            
            batch_edits = self._generate_symbol_edits(
                batch,
                implementation_plan,
                config
            )
            
            all_edits.extend(batch_edits)
            
            for edit in batch_edits:
                self.edit_history.append({
                    'type': 'existing_symbol',
                    'symbol_name': edit['symbol_name'],
                    'file': edit['file'],
                    'edit': edit
                })
        
        return all_edits
    
    def _generate_symbol_edits(self, symbols: List[dict],
                               implementation_plan: dict,
                               config: dict) -> List[dict]:
        """Similar to _generate_blocker_edits but for existing symbols."""
        edits = []
        
        for symbol_edit in symbols:
            symbol_name = symbol_edit['symbol_name']
            file_path = symbol_edit['file_path']
            
            rays_ui.print_info(f"Generating edit for: {symbol_name}")
            
            # Get code with line numbers
            code_with_lines = self._get_code_with_line_numbers(file_path)
            
            # Build prompt
            prompt_template = config['code_generation_prompts']['generate_symbol_edit']
            prompt = prompt_template.format(
                symbol_name=symbol_name,
                file_path=file_path,
                edit_type=symbol_edit.get('edit_type', 'modify'),
                planned_changes=self._format_planned_changes(symbol_edit),
                current_code_with_lines=code_with_lines,
                implementation_plan_summary=implementation_plan.get('plan_summary', ''),
                previous_edits=self._format_edit_history()
            )
            
            try:
                edit_result = self.ai_client.generate_json(
                    prompt,
                    config['task_analysis_prompts']['system_instructions']
                )
                
                edit_result['symbol_name'] = symbol_name
                edit_result['file'] = file_path
                edits.append(edit_result)
                
                rays_ui.print_step(f"Generated edit for {symbol_name}")
                
            except Exception as e:
                rays_ui.print_error(f"Error generating edit for {symbol_name}: {e}")
        
        return edits
    
    def _format_planned_changes(self, symbol_edit: dict) -> str:
        """Format planned changes from implementation plan."""
        changes = symbol_edit.get('changes', [])
        
        text = ""
        for i, change in enumerate(changes, 1):
            text += f"\n{i}. Location: {change.get('location', 'N/A')}\n"
            text += f"   Current: {change.get('current', 'N/A')}\n"
            text += f"   New: {change.get('new', 'N/A')}\n"
            text += f"   Reason: {change.get('reason', 'N/A')}\n"
        
        return text
    
    def _create_new_symbols(self, new_symbols: List[dict],
                           implementation_plan: dict,
                           config: dict) -> List[dict]:
        """
        Phase 3: Create new symbols in existing files (5 at a time).
        """
        BATCH_SIZE = 5
        all_creations = []
        
        for i in range(0, len(new_symbols), BATCH_SIZE):
            batch = new_symbols[i:i+BATCH_SIZE]
            batch_num = (i // BATCH_SIZE) + 1
            rays_ui.print_info(f"Creating new symbols batch {batch_num}")
            
            batch_creations = self._generate_new_symbol_code(
                batch,
                implementation_plan,
                config
            )
            
            all_creations.extend(batch_creations)
        
        return all_creations
    
    def _generate_new_symbol_code(self, symbols: List[dict],
                                  implementation_plan: dict,
                                  config: dict) -> List[dict]:
        """Generate code for new symbols."""
        creations = []
        
        for symbol in symbols:
            symbol_name = symbol['name']
            anchor = symbol.get('anchor', {})
            
            rays_ui.print_info(f"Generating code for: {symbol_name}")
            
            # Get context code around insertion point
            target_file = anchor.get('target_file', symbol.get('file', 'unknown'))
            insertion_line = anchor.get('insertion_line', 0)
            
            context_code = self._get_context_around_line(
                target_file,
                insertion_line,
                lines_before=10,
                lines_after=5
            )
            
            # Build prompt
            prompt_template = config['code_generation_prompts']['generate_new_symbol']
            prompt = prompt_template.format(
                symbol_name=symbol_name,
                symbol_type=symbol['type'],
                signature=symbol.get('signature', ''),
                purpose=symbol.get('purpose', ''),
                implementation_logic=symbol.get('implementation_logic', ''),
                target_file=target_file,
                insertion_line=insertion_line,
                insertion_context=anchor.get('context', 'end of file'),
                context_code=context_code,
                previous_edits=self._format_edit_history()
            )
            
            try:
                response_text = self.ai_client.generate_text(
                    prompt,
                    config['task_analysis_prompts']['system_instructions']
                )
                
                # Try to parse as JSON first (for metadata), fallback to raw code extraction
                creation_result = self.ai_client._extract_json(response_text) or {}
                if 'code' not in creation_result:
                    creation_result['code'] = self.ai_client.extract_code_block(response_text)
                
                creation_result['symbol_name'] = symbol_name
                creation_result['file'] = target_file
                creation_result['insertion_line'] = insertion_line
                creations.append(creation_result)
                
                rays_ui.print_step(f"Generated code for {symbol_name}")
                
            except Exception as e:
                rays_ui.print_error(f"Error generating symbol code for {symbol_name}: {e}")
        
        return creations
    
    def _get_context_around_line(self, file_path: str, line_num: int,
                                 lines_before: int = 10,
                                 lines_after: int = 5) -> str:
        """Get code context around a specific line."""
        full_path = self.codebase_root / file_path
        
        if not full_path.exists():
            return "// File not found or will be created"
        
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            start = max(0, line_num - lines_before - 1)
            end = min(len(lines), line_num + lines_after)
            
            context_lines = lines[start:end]
            
            formatted = []
            for i, line in enumerate(context_lines):
                actual_line_num = start + i + 1
                marker = " >>> INSERT HERE >>>" if actual_line_num == line_num else ""
                formatted.append(f"{actual_line_num:4d} | {line.rstrip()}{marker}")
            
            return "\n".join(formatted)
            
        except Exception as e:
            return f"// Error reading context: {e}"
    
    def _create_new_files(self, new_files: List[dict],
                         anchoring_results: dict,
                         implementation_plan: dict,
                         config: dict) -> List[dict]:
        """
        Phase 4: Create new files (1 at a time, more complex).
        """
        creations = []
        
        for file_spec in new_files:
            file_name = file_spec['name']
            anchor = file_spec.get('anchor', {})
            
            rays_ui.print_info(f"Generating code for new file: {file_name}")
            
            # Get similar files for context
            similar_files_context = self._get_similar_files_context(
                anchor.get('related_files', [])
            )
            
            # Build prompt
            prompt_template = config['code_generation_prompts']['generate_new_file']
            prompt = prompt_template.format(
                file_name=file_name,
                target_directory=anchor.get('target_directory', 'src/'),
                file_purpose=file_spec.get('purpose', ''),
                file_structure=file_spec.get('structure', ''),
                symbols_to_create=self._format_symbols_for_file(file_spec.get('symbols_to_create', [])),
                similar_files_context=similar_files_context,
                previous_edits=self._format_edit_history()
            )
            
            try:
                response_text = self.ai_client.generate_text(
                    prompt,
                    config['task_analysis_prompts']['system_instructions']
                )

                # Always extract actual source code for file content.
                # Metadata JSON may be present in model output, but file writer must only receive code.
                extracted_code = self.ai_client.extract_code_block(response_text).strip()
                creation_result = {'file_content': extracted_code}

                creation_result['file_name'] = file_name
                creation_result['full_path'] = anchor.get('full_path', f"src/{file_name}")
                creations.append(creation_result)
                
                rays_ui.print_step(f"Generated file code for {file_name}")
                
            except Exception as e:
                rays_ui.print_error(f"Error generating file code for {file_name}: {e}")
        
        return creations
    
    def _get_similar_files_context(self, related_files: List[str]) -> str:
        """Get snippets from related files for context."""
        if not related_files:
            return "No related files found."
        
        context = ""
        for file in related_files[:3]:  # Max 3 files
            # Try to find this file and get first 20 lines
            matching_files = list(self.codebase_root.rglob(file))
            if matching_files:
                try:
                    with open(matching_files[0], 'r', encoding='utf-8', errors='ignore') as f:
                        # [FIX] Read only first 20 lines without loading entire file
                        import itertools
                        first_20 = list(itertools.islice(f, 20))
                    context += f"\n--- {file} (first 20 lines) ---\n"
                    context += "".join(first_20)
                except:
                    pass
        
        return context if context else "Could not read related files."
    
    def _format_symbols_for_file(self, symbols: List[dict]) -> str:
        """Format symbols to be created in new file."""
        if not symbols:
            return "No symbols defined."
        
        text = ""
        for i, sym in enumerate(symbols, 1):
            text += f"\n{i}. {sym.get('type', 'function')}: {sym.get('name', 'unknown')}\n"
            text += f"   Signature: {sym.get('signature', 'N/A')}\n"
            text += f"   Purpose: {sym.get('purpose', 'N/A')}\n"
            text += f"   Logic: {sym.get('implementation_logic', 'N/A')[:100]}...\n"
        
        return text

