# execution.py
from code_generator import CodeGenerator
from code_executor import CodeExecutor
from ai_client import AIClient
from pathlib import Path
class Executor:
    def __init__(self, codebase_root: Path, rays_dir: Path, ai_client: AIClient, config: dict, execution_mode: str = 'ask'):
        self.codebase_root = codebase_root
        self.rays_dir = rays_dir
        self.ai_client = ai_client
        self.config = config
        self.execution_mode = execution_mode

    def generate_and_apply_code(self, implementation_plan: dict,
                               blocking_analysis: dict,
                               anchoring_results: dict) -> dict:
        """
        Step 12-13: Generate code and apply to codebase.
        Step 12-13: Generate code and apply to codebase.
        
        Args:
            implementation_plan: Final implementation plan
            blocking_analysis: Blocking symbols analysis
            anchoring_results: Anchoring results
        
        Returns:
            Complete execution results
        """
        from code_generator import CodeGenerator
        from code_executor import CodeExecutor
        
        # Step 12: Generate code
        generator = CodeGenerator(self.codebase_root, self.rays_dir, self.ai_client)
        generation_results = generator.execute_implementation_plan(
            implementation_plan,
            blocking_analysis,
            anchoring_results,
            self.config
        )
        
        # Step 13: Apply code to files
        executor = CodeExecutor(self.codebase_root, self.rays_dir, execution_mode=self.execution_mode)
        execution_results = executor.apply_all_edits(generation_results)
        
        # If successful, commit changes
        if execution_results['success'] and not execution_results['errors']:
            executor.commit_changes()
        else:
            pass
        
        return {
            'generation': generation_results,
            'execution': execution_results,
            'backup_location': str(executor.backup_dir)
        }
