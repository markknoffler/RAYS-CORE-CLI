# anchoring.py
"""
Anchoring Module - Coordinates symbol and file anchoring.

Uses LLM-based anchoring to determine:
1. Where to insert new symbols in existing files (line numbers)
2. Where to create new files (directory paths)
"""

from pathlib import Path
from typing import Dict, Optional

from ai_client import AIClient


class Anchorer:
    def __init__(self, codebase_root: Path, rays_dir: Path, 
                 config: dict = None, ai_client: AIClient = None):
        self.codebase_root = codebase_root
        self.rays_dir = rays_dir
        self.config = config
        self.ai_client = ai_client

    def anchor_new_symbols_and_files(self, implementation_plan: dict) -> dict:
        """
        Step 11: Anchor all new symbols and files BEFORE code generation.
        
        Uses LLM-based anchoring with:
        - File skeleton (for symbol insertion)
        - Directory tree (for file creation)
        
        Handles:
        - New files (with nested symbols_to_create)
        - New symbols in existing files
        
        Args:
            implementation_plan: Implementation plan with new_files and new_symbols
        
        Returns:
            Anchoring results with precise locations
        """
        
        from symbol_anchor import SymbolAnchor
        from file_anchor import FileAnchor
        
        # Initialize anchors with config and ai_client
        symbol_anchor = SymbolAnchor(
            self.codebase_root, 
            self.rays_dir,
            config=self.config,
            ai_client=self.ai_client
        )
        file_anchor = FileAnchor(
            self.codebase_root, 
            self.rays_dir,
            config=self.config,
            ai_client=self.ai_client
        )
        
        anchoring_results = {
            'symbol_anchors': [],
            'file_anchors': []
        }
        
        # PART 1: Anchor NEW FILES (with their nested symbols)
        new_files = implementation_plan.get('new_files', [])
        if new_files:
            
            for file in new_files:
                file_name = file['name']
                
                # Find directory for this file using LLM
                file_anchor_result = file_anchor.find_directory_for_new_file(
                    file,
                    implementation_plan=implementation_plan
                )
                
                # Attach anchor to file
                file['anchor'] = file_anchor_result
                
                # Count symbols in this file
                symbols_in_file = file.get('symbols_to_create', [])
                
                anchoring_results['file_anchors'].append({
                    'file_name': file_name,
                    'symbols_count': len(symbols_in_file),
                    **file_anchor_result
                })
                
        

        # PART 2: Anchor NEW SYMBOLS in EXISTING files
        new_symbols = implementation_plan.get('new_symbols', [])
        if new_symbols:
            
            # Get previous edits for file path resolution
            previous_edits = implementation_plan.get('existing_symbol_edits', [])
            
            for symbol in new_symbols:
                
                # Find insertion point using LLM with file skeleton
                anchor = symbol_anchor.find_insertion_point(
                    symbol, 
                    previous_edits,
                    implementation_plan=implementation_plan
                )
                
                # Attach anchor to symbol
                symbol['anchor'] = anchor
                
                anchoring_results['symbol_anchors'].append({
                    'symbol_name': symbol['name'],
                    'symbol_type': symbol['type'],
                    **anchor
                })

        
        # Summary silenced as results are printed during anchoring
        pass
        
        
        return anchoring_results
