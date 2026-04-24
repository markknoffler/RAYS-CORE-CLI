import os
import json
import chromadb
from pathlib import Path
from typing import Dict, List, Any, Optional
from ai_client import AIClient

class MemoryManager:
    def __init__(self, gen_client: AIClient, embed_client: AIClient, config: Dict[str, Any], conversation_id: str):
        self.gen_client = gen_client
        self.embed_client = embed_client
        self.config = config
        self.conversation_id = conversation_id
        
        # Persistent path: ~/rays/memories/<conversation_id>/
        self.base_dir = Path.home() / "rays" / "memories" / conversation_id
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=str(self.base_dir))
        self.collection = self.chroma_client.get_or_create_collection(
            name="chat_memories",
            metadata={"hnsw:space": "cosine"}
        )
        
        self.prompts = config.get('memory_prompts', {})

    def summarize_chat(self, user_prompt: str, execution_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate a surgical summary of all changes made in the current chat.
        Includes edits, new symbols/files, and terminal intents.
        """
        prompt_template = self.prompts.get('summarize_chat')
        if not prompt_template:
            return []

        # Prune execution_data to prevent oversized prompts
        pruned_data = execution_data.copy()
        
        # Truncate lists that can become massive
        for key in ['created_files', 'modified_files', 'files_modified_list', 'terminal_history', 'command_history']:
            if key in pruned_data and isinstance(pruned_data[key], list) and len(pruned_data[key]) > 30:
                pruned_data[key] = pruned_data[key][:30] + [f"... [{len(pruned_data[key]) - 30} more items truncated]"]
        
        # Deep truncate for specific fields if they are still too big
        data_json = json.dumps(pruned_data, indent=2)
        if len(data_json) > 80000: # We increased num_ctx to 64k, so 80k chars is usually safe
            data_json = data_json[:80000] + "\n... [Output truncated for size]"

        # Ensure we don't pass non-serializable objects (fix from previous sessions)
        # We already do json.dumps above, so if that succeeds, we are good.

        prompt = prompt_template.format(
            user_prompt=user_prompt,
            execution_data=data_json
        )
        
        try:
            summaries = self.gen_client.generate_json(prompt)
            return summaries if isinstance(summaries, list) else []
        except Exception as e:
            pass
            return []

    def store_chat_memory(self, summaries: List[Dict[str, Any]]):
        """
        Store summaries into the vector database.
        """
        if summaries:
            pass
        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for i, item in enumerate(summaries):
            content = f"Type: {item.get('type')}\nName: {item.get('name')}\nPath: {item.get('file_path')}\nReason: {item.get('reasoning')}\nSummary: {item.get('summary')}"
            
            # UNIQUE ID for this chat event: conversation_id + timestamp + index
            unique_id = f"{self.conversation_id}_{os.getpid()}_{i}"
            
            embedding = self.embed_client.get_embedding(content)
            if not embedding:
                continue
            
            ids.append(unique_id)
            embeddings.append(embedding)
            documents.append(content)
            metadatas.append({
                "type": item.get('type', 'unknown'),
                "name": item.get('name', 'unknown'),
                "file_path": item.get('file_path', 'unknown'),
                "conversation_id": self.conversation_id,
                "json_data": json.dumps(item)
            })

        if ids:
            try:
                self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=documents,
                    metadatas=metadatas
                )
            except Exception as e:
                pass

    def retrieve_relevant_memories(self, user_prompt: str, top_k: int = 20) -> List[Dict[str, Any]]:
        """
        Retrieve relevant historical memories via similarity search.
        """
        try:
            query_embedding = self.embed_client.get_embedding(user_prompt)
            if not query_embedding:
                return []
            
            if self.collection.count() == 0:
                return []

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(self.collection.count(), top_k)
            )
            
            extracted = []
            if results['metadatas'] and results['metadatas'][0]:
                for meta in results['metadatas'][0]:
                    extracted.append(json.loads(meta['json_data']))
            
            return extracted
        except Exception as e:
            return []

    def retrieve_last_n_memories(self, n: int = 2) -> List[Dict[str, Any]]:
        """
        Retrieve the last N summaries deterministically (by most recent index).
        Chroma doesn't easily support 'sort by timestamp' unless we add it to metadata.
        We'll use our unique ID structure or just get the latest entries.
        """
        # Get all entries for this conversation
        results = self.collection.get(
            where={"conversation_id": self.conversation_id},
            include=['metadatas']
        )
        
        if not results['metadatas']:
            return []
            
        # Chroma IDs are not necessarily ordered. 
        # But we can try to sort by the index suffix if we assume they were added in order.
        # For now, let's just return the last N from the list.
        # A better way is to store a timestamp in metadata.
        
        return [json.loads(m['json_data']) for m in results['metadatas'][-n:]]

    def filter_memories_with_ai(self, user_prompt: str, historical_memories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Surgically filter retrieved memories based on current prompt relevance.
        """
        if not historical_memories:
            return []

        prompt_template = self.prompts.get('filter_memories')
        if not prompt_template:
            return []

        prompt = prompt_template.format(
            user_prompt=user_prompt,
            historical_memories=json.dumps(historical_memories, indent=2)
        )
        
        try:
            result = self.gen_client.generate_json(prompt)
            return result.get('relevant_elements', [])
        except Exception as e:
            return []
