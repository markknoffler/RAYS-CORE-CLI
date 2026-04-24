import requests
import time
import json
import re
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import rays_ui

class AIClient:
    def __init__(self, config: Dict[str, Any]):
        self.provider = config['provider']
        self.model = config['model']
        self.base_url = config['base_url']
        self.api_key = config.get('api_key', '')
        self.delay = config.get('delay', 0.05)
        self.max_workers = 50
        self.num_ctx = config.get('num_ctx', 32768)  # Reduced default for local stability
        self._ollama_embedding_endpoint = None # Cache for working endpoint
    
    def is_available(self) -> bool:
        """Check if the AI provider is reachable"""
        if self.provider == "ollama":
            try:
                # Direct check to the base URL
                resp = requests.get(self.base_url, timeout=2)
                return resp.status_code == 200
            except:
                return False
        elif self.provider == "gemini":
            # For Gemini, we just check if API key exists (network check is expensive/unreliable here)
            return bool(self.api_key)
        return False
    
    def get_embedding(self, text: str) -> List[float]:
        """Generate single embedding vector"""
        snippet = (text[:50] + "...") if len(text) > 50 else text
        rays_ui.log_model_interaction("Model Read (Embedding)", snippet)
        result = self.get_embeddings_batch([text])
        return result[0] if result else []
    
    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate batch embeddings using threading"""
        if self.provider == "ollama":
            return self._ollama_parallel(texts)
        elif self.provider == "gemini":
            return self._gemini_parallel(texts)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text completion from LLM"""
        # Global hard throttle to reduce provider-side rate limiting.
        time.sleep(3.0)

        # Log the request
        prompt_snippet = (prompt[:100] + "...") if len(prompt) > 100 else prompt
        rays_ui.log_model_interaction("Model Request", prompt_snippet)
        
        if self.provider == "ollama":
            response = self._ollama_generate(prompt, system_prompt)
        elif self.provider == "gemini":
            response = self._gemini_generate(prompt, system_prompt)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
            
        # Log the response (truncated)
        resp_snippet = (response[:100] + "...") if len(response) > 100 else response
        rays_ui.log_model_interaction("Model Response", resp_snippet)

        # Symmetric post-call delay to space out consecutive prompts.
        time.sleep(3.0)
        return response
    
    def generate_json(self, prompt: str, system_prompt: Optional[str] = None, retry_count: int = 3) -> Dict[str, Any]:
        """
        Generate JSON response from LLM with automatic parsing and retry logic.
        
        Args:
            prompt: User prompt
            system_prompt: System instructions
            retry_count: Number of retry attempts if JSON parsing fails
        
        Returns:
            Parsed JSON dictionary
        """
        for attempt in range(retry_count):
            try:
                # Add JSON formatting instruction to prompt
                json_prompt = prompt + "\n\nYou MUST respond with valid JSON only. No explanations, no markdown code blocks, just raw JSON."
                
                response = self.generate_text(json_prompt, system_prompt)
                
                # Extract JSON from response (handles markdown code blocks)
                parsed_json = self._extract_json(response)
                
                if parsed_json:
                    return parsed_json
                else:
                    if attempt < retry_count - 1:
                        rays_ui.print_warning(f"JSON parsing failed, retrying ({attempt + 1}/{retry_count})...")
                        time.sleep(1)
                    else:
                        raise ValueError("Failed to parse JSON after multiple attempts")
            
            except Exception as e:
                if attempt < retry_count - 1:
                    rays_ui.print_exception(e)
                    rays_ui.print_warning(f"Retrying JSON generation ({attempt + 1}/{retry_count})...")
                    time.sleep(1)
                else:
                    raise
        
        return {}
    
    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract and parse JSON from text (handles markdown code blocks and malformed JSON)"""
        def clean_json(s):
            # Remove markdown logic if present
            s = re.sub(r'```(?:json)?\s*', '', s)
            s = s.strip('`').strip()
            # Remove trailing commas in objects and arrays
            s = re.sub(r',\s*([\]}])', r'\1', s)
            # Remove comments (single line // or hash #)
            s = re.sub(r'^\s*//.*$', '', s, flags=re.MULTILINE)
            s = re.sub(r'^\s*#.*$', '', s, flags=re.MULTILINE)
            return s

        # Strategy 1: Look for { ... } code blocks first (often the cleanest)
        json_blocks = re.findall(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        for block in json_blocks:
            try:
                return json.loads(clean_json(block))
            except json.JSONDecodeError:
                continue

        # Strategy 2: Look for any curly brace structure
        # Use a more aggressive pattern for finding the outermost { }
        try:
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            if start_idx != -1 and end_idx != -1:
                candidate = text[start_idx:end_idx+1]
                return json.loads(clean_json(candidate))
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 3: Regex fallback for smaller objects
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(json_pattern, text, re.DOTALL)
        for match in matches:
            try:
                return json.loads(clean_json(match))
            except json.JSONDecodeError:
                continue
        
        return None
    
    def extract_code_block(self, text: str, language: str = "python") -> str:
        """Extract code from markdown blocks or raw text with fallback."""
        # Strategy 1: Look for markdown code blocks
        patterns = [
            rf'```(?:{language})?\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
            r'CODE_START\s*(.*?)\s*CODE_END',
            r'SOURCE_START\s*(.*?)\s*SOURCE_END'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        
        # Strategy 2: If no blocks but looks like raw code, return as is (minus leading/trailing junk)
        if text.strip().startswith(('def ', 'import ', 'class ', 'from ')):
             # Strip common preamble like "Here is the code:"
             lines = text.strip().split('\n')
             start_idx = 0
             for i, line in enumerate(lines):
                 if line.strip().startswith(('def ', 'import ', 'class ', 'from ')):
                     start_idx = i
                     break
             return '\n'.join(lines[start_idx:]).strip()

        return text.strip()
    
    # ========== OLLAMA METHODS ==========
    
    def _ollama_generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text using Ollama"""
        url = f"{self.base_url}/api/generate"
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_ctx": self.num_ctx,
                "num_predict": 16384,  # Safety limit to prevent infinite loops
                "stop": ["```\n", "}\n\n", "PROMPT_END"]
            }
        }
        
        if system_prompt:
            payload["system"] = system_prompt
        
        try:
            # Use streaming internally to show progress if needed, but for now just handle the large response better
            payload["stream"] = True
            response = requests.post(url, json=payload, timeout=3600, stream=True)
            response.raise_for_status()
            
            full_response = ""
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    text = chunk.get('response', '')
                    full_response += text
                    # Minimal feedback to UI during stream
                    if len(full_response) % 100 == 0:
                         rays_ui.log_model_interaction("Model Thinking", f"...generated {len(full_response)} chars")
                    
                    if chunk.get('done'):
                        break
            
            return full_response
        except Exception as e:
            rays_ui.print_exception(e)
            return ""
    
    def _ollama_parallel(self, texts: List[str]) -> List[List[float]]:
        """Ollama parallel embedding"""
        def embed_single(text):
            # Check cache first
            if self._ollama_embedding_endpoint:
                try:
                    payload = {"model": self.model, "input": text} if "embed" in self._ollama_embedding_endpoint.split('/')[-1] else {"model": self.model, "prompt": text}
                    if "embeddings" in self._ollama_embedding_endpoint:
                        payload = {"model": self.model, "prompt": text}
                    else:
                        payload = {"model": self.model, "input": text}
                        
                    response = requests.post(self._ollama_embedding_endpoint, json=payload, timeout=600)
                    response.raise_for_status()
                    result = response.json()
                    return result.get('embedding') or result.get('embeddings', [[]])[0]
                except Exception:
                    pass # Fallback to discovery if cache fails
            
            # Discovery Phase
            endpoints = [f"{self.base_url}/api/embed", f"{self.base_url}/api/embeddings"]
            
            for endpoint in endpoints:
                try:
                    time.sleep(0.01)
                    if "embeddings" in endpoint:
                        payload = {"model": self.model, "prompt": text}
                    else:
                        payload = {"model": self.model, "input": text}
                        
                    response = requests.post(endpoint, json=payload, timeout=600) # Increased timeout
                    if response.status_code in [404, 501]: 
                        continue
                    
                    response.raise_for_status()
                    result = response.json()
                    
                    if 'embedding' in result or 'embeddings' in result:
                        self._ollama_embedding_endpoint = endpoint # Cache it!
                        return result.get('embedding') or result.get('embeddings', [[]])[0]
                except Exception:
                    continue
            return []
        
        results = [None] * len(texts)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_idx = {executor.submit(embed_single, text): idx for idx, text in enumerate(texts)}
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                results[idx] = future.result()
        
        return results
    
    # ========== GEMINI METHODS ==========
    
    def _gemini_generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate text using Gemini"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": system_prompt}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})
        
        payload = {"contents": contents}
        
        try:
            response = requests.post(url, json=payload, timeout=3600)
            response.raise_for_status()
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            rays_ui.print_exception(e)
            return ""
    
    def _gemini_parallel(self, texts: List[str]) -> List[List[float]]:
        """Gemini parallel embedding"""
        def embed_single(text):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:embedContent?key={self.api_key}"
                payload = {"content": {"parts": [{"text": text}]}}
                response = requests.post(url, json=payload, timeout=120)
                response.raise_for_status()
                return response.json()['embedding']['values']
            except Exception as e:
                rays_ui.print_exception(e)
                return []
        
        results = [None] * len(texts)
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_idx = {executor.submit(embed_single, text): idx for idx, text in enumerate(texts)}
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                results[idx] = future.result()
        
        return results

