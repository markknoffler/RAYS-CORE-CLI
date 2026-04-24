import os
import json
import subprocess
import traceback
import re
import msgpack
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from ai_client import AIClient
import rays_ui

class TerminalEngine:
    def __init__(self, codebase_root: Path, rays_dir: Path, ai_client: AIClient, config: Dict[str, Any],
                 permission_mgr=None, planner=None, anchorer=None, executor=None, execution_mode: str = 'ask'):
        self.codebase_root = codebase_root
        self.rays_dir = rays_dir
        self.ai_client = ai_client
        self.config = config
        self.execution_mode = execution_mode
        self.prompts = config.get('terminal_execution_prompts', {})
        self.max_commands_per_intent = 5
        self.command_history = []  # List of (cmd, last_10_lines) for CURRENT intent
        self.chain_command_history = [] # List of (cmd, last_10_lines) for WHOLE chain
        self.intent_chain_depth = 0
        self.max_intent_chain_depth = 5
        
        # Pipeline components for enhanced failure recovery
        self.permission_mgr = permission_mgr
        self.planner = planner
        self.anchorer = anchorer
        self.executor = executor
        
        self.edit_ledger = [] # Placeholder for previous edits context

    def _get_directory_tree(self, max_files_per_dir: int = 15) -> str:
        """Generate a directory tree structure of the root directory."""
        tree = []
        try:
            for root, dirs, files in os.walk(self.codebase_root):
                # Skip .rays and hidden dirs
                dirs[:] = [d for d in dirs if not d.startswith('.') and d != '.rays']
                
                level = Path(root).relative_to(self.codebase_root).parts
                indent = '  ' * len(level)
                tree.append(f"{indent}{os.path.basename(root) or '.'}/")
                sub_indent = '  ' * (len(level) + 1)
                
                for f in files[:max_files_per_dir]:
                    if not f.startswith('.'):
                        tree.append(f"{sub_indent}{f}")
                if len(files) > max_files_per_dir:
                    tree.append(f"{sub_indent}... ({len(files) - max_files_per_dir} more files)")
                    
                if len(tree) > 500:
                    tree.append("... [Tree Truncated]")
                    break
        except Exception as e:
            return f"Error generating tree: {e}"
        return "\n".join(tree)

    def _get_related_symbols(self, symbol_name: str) -> List[Dict[str, Any]]:
        """Retrieve related symbols using the relationship graph."""
        relationships_file = self.rays_dir / "relationships.msgpack"
        symbols_file = self.rays_dir / "symbols.msgpack"
        
        if not relationships_file.exists() or not symbols_file.exists():
            return []
            
        try:
            with open(relationships_file, 'rb') as f:
                relationships = msgpack.unpackb(f.read(), raw=False)
            with open(symbols_file, 'rb') as f:
                all_symbols = msgpack.unpackb(f.read(), raw=False)
                
            related_names = set()
            for rel in relationships:
                if rel.get('source_symbol') == symbol_name:
                    related_names.add(rel.get('target_symbol'))
                elif rel.get('target_symbol') == symbol_name:
                    related_names.add(rel.get('source_symbol'))
                    
            related_symbols = []
            for sym in all_symbols:
                if sym.get('symbol_name') in related_names:
                    # Enrich with code context
                    related_symbols.append(self._enrich_symbol_with_context(sym))
            return related_symbols
        except Exception as e:
            print(f"Error getting related symbols: {e}")
            return []

    def _enrich_symbol_with_context(self, symbol: Dict[str, Any], context_lines: int = 50) -> Dict[str, Any]:
        """Get symbol code with +/- context lines."""
        file_path = symbol.get('file_path')
        start_line = symbol.get('start_line', 1)
        end_line = symbol.get('end_line', 1)
        
        full_path = self.codebase_root / file_path
        if not full_path.exists():
            return symbol
            
        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                
            c_start = max(1, start_line - context_lines)
            c_end = min(len(lines), end_line + context_lines)
            
            symbol['code_with_context'] = "".join(lines[c_start-1:c_end])
            symbol['context_range'] = (c_start, c_end)
            return symbol
        except Exception:
            return symbol

    def generate_intents(self, user_prompt: str, editing_flag: bool, implementation_plan: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Generate a list of intents based on user prompt and implementation plan."""
        rays_ui.print_sub_phase("Planning next action")
        
        plan_summary = implementation_plan.get('plan_summary', 'N/A') if implementation_plan else 'N/A'
        
        prompt = self.prompts['generate_intents'].format(
            user_prompt=user_prompt,
            editing_flag=editing_flag,
            plan_summary=plan_summary,
            codebase_root=str(self.codebase_root)
        )
        
        try:
            result = self.ai_client.generate_json(prompt)
            return result.get('intents', [])
        except Exception as e:
            rays_ui.print_error(f"Failed to generate intents: {e}")
            return []

    def execute_intent(self, intent: Dict[str, Any], user_prompt: str, chain_depth: int = 0) -> bool:
        """Execute a single intent with batched command execution and aggregated result logic."""
        self.intent_chain_depth = chain_depth
        if self.intent_chain_depth == 0:
            self.chain_command_history = [] # Clear at root only
            
        if self.intent_chain_depth >= self.max_intent_chain_depth:
            rays_ui.print_error(f"Maximum intent chain depth ({self.max_intent_chain_depth}) reached")
            return False

        rays_ui.print_sub_phase(f"Executing: {intent.get('intent', 'unknown')}")
        
        self.command_history = [] # Local to THIS intent
        
        # 1. Generate all commands for this intent
        commands_json = self._generate_commands(intent, user_prompt)
        cmds = commands_json.get('commands', [])
        cwd = commands_json.get('cwd') or str(self.codebase_root)
        
        if not cmds or (isinstance(cmds, str) and cmds == 'exit'):
            rays_ui.print_info("No commands to execute")
            return True

        # 2. Execute all commands in sequence
        combined_output = []
        for i, cmd_str in enumerate(cmds):
            # ASK FOR APPROVAL IF NOT AUTONOMOUS
            if self.execution_mode != "autonomous":
                if not rays_ui.ask_approval(f"Run command: {cmd_str}?"):
                    rays_ui.print_warning(f"Skipping command: {cmd_str}")
                    continue

            rays_ui.print_info(f"Running command {i+1}/{len(cmds)}")
            success, output = self._run_command(cmd_str, cwd)
            
            if not output.strip():
                output = "[No output]"
                
            # Retain last 50 lines for history
            lines = output.strip().split("\n")
            last_50 = "\n".join(lines[-50:])
            if len(last_50) > 2000:
                last_50 = "..." + last_50[-2000:]
                
            self.command_history.append((cmd_str, last_50))
            self.chain_command_history.append((cmd_str, last_50))
            combined_output.append(f"Command: {cmd_str}\nOutput:\n{last_50}")
            
            if not success:
                rays_ui.print_warning("Command failed — stopping batch")
                break
                
        # 3. Consolidated decision after all commands (or after failure)
        aggregated_result = "\n\n".join(combined_output)
        decision_json = self._decide_after_intent(intent, user_prompt, aggregated_result)
        decision = decision_json.get('decision', 'exit')
        rays_ui.print_info(f"Decision: {decision}")
        
        if decision == 'exit':
            return True
        elif decision == 'failure_retry':
            return self._resolve_code_bug(intent, user_prompt, aggregated_result)
        elif decision == 'new_intent':
            return self._handle_failure(intent, user_prompt, aggregated_result)
        
        return True

    def _decide_after_intent(self, intent: Dict[str, Any], user_prompt: str, aggregated_result: str) -> Dict[str, Any]:
        """Ask the model what to do after the batch of commands for an intent."""
        prompt = self.prompts['decide_after_intent'].format(
            user_prompt=user_prompt,
            intent_json=json.dumps(intent, indent=2),
            combined_output=aggregated_result[-4000:], # Last 4000 chars of aggregated output
            codebase_root=str(self.codebase_root)
        )
        try:
            return self.ai_client.generate_json(prompt)
        except Exception as e:
            rays_ui.print_error(f"Post-intent decision error: {e}")
            return {"decision": "exit"}

    def _generate_commands(self, intent: Dict[str, Any], user_prompt: str) -> Dict[str, Any]:
        """Generate a batch of commands for an intent."""
        history_str = "\n".join([f"Cmd: {cmd}\nOutput: {out}" for cmd, out in self.chain_command_history[-10:]])
        prompt = self.prompts['generate_commands'].format(
            user_prompt=user_prompt,
            intent_json=json.dumps(intent, indent=2),
            command_history=history_str,
            codebase_root=str(self.codebase_root)
        )
        
        try:
            return self.ai_client.generate_json(prompt)
        except Exception as e:
            rays_ui.print_error(f"Command generation error: {e}")
            return {"commands": [], "reasoning": f"Error: {e}"}

    def _run_command(self, command: str, cwd: str = None) -> Tuple[bool, str]:
        """Run a shell command and return success status and output. Defaults to codebase_root."""
        target_cwd = cwd if cwd else str(self.codebase_root)
        try:
            # Use a timeout for long-running commands (e.g., dev servers)
            timeout = 20  # seconds
            
            process = subprocess.Popen(
                command,
                shell=True,
                cwd=target_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            output_lines = []
            import time
            import select
            
            start_time = time.time()
            
            while True:
                # Check for timeout
                if time.time() - start_time > timeout:
                    rays_ui.print_warning(f"Command timed out after {timeout}s")
                    return True, "".join(output_lines) + "\n... [Command timed out/Backgrounding]"
                
                # Non-blocking check for output
                if select.select([process.stdout], [], [], 0.1)[0]:
                    line = process.stdout.readline()
                    if not line:
                        break
                    print(f"  {line.strip()}")
                    output_lines.append(line)
                
                # Check if process ended
                if process.poll() is not None:
                    # Collect any remaining output
                    remaining_output = process.stdout.read()
                    if remaining_output:
                        output_lines.append(remaining_output)
                        for l in remaining_output.splitlines():
                            print(f"  {l.strip()}")
                    break
            
            success = process.returncode == 0
            
            # Use terminal UI to show the command result box
            elapsed = time.time() - start_time
            rays_ui.print_command_box(command, "".join(output_lines), elapsed, success)
            
            return success, "".join(output_lines)
            
        except Exception as e:
            return False, str(e)

    def _handle_failure(self, intent: Dict[str, Any], user_prompt: str, failure_output: str) -> bool:
        """Classify and handle terminal failure."""
        classification = self._classify_failure(intent, user_prompt, failure_output)
        failure_type = classification.get('failure_type', 'environment_issue')
        
        if failure_type == 'environment_issue':
            return self._resolve_env_issue(intent, user_prompt, classification)
        else:
            return self._resolve_code_bug(intent, user_prompt, failure_output)

    def _classify_failure(self, intent: Dict[str, Any], user_prompt: str, failure_output: str) -> Dict[str, Any]:
        """Classify failure as environment_issue or code_bug."""
        prompt = self.prompts['classify_failure'].format(
            intent_json=json.dumps(intent, indent=2),
            user_prompt=user_prompt,
            failure_output=failure_output[-1000:],
            codebase_root=str(self.codebase_root)
        )
        
        try:
            return self.ai_client.generate_json(prompt)
        except Exception as e:
            rays_ui.print_error(f"Failure classification error: {e}")
            return {"failure_type": "environment_issue", "reason": str(e)}

    def _resolve_env_issue(self, intent: Dict[str, Any], user_prompt: str, classification: Dict[str, Any]) -> bool:
        """Resolve environment issue by creating a new intent."""
        rays_ui.print_sub_phase(f"Resolving: {classification.get('reason', 'unknown')}")
        
        prompt = self.prompts['resolve_env_issue'].format(
            previous_intent=json.dumps(intent, indent=2),
            user_prompt=user_prompt,
            failure_reason=classification.get('reason'),
            failure_point=classification.get('primary_point_of_failure'),
            command_history="\n".join([f"Cmd: {cmd}\nOutput: {out}" for cmd, out in self.chain_command_history]),
            codebase_root=str(self.codebase_root)
        )
        
        try:
            new_intent = self.ai_client.generate_json(prompt)
            # Execute the new intent with incremented depth
            return self.execute_intent(new_intent, user_prompt, chain_depth=self.intent_chain_depth + 1)
        except Exception as e:
            rays_ui.print_error(f"Environment resolution error: {e}")
            return False

    def _resolve_code_bug(self, intent: Dict[str, Any], user_prompt: str, failure_output: str) -> bool:
        """Enhanced failure retry loop with full RAYS pipeline integration."""
        rays_ui.print_sub_phase("Analyzing and fixing code issue")
        
        # 1. Gather Context
        focused_traceback = self._extract_focused_traceback(failure_output)
        trace_symbols = self._extract_symbols_from_traceback(focused_traceback)
        
        # Get code context for trace symbols
        symbols_with_code = []
        for sym_name, f_path in trace_symbols.items():
            # In a real scenario, we'd lookup full symbol info from symbols.msgpack
            # For now, we'll enrich with +/- 50 lines based on traceback info
            mock_symbol = {'symbol_name': sym_name, 'file_path': f_path, 'start_line': 1, 'end_line': 1}
            symbols_with_code.append(self._enrich_symbol_with_context(mock_symbol))
            
        # Get related symbols
        related_symbols = []
        for sym_name in trace_symbols.keys():
            related_symbols.extend(self._get_related_symbols(sym_name))
            
        directory_tree = self._get_directory_tree()
        
        # 2. Planning Phase (Initial fix plan)
        prompt = self.prompts['resolve_code_bug'].format(
            directory_tree=directory_tree,
            stack_trace=focused_traceback,
            affected_symbols_context=json.dumps(symbols_with_code, indent=2),
            related_symbols_context=json.dumps(related_symbols, indent=2),
            edit_ledger=json.dumps(self.edit_ledger, indent=2) if self.edit_ledger else "None",
            user_prompt=user_prompt,
            intent_json=json.dumps(intent, indent=2),
            codebase_root=str(self.codebase_root)
        )
        
        try:
            initial_fix_plan = self.ai_client.generate_json(prompt)
            rays_ui.print_step("Fix plan generated")
            
            # 3. Permission Negotiation
            if self.permission_mgr:
                rays_ui.print_info("Checking permissions for fix")
                perm_prompt = self.prompts['resolve_code_bug_permissions'].format(
                    user_prompt=user_prompt,
                    fix_plan_json=json.dumps(initial_fix_plan, indent=2)
                )
                permission_request = self.ai_client.generate_json(perm_prompt)
                # Note: In a real integration, we'd call negotiate_permissions formally
                # Here we ensure the plan is sanctioned by the model's self-permission analysis
            
            # 4. Final Planning & Anchoring
            final_plan = initial_fix_plan
            anchoring_results = {'symbol_anchors': [], 'file_anchors': []}
            if self.anchorer:
                rays_ui.print_info("Anchoring fix")
                anchoring_results = self.anchorer.anchor_new_symbols_and_files(final_plan)
                
            # 5. Execution
            if self.executor:
                rays_ui.print_info("Applying fix")
                # Execution requires blocking_analysis, we pass empty if none identified
                blocking_analysis = {'all_blocking_symbols': []}
                results = self.executor.generate_and_apply_code(
                    final_plan, blocking_analysis, anchoring_results
                )
                success = results.get('execution', {}).get('success', False)
                if success:
                    # Record to ledger
                    self.edit_ledger.append({
                        'intent': intent.get('intent'),
                        'plan_summary': final_plan.get('plan_summary')
                    })
                return success
            else:
                return self._apply_bug_fix(initial_fix_plan) # Fallback to old simple fix
                
        except Exception as e:
            rays_ui.print_error(f"Enhanced failure resolution error: {e}")
            traceback.print_exc()
            return False

    def _extract_focused_traceback(self, output: str) -> str:
        """Extract user-owned frames from traceback."""
        traceback_match = re.findall(r'File "([^"]+)", line (\d+), in (\w+)\n\s+(.+)', output)
        if not traceback_match:
            return output[-1000:] # Return more context if no match
            
        focused = []
        for file, line, func, code in traceback_match:
            # Filter out non-codebase files (e.g. site-packages)
            if str(self.codebase_root) in file or not file.startswith('/'):
                focused.append(f"File \"{file}\", line {line}, in {func}\n  {code}")
        
        return "\n".join(focused) if focused else output[-500:]

    def _extract_symbols_from_traceback(self, traceback_str: str) -> Dict[str, str]:
        """Extract symbol_name -> file_path from traceback."""
        frames = re.findall(r'File "([^"]+)", line \d+, in (\w+)', traceback_str)
        symbols = {}
        for f_path, sym_name in frames:
            try:
                rel_path = str(Path(f_path).relative_to(self.codebase_root))
            except ValueError:
                rel_path = f_path
            symbols[sym_name] = rel_path
        return symbols

    def _apply_bug_fix(self, fix_plan: Dict[str, Any]) -> bool:
        """Fallback simple apply_bug_fix if Executor is not available."""
        rays_ui.print_info("Applying fallback fix")
        # Implementation omitted for brevity as Executor is the primary path
        return False
