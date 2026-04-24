# indexing.py
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional
from chunk_generator import VectorDBGenerator
import rays_ui
import sys
import os

# Priority to local directory to avoid cross-version conflicts
sys.path.insert(0, str(Path(__file__).parent.absolute()))

class Indexer:
    def __init__(self, codebase_root: Path, rays_dir: Path, config: dict):
        self.codebase_root = codebase_root
        self.rays_dir = rays_dir
        self.config = config

    def index_codebase(self, force_reindex: bool = False, skip_if_exists: bool = True):
        """
        Step 1: Generate .rays files using Python RaysBuilder
        """
        # Check if .rays and mandatory files exist
        mandatory_files = ["symbols.msgpack", "relationships.msgpack", "files.msgpack", "boundaries.msgpack"]
        all_files_exist = self.rays_dir.exists() and all((self.rays_dir / f).exists() for f in mandatory_files)

        if all_files_exist and skip_if_exists and not force_reindex:
            rays_ui.print_step("Codebase index is up to date")
            return
        
        if force_reindex and self.rays_dir.exists():
            rays_ui.print_warning("Force reindex: clearing existing index")
            import shutil
            shutil.rmtree(self.rays_dir)
        
        rays_ui.print_phase("Mapping codebase")
        
        from rays_generator import RaysBuilder
        
        try:
            builder = RaysBuilder(str(self.codebase_root))
            
            with rays_ui.spinner("Scanning files"):
                builder.build_file_registry()
                builder.write_to_msgpack()
            rays_ui.print_step("File registry built")
            
            with rays_ui.spinner("Analyzing symbols"):
                builder.build_symbol_registry()
                builder.write_symbols_to_msgpack()
            rays_ui.print_step("Symbol registry built")
            
            with rays_ui.spinner("Tracing relationships"):
                builder.build_relationship_registry()
                builder.write_relationships_to_msgpack()
            rays_ui.print_step("Relationship graph built")
            
            with rays_ui.spinner("Detecting boundaries"):
                builder.build_boundary_registry()
                builder.write_boundaries_to_msgpack()
            rays_ui.print_step("Boundary map built")
            
            rays_ui.print_step(f"Index created at {self.rays_dir}")
        except Exception as e:
            rays_ui.print_error(f"Indexing failed: {e}")
            raise
    
    def create_vector_database(self, force_rebuild: bool = False, affected_files: Optional[List[str]] = None):
        """
        Step 2: Generate vector database using chunk_generator.py
        """
        chroma_db_path = self.rays_dir / "chroma_db"
        
        # Check if ChromaDB already exists and is populated
        chroma_is_populated = False
        if chroma_db_path.exists():
            try:
                import chromadb
                client = chromadb.PersistentClient(path=str(chroma_db_path))
                col = client.get_collection("code_chunks")
                if col.count() > 0:
                    chroma_is_populated = True
                else:
                    rays_ui.print_warning("Vector database exists but is empty — rebuilding")
            except Exception:
                pass

        if chroma_is_populated and not force_rebuild and not affected_files:
            rays_ui.print_step("Vector database is up to date")
            return
        
        if force_rebuild and chroma_db_path.exists():
            rays_ui.print_warning("Force rebuild: clearing vector database")
            import shutil
            shutil.rmtree(chroma_db_path)
        
        rays_ui.print_phase("Understanding codebase")
        
        try:
            chunk_gen = VectorDBGenerator(str(self.codebase_root), config=self.config)
            
            with rays_ui.spinner("Generating embeddings"):
                result = chunk_gen.build(affected_files=affected_files)
            
            if result is False:
                rays_ui.print_warning("Embedding generation skipped — provider unreachable")
            elif affected_files:
                rays_ui.print_step(f"Updated embeddings for {len(affected_files)} files")
            else:
                rays_ui.print_step(f"Vector database created at {chroma_db_path}")
        except Exception as e:
            rays_ui.print_error(f"Vector database creation failed: {e}")
            raise
