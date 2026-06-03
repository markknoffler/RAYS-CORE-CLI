import os
import json
import yaml
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from .ai_client import AIClient
from . import rays_ui

class SkillsOrchestrator:
    def __init__(self, ai_client: AIClient, config: Dict[str, Any], codebase_root: Path):
        self.ai_client = ai_client
        self.config = config
        self.codebase_root = Path(codebase_root).resolve()
        self.local_skills_dir = self.codebase_root / "skills"
        self.global_skills_dir = Path.home() / ".rays" / "skills"
        self.prompts = config.get('skills_orchestrator_prompts', {})

    def discover_skills(self) -> List[Dict[str, str]]:
        """Scan both local and global skills directories."""
        skills = []
        seen_names = set()

        for skills_dir in [self.local_skills_dir, self.global_skills_dir]:
            if not skills_dir.exists():
                continue

            for skill_path in skills_dir.iterdir():
                if skill_path.is_dir():
                    skill_name = skill_path.name
                    if skill_name in seen_names:
                        continue
                        
                    skill_md = skill_path / "SKILL.md"
                    if skill_md.exists():
                        try:
                            content = skill_md.read_text()
                            # Simple frontmatter extraction
                            if content.startswith('---'):
                                parts = content.split('---', 2)
                                if len(parts) >= 3:
                                    frontmatter = yaml.safe_load(parts[1])
                                    skills.append({
                                        "name": frontmatter.get("name", skill_name),
                                        "description": frontmatter.get("description", ""),
                                        "path": str(skill_md),
                                        "root": str(skill_path)
                                    })
                            else:
                                skills.append({
                                    "name": skill_name,
                                    "description": content.split('\n')[0].strip('# '),
                                    "path": str(skill_md),
                                    "root": str(skill_path)
                                })
                            seen_names.add(skill_name)
                        except Exception as e:
                            rays_ui.print_warning(f"Failed to read skill at {skill_path}: {e}")
        return skills

    def run(self, user_prompt: str) -> Dict[str, Any]:
        """Main orchestration loop with re-planning support."""
        rays_ui.print_phase("Skills Orchestration")
        
        cumulative_history = []
        max_loops = 3
        
        for loop_idx in range(max_loops):
            if loop_idx > 0:
                rays_ui.print_sub_phase(f"Re-planning Loop {loop_idx + 1}")

            skills_list = self.discover_skills()
            
            # 1. Identify required skills
            required_skills_data = self._identify_required_skills(user_prompt, skills_list, cumulative_history)
            required_skills = required_skills_data.get('required_skills', [])
            reasoning = required_skills_data.get('reasoning', 'No reasoning provided.')
            
            if reasoning:
                rays_ui.print_info(f"AI Reasoning: {reasoning}")
            
            if required_skills:
                rays_ui.print_info(f"Required Skills: {', '.join(required_skills)}")
            elif loop_idx == 0:
                rays_ui.print_info("No skills identified for this task.")

            # 2. Generate execution plan
            plan_data = self._generate_plan(user_prompt, required_skills, cumulative_history)
            summary = plan_data.get('summary', 'No summary provided.')
            
            if loop_idx == 0 or plan_data.get('plan'):
                rays_ui.print_box(f"Orchestrator Summary (Loop {loop_idx + 1})", summary, rays_ui.C_LAVENDER)

            # Filter plan to only include existing skills
            discovered_map = {s['name']: s for s in skills_list}
            raw_plan = plan_data.get('plan', [])
            plan = [step for step in raw_plan if step.get('skill') in discovered_map]

            if not plan:
                if raw_plan:
                    rays_ui.print_warning("The orchestrator proposed skills that are not available.")
                if loop_idx == 0:
                    rays_ui.print_info("No valid skill execution steps found. Done.")
                    return {"status": "completed", "summary": summary, "history": cumulative_history}
                else:
                    break

            # 3. Execute skills sequentially
            for i, step in enumerate(plan):
                skill_name = step.get('skill')
                reason = step.get('reason')
                skill_info = discovered_map.get(skill_name)
                
                rays_ui.print_sub_phase(f"Step {i+1}/{len(plan)}: {skill_name}")
                rays_ui.print_info(f"Reason: {reason}")
                
                skill_result = self._execute_skill(skill_info, reason, user_prompt, plan, cumulative_history)
                cumulative_history.append({
                    "skill": skill_name,
                    "reason": reason,
                    "summary": skill_result
                })

            # 4. Final completion check
            completion_data = self._evaluate_completion(user_prompt, cumulative_history)
            if completion_data.get('is_complete', True):
                rays_ui.print_info("Task verified as complete.")
                break
            else:
                rays_ui.print_box("Validation Feedback", completion_data.get('reasoning', 'Task not fully completed.'), rays_ui.C_RED)
                rays_ui.print_info("Continuing to next orchestration loop...")

        return {
            "status": "completed",
            "history": cumulative_history,
            "summary": "Final orchestration cycle finished."
        }

    def _identify_required_skills(self, user_prompt: str, skills_list: List[Dict[str, str]], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = self.prompts['select_required_skills'].format(
            user_prompt=user_prompt,
            skills_list=json.dumps(skills_list, indent=2),
            execution_history=json.dumps(history, indent=2)
        )
        return self.ai_client.generate_json(prompt)

    def _generate_plan(self, user_prompt: str, required_skills: List[str], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = self.prompts['generate_execution_plan'].format(
            user_prompt=user_prompt,
            required_skills=json.dumps(required_skills),
            execution_history=json.dumps(history, indent=2)
        )
        return self.ai_client.generate_json(prompt)

    def _execute_skill(self, skill_info: Dict[str, Any], reason: str, user_prompt: str, plan: List[Dict[str, Any]], previous_results: List[Dict[str, Any]]) -> str:
        skill_name = skill_info['name']
        skill_root = skill_info['root']
        skill_md_path = Path(skill_info['path'])
        
        if not skill_md_path.exists():
            return f"Error: Skill definition for '{skill_name}' not found."
            
        skill_md_content = skill_md_path.read_text()

        local_history = []
        max_steps = 15
        
        for _ in range(max_steps):
            prompt = self.prompts['execute_skill_step'].format(
                user_prompt=user_prompt,
                overall_plan=json.dumps(plan, indent=2),
                skill_name=skill_name,
                skill_root=skill_root,
                workspace_root=str(self.codebase_root),
                reason=reason,
                skill_md=skill_md_content,
                previous_results=json.dumps(previous_results, indent=2),
                local_history=json.dumps(local_history, indent=2)
            )
            
            response = self.ai_client.generate_json(prompt)
            thought = response.get('thought', '')
            status = response.get('status', 'running')
            tool_call = response.get('tool_call')

            if thought:
                rays_ui.print_step(f"Sub-agent thought: {thought}")

            if tool_call:
                result = self._dispatch_tool(tool_call)
                local_history.append({
                    "tool_call": tool_call,
                    "result": result
                })
            
            if status == 'completed':
                return response.get('summary', 'Skill execution completed.')

        return "Skill execution timed out."

    def _dispatch_tool(self, tool_call: Dict[str, Any]) -> str:
        name = tool_call.get('name')
        args = tool_call.get('arguments', {})
        
        if not name:
            return "Error: Tool call missing 'name'."
            
        if name == 'run_shell_command':
            return self._run_shell_command(args.get('command'))
        elif name == 'write_file':
            return self._write_file(args.get('path'), args.get('content'))
        elif name == 'patch_file':
            return self._patch_file(args.get('path'), args.get('search'), args.get('replace'))
        elif name == 'read_file':
            return self._read_file(args.get('path'))
        elif name == 'list_directory':
            return self._list_directory(args.get('path', '.'))
        else:
            return f"Error: Tool '{name}' is not allowed in this mode. Only run_shell_command, write_file, patch_file, read_file, and list_directory are permitted."

    def _run_shell_command(self, command: str) -> str:
        if not command:
            return "Error: 'command' argument is required for run_shell_command"
        rays_ui.print_step(f"Executing: {command}")
        try:
            # Explicitly run in codebase_root
            result = subprocess.run(command, shell=True, capture_output=True, text=True, cwd=self.codebase_root)
            output = result.stdout + result.stderr
            return output if output else "Command executed successfully with no output."
        except Exception as e:
            return f"Error executing command: {e}"

    def _write_file(self, path: str, content: str) -> str:
        if not path:
            return "Error: 'path' argument is required for write_file"
        full_path = self.codebase_root / path
        rays_ui.print_step(f"Writing file: {path}")
        try:
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text(content or "")
            return f"File written successfully: {path}"
        except Exception as e:
            return f"Error writing file: {e}"

    def _patch_file(self, path: str, search: str, replace: str) -> str:
        if not path:
            return "Error: 'path' argument is required for patch_file"
        full_path = self.codebase_root / path
        rays_ui.print_step(f"Patching file: {path}")
        try:
            if not full_path.exists():
                return f"Error: File does not exist: {path}"
            content = full_path.read_text()
            if not search:
                return "Error: 'search' block is required for patch_file"
            if search not in content:
                return f"Error: Search block not found in {path}"
            
            new_content = content.replace(search, replace or "", 1)
            full_path.write_text(new_content)
            return f"File patched successfully: {path}"
        except Exception as e:
            return f"Error patching file: {e}"

    def _read_file(self, path: str) -> str:
        if not path:
            return "Error: 'path' argument is required for read_file"
        full_path = self.codebase_root / path
        try:
            if not full_path.exists():
                return f"Error: File does not exist: {path}"
            return full_path.read_text()
        except Exception as e:
            return f"Error reading file: {e}"

    def _list_directory(self, path: str) -> str:
        path = path or "."
        full_path = self.codebase_root / path
        try:
            if not full_path.exists():
                return f"Error: Directory does not exist: {path}"
            files = os.listdir(full_path)
            return "\n".join(files)
        except Exception as e:
            return f"Error listing directory: {e}"

    def _evaluate_completion(self, user_prompt: str, execution_history: List[Dict[str, Any]]) -> Dict[str, Any]:
        prompt = self.prompts['check_completion'].format(
            user_prompt=user_prompt,
            execution_history=json.dumps(execution_history, indent=2)
        )
        return self.ai_client.generate_json(prompt)
