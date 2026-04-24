"""
Code Executor - Applies generated code edits to actual files.

Features:
- Backup files before editing
- Apply SEARCH/REPLACE edits
- Handle imports
- Rollback on errors
- Validate edits
"""

from pathlib import Path
import shutil
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import rays_ui

# Add to code_executor.py

class EditValidator:
    """Validate edits before applying."""
    
    @staticmethod
    def validate_search_replace(search: str, replace: str, content: str) -> Tuple[bool, str]:
        """
        Validate a SEARCH/REPLACE block.
        
        Returns:
            (is_valid, error_message)
        """
        if not search:
            return False, "Empty search block"
        
        if search not in content:
            # Try with normalized whitespace
            search_norm = re.sub(r'\s+', ' ', search.strip())
            content_norm = re.sub(r'\s+', ' ', content)
            
            if search_norm not in content_norm:
                return False, f"Search block not found in file"
        
        # Count occurrences
        count = content.count(search)
        if count > 1:
            return False, f"Search block appears {count} times (ambiguous)"
        
        return True, ""
    
    @staticmethod
    def validate_imports(imports: List[str]) -> Tuple[bool, str]:
        """Validate import statements."""
        for imp in imports:
            if not imp.strip().startswith(('import ', 'from ')):
                return False, f"Invalid import: {imp}"
        
        return True, ""
    
    @staticmethod
    def validate_python_syntax(code: str) -> Tuple[bool, str]:
        """Validate Python syntax."""
        try:
            import ast
            ast.parse(code)
            return True, ""
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

class CodeExecutor:
    """Execute code edits on actual files with backup and rollback."""
    
    def __init__(self, codebase_root: Path, rays_dir: Path, execution_mode: str = 'ask'):
        self.codebase_root = Path(codebase_root)
        self.rays_dir = Path(rays_dir)
        self.execution_mode = execution_mode
        self.backup_dir = rays_dir / "backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Track all changes for rollback
        self.changes_made = []
        self.files_modified = set()
        self.files_created = set()
    
    def apply_all_edits(self, generation_results: dict) -> dict:
        """
        Apply all generated edits to the codebase.
        
        Args:
            generation_results: Output from CodeGenerator.execute_implementation_plan()
        
        Returns:
            Execution results with success/failure status
        """
        rays_ui.print_phase("Applying code edits")
        
        results = {
            'success': True,
            'files_modified': 0,
            'files_created': 0,
            'files_modified_list': [],
            'files_created_list': [],
            'edits_applied': 0,
            'errors': []
        }
        
        try:
            # Phase 1: Apply blocking symbol edits
            blocking_edits = generation_results.get('blocking_edits', [])
            if blocking_edits:
                rays_ui.print_sub_phase(f"Applying {len(blocking_edits)} dependency edits")
                self._apply_edit_batch(blocking_edits, results)
            
            # Phase 2: Apply existing symbol edits
            symbol_edits = generation_results.get('symbol_edits', [])
            if symbol_edits:
                rays_ui.print_sub_phase(f"Applying {len(symbol_edits)} symbol edits")
                self._apply_edit_batch(symbol_edits, results)
            
            # Phase 3: Apply new symbol creations
            new_symbols = generation_results.get('new_symbol_creations', [])
            if new_symbols:
                rays_ui.print_sub_phase(f"Inserting {len(new_symbols)} new symbols")
                self._apply_new_symbols(new_symbols, results)
            
            # Phase 4: Create new files
            new_files = generation_results.get('new_file_creations', [])
            if new_files:
                rays_ui.print_sub_phase(f"Creating {len(new_files)} new files")
                self._create_new_files(new_files, results)
            
            results['git_status'] = rays_ui.get_git_status(str(self.codebase_root))
            rays_ui.print_summary_box(results)
            
            if results['errors']:
                for error in results['errors']:
                    rays_ui.print_error(error)
            
            results['files_modified_list'] = list(self.files_modified)
            results['files_created_list'] = list(self.files_created)
            
        except Exception as e:
            rays_ui.print_error(f"Critical error: {e}")
            rays_ui.print_warning("Rolling back all changes")
            self.rollback()
            results['success'] = False
            results['errors'].append(f"Critical error: {e}")
        
        return results
    
    def _apply_edit_batch(self, edits: List[dict], results: dict):
        """Apply a batch of edits (blocking or existing symbols)."""
        for edit in edits:
            file_path = edit.get('file', 'unknown')
            symbol_name = edit.get('symbol_name', 'unknown')
            num_edits = len(edit.get('edits', []))
            
            # ASK FOR APPROVAL IF NOT AUTONOMOUS
            if self.execution_mode != "autonomous":
                msg = f"Edit {file_path} ({num_edits} changes for {symbol_name})?"
                if not rays_ui.ask_approval(msg):
                    rays_ui.print_warning(f"Skipping edits for {file_path}")
                    continue

            # Log the model edit action
            rays_ui.log_model_interaction("Model Generate", f"Applying {num_edits} code edits to {file_path} (Symbol: {symbol_name})")

            # Use the "Update" action for existing files
            rays_ui.print_file_modified(file_path, num_edits)
            
            try:
                success = self._apply_single_edit(file_path, edit)
                if success:
                    results['edits_applied'] += len(edit.get('edits', []))
                else:
                    results['errors'].append(f"Partial failure in {file_path}:{symbol_name}")
                    
            except Exception as e:
                rays_ui.print_error(f"Error in {file_path}:{symbol_name} — {e}")
                results['errors'].append(f"Error in {file_path}:{symbol_name} - {e}")
        
        results['files_modified'] = len(self.files_modified)

    def _apply_single_edit(self, file_path: str, edit: dict) -> bool:
        """Apply a single edit with validation."""
        full_path = self.codebase_root / file_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Backup file first
        self._backup_file(full_path)
        
        # Read current content
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        all_success = True
        
        # Apply each SEARCH/REPLACE block with validation
        for edit_block in edit.get('edits', []):
            search = edit_block.get('search', '')
            replace = edit_block.get('replace', '')
            reason = edit_block.get('reason', '')
            
            # Validate before applying
            is_valid, error = EditValidator.validate_search_replace(search, replace, content)
            
            if not is_valid:
                rays_ui.print_warning(f"Validation failed: {error}")
                all_success = False
                continue
            
            # Apply edit
            content = content.replace(search, replace, 1)
            rays_ui.print_diff(edit.get('file', ''), search, replace, reason)
        
        # Validate imports
        imports_to_add = edit.get('imports_to_add', [])
        if imports_to_add:
            is_valid, error = EditValidator.validate_imports(imports_to_add)
            if not is_valid:
                rays_ui.print_warning(f"Invalid imports: {error}")
                all_success = False
                imports_to_add = []
        
        # Handle imports
        imports_to_remove = edit.get('imports_to_remove', [])
        if imports_to_add or imports_to_remove:
            content = self._handle_imports(content, imports_to_add, imports_to_remove)
        
        # Validate Python syntax (if .py file)
        if file_path.endswith('.py'):
            is_valid, error = EditValidator.validate_python_syntax(content)
            if not is_valid:
                rays_ui.print_warning(f"Syntax error in result: {error} — rolling back file")
                content = original_content  # Revert
                all_success = False
        
        # Write back if changes were made and valid
        if content != original_content:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            self.files_modified.add(file_path)
            self.changes_made.append({
                'type': 'edit',
                'file': file_path,
                'backup': self._get_backup_path(full_path)
            })
        
        return all_success

    def _normalize_whitespace(self, text: str) -> str:
        """Normalize whitespace for fuzzy matching."""
        # Replace multiple spaces/tabs with single space
        text = re.sub(r'[ \t]+', ' ', text)
        # Remove trailing whitespace from lines
        text = '\n'.join(line.rstrip() for line in text.split('\n'))
        return text
    
    def _handle_imports(self, content: str, to_add: List[str], 
                       to_remove: List[str]) -> str:
        """Add and remove imports from file content."""
        lines = content.split('\n')
        
        # Find where imports section ends
        import_end_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(('import ', 'from ')):
                import_end_idx = i + 1
            elif stripped and not stripped.startswith('#'):
                # Found first non-import, non-comment line
                break
        
        # Remove imports
        for imp in to_remove:
            lines = [line for line in lines if imp not in line]
        
        # Add new imports
        if to_add:
            # Check if import already exists
            existing_imports = '\n'.join(lines[:import_end_idx])
            for imp in to_add:
                if imp not in existing_imports:
                    lines.insert(import_end_idx, imp)
                    import_end_idx += 1
        
        return '\n'.join(lines)
    
    def _apply_new_symbols(self, new_symbols: List[dict], results: dict):
        """Insert new symbols into existing files."""
        for symbol_creation in new_symbols:
            symbol_name = symbol_creation.get('symbol_name', 'unknown')
            file_path = symbol_creation.get('file', 'unknown')
            insertion_line = symbol_creation.get('insertion_line', 0)
            code = symbol_creation.get('code', '')

            # Ask explicit permission for insertion edits on existing files in ask mode.
            if self.execution_mode != "autonomous":
                msg = f"Insert symbol {symbol_name} into {file_path} at line {insertion_line}?"
                if not rays_ui.ask_approval(msg):
                    rays_ui.print_warning(f"Skipping symbol insertion for {symbol_name} in {file_path}")
                    continue
            
            # This is an insertion into an existing file, so show as Update
            rays_ui.print_file_modified(file_path, 1)
            
            try:
                success = self._insert_code_at_line(
                    file_path,
                    insertion_line,
                    code,
                    symbol_creation.get('imports_to_add', [])
                )
                
                if success:
                    # Show the insertion as a diff for consistency in current style
                    rays_ui.print_diff(file_path, "", code, f"Inserted symbol: {symbol_name}")
                
                if success:
                    results['edits_applied'] += 1
                    rays_ui.print_step(f"Inserted {symbol_name}")
                else:
                    rays_ui.print_warning(f"Insertion failed for {symbol_name}")
                    results['errors'].append(f"Failed to insert {symbol_name} in {file_path}")
                    
            except Exception as e:
                rays_ui.print_error(f"Error inserting {symbol_name}: {e}")
                results['errors'].append(f"Error inserting {symbol_name}: {e}")
        
        results['files_modified'] = len(self.files_modified)
    
    def _insert_code_at_line(self, file_path: str, line_num: int, 
                            code: str, imports: List[str]) -> bool:
        """Insert code at specific line number."""
        full_path = self.codebase_root / file_path
        
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Backup file
        self._backup_file(full_path)
        
        # Read content
        with open(full_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Insert code at specified line
        if line_num == 0 or line_num > len(lines):
            # Insert at end
            lines.append('\n\n' + code + '\n')
        else:
            # Insert at specific line
            lines.insert(line_num, '\n' + code + '\n')
        
        # Handle imports
        content = ''.join(lines)
        if imports:
            content = self._handle_imports(content, imports, [])
        
        # Write back
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.files_modified.add(file_path)
        self.changes_made.append({
            'type': 'insert',
            'file': file_path,
            'backup': self._get_backup_path(full_path)
        })
        
        return True
    
    def _create_new_files(self, new_files: List[dict], results: dict):
        """Create new files with generated content."""
        for file_creation in new_files:
            file_name = file_creation.get('file_name', 'unknown')
            full_path = file_creation.get('full_path', f"src/{file_name}")
            content = file_creation.get('file_content', '')
            
            rays_ui.print_info(f"Creating file: {full_path}")

            # Ask explicit permission for EACH new file creation in ask mode.
            if self.execution_mode != "autonomous":
                if not rays_ui.ask_approval(f"Create new file {full_path}?"):
                    rays_ui.print_warning(f"Skipping file creation: {full_path}")
                    continue
            
            try:
                success = self._create_file(full_path, content)
                
                if success:
                    results['files_created'] += 1
                    rays_ui.print_file_created(full_path, content)
                else:
                    rays_ui.print_warning(f"Failed to create {full_path}")
                    results['errors'].append(f"Failed to create {full_path}")
                    
            except Exception as e:
                rays_ui.print_error(f"Error creating {full_path}: {e}")
                results['errors'].append(f"Error creating {full_path}: {e}")
    
    def _create_file(self, file_path: str, content: str) -> bool:
        """Create a new file with content."""
        full_path = self.codebase_root / file_path
        
        # Create parent directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)
        if full_path.exists():
            rays_ui.print_warning("File already exists, backing up")
            self._backup_file(full_path)
        
        # Write content
        if full_path.is_dir():
            rays_ui.print_warning(f"Target path {file_path} is a directory. Skipping.")
            return False

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.files_created.add(file_path)
        self.changes_made.append({
            'type': 'create',
            'file': file_path
        })
        
        return True
    
    def _backup_file(self, file_path: Path):
        """Create a backup of a file before modifying."""
        if not file_path.exists():
            return
        
        # Create backup path maintaining directory structure
        relative_path = file_path.relative_to(self.codebase_root)
        backup_path = self.backup_dir / relative_path
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Copy file to backup
        shutil.copy2(file_path, backup_path)
    
    def _get_backup_path(self, file_path: Path) -> Path:
        """Get backup path for a file."""
        relative_path = file_path.relative_to(self.codebase_root)
        return self.backup_dir / relative_path
    
    def rollback(self):
        """Rollback all changes made in this session."""
        rays_ui.print_phase("Rolling back changes")
        
        # Restore backed up files
        for change in reversed(self.changes_made):
            try:
                if change['type'] == 'create':
                    # Delete created file
                    file_path = self.codebase_root / change['file']
                    if file_path.exists():
                        file_path.unlink()
                        rays_ui.print_step(f"Deleted: {change['file']}")
                
                elif change['type'] in ['edit', 'insert']:
                    # Restore from backup
                    backup_path = change['backup']
                    file_path = self.codebase_root / change['file']
                    
                    if backup_path.exists():
                        shutil.copy2(backup_path, file_path)
                        rays_ui.print_step(f"Restored: {change['file']}")
            except Exception as e:
                rays_ui.print_error(f"Error rolling back {change['file']}: {e}")
        
        rays_ui.print_step(f"Rollback complete. Backups at: {self.backup_dir}")
    
    def commit_changes(self):
        """Commit changes (delete backups)."""
        rays_ui.print_step(f"Changes committed. Backups at: {self.backup_dir}")

