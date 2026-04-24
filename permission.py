import msgpack
import chromadb
from pathlib import Path
from ai_client import AIClient

class PermissionManager:
    def __init__(self, ai_client: AIClient, config: dict):
        self.ai_client = ai_client
        self.config = config

    def generate_permission_slip(self, final_selection: dict, explicit_mentions: dict) -> dict:
        """
        Step 6: Generate Permission Slip
        
        Creates a permission slip that defines what the system is allowed to modify.
        
        Initial rules:
            pass
        - Symbols to edit: From final_affected_symbols
        - Files to edit: 0 (unless explicitly mentioned)
        - Files to create: 0 (unless explicitly mentioned)
        - Symbols to create: 0 (unless explicitly mentioned)
        - Max lines to edit: 25 (hardcoded for now)
        
        Args:
            final_selection: Final symbol selection results
            explicit_mentions: Explicit mentions from user
        
        Returns:
            Permission slip dictionary
        """
        
        # Get symbols to edit from final selection
        symbols_to_edit = final_selection['affected_symbols']
        
        # Extract unique file paths from symbols to edit
        files_from_symbols = set()
        for symbol in symbols_to_edit:
            if symbol.get('file_path'):
                files_from_symbols.add(symbol['file_path'])
        
        # Initialize counters
        files_to_edit = set()
        files_to_create = set()
        symbols_to_create = []
        lines_to_edit_count = 0
        
        # Check explicit mentions for files to edit
        if explicit_mentions.get('explicit_file_edits'):
            for file_edit in explicit_mentions['explicit_file_edits']:
                file_path = file_edit.get('file')
                action = file_edit.get('action', '')
                
                if file_path:
                    if action == 'create':
                        files_to_create.add(file_path)
                    elif action in ['modify', 'edit']:
                        files_to_edit.add(file_path)
        
        # Check explicit mentions for symbols to edit/create
        if explicit_mentions.get('explicit_symbol_edits'):
            for symbol_edit in explicit_mentions['explicit_symbol_edits']:
                file_path = symbol_edit.get('file')
                if file_path:
                    files_to_edit.add(file_path)
        
        # Check explicit mentions for line edits
        if explicit_mentions.get('explicit_line_edits'):
            for line_edit in explicit_mentions['explicit_line_edits']:
                file_path = line_edit.get('file')
                if file_path:
                    files_to_edit.add(file_path)
                
                # Count lines if range is specified
                line_range = line_edit.get('line_range')
                if line_range:
                    start = line_range.get('start', 0)
                    end = line_range.get('end', 0)
                    lines_to_edit_count += max(0, end - start + 1)
                elif line_edit.get('line'):
                    lines_to_edit_count += 1
        
        # Check new creations
        if explicit_mentions.get('new_creations'):
            for creation in explicit_mentions['new_creations']:
                creation_type = creation.get('type', '')
                name = creation.get('name', '')
                location = creation.get('location', '')
                
                if creation_type == 'file':
                    if name:
                        files_to_create.add(name)
                elif creation_type in ['symbol', 'function', 'class', 'component']:
                    symbols_to_create.append({
                        'type': creation_type,
                        'name': name,
                        'location': location,
                        'details': creation.get('details', '')
                    })
        
        # Build permission slip
        permission_slip = {
            'symbols_allowed_to_edit': symbols_to_edit,
            'num_symbols_to_edit': len(symbols_to_edit),
            
            'files_allowed_to_edit': list(files_to_edit),
            'num_files_to_edit': len(files_to_edit),
            
            'files_allowed_to_create': list(files_to_create),
            'num_files_to_create': len(files_to_create),
            
            'symbols_allowed_to_create': symbols_to_create,
            'num_symbols_to_create': len(symbols_to_create),
            
            'max_lines_to_edit': 25,
            'explicit_lines_mentioned': lines_to_edit_count,
            
            'has_file_creation_request': len(files_to_create) > 0,
            'has_symbol_creation_request': len(symbols_to_create) > 0,
            'has_explicit_line_edits': lines_to_edit_count > 0,
            
            'files_containing_affected_symbols': list(files_from_symbols)
        }
        
        # Print summary
        
        if permission_slip['files_allowed_to_edit']:
            for f in permission_slip['files_allowed_to_edit']:
                pass
        
        if permission_slip['files_allowed_to_create']:
            for f in permission_slip['files_allowed_to_create']:
                pass
        
        if permission_slip['symbols_allowed_to_create']:
            for s in permission_slip['symbols_allowed_to_create']:
                pass
        
        
        return permission_slip

    def update_permission_slip(self, current_slip: dict, additional_perms: dict) -> dict:
        """
        Update permission slip with additional requested permissions.
        
        Args:
            current_slip: Current permission slip
            additional_perms: Additional permissions requested by AI
        
        Returns:
            Updated permission slip
        """
        updated_slip = current_slip.copy()
        
        # Update files to edit
        if additional_perms.get('files_to_edit', 0) > 0:
            new_files = additional_perms.get('files_to_edit_names', [])
            updated_slip['files_allowed_to_edit'].extend(new_files)
            updated_slip['num_files_to_edit'] += additional_perms['files_to_edit']
        
        # Update files to create
        if additional_perms.get('files_to_create', 0) > 0:
            new_files_details = additional_perms.get('files_to_create_details', [])
            for file_detail in new_files_details:
                updated_slip['files_allowed_to_create'].append(file_detail['name'])
            updated_slip['num_files_to_create'] += additional_perms['files_to_create']
        
        # Update symbols to create
        if additional_perms.get('symbols_to_create', 0) > 0:
            new_symbols_details = additional_perms.get('symbols_to_create_details', [])
            for symbol_detail in new_symbols_details:
                updated_slip['symbols_allowed_to_create'].append({
                    'type': symbol_detail.get('type', 'unknown'),
                    'name': symbol_detail.get('name', ''),
                    'location': '',
                    'details': symbol_detail.get('purpose', '')
                })
            updated_slip['num_symbols_to_create'] += additional_perms['symbols_to_create']
        
        # Update max lines
        if additional_perms.get('additional_lines', 0) > 0:
            updated_slip['max_lines_to_edit'] += additional_perms['additional_lines']
        
        return updated_slip

    def check_permission_sufficiency(self, user_prompt: str, analysis: dict, 
                                     permission_slip: dict, symbols_with_code: list,
                                     previous_summaries: str = "None") -> dict:
        """
        Check if current permissions are sufficient for implementation.
        Check if current permissions are sufficient for implementation.
        
        Args:
            user_prompt: User's request
            analysis: Task analysis
            permission_slip: Current permission slip
            symbols_with_code: Affected symbols with code
            previous_summaries: Placeholder for previous context
        
        Returns:
            Dict with status and optional additional permissions
        """
        
        # Format task summary
        task_summary = (
            f"Type: {analysis.get('task_type', 'unknown')}, "
            f"SDS: {analysis.get('sds_score', 0):.2f}, "
            f"IES: {analysis.get('ies_score', 0):.2f}"
        )
        
        # Format affected symbols with code
        symbols_text = ""
        for idx, symbol in enumerate(symbols_with_code, 1):
            symbols_text += f"\n--- Symbol {idx}: {symbol['symbol_name']} ---\n"
            symbols_text += f"Type: {symbol['symbol_type']}\n"
            symbols_text += f"File: {symbol['file_path']} (lines {symbol['start_line']}-{symbol['end_line']})\n"
            symbols_text += f"Code:\n```\n{symbol['code']}\n```\n"
        
        # Build prompt
        prompt_template = self.config['permission_planning_prompts']['check_permissions_sufficiency']
        prompt = prompt_template.format(
            user_prompt=user_prompt,
            task_summary=task_summary,
            previous_summaries=previous_summaries,
            num_symbols_to_edit=permission_slip['num_symbols_to_edit'],
            num_files_to_edit=permission_slip['num_files_to_edit'],
            num_files_to_create=permission_slip['num_files_to_create'],
            num_symbols_to_create=permission_slip['num_symbols_to_create'],
            max_lines_to_edit=permission_slip['max_lines_to_edit'],
            affected_symbols_code=symbols_text
        )
        
        system_prompt = self.config['task_analysis_prompts']['system_instructions']
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            
            status = result.get('status', 'requesting_additional_permissions')
            reasoning = result.get('reasoning', '')
            additional_perms = result.get('additional_permissions')
            
            
            if additional_perms and status == 'requesting_additional_permissions':
                if additional_perms.get('files_to_edit', 0) > 0:
                    pass
                if additional_perms.get('files_to_create', 0) > 0:
                    pass
                if additional_perms.get('symbols_to_create', 0) > 0:
                    pass
                if additional_perms.get('additional_lines', 0) > 0:
                    pass
            
            return result
            
        except Exception as e:
            # Silent fallback
            return {
                'status': 'allowed',
                'reasoning': 'Error during check, proceeding with current permissions',
                'additional_permissions': None
            }

    def negotiate_permissions(self, user_prompt: str, analysis: dict, 
                             permission_slip: dict, symbols_with_code: list,
                             max_iterations: int = 5) -> dict:
        """
        Negotiate permissions with AI until sufficient.
        
        Args:
            user_prompt: User's request
            analysis: Task analysis
            permission_slip: Initial permission slip
            symbols_with_code: Affected symbols with code
            max_iterations: Maximum negotiation rounds
        
        Returns:
            Final approved permission slip
        """
        
        current_slip = permission_slip.copy()
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Check if current permissions are sufficient
            check_result = self.check_permission_sufficiency(
                user_prompt,
                analysis,
                current_slip,
                symbols_with_code
            )
            
            status = check_result.get('status')
            
            if status == 'allowed':
                break
            
            elif status == 'requesting_additional_permissions':
                additional_perms = check_result.get('additional_permissions')
                
                if not additional_perms:
                    break
                
                # Update permission slip
                new_slip = self.update_permission_slip(current_slip, additional_perms)
                
                # Check if anything actually changed
                if new_slip == current_slip:
                    break
                
                current_slip = new_slip
                
            
            else:
                break
        
        if iteration >= max_iterations:
            pass
        
        
        return current_slip

    def negotiate_new_codebase_permissions(self, user_prompt: str, initial_permissions: dict) -> dict:
        """
        Ask model if user explicitly requested more files/symbols than initial limits for a new project.
        """
        
        prompt = self.config['new_codebase_prompts']['permission_negotiation'].format(
            user_prompt=user_prompt
        )
        system_prompt = self.config['task_analysis_prompts']['system_instructions']
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            additional_files = result.get('additional_files', 0)
            additional_symbols = result.get('additional_symbols', 0)
            reason = result.get('justification', 'No explicit request for more.')

            final = initial_permissions.copy()
            final['num_files_to_create'] += additional_files
            final['num_symbols_to_create'] += additional_symbols
            
            
            return final
        except Exception as e:
            return initial_permissions

