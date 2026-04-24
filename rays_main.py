#!/usr/bin/env python3
"""
RAYS - Main Entry Point
Orchestrates the entire RAYS pipeline from codebase analysis to task execution.
"""
import os
import sys
from pathlib import Path

# Priority to local directory to avoid cross-version conflicts
sys.path.insert(0, str(Path(__file__).parent.absolute()))

import yaml
from typing import Dict, Any, Optional, List
from datetime import datetime

import msgpack
import json
import chromadb
from ai_client import AIClient
from task_analyzer import TaskAnalyzer
import rays_ui

# Import the new helper classes
from indexing import Indexer
from symbol_detection import SymbolDetector
from permission import PermissionManager
from planning import Planner
from anchoring import Anchorer
from execution import Executor
from terminal_engine import TerminalEngine
from memory import MemoryManager
from new_codebase_generator import NewCodebaseGenerator
from git_status_summarizer import GitStatusSummarizer
from affected_symbols_skeleton_fill import AffectedSymbolsSkeletonFiller
from chat_context_pipeline import ChatContextPipeline

class RAYS:
    def __init__(
        self,
        codebase_root: Optional[str] = None,
        config_path: str = "./config.yaml",
        conversation_id: Optional[str] = None,
        runtime_overrides: Optional[Dict[str, Any]] = None,
    ):
        self.config = self._load_config(config_path)
        if runtime_overrides:
            for section, values in runtime_overrides.items():
                if not isinstance(values, dict):
                    continue
                if section not in self.config or not isinstance(self.config[section], dict):
                    self.config[section] = {}
                self.config[section].update(values)
        if codebase_root is None:
            self.codebase_root = Path.cwd().resolve()
        else:
            self.codebase_root = Path(codebase_root).resolve()
        self.rays_dir = self.codebase_root / ".rays"
        self.script_dir = Path(__file__).parent.resolve()
        
        # conversation_id for memory
        if conversation_id is None:
            conversation_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.conversation_id = conversation_id
        
        # Deterministic history of last 2 summaries
        self.deterministic_history = [] 

        # Initialize AI client for text generation
        llm_endpoint = self.config['llm'].get('ollama_endpoint', 'http://localhost:11434/api/generate')
        self.ai_client = AIClient({
            'provider': self.config['llm']['provider'],
            'model': self.config['llm']['model'],
            'base_url': llm_endpoint.replace('/api/generate', '').replace('/api', ''),
            'api_key': self.config['llm'].get('api_key', ''),
            'delay': 0.1
        })
        
        # Initialize separate AI client for embeddings (using embedding model)
        embedding_cfg = self.config.get('embedding', {})
        embedding_provider = embedding_cfg.get('provider', self.config['llm']['provider'])
        embedding_endpoint = embedding_cfg.get('ollama_endpoint', llm_endpoint)
        embedding_api_key = embedding_cfg.get('api_key', self.config['llm'].get('api_key', ''))
        self.embedding_ai_client = AIClient({
            'provider': embedding_provider,
            'model': self.config['embedding']['model'],
            'base_url': embedding_endpoint.replace('/api/generate', '').replace('/api/embeddings', '').replace('/api', ''),
            'api_key': embedding_api_key,
            'delay': 0.01
        })
        
        # Store execution mode from config
        self.execution_mode = self.config.get('execution_mode', 'ask')

        # Initialize MemoryManager with both generation and embedding clients
        self.memory_mgr = MemoryManager(self.ai_client, self.embedding_ai_client, self.config, self.conversation_id)

        # Instantiate helpers
        self.indexer = Indexer(self.codebase_root, self.rays_dir, self.config)
        self.symbol_detector = SymbolDetector(self.rays_dir, self.ai_client, self.config, self.codebase_root)
        self.permission_mgr = PermissionManager(self.ai_client, self.config)
        self.planner = Planner(self.codebase_root, self.rays_dir, self.ai_client, self.config)
        self.anchorer = Anchorer(self.codebase_root, self.rays_dir, self.config, self.ai_client)
        self.executor = Executor(self.codebase_root, self.rays_dir, self.ai_client, self.config, execution_mode=self.execution_mode)
        self.skeleton_symbol_filler = AffectedSymbolsSkeletonFiller()
        self.chat_context_pipeline = ChatContextPipeline(
            self.codebase_root, self.rays_dir, self.ai_client, self.symbol_detector, self.config
        )
        self.terminal_engine = TerminalEngine(
            self.codebase_root, self.rays_dir, self.ai_client, self.config,
            permission_mgr=self.permission_mgr,
            planner=self.planner,
            anchorer=self.anchorer,
            executor=self.executor,
            execution_mode=self.execution_mode
        )

        # Initialize CLI history
        rays_ui.setup_history(str(self.rays_dir))

    def set_execution_mode(self, mode: str):
        """
        Update execution mode across orchestrator and downstream executors.
        """
        normalized = "autonomous" if mode == "autonomous" else "ask"
        self.execution_mode = normalized
        self.executor.execution_mode = normalized
        self.terminal_engine.execution_mode = normalized

    
    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        config_path = Path(path)
        if not config_path.exists():
            config_path = Path(__file__).parent / "config.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError("config.yaml not found!")
        
        with open(config_path) as f:
            return yaml.safe_load(f)

    def _is_codebase_populated(self, min_symbols: int = 5, min_files: int = 5) -> bool:
        """
        Heuristic guard to avoid accidental new-project branch on existing repos.
        """
        symbols_file = self.rays_dir / "symbols.msgpack"
        files_file = self.rays_dir / "files.msgpack"

        # Prefer symbol count when available
        try:
            if symbols_file.exists():
                with open(symbols_file, "rb") as f:
                    symbols = msgpack.unpackb(f.read(), raw=False)
                if isinstance(symbols, list) and len(symbols) >= min_symbols:
                    return True
        except Exception:
            pass

        # Fallback to indexed file count if symbol indexing is sparse/failed.
        try:
            if files_file.exists():
                with open(files_file, "rb") as f:
                    files = msgpack.unpackb(f.read(), raw=False)
                if isinstance(files, list) and len(files) >= min_files:
                    return True
        except Exception:
            pass

        return False

    def _generate_final_pipeline_summary(
        self,
        user_prompt: str,
        augmented_prompt: str,
        execution_data: Dict[str, Any],
        memory_summary: List[Dict[str, Any]],
        git_status_summary: str,
    ) -> str:
        """
        Generate final human-readable run summary for terminal output.
        """
        prompt_template = (
            self.config.get("final_run_summary_prompts", {}).get("generate_final_summary", "")
        )
        if not prompt_template:
            return "Final summary prompt not configured."

        # Keep prompt payload bounded while preserving signal.
        serializable_execution = dict(execution_data)
        command_history = serializable_execution.get("terminal_commands_executed", [])
        if isinstance(command_history, list) and len(command_history) > 40:
            serializable_execution["terminal_commands_executed"] = command_history[:40] + [
                {"command": "...", "output_tail": f"[{len(command_history) - 40} more commands truncated]"}
            ]

        execution_data_text = json.dumps(serializable_execution, indent=2, default=str)
        if len(execution_data_text) > 100000:
            execution_data_text = execution_data_text[:100000] + "\n... [execution data truncated]"

        memory_summary_text = json.dumps(memory_summary, indent=2, default=str)
        if len(memory_summary_text) > 40000:
            memory_summary_text = memory_summary_text[:40000] + "\n... [memory summary truncated]"

        prompt = prompt_template.format(
            user_prompt=user_prompt,
            augmented_prompt=augmented_prompt,
            execution_data=execution_data_text,
            memory_summary=memory_summary_text,
            git_status_summary=git_status_summary or "N/A",
        )
        system_prompt = self.config.get("task_analysis_prompts", {}).get("system_instructions")

        try:
            summary = self.ai_client.generate_text(prompt, system_prompt).strip()
            # Guardrail: if model still returns structured JSON-like output, force prose conversion.
            if summary.startswith("{") or summary.startswith("["):
                rewrite_prompt = (
                    "Rewrite the following into clean human-readable plain text summary. "
                    "Do NOT output JSON or any structured object format.\n\n"
                    f"{summary}"
                )
                summary = self.ai_client.generate_text(rewrite_prompt, system_prompt).strip()
            return summary or "Final summary generation returned an empty response."
        except Exception as e:
            return f"Failed to generate final summary: {e}"

    def _build_augmented_prompt_context(self, user_prompt: str, analysis: dict) -> Dict[str, Any]:
        """Build prompt context with memory retrieval and deterministic history."""
        rays_ui.print_sub_phase("Recalling previous context")
        raw_memories = self.memory_mgr.retrieve_relevant_memories(user_prompt)
        filtered_memories = self.memory_mgr.filter_memories_with_ai(user_prompt, raw_memories)

        memory_symbols = [
            m for m in filtered_memories if m.get('type') in ['symbol_edit', 'symbol_creation', 'file_creation']
        ]
        memory_context_text = "\n".join(
            [f"- {m['name']} ({m['file_path']}): {m['relevance_explanation']}" for m in filtered_memories]
        )

        history_objs = self.deterministic_history[-2:]
        if len(history_objs) < 2:
            persistent_history = self.memory_mgr.retrieve_last_n_memories(2 - len(history_objs))
            history_objs = persistent_history + history_objs

        history_context = "\n".join([f"CHAT HISTORY SUMMARY:\n{json.dumps(h, indent=2)}" for h in history_objs])
        augmented_prompt = (
            f"{user_prompt}\n\nHISTORICAL CONTEXT (SIMILAR PAST CHANGES):\n{memory_context_text}\n\n"
            f"RECENT ACTIVITY (LAST 2 TASKS):\n{history_context}"
        )

        return {
            'filtered_memories': filtered_memories,
            'memory_symbols': memory_symbols,
            'memory_context_text': memory_context_text,
            'augmented_prompt': augmented_prompt,
        }

    def run_chat_mode(self, user_prompt: str, force_reindex: bool = False, force_rebuild_db: bool = False) -> Dict[str, Any]:
        """
        /chat mode: read-only response pipeline with file+skeleton selection and symbol chunks.
        """
        if not self.ai_client.is_available():
            rays_ui.print_provider_warning(self.ai_client.provider, self.ai_client.base_url)

        self.indexer.index_codebase(force_reindex)
        self.indexer.create_vector_database(force_rebuild_db)

        analysis = self.analyze_task(user_prompt)
        context = self._build_augmented_prompt_context(user_prompt, analysis)

        chat_result = self.chat_context_pipeline.respond(
            user_prompt=user_prompt,
            augmented_prompt=context['augmented_prompt'],
            analysis=analysis,
            memory_symbols=context['memory_symbols'],
            memory_context_text=context['memory_context_text'],
        )

        rays_ui.print_full_width_box("Chat Response", chat_result.get('answer', ''), rays_ui.C_VIOLET, rays_ui.C_CREAM)

        execution_data = {
            'mode': 'chat',
            'analysis': analysis,
            'chat_answer': chat_result.get('answer', ''),
            'chat_selected_files': chat_result.get('selected_files', []),
            'chat_symbols_count': len(chat_result.get('symbols_with_code', [])),
            'terminal_commands_executed': [
                {'command': cmd, 'output_tail': out}
                for cmd, out in self.terminal_engine.chain_command_history
            ],
        }
        current_summary = self.memory_mgr.summarize_chat(user_prompt, execution_data)
        self.memory_mgr.store_chat_memory(current_summary)
        self.deterministic_history.append(current_summary)

        summarizer = GitStatusSummarizer(self.codebase_root, self.ai_client, self.config)
        git_status_summary = summarizer.summarize()

        final_run_summary = self._generate_final_pipeline_summary(
            user_prompt=user_prompt,
            augmented_prompt=context['augmented_prompt'],
            execution_data=execution_data,
            memory_summary=current_summary,
            git_status_summary=git_status_summary,
        )
        rays_ui.print_final_run_summary(final_run_summary)

        return {
            'mode': 'chat',
            'analysis': analysis,
            'chat_answer': chat_result.get('answer', ''),
            'chat_selected_files': chat_result.get('selected_files', []),
            'chat_symbols_count': len(chat_result.get('symbols_with_code', [])),
            'final_run_summary': final_run_summary,
            'git_status': git_status_summary,
        }

    def analyze_task(self, user_prompt: str) -> Dict[str, Any]:
        """
        Step 3: Analyze user prompt using task_analyzer.py
        
        Args:
            user_prompt: The user's natural language request
        
        Returns:
            Dictionary with all analysis results
        """
        rays_ui.print_phase("Analyzing your request")
        
        analyzer = TaskAnalyzer(self.config)
        with rays_ui.thinking("Reading and understanding your prompt"):
            result = analyzer.analyze(user_prompt, str(self.codebase_root))
        
        # Return as dictionary for easy access
        return {
            'task_type': result.task_type,
            'edit_codebase': result.edit_codebase,
            'terminal_tool': result.terminal_tool,
            'sds_score': result.sds_score,
            'ies_score': result.ies_score,
            'keywords': result.keywords,
            'symbol_names': result.symbol_names,
            'symbol_types': result.symbol_types,
            'file_patterns': result.file_patterns,
        }

    def _generate_new_codebase(self, user_prompt: str, analysis: dict):
        """
        New Pipeline for Generating Entirely New Codebases.
        """
        rays_ui.print_phase("Creating New Project")

        # 1. Terminal Setup (npm init, git init, etc.)
        rays_ui.print_sub_phase("Setting up environment")
        terminal_intents = self.terminal_engine.generate_intents(user_prompt, False)
        for intent in terminal_intents:
            self.terminal_engine.execute_intent(intent, user_prompt)

        # 2. Get current skeleton (likely empty or just setup files)
        from file_skeleton import FileSkeletonGenerator
        skeleton_gen = FileSkeletonGenerator(self.codebase_root, self.rays_dir)
        directory_tree = skeleton_gen.get_directory_tree()

        # 3. Permission Negotiation
        initial_perms = {
            'num_files_to_create': 7,
            'num_symbols_to_create': 20,
            'num_files_to_edit': 0,
            'num_symbols_to_edit': 0,
            'max_lines_to_edit': 0
        }
        approved_permissions = self.permission_mgr.negotiate_new_codebase_permissions(user_prompt, initial_perms)

        # 4. Generate Implementation Plan
        plan = self.planner.generate_new_codebase_plan(
            user_prompt, 
            approved_permissions['num_files_to_create'],
            approved_permissions['num_symbols_to_create'],
            directory_tree
        )

        # 5. Iterative Generation
        generator = NewCodebaseGenerator(self.codebase_root, self.rays_dir, self.ai_client, self.config, execution_mode=self.execution_mode)
        created_files = generator.generate_files(plan, user_prompt)

        # 6. Summarization & Memory
        rays_ui.print_sub_phase("Saving to memory")
        execution_data = {
            'analysis': analysis,
            'plan': plan,
            'created_files': created_files,
            'terminal_intents': terminal_intents
        }
        summary = self.memory_mgr.summarize_chat(user_prompt, execution_data)
        self.memory_mgr.store_chat_memory(summary)
        self.deterministic_history.append(summary)

        # Re-index new codebase 
        rays_ui.print_sub_phase("Updating codebase index")
        self.indexer.index_codebase(force_reindex=False, skip_if_exists=False)
        self.indexer.create_vector_database(force_rebuild=False, affected_files=created_files)

        return {
            'task_type': 'new_codebase',
            'implementation_plan': plan,
            'code_generation': {'execution': {'success': True, 'files_created': len(created_files)}},
            'summary': summary
        }

    def run(self, user_prompt: str, force_reindex: bool = False, force_rebuild_db: bool = False):
        # Step 0: Pre-flight check
        if not self.ai_client.is_available():
            rays_ui.print_provider_warning(self.ai_client.provider, self.ai_client.base_url)

        # Step 1: Indexing
        self.indexer.index_codebase(force_reindex)

        # Step 2: Vector DB
        self.indexer.create_vector_database(force_rebuild_db)

        # Step 3: Task analysis
        analysis = self.analyze_task(user_prompt)

        # TRIGGER LOGIC: SDS + PROMPT CHECK
        # Guardrail: never route to new-codebase generation for already populated repos.
        codebase_populated = self._is_codebase_populated()
        if analysis.get('task_type') in ['new_project', 'new_codebase']:
            if analysis.get('sds_score', 1.0) < 0.2 and not codebase_populated:
                return self._generate_new_codebase(user_prompt, analysis)
            else:
                rays_ui.print_info("Codebase already populated — redirecting to editing pipeline")

        # Step 3.5: Memory Retrieval & Prompt Augmentation
        context = self._build_augmented_prompt_context(user_prompt, analysis)
        filtered_memories = context['filtered_memories']
        memory_symbols = context['memory_symbols']
        memory_context_text = context['memory_context_text']
        augmented_prompt = context['augmented_prompt']

        # Step 4: Symbol detection
        symbol_detection = self.symbol_detector.detect_affected_symbols(augmented_prompt, analysis, memory_symbols)

        # Step 4b: If deterministic retrieval is sparse, seed candidates from skeleton + LLM (before finalize)
        self.skeleton_symbol_filler.fill_if_sparse(
            self.symbol_detector, symbol_detection, augmented_prompt, analysis
        )

        # Step 5: Final symbol selection
        final_selection = self.symbol_detector.finalize_symbol_selection(augmented_prompt, analysis, symbol_detection, memory_context_text)

        # Step 5.5: Deep Scan Branch (V16)
        # Uses RAW user_prompt (not augmented) for broader architectural detection
        deep_scan_results = self.symbol_detector.deep_scan_symbols(
            user_prompt,
            analysis,
            symbol_detection.get('explicit_mentions', {}),
            final_selection
        )

        # Merge deep scan results into final_selection
        if deep_scan_results:
            existing_keys = {
                (s.get('symbol_name'), s.get('file_path'))
                for s in final_selection['affected_symbols']
            }
            for sym in deep_scan_results:
                key = (sym.get('symbol_name'), sym.get('file_path'))
                if key not in existing_keys:
                    final_selection['affected_symbols'].append(sym)
                    existing_keys.add(key)

        # [FIX] Force planning phase if deep scan found symbols OR if it was a search/audit task
        if deep_scan_results or self.symbol_detector._classify_prompt_openness(user_prompt, symbol_detection.get('explicit_mentions', {})):
            analysis['edit_codebase'] = True

        # Step 6: Permission slip
        permission_slip = self.permission_mgr.generate_permission_slip(final_selection, symbol_detection['explicit_mentions'])

        # Step 7: Retrieve code chunks for negotiation
        symbols_with_code = self.symbol_detector.retrieve_code_chunks(final_selection['affected_symbols'])

        # Step 8: Negotiate permissions
        approved_permissions = self.permission_mgr.negotiate_permissions(
            augmented_prompt, analysis, permission_slip, symbols_with_code
        )

        # Step 9: Terminal PRE_EDIT tasks
        terminal_intents = []
        if analysis['terminal_tool']:
            terminal_intents = self.terminal_engine.generate_intents(
                augmented_prompt, analysis['edit_codebase'], None
            )
            
            for intent in terminal_intents:
                # Execute PRE_EDIT intents, or ALL intents if no editing is required
                if intent.get('phase') == 'PRE_EDIT' or (not analysis['edit_codebase'] and intent.get('phase') in ['NONE', 'POST_EDIT']):
                    self.terminal_engine.execute_intent(intent, augmented_prompt)

        # Step 10-14: Implementation Planning & Execution
        final_plan = {"plan_summary": "N/A"}
        final_permissions = approved_permissions
        anchoring_results = {}
        code_results = {"execution": {"success": True}}
        blocking_analysis = {'all_blocking_symbols': [], 'blocker_count': 0, 'total_hops': 0}

        if analysis['edit_codebase']:
            rays_ui.print_phase("Planning edits")
            # Step 10: Implementation plan
            implementation_plan = self.planner.generate_implementation_plan(
                augmented_prompt, analysis, approved_permissions, symbols_with_code
            )

            # Step 11: Merge blocker resolutions (Deferred multihop)
            final_plan, final_permissions = self.planner.merge_blocker_resolutions_into_plan(
                implementation_plan, blocking_analysis, approved_permissions
            )

            # Step 12: Anchor new symbols/files
            anchoring_results = self.anchorer.anchor_new_symbols_and_files(final_plan)

            # Step 13-14: Generate and apply code
            code_results = self.executor.generate_and_apply_code(
                final_plan, blocking_analysis, anchoring_results
            )
        else:
            rays_ui.print_step("Terminal-only task — no code edits needed")

        # Filter memory summaries to only keep those whose symbols survived final selection
        final_symbol_names = {s['symbol_name'] for s in final_selection['affected_symbols']}
        survived_memories = [m for m in filtered_memories if m.get('name') in final_symbol_names or m.get('type') == 'intent_result']
        survived_context_text = "\n".join([f"- {m['name']} ({m['file_path']}): {m['original_summary']}" for m in survived_memories])
        # This survived_context_text could be used in subsequent steps if needed

        # Step 15: Terminal POST_EDIT tasks
        if analysis['terminal_tool']:
            # Augment intents if needed based on plan
            post_intents = [i for i in terminal_intents if i.get('phase') == 'POST_EDIT']
            if not post_intents and analysis['edit_codebase']:
                # Generate new post-edit intents if none exist
                new_post_intents = self.terminal_engine.generate_intents(
                    user_prompt, True, final_plan
                )
                post_intents = [i for i in new_post_intents if i.get('phase') == 'POST_EDIT']
            
            for intent in post_intents:
                self.terminal_engine.execute_intent(intent, user_prompt)
        
        # Skip editing if analysis says so
        if not analysis['edit_codebase'] and analysis['terminal_tool']:
            rays_ui.print_step("Terminal-only task — skipping code application")
            
        # Step 16: Summarization & Persistent Memory
        rays_ui.print_sub_phase("Saving session to memory")
        
        # Track all affected files for incremental indexing
        affected_files = set()
        if analysis['edit_codebase']:
            # From executor
            exec_results = code_results.get('execution', {})
            affected_files.update(exec_results.get('files_modified_list', []))
            affected_files.update(exec_results.get('files_created_list', []))
            
            # From anchoring (pre-creation)
            for file_anchor in anchoring_results.get('file_anchors', []):
                if file_anchor.get('full_path'):
                    affected_files.add(file_anchor['full_path'])
        
        # Also check terminal intents for file manipulations (basic heuristic)
        for intent in terminal_intents:
            # Look for common file creation/modification patterns in commands
            # This is a bit of a stretch but helps with 'touch' or 'mkdir'
            pass

        execution_data = {
            'analysis': analysis,
            'final_selection': final_selection,
            'plan': final_plan,
            'code_results': code_results,
            'terminal_intents': terminal_intents,
            'terminal_commands_executed': [
                {'command': cmd, 'output_tail': out}
                for cmd, out in self.terminal_engine.chain_command_history
            ],
            'affected_files': list(affected_files),
        }
        current_summary = self.memory_mgr.summarize_chat(user_prompt, execution_data)
        self.memory_mgr.store_chat_memory(current_summary)
        
        # Update deterministic history
        self.deterministic_history.append(current_summary)

        # Combine results
        complete_analysis = {
            **analysis,
            **symbol_detection,
            'final_affected_symbols': final_selection['affected_symbols'],
            'final_analysis_summary': final_selection['analysis_summary'],
            'initial_permission_slip': permission_slip,
            'approved_permissions': final_permissions,
            'implementation_plan': final_plan,
            'blocking_symbols': blocking_analysis,
            'anchoring': anchoring_results,
            'code_generation': code_results,
            'terminal_intents': terminal_intents
        }

        # Step 16b: Git status summary for the final box
        summarizer = GitStatusSummarizer(self.codebase_root, self.ai_client, self.config)
        complete_analysis['git_status'] = summarizer.summarize()
        if 'execution' in code_results:
            code_results['execution']['git_status'] = complete_analysis['git_status']

        complete_analysis['final_run_summary'] = self._generate_final_pipeline_summary(
            user_prompt=user_prompt,
            augmented_prompt=augmented_prompt,
            execution_data=execution_data,
            memory_summary=current_summary,
            git_status_summary=complete_analysis['git_status'],
        )

        # Print final results summary
        rays_ui.print_summary_box(code_results.get('execution', {}))
        # Step 17: Persistent Re-indexing (Sync codebase state)
        if analysis['edit_codebase'] or affected_files:
            rays_ui.print_sub_phase("Syncing codebase index")
            # We run indexing to update symbols.msgpack without deleting the .rays directory
            self.indexer.index_codebase(force_reindex=False, skip_if_exists=False)
            self.indexer.create_vector_database(force_rebuild=False, affected_files=list(affected_files))

        # Print final AI-generated run summary at very end of full pipeline execution
        rays_ui.print_final_run_summary(complete_analysis.get('final_run_summary', ""))

        return complete_analysis

def main():
    """
    Command-line interface for RAYS development assistant.
    Always interactive — slash commands for in-session control.
    """
    import sys
    import argparse
    from pathlib import Path
    
    parser = argparse.ArgumentParser(
        description="RAYS — AI-Powered Development Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
  Examples:
    rays                                   # Start in current directory
    rays -c /path/to/codebase              # Start in a specific directory
    rays --reindex                         # Force re-index on startup
    
  In-session commands:
    /help       Show all commands
    /chat       Read-only contextual Q&A (no edit pipeline)
    /model      Switch model
    /mode auto  Switch to autonomous mode
    /exit       Exit RAYS
        """
    )

    parser.add_argument(
        "codebase_path",
        type=str,
        nargs="?",
        default=".",
        help="Path to the codebase (default: current directory)"
    )
    
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Force re-index the codebase on startup"
    )
    
    parser.add_argument(
        "--rebuild_db",
        action="store_true",
        help="Force rebuild of the vector database"
    )
    
    parser.add_argument(
        "--auto_approve",
        action="store_true",
        help="Auto-approve permission slips"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config file (default: config.yaml in RAYS install dir)"
    )
    
    parser.add_argument(
        "--devmode",
        action="store_true",
        help="Enable developer mode (prints stack traces on error)"
    )
    
    parser.add_argument(
        "--conversation_id",
        type=str,
        help="Resume or name a specific conversation session"
    )
    
    args = parser.parse_args()
    
    # Inject Dev Mode state into UI module
    rays_ui.DEVMODE = args.devmode
    
    # Resolve codebase path
    codebase_path = Path(args.codebase_path).resolve()
    
    if not codebase_path.exists():
        rays_ui.print_error(f"Codebase path does not exist: {codebase_path}")
        sys.exit(1)
    
    # Resolve config path — look relative to RAYS install dir
    if args.config:
        config_path = args.config
    else:
        script_dir = Path(__file__).parent.resolve()
        config_path = str(script_dir / "config.yaml")
    
    rays_dir = codebase_path / ".rays"
    
    try:
        # Show banner
        rays_ui.display_banner()
        
        import requests

        def env_key_for_provider(provider_name: str) -> str:
            p = provider_name.lower()
            if p == "gemini":
                return os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
            if p == "openai":
                return os.getenv("OPENAI_API_KEY", "")
            return ""
        
        # Load current config
        with open(config_path, 'r') as f:
            current_config = yaml.safe_load(f)
            
        providers = ["ollama (locally)", "gemini api", "openai api"]
        chosen_provider_label = rays_ui.select_from_menu("Select AI Provider", providers)
        
        # Parse choice into canonical provider slugs used by AIClient
        if chosen_provider_label == "ollama (locally)":
            chosen_provider = "ollama"
        elif chosen_provider_label == "gemini api":
            chosen_provider = "gemini"
        elif chosen_provider_label == "openai api":
            chosen_provider = "openai"
        else:
            chosen_provider = "ollama"
        current_config['llm']['provider'] = chosen_provider
        session_llm_api_key = ""
        
        if chosen_provider_label == "ollama (locally)":
            current_config['llm']['ollama_endpoint'] = "http://localhost:11434/api/generate"
            rays_ui.print_step("Fetching local models...")
            try:
                resp = requests.get("http://localhost:11434/api/tags", timeout=2)
                resp.raise_for_status()
                models = [m['name'] for m in resp.json().get('models', [])]
                if not models:
                    models = ["llama3:latest", "qwen2.5-coder:latest", "mistral:latest"]
            except Exception:
                rays_ui.print_warning("Could not reach local Ollama. Ensure it's running.")
                models = ["llama3:latest", "qwen2.5-coder:latest", "mistral:latest"]
                
        elif chosen_provider == "gemini":
            session_llm_api_key = env_key_for_provider("gemini")
            if session_llm_api_key:
                rays_ui.print_step("Using Gemini API key from environment")
            else:
                session_llm_api_key = input(f"  {rays_ui.C_PINK}❯ Enter Gemini API Key: {rays_ui.RESET}").strip()
            entered_model = input(f"  {rays_ui.C_PINK}❯ Enter Gemini Model Name: {rays_ui.RESET}").strip()
            models = [entered_model] if entered_model else ["gemini-1.5-flash"]
            
        elif chosen_provider == "openai":
            session_llm_api_key = env_key_for_provider("openai")
            if session_llm_api_key:
                rays_ui.print_step("Using OpenAI API key from environment")
            else:
                session_llm_api_key = input(f"  {rays_ui.C_PINK}❯ Enter OpenAI API Key: {rays_ui.RESET}").strip()
            entered_model = input(f"  {rays_ui.C_PINK}❯ Enter OpenAI Model Name: {rays_ui.RESET}").strip()
            models = [entered_model] if entered_model else ["gpt-4o"]
            
        # Select Model
        if chosen_provider in ("gemini", "openai"):
            chosen_model = models[0]
        else:
            chosen_model = rays_ui.select_from_menu(f"Select Model ({chosen_provider_label})", models)
        current_config['llm']['model'] = chosen_model

        # Embedding setup (session/runtime aware)
        embedding_choice = rays_ui.select_from_menu(
            "Embedding Model Setup",
            ["Use existing embedding model", "Bring your own embedding model"]
        )
        session_embedding_api_key = ""
        if embedding_choice == "Use existing embedding model":
            current_config.setdefault('embedding', {})
            # Built-in default path uses local ollama embedding model from config.
            current_config['embedding']['provider'] = "ollama"
            current_config['embedding'].setdefault('ollama_endpoint', "http://localhost:11434/api/generate")
        else:
            provider_choice = rays_ui.select_from_menu(
                "Select Embedding Provider",
                ["ollama"]
            )
            if provider_choice == "ollama":
                current_config.setdefault('embedding', {})
                current_config['embedding']['provider'] = "ollama"
                current_config['embedding']['ollama_endpoint'] = "http://localhost:11434/api/generate"
                rays_ui.print_step("Fetching local embedding models...")
                try:
                    resp = requests.get("http://localhost:11434/api/tags", timeout=2)
                    resp.raise_for_status()
                    embedding_models = [m['name'] for m in resp.json().get('models', [])]
                    if not embedding_models:
                        embedding_models = [current_config.get('embedding', {}).get('model', "qwen3-embedding:4b")]
                except Exception:
                    rays_ui.print_warning("Could not reach local Ollama. Ensure it's running.")
                    embedding_models = [current_config.get('embedding', {}).get('model', "qwen3-embedding:4b")]
                chosen_embedding_model = rays_ui.select_from_menu("Select Embedding Model (ollama)", embedding_models)
                current_config['embedding']['model'] = chosen_embedding_model
        
        # Save config
        # Never persist API keys; keep them session-only.
        current_config.setdefault('llm', {})
        current_config['llm']['api_key'] = ''
        current_config.setdefault('embedding', {})
        current_config['embedding']['api_key'] = ''
        with open(config_path, 'w') as f:
            yaml.dump(current_config, f, default_flow_style=False)
        
        rays_ui.print_step(f"Configured: {chosen_provider_label} -> {chosen_model}")
        
        current_model = chosen_model
        available_models = models

        # Create RAYS instance
        with rays_ui.spinner("Initializing RAYS"):
            rays = RAYS(
                codebase_root=str(codebase_path),
                config_path=config_path,
                conversation_id=args.conversation_id,
                runtime_overrides={
                    'llm': {'api_key': session_llm_api_key},
                    'embedding': {'api_key': session_embedding_api_key}
                }
            )
        
        execution_mode = rays.execution_mode
        
        # Show session info
        rays_ui.print_session_info(
            str(codebase_path),
            current_model,
            execution_mode,
            rays.conversation_id
        )
        
        # Override auto-approve if specified
        if args.auto_approve:
            rays_ui.print_warning("Auto-approve mode active — permissions will be auto-approved")
            rays.set_execution_mode("autonomous")
            execution_mode = "autonomous"
        
        # ─── Interactive Loop ───────────────────────────────────
        first_run = True
        intentional_exit = False
        while True:
            try:
                user_input = rays_ui.get_user_prompt()
                
                if user_input is None:
                    # EOF or Ctrl+C at prompt
                    intentional_exit = True
                    break
                
                if not user_input:
                    continue
                
                # ── Slash Commands ──────────────────────────────
                if user_input.startswith('/'):
                    cmd_parts = user_input.split(maxsplit=1)
                    cmd = cmd_parts[0].lower()
                    cmd_arg = cmd_parts[1] if len(cmd_parts) > 1 else ""
                    
                    if cmd in ('/exit', '/quit'):
                        print(f"\n  {rays_ui.C_LAVENDER}Goodbye!{rays_ui.RESET}\n")
                        intentional_exit = True
                        break
                    
                    elif cmd == '/help':
                        rays_ui.print_help()
                        continue
                    
                    elif cmd == '/model':
                        if cmd_arg:
                            current_model = cmd_arg.strip()
                            rays.ai_client.model = current_model
                            rays.config['llm']['model'] = current_model
                            rays_ui.print_step(f"Model switched to: {current_model}")
                        else:
                            selected = rays_ui.print_model_selector(available_models, current_model)
                            if selected:
                                current_model = selected
                                rays.ai_client.model = selected
                                rays.config['llm']['model'] = selected
                        continue
                    
                    elif cmd == '/mode':
                        if cmd_arg.strip().lower() in ('auto', 'autonomous'):
                            execution_mode = 'autonomous'
                            rays.set_execution_mode('autonomous')
                        else:
                            execution_mode = 'ask'
                            rays.set_execution_mode('ask')
                        rays_ui.print_mode_change(execution_mode)
                        continue
                    
                    elif cmd == '/chat':
                        if not cmd_arg.strip():
                            rays_ui.print_warning("Usage: /chat <your question>")
                            continue
                        _ = rays.run_chat_mode(
                            user_prompt=cmd_arg.strip(),
                            force_reindex=args.reindex if first_run else False,
                            force_rebuild_db=args.rebuild_db if first_run else False
                        )
                        first_run = False
                        continue
                    
                    elif cmd == '/clear':
                        os.system('clear' if os.name != 'nt' else 'cls')
                        rays_ui.display_banner()
                        continue
                    
                    elif cmd == '/git':
                        summarizer = GitStatusSummarizer(rays.codebase_root, rays.ai_client, rays.config)
                        summary = summarizer.summarize()
                        rays_ui.print_box("Git Change Summary", summary, rays_ui.C_VIOLET)
                        continue
                    
                    else:
                        rays_ui.print_warning(f"Unknown command: {cmd}. Type /help for available commands.")
                        continue
                
                # ── Run the pipeline ────────────────────────────
                results = rays.run(
                    user_prompt=user_input,
                    force_reindex=args.reindex if first_run else False,
                    force_rebuild_db=args.rebuild_db if first_run else False
                )
                first_run = False
                
                # Results are already printed inside rays.run
                _save_results(results, user_input, rays_dir)
                
            except KeyboardInterrupt:
                print(f"\n  {rays_ui.C_LAVENDER}Interrupted — returning to prompt{rays_ui.RESET}")
            except Exception as e:
                rays_ui.print_exception(e)
            
            # Diagnostic message to ensure we reach end of loop
            if rays_ui.DEVMODE:
                print(f"  {rays_ui.C_GRAY}[DEBUG] Loop iteration finished. Looping back...{rays_ui.RESET}")
        
        if not intentional_exit:
            print(f"\n  {rays_ui.C_RED}[CRITICAL] Interactive loop broken unexpectedly. Please report this error.{rays_ui.RESET}")
            
    except KeyboardInterrupt:
        print(f"\n\n  {rays_ui.C_LAVENDER}Goodbye!{rays_ui.RESET}\n")
        sys.exit(130)
    except Exception as e:
        rays_ui.print_exception(e)
        sys.exit(1)


def _print_execution_summary(results):
    """Print the styled execution summary."""
    exec_results = results.get('code_generation', {}).get('execution', {})
    rays_ui.print_summary_box(exec_results)


def _save_results(results, prompt, rays_dir):
    """Save run results to JSON."""
    try:
        rays_dir.mkdir(parents=True, exist_ok=True)
        results_file = rays_dir / "last_run_results.json"
        import json
        with open(results_file, 'w') as f:
            json_results = {
                'prompt': prompt,
                'timestamp': str(datetime.now()),
                'success': results.get('code_generation', {}).get('execution', {}).get('success', False),
                'plan_summary': results.get('implementation_plan', {}).get('plan_summary', ''),
                'files_modified': results.get('code_generation', {}).get('execution', {}).get('files_modified', 0),
                'files_created': results.get('code_generation', {}).get('execution', {}).get('files_created', 0)
            }
            json.dump(json_results, f, indent=2)
    except Exception:
        pass  # Non-critical


if __name__ == "__main__":
    main()
