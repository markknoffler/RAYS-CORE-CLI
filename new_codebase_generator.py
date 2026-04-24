import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from ai_client import AIClient
from file_skeleton import FileSkeletonGenerator

class NewCodebaseGenerator:
    """
    Iteratively generates a new codebase file by file.
    Maintains a context of previously generated file skeletons to ensure consistency.
    """
    def __init__(self, codebase_root: Path, rays_dir: Path, ai_client: AIClient, config: Dict[str, Any], execution_mode: str = 'ask'):
        self.codebase_root = codebase_root
        self.rays_dir = rays_dir
        self.ai_client = ai_client
        self.config = config
        self.execution_mode = execution_mode
        self.prompts = config.get('new_codebase_prompts', {})
        self.skeleton_gen = FileSkeletonGenerator(self.codebase_root, self.rays_dir)

    def generate_files(self, plan: Dict[str, Any], user_prompt: str) -> List[Dict[str, Any]]:
        """
        Iteratively generate each file in the plan order.
        """
        created_files = []
        previous_files_context = ""

        # Sort files by 'order' if available, otherwise use index
        files_to_generate = plan.get('files', [])
        files_to_generate.sort(key=lambda x: x.get('order', 0))

        for i, file_info in enumerate(files_to_generate):
            file_path = file_info.get('file_path')
            
            # ASK FOR APPROVAL IF NOT AUTONOMOUS
            import rays_ui
            if self.execution_mode != "autonomous":
                if not rays_ui.ask_approval(f"Create project file {file_path}?"):
                    rays_ui.print_warning(f"Skipping generation of {file_path}")
                    continue

            # Format symbols details for this specific file
            symbols_details = ""
            for sym in file_info.get('symbols', []):
                symbols_details += f"- {sym['name']} ({sym['type']}): {sym['signature']} — {sym['purpose']}\n"
                if sym.get('dependencies'):
                    symbols_details += f"  Depends on: {', '.join(sym['dependencies'])}\n"

            # Build iterative generation prompt
            prompt = self.prompts['generate_file'].format(
                user_prompt=user_prompt,
                plan_summary=plan.get('summary', 'N/A'),
                file_path=file_path,
                language=file_info.get('language', 'Unknown'),
                purpose=file_info.get('purpose', 'N/A'),
                symbols_details=symbols_details,
                previous_files_context=previous_files_context if previous_files_context else "None (First file)."
            )

            system_prompt = self.config.get('task_analysis_prompts', {}).get('system_instructions', '')
            
            # Generate code, then strip markdown fences via shared extractor.
            raw_response = self.ai_client.generate_text(prompt, system_prompt)
            language_hint = str(file_info.get('language', 'python')).lower()
            if not language_hint:
                language_hint = "python"
            code = self.ai_client.extract_code_block(raw_response or "", language=language_hint).strip()

            if not code:
                import rays_ui
                rays_ui.print_warning(f"Model returned empty code for {file_path}; skipping file")
                continue

            # Write the file
            full_path = self.codebase_root / file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(code)

            # Show creation preview with green added lines (consistent with edit pipeline visuals)
            rays_ui.print_file_created(file_path, code)
            

            # Extract skeleton for next iterations
            file_skeleton = self.skeleton_gen.get_file_skeleton(file_path, include_docstrings=False)
            
            # Append a simplified summary of this file to the context for next iterations
            # We only really need imports and signatures
            previous_files_context += f"\n--- Already Created: {file_path} ---\n{file_skeleton}\n"

            created_files.append({
                'file_path': file_path,
                'symbols': file_info.get('symbols', [])
            })

        return created_files
