"""Sparse symbol fallback using skeleton-based LLM analysis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import rays_ui
from file_skeleton import FileSkeletonGenerator
from symbol_detection import SymbolDetector


@dataclass
class SparseFillConfig:
    """Tuning options for sparse symbol expansion."""

    sparse_symbol_threshold: int = 10
    skeleton_batch_size: int = 150


class AffectedSymbolsSkeletonFiller:
    """
    Production-grade sparse symbol expansion service.
    Uses file skeletons plus the active session LLM to enrich candidate symbols.
    """

    def __init__(self, config: Optional[SparseFillConfig] = None):
        self.config = config or SparseFillConfig()

    @staticmethod
    def _symbol_key(symbol: Dict[str, Any]) -> Tuple[str, str, int]:
        return (
            str(symbol.get("file_path") or ""),
            str(symbol.get("symbol_name") or ""),
            int(symbol.get("start_line") or 0),
        )

    @staticmethod
    def _make_chunk_id(symbol: Dict[str, Any]) -> str:
        fp = symbol.get("file_path") or ""
        start = symbol.get("start_line", 0)
        name = symbol.get("symbol_name") or ""
        return f"{fp}:{start}:{name}"

    @staticmethod
    def _get_prompt_template(config: Dict[str, Any]) -> str:
        prompts = config.get("symbol_detection_prompts") or {}
        template = prompts.get("sparse_fill_skeleton_batch")
        if template:
            return template
        return config["deep_scan_prompts"]["skeleton_batch_scan"]

    def _resolve_llm_hit_to_indexed_symbol(
        self,
        detector: SymbolDetector,
        name: str,
        file_path: str,
        meta: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Map an LLM (name, file_path) pair onto indexed symbols + chunk id."""
        if not name:
            return None

        found = detector._get_symbols_by_name(name, file_path or None)
        if not found:
            found = detector._get_symbols_by_name(name, None)
        if not found:
            return None

        best = found[0]
        if file_path:
            for symbol in found:
                if symbol.get("file_path") == file_path:
                    best = symbol
                    break

        resolved = dict(best)
        resolved["chunk_id"] = self._make_chunk_id(best)
        resolved["reason"] = meta.get("reason", "Skeleton-based sparse fill")
        resolved["change_type"] = meta.get("change_type", "modify")
        resolved["priority"] = meta.get("priority", "medium")
        resolved["from_skeleton_fill"] = True
        return resolved

    def fill_if_sparse(
        self,
        detector: SymbolDetector,
        symbol_detection: Dict[str, Any],
        augmented_prompt: str,
        analysis: Dict[str, Any],
    ) -> None:
        """
        Expand `symbol_detection['affected_symbols']` in place when sparse.
        """
        affected_symbols = symbol_detection.get("affected_symbols") or []
        if len(affected_symbols) >= self.config.sparse_symbol_threshold:
            return

        skeleton_generator = FileSkeletonGenerator(detector.codebase_root, detector.rays_dir)
        all_files = detector._get_all_codebase_files()
        if not all_files:
            return

        prompt_template = self._get_prompt_template(detector.config)
        system_prompt = detector.config["task_analysis_prompts"]["system_instructions"]
        task_type = analysis.get("task_type", "unknown")
        keywords = ", ".join(analysis.get("keywords") or [])

        merged_symbols: List[Dict[str, Any]] = list(affected_symbols)
        seen_keys: Set[Tuple[str, str, int]] = {self._symbol_key(symbol) for symbol in merged_symbols}

        rays_ui.print_sub_phase("Expanding sparse symbol candidates (skeleton fill)")

        batch_size = max(1, int(self.config.skeleton_batch_size))
        with rays_ui.cool_thinking(
            title="Sparse Symbol Expansion",
            sub_messages=[
                "Scanning file skeletons...",
                "Ranking candidate files...",
                "Extracting relevant symbols...",
                "Resolving indexed chunks..."
            ],
        ) as spinner:
            for i in range(0, len(all_files), batch_size):
                batch = all_files[i : i + batch_size]
                batch_num = i // batch_size + 1

                file_skeletons = ""
                for fp in batch:
                    file_skeletons += f"\n{'=' * 60}\n"
                    file_skeletons += f"FILE: {fp}\n"
                    file_skeletons += f"{'=' * 60}\n"
                    file_skeletons += skeleton_generator.get_file_skeleton(fp, include_docstrings=True)
                    file_skeletons += "\n"

                prompt = prompt_template.format(
                    user_prompt=augmented_prompt,
                    task_type=task_type,
                    keywords=keywords,
                    num_files=len(batch),
                    file_skeletons=file_skeletons,
                )

                try:
                    rays_ui.log_model_interaction(
                        "Skeleton fill",
                        f"batch {batch_num} ({len(batch)} files)",
                    )
                    if spinner:
                        spinner.set_sub_message(f"Batch {batch_num}: {len(batch)} files")
                    result = detector.ai_client.generate_json(prompt, system_prompt)
                    llm_hits = result.get("affected_symbols") or []

                    for hit in llm_hits:
                        resolved = self._resolve_llm_hit_to_indexed_symbol(
                            detector,
                            hit.get("symbol_name") or "",
                            hit.get("file_path") or "",
                            hit,
                        )
                        if not resolved:
                            continue

                        key = self._symbol_key(resolved)
                        if key not in seen_keys:
                            merged_symbols.append(resolved)
                            seen_keys.add(key)
                except Exception as e:
                    rays_ui.log_model_interaction("Skeleton fill error", str(e)[:120])
                    continue

                if len(merged_symbols) >= self.config.sparse_symbol_threshold:
                    break

        symbol_detection["affected_symbols"] = merged_symbols
        if len(merged_symbols) > len(affected_symbols):
            symbol_detection["filtered_symbols_count"] = len(merged_symbols)
