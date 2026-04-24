"""
RAYS Task Analyzer
Analyzes user prompts and calculates SDS from codebase.
"""

import yaml
import re
import msgpack
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from ai_client import AIClient
import rays_ui


class TaskAnalysisResult:
    """Structured result from task analysis"""
    def __init__(self, data: Dict[str, Any]):
        self.task_type = data.get('task_type', 'edit_code')
        self.edit_codebase = data.get('edit_codebase', False)
        self.terminal_tool = data.get('terminal_tool', False)
        self.sds_score = data.get('sds_score', 0.0)
        self.ies_score = data.get('ies_score', 0.0)
        self.keywords = data.get('keywords', [])
        self.symbol_names = data.get('symbol_names', [])
        self.symbol_types = data.get('symbol_types', [])
        self.file_patterns = data.get('file_patterns', [])
        self.raw_data = data
    
    def __repr__(self):
        return f"TaskAnalysisResult(task={self.task_type}, sds={self.sds_score:.2f}, ies={self.ies_score:.2f})"


class TaskAnalyzer:
    """
    Analyzes user prompts to determine:
    1. Task classification (edit_code/chat_with_code/new_project)
    2. SDS score (Scope Density Score - codebase complexity)
    3. IES score (Intent Expression Score - creative freedom)
    4. Keywords, symbol names, file patterns
    5. Symbol types needed for filtering
    6. Terminal tool requirements
    """
    
    def __init__(self, config: Any = None):
        if isinstance(config, dict):
            self.config = config
        else:
            # If path string or None, load from file
            path = config or "./config.yaml"
            self.config = self._load_config(path)
        
        # Initialize AI client
        self.ai_client = AIClient({
            'provider': self.config['llm']['provider'],
            'model': self.config['llm']['model'],
            'base_url': self.config['llm']['ollama_endpoint'].replace('/api/generate', '').replace('/api', ''),
            'api_key': self.config['llm'].get('api_key', ''),
            'delay': 0.1
        })
        
        self.prompts = self.config.get('task_analysis_prompts', {})
    
    def _load_config(self, path: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        config_path = Path(path)
        if not config_path.exists():
            # Fallback to RAYS root config if run from elsewhere
            config_path = Path(__file__).parent / "config.yaml"
        
        if not config_path.exists():
            raise FileNotFoundError("config.yaml not found!")
            
        with open(config_path) as f:
            return yaml.safe_load(f)
    
    def analyze(self, user_prompt: str, codebase_path: str) -> TaskAnalysisResult:
        """
        Main analysis pipeline
        
        Args:
            user_prompt: User's natural language request
            codebase_path: Path to the codebase (for SDS calculation)
        
        Returns:
            TaskAnalysisResult with all analysis data
        """
        # Clean user prompt of common shell garbage (e.g., ❯, $, path/fragments)
        clean_prompt = re.sub(r'^[❯\$]\s*', '', user_prompt, flags=re.MULTILINE)
        clean_prompt = re.sub(r'^[^\n]*\s[on|via]\s[^\n]*\n', '', clean_prompt)
        
        # Step 1: Calculate IES (deterministic, prompt-only)
        ies_score = self._calculate_ies_deterministic(user_prompt)
        
        # Step 2: Calculate SDS (deterministic, codebase-based)
        sds_score = self._calculate_sds_deterministic(codebase_path)
        
        # Step 3: Task Classification (LLM-based)
        rays_ui.log_model_interaction("Model Analysis", "Classifying task intent and scope...")
        task_classification = self._classify_task(clean_prompt)
        
        # Step 4: Extract Keywords (LLM-based)
        keywords_data = self._extract_keywords(clean_prompt)
        
        # Step 5: Determine Symbol Types (LLM-based)
        symbol_types = self._determine_symbol_types(clean_prompt, keywords_data)
        
        # Step 6: Check Terminal Tool (LLM-based)
        tool_requirements = self._check_tool_requirements(clean_prompt)
        
        # Combine results
        combined_result = {
            **task_classification,
            'sds_score': sds_score,
            'ies_score': ies_score,
            **keywords_data,
            'symbol_types': symbol_types,
            **tool_requirements
        }
        
        result = TaskAnalysisResult(combined_result)
        return result
    #change the IES into more deterministic  
    def _calculate_ies_deterministic(self, user_prompt: str) -> float:
        """
        Calculate IES (Intent Expression Score) deterministically.
        
        Measures creative freedom:
        - 0.0-0.3: Strict instructions (low freedom)
        - 0.4-0.6: Moderate flexibility
        - 0.7-1.0: High creative freedom
        """
        prompt_lower = user_prompt.lower()
        score = 0.5  # Start at neutral
        
        # STRICT indicators (reduce freedom)
        strict_patterns = [
            (r'line \d+', -0.15),
            (r'on line', -0.15),
            ('change to', -0.10),
            ('set to', -0.10),
            ('replace with', -0.10),
            ('rename to', -0.10),
            ('must', -0.10),
            ('exactly', -0.15),
            ('only', -0.10),
            ('just', -0.05),
            ('precisely', -0.10),
            ('delete', -0.10),
            ('remove line', -0.15),
            ('return true', -0.10),
            ('return false', -0.10),
        ]
        
        for pattern, weight in strict_patterns:
            if pattern.startswith('r\''):
                if re.search(pattern, prompt_lower):
                    score += weight
            else:
                if pattern in prompt_lower:
                    score += weight
        
        # FREEDOM indicators (increase freedom)
        freedom_keywords = [
            ('improve', 0.10),
            ('enhance', 0.10),
            ('better', 0.10),
            ('optimize', 0.10),
            ('refactor', 0.15),
            ('redesign', 0.15),
            ('rework', 0.15),
            ('clean up', 0.10),
            ('make it', 0.10),
            ('could you', 0.10),
            ('perhaps', 0.10),
            ('maybe', 0.10),
            ('consider', 0.10),
            ('try', 0.10),
            ('somehow', 0.15),
        ]
        
        for keyword, weight in freedom_keywords:
            if keyword in prompt_lower:
                score += weight
        
        return max(0.0, min(1.0, score))
    
    def _calculate_sds_deterministic(self, codebase_path: str) -> float:
        """
        Calculate SDS (Scope Density Score) deterministically.
        
        Measures codebase density/complexity:
        - 0.0-0.2: Small codebase (few files/symbols)
        - 0.3-0.5: Medium codebase
        - 0.6-0.8: Large codebase
        - 0.9-1.0: Very large codebase
        
        Reads from .rays folder (symbols.msgpack, relationships.msgpack)
        """
        rays_dir = Path(codebase_path) / ".rays"
        
        if not rays_dir.exists():
            return 0.0
        
        # Read symbols.msgpack
        symbols_file = rays_dir / "symbols.msgpack"
        if not symbols_file.exists():
            return 0.0
        
        with open(symbols_file, 'rb') as f:
            symbols = msgpack.unpackb(f.read(), raw=False)
        
        # Read relationships.msgpack
        relationships_file = rays_dir / "relationships.msgpack"
        relationships = []
        if relationships_file.exists():
            with open(relationships_file, 'rb') as f:
                relationships = msgpack.unpackb(f.read(), raw=False)
        
        # Calculate metrics
        symbol_count = len(symbols)
        file_set = set(sym['file_path'] for sym in symbols if 'file_path' in sym)
        file_count = len(file_set)
        relationship_count = len(relationships)
        
        # Calculate total lines of code
        total_loc = sum(
            max(0, sym.get('end_line', 0) - sym.get('start_line', 0) + 1)
            for sym in symbols
        )
        
        # Weighted calculation
        symbol_factor = min(1.0, symbol_count / 100.0)  # Cap at 100
        file_factor = min(1.0, file_count / 20.0)  # Cap at 20
        rel_factor = min(1.0, relationship_count / 200.0)  # Cap at 200
        loc_factor = min(1.0, total_loc / 5000.0)  # Cap at 5000
        
        score = (
            symbol_factor * 0.30 +
            file_factor * 0.20 +
            rel_factor * 0.30 +
            loc_factor * 0.20
        )
        
        return score
    
    def _classify_task(self, user_prompt: str) -> Dict[str, Any]:
        """Classify task type using LLM"""
        prompt = self.prompts['task_classification'].format(user_prompt=user_prompt)
        system_prompt = self.prompts['system_instructions']
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            task_type = result.get('task_type', 'edit_code')
            return {
                'task_type': task_type,
                'edit_codebase': task_type in ['edit_code', 'new_project', 'new_codebase']
            }
        except Exception as e:
            return {'task_type': 'edit_code', 'edit_codebase': True}
    
    def _extract_keywords(self, user_prompt: str) -> Dict[str, List[str]]:
        """Extract keywords using LLM"""
        prompt = self.prompts['keyword_extraction'].format(user_prompt=user_prompt)
        system_prompt = self.prompts['system_instructions']
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            return {
                'keywords': result.get('keywords', []),
                'symbol_names': result.get('symbol_names', []),
                'file_patterns': result.get('file_patterns', [])
            }
        except Exception as e:
            pass  # Silent fallback
            return {'keywords': [], 'symbol_names': [], 'file_patterns': []}
    #check symbol types defined in the instructions should match the symbol types actually existing
    def _determine_symbol_types(self, user_prompt: str, keywords_data: Dict[str, List[str]]) -> List[str]:
        """Determine symbol types using LLM"""
        prompt = self.prompts['symbol_type_detection'].format(
            user_prompt=user_prompt,
            keywords=", ".join(keywords_data.get('keywords', []))
        )
        system_prompt = self.prompts['system_instructions']
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            return result.get('symbol_types', ['function', 'class'])
        except Exception as e:
            rays_ui.print_warning(f"LLM symbol type detection warning: {e}")
            return ['function', 'class']
    
    def _check_tool_requirements(self, user_prompt: str) -> Dict[str, bool]:
        """Check if terminal tool and/or code editing is needed using LLM"""
        prompt = self.prompts['tool_requirements'].format(user_prompt=user_prompt)
        system_prompt = self.prompts['system_instructions']
        
        try:
            result = self.ai_client.generate_json(prompt, system_prompt)
            return {
                'edit_codebase': result.get('edit_codebase', False),
                'terminal_tool': result.get('terminal_tool', False)
            }
        except Exception as e:
            rays_ui.print_warning(f"LLM tool requirement check warning: {e}")
            # Fallback: assume code editing by default
            return {'edit_codebase': True, 'terminal_tool': False}


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        sys.exit(1)
    
    user_prompt = sys.argv[1]
    codebase_path = sys.argv[2]
    
    analyzer = TaskAnalyzer()
    result = analyzer.analyze(user_prompt, codebase_path)

