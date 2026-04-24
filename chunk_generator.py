import os
import sys
import msgpack
import yaml
import chromadb
from pathlib import Path
from typing import List, Dict, Optional
from ai_client import AIClient

class VectorDBGenerator:
    def __init__(self, codebase_root: str, batch_size: int = 100, config: Optional[Dict] = None):
        self.codebase_root = Path(codebase_root)
        self.rays_dir = self.codebase_root / ".rays"
        self.batch_size = batch_size  # Number of chunks per batch
        
        # Load config or use provided
        if config:
            self.config = config
        else:
            self.config = self.load_config()

        embedding_cfg = self.config.get('embedding', {})
        embedding_provider = embedding_cfg.get('provider', self.config['llm']['provider'])
        embedding_endpoint = embedding_cfg.get('ollama_endpoint', self.config['llm'].get('ollama_endpoint', 'http://localhost:11434/api/generate'))
        embedding_api_key = embedding_cfg.get('api_key', self.config['llm'].get('api_key', ''))
        self.ai_client = AIClient({
            'provider': embedding_provider,
            'model': self.config['embedding']['model'],
            'base_url': embedding_endpoint.replace('/api/generate', '').replace('/api/embeddings', '').replace('/api', ''),
            'api_key': embedding_api_key,
            'delay': 0.2  # Lower delay for batch processing
        })
        
        # Initialize ChromaDB
        chroma_path = str(self.rays_dir / "chroma_db")
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(
            name="code_chunks",
            metadata={"hnsw:space": "cosine"}
        )
    
    def load_config(self) -> Dict:
        """Load config.yaml from SDE directory with robust absolute path search"""
        # 1. Try absolute path of the script's directory (most reliable)
        script_dir = Path(__file__).parent.resolve()
        config_path = script_dir / "config.yaml"
        
        # 2. Fallbacks for other structures
        if not config_path.exists():
            config_path = Path("./config.yaml").resolve()
        
        if not config_path.exists():
            config_path = (script_dir.parent / "config.yaml").resolve()
            
        if not config_path.exists():
            raise FileNotFoundError(f"config.yaml not found at {config_path} or parent dirs. RAYS cannot continue.")
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        return config
    
    def load_msgpack(self, filename: str) -> List[Dict]:
        """Load msgpack file"""
        path = self.rays_dir / filename
        if not path.exists():
            return []
        
        try:
            with open(path, 'rb') as f:
                return msgpack.unpackb(f.read(), raw=False)
        except Exception as e:
            return []
    
    def read_code(self, rel_path: str, start: int, end: int) -> str:
        """Read code from file"""
        full = self.codebase_root / rel_path
        if not full.exists():
            return ""
        
        try:
            with open(full, 'r', encoding='utf-8', errors='ignore') as f:
                res = ""
                curr = 1
                for line in f:
                    if curr >= start and curr <= end:
                        res += line
                    if curr > end:
                        break
                    curr += 1
                return res
        except:
            return ""
    
    def build(self, affected_files: Optional[List[str]] = None):
        """Generate vector database with BATCH processing"""
        if affected_files:
            pass
        else:
            pass
        if not self.ai_client.is_available():
            return False
            
        # [1/3] Load RAYS data
        if not self.rays_dir.exists():
            raise FileNotFoundError(f".rays directory not found at {self.rays_dir}")
        
        symbols = self.load_msgpack("symbols.msgpack")
        relationships = self.load_msgpack("relationships.msgpack")
        
        # Filter symbols if incremental
        if affected_files:
            symbols = [s for s in symbols if s.get('file_path') in affected_files]
            
            # Delete old entries for these files
            try:
                # ChromaDB requires a where clause with $in for multiple values
                if len(affected_files) == 1:
                    self.collection.delete(where={"file_path": affected_files[0]})
                else:
                    self.collection.delete(where={"file_path": {"$in": affected_files}})
            except Exception as e:
                pass

        # [2/3] Build dependency graph
        uses_map = {}
        used_by_map = {}
        
        for rel in relationships:
            src = rel['source_symbol']
            tgt = rel['target_symbol']
            
            if src not in uses_map:
                uses_map[src] = []
            uses_map[src].append(tgt)
            
            if tgt not in used_by_map:
                used_by_map[tgt] = []
            used_by_map[tgt].append(src)
        
        # [3/3] Generate embeddings in BATCHES
        
        # Prepare all chunks first (no embedding yet)
        all_chunks = []
        
        for sym in symbols:
            if not sym.get('file_path'):
                continue
            
            code = self.read_code(sym['file_path'], sym['start_line'], sym['end_line'])
            if not code:
                continue
            
            # Build context
            ctx = f"Symbol: {sym['symbol_name']} ({sym['symbol_type']}) in {sym['file_path']}.\n"
            
            if sym['symbol_name'] in uses_map:
                ctx += "Uses: "
                deps = uses_map[sym['symbol_name']]
                for i in range(min(len(deps), 8)):
                    ctx += f"{deps[i]}, "
                ctx += "\n"
            
            if sym['symbol_name'] in used_by_map:
                ctx += "Used By: "
                users = used_by_map[sym['symbol_name']]
                for i in range(min(len(users), 8)):
                    ctx += f"{users[i]}, "
                ctx += "\n"
           
            # Store chunk data (no embedding yet)
            # Create UNIQUE ID: file_path:line:symbol_name
            unique_id = f"{sym['file_path']}:{sym['start_line']}:{sym['symbol_name']}"

            all_chunks.append({
                'id': unique_id,
                'symbol_name': sym['symbol_name'],
                'symbol_type': sym.get('symbol_type', 'unknown'),
                'code': code,
                'context': ctx,
                'file_path': sym['file_path'],
                'start_line': sym['start_line'],
                'end_line': sym['end_line']
            })
        
        if not all_chunks:
            return

        
        # Process in batches
        ids = []
        embeddings = []
        documents = []
        metadatas = []
        
        total_batches = (len(all_chunks) + self.batch_size - 1) // self.batch_size
        
        for batch_idx in range(0, len(all_chunks), self.batch_size):
            batch = all_chunks[batch_idx:batch_idx + self.batch_size]
            batch_num = (batch_idx // self.batch_size) + 1
            
            
            # Prepare texts for batch embedding
            texts_to_embed = [chunk['context'] + "\n" + chunk['code'] for chunk in batch]
            
            # Get embeddings for entire batch in ONE API call
            batch_embeddings = self.ai_client.get_embeddings_batch(texts_to_embed)
            
            # Store results
            for chunk, embedding in zip(batch, batch_embeddings):
                if not embedding:
                    continue
                
                ids.append(chunk['id'])
                embeddings.append(embedding)
                documents.append(chunk['code'])

                metadatas.append({
                    'chunk_id': chunk['id'],
                    'symbol_name': chunk['symbol_name'],
                    'symbol_type': chunk['symbol_type'],
                    'file_path': chunk['file_path'],
                    'start_line': chunk['start_line'],
                    'end_line': chunk['end_line'],
                    'code_content': chunk['code'],
                    'context_tags': chunk['context']
                })
        
        if not ids:
            return
        
        
        # Insert into ChromaDB
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas
        )
        
        return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(1)
    
    batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    
    generator = VectorDBGenerator(sys.argv[1], batch_size=batch_size)
    generator.build()

