#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

# Add parent directory to path to import RAYS modules
sys.path.insert(0, str(Path(__file__).parent.resolve()))

import rays_ui
from ai_client import AIClient
import yaml

class GitStatusSummarizer:
    def __init__(self, codebase_root: Path, ai_client: AIClient, config: dict):
        self.codebase_root = codebase_root
        self.ai_client = ai_client
        self.config = config
        self.prompts = config.get('git_status_summarizer_prompts', {})

    def get_git_status(self) -> str:
        """Run git status --porcelain and return output."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.codebase_root,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            return f"Error running git status: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"

    def summarize(self) -> str:
        """Get git status and return an AI-generated summary."""
        status_output = self.get_git_status()
        
        if not status_output:
            return "Codebase is clean (no changes since last commit)."
        
        rays_ui.print_sub_phase("Summarizing code changes")
        
        prompt = self.prompts.get('summarize_git_status', '').format(
            git_status_output=status_output
        )
        
        if not prompt:
            return f"Git Status Output:\n{status_output}"
            
        try:
            with rays_ui.thinking("Analyzing git status"):
                summary = self.ai_client.generate_text(prompt)
            return summary
        except Exception as e:
            return f"Failed to generate summary: {e}\n\nRaw Status:\n{status_output}"

def main():
    """Standalone entry point for the tool."""
    codebase_root = Path.cwd().resolve()
    
    # Load config
    config_path = codebase_root / "config.yaml"
    if not config_path.exists():
        # Try finding it in the same directory as the script
        config_path = Path(__file__).parent / "config.yaml"
        
    if not config_path.exists():
        print("Error: config.yaml not found!")
        sys.exit(1)
        
    with open(config_path) as f:
        config = yaml.safe_load(f)
        
    # Initialize AI client
    ai_client = AIClient({
        'provider': config['llm']['provider'],
        'model': config['llm']['model'],
        'base_url': config['llm']['ollama_endpoint'].replace('/api/generate', '').replace('/api', ''),
        'api_key': config['llm'].get('api_key', ''),
    })
    
    summarizer = GitStatusSummarizer(codebase_root, ai_client, config)
    summary = summarizer.summarize()
    
    # Print the summary in a box
    rays_ui.print_box("Git Change Summary", summary, rays_ui.C_VIOLET)

if __name__ == "__main__":
    main()
