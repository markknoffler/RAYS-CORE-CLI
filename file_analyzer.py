
import msgpack
from pathlib import Path
from collections import defaultdict

class FileAnalyzer:
    """Extract file-level metadata from existing symbols."""
    
    def __init__(self, rays_dir: Path):
        self.rays_dir = rays_dir
        self.symbols_file = rays_dir / "symbols.msgpack"
        self.relationships_file = rays_dir / "relationships.msgpack"
    
    def generate_file_anchors(self) -> dict:
        """
        Generate file anchors from existing symbol data.
        No need to re-parse - use what we have!
        """
        with open(self.symbols_file, 'rb') as f:
            symbols = msgpack.unpackb(f.read(), raw=False)
        
        with open(self.relationships_file, 'rb') as f:
            relationships = msgpack.unpackb(f.read(), raw=False)
        
        # Group symbols by file
        files = defaultdict(lambda: {
            'imports': set(),
            'top_level_symbols': [],
            'classes': [],
            'functions': [],
            'symbol_order': []
        })
        
        for symbol in symbols:
            file_path = symbol.get('file_path', '')
            symbol_name = symbol.get('symbol_name', '')
            symbol_type = symbol.get('symbol_type', '')
            parent = symbol.get('parent_symbol')
            
            if not file_path:
                continue
            
            # Top-level symbols (no parent)
            if not parent:
                files[file_path]['top_level_symbols'].append(symbol_name)
            
            # Categorize by type
            if symbol_type == 'class':
                files[file_path]['classes'].append(symbol_name)
            elif symbol_type == 'function':
                files[file_path]['functions'].append(symbol_name)
            
            # Symbol order (by start_line)
            files[file_path]['symbol_order'].append({
                'name': symbol_name,
                'type': symbol_type,
                'line': symbol.get('start_line', 0),
                'parent': parent
            })
        
        # Extract imports from relationships
        for rel in relationships:
            if rel.get('relationship_type') == 'import':
                src_file = rel.get('source_file', '')
                if src_file:
                    files[src_file]['imports'].add(rel.get('target_symbol', ''))
        
        # Sort symbol order by line number
        for file_path in files:
            files[file_path]['symbol_order'].sort(key=lambda x: x['line'])
            files[file_path]['imports'] = list(files[file_path]['imports'])
        
        return dict(files)
    
    def infer_file_role(self, file_path: str, file_data: dict) -> str:
        """Infer file role from its contents."""
        # Simple heuristics
        path_lower = file_path.lower()
        
        if 'test' in path_lower:
            return 'testing'
        elif 'model' in path_lower:
            return 'data models'
        elif 'view' in path_lower or 'route' in path_lower:
            return 'routing / views'
        elif 'auth' in path_lower:
            return 'authentication'
        elif 'util' in path_lower or 'helper' in path_lower:
            return 'utilities'
        elif 'config' in path_lower:
            return 'configuration'
        
        # Infer from symbol types
        if len(file_data['classes']) > len(file_data['functions']):
            return 'class definitions'
        elif len(file_data['functions']) > 0:
            return 'functions / logic'
        
        return 'general'

