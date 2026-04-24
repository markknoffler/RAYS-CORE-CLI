"""
Chat-mode context pipeline.

This pipeline is intentionally read-only and bypasses editing execution. It:
1) Selects relevant files from batched skeletons.
2) Retrieves symbol chunks using the existing symbol-detection pipeline.
3) Answers the user with full file contents + symbol chunks context.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import rays_ui
from ai_client import AIClient
from file_skeleton import FileSkeletonGenerator
from symbol_detection import SymbolDetector


class ChatContextPipeline:
    """Read-only chat responder powered by file and symbol context."""

    def __init__(
        self,
        codebase_root: Path,
        rays_dir: Path,
        ai_client: AIClient,
        symbol_detector: SymbolDetector,
        config: Dict[str, Any],
    ):
        self.codebase_root = codebase_root
        self.rays_dir = rays_dir
        self.ai_client = ai_client
        self.symbol_detector = symbol_detector
        self.config = config
        self.skeleton_generator = FileSkeletonGenerator(codebase_root, rays_dir)

    def _select_relevant_files_from_skeletons(
        self, augmented_prompt: str, analysis: Dict[str, Any]
    ) -> List[str]:
        prompts = self.config.get("chat_mode_prompts", {})
        prompt_template = prompts.get("select_files_from_skeleton_batches", "")
        if not prompt_template:
            return []

        system_prompt = self.config.get("task_analysis_prompts", {}).get("system_instructions")
        batch_size = int(prompts.get("skeleton_batch_size", 150))

        all_files = self.symbol_detector._get_all_codebase_files()
        if not all_files:
            return []

        selected: List[str] = []
        selected_set = set()
        all_files_set = set(all_files)

        rays_ui.print_sub_phase("Chat mode: selecting relevant files")
        for i in range(0, len(all_files), max(1, batch_size)):
            batch = all_files[i : i + batch_size]
            batch_num = i // max(1, batch_size) + 1

            skeleton_text = ""
            for fp in batch:
                skeleton_text += f"\n{'=' * 60}\n"
                skeleton_text += f"FILE: {fp}\n"
                skeleton_text += f"{'=' * 60}\n"
                skeleton_text += self.skeleton_generator.get_file_skeleton(fp, include_docstrings=True)
                skeleton_text += "\n"

            prompt = prompt_template.format(
                user_prompt=augmented_prompt,
                task_type=analysis.get("task_type", "unknown"),
                keywords=", ".join(analysis.get("keywords", [])),
                num_files=len(batch),
                file_skeletons=skeleton_text,
            )

            try:
                rays_ui.log_model_interaction(
                    "Chat skeleton selection",
                    f"batch {batch_num} ({len(batch)} files)",
                )
                result = self.ai_client.generate_json(prompt, system_prompt)
                batch_files = (
                    result.get("relevant_files")
                    or result.get("files")
                    or result.get("selected_files")
                    or []
                )
                for file_path in batch_files:
                    if file_path in all_files_set and file_path not in selected_set:
                        selected_set.add(file_path)
                        selected.append(file_path)
            except Exception as e:
                rays_ui.log_model_interaction("Chat skeleton selection error", str(e)[:120])
                continue

        return selected

    def _load_file_contents(self, files: List[str]) -> List[Dict[str, str]]:
        loaded: List[Dict[str, str]] = []
        for rel_path in files:
            full_path = self.codebase_root / rel_path
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    loaded.append({"file_path": rel_path, "content": f.read()})
            except Exception:
                continue
        return loaded

    @staticmethod
    def _format_file_context(files_with_content: List[Dict[str, str]]) -> str:
        out = []
        for idx, f in enumerate(files_with_content, 1):
            out.append(f"\n--- FILE {idx} ---")
            out.append(f"PATH: {f['file_path']}")
            out.append("CONTENT:")
            out.append(f["content"])
        return "\n".join(out)

    @staticmethod
    def _format_symbol_context(symbols_with_code: List[Dict[str, Any]]) -> str:
        out = []
        for idx, s in enumerate(symbols_with_code, 1):
            out.append(f"\n--- SYMBOL CHUNK {idx} ---")
            out.append(f"Name: {s.get('symbol_name', 'unknown')}")
            out.append(f"Type: {s.get('symbol_type', 'unknown')}")
            out.append(f"File: {s.get('file_path', '')}")
            out.append(f"Lines: {s.get('start_line', 0)}-{s.get('end_line', 0)}")
            out.append(f"Chunk ID: {s.get('chunk_id', '')}")
            out.append("Code:")
            out.append(s.get("code", ""))
        return "\n".join(out)

    def respond(
        self,
        user_prompt: str,
        augmented_prompt: str,
        analysis: Dict[str, Any],
        memory_symbols: List[Dict[str, Any]],
        memory_context_text: str,
    ) -> Dict[str, Any]:
        """
        Execute read-only /chat flow and return final answer + context stats.
        """
        selected_files = self._select_relevant_files_from_skeletons(augmented_prompt, analysis)
        files_with_content = self._load_file_contents(selected_files)

        symbol_detection = self.symbol_detector.detect_affected_symbols(
            augmented_prompt, analysis, memory_symbols
        )
        final_selection = self.symbol_detector.finalize_symbol_selection(
            augmented_prompt, analysis, symbol_detection, memory_context_text
        )
        symbols_with_code = self.symbol_detector.retrieve_code_chunks(
            final_selection.get("affected_symbols", [])
        )

        prompts = self.config.get("chat_mode_prompts", {})
        answer_template = prompts.get("answer_with_files_and_symbols", "")
        system_prompt = self.config.get("task_analysis_prompts", {}).get("system_instructions")

        if not answer_template:
            return {
                "answer": "Chat mode prompt not configured.",
                "selected_files": selected_files,
                "symbols_with_code": symbols_with_code,
            }

        prompt = answer_template.format(
            user_prompt=user_prompt,
            augmented_prompt=augmented_prompt,
            task_type=analysis.get("task_type", "unknown"),
            keywords=", ".join(analysis.get("keywords", [])),
            num_files=len(files_with_content),
            selected_files=", ".join(selected_files) if selected_files else "None",
            files_content=self._format_file_context(files_with_content),
            num_symbols=len(symbols_with_code),
            symbols_with_code=self._format_symbol_context(symbols_with_code),
        )

        answer = self.ai_client.generate_text(prompt, system_prompt).strip()
        return {
            "answer": answer or "No response generated.",
            "selected_files": selected_files,
            "symbols_with_code": symbols_with_code,
        }
