"""
rays_generator.py

Python port of rays_generator.cpp.

Builds four msgpack registries inside <project_root>/.rays/:
  files.msgpack         – FileRecord for every recognised source file
  symbols.msgpack       – SymbolRecord for every named symbol
  relationships.msgpack – RelationshipRecord for every cross-symbol edge
  boundaries.msgpack    – BoundaryRecord for entry-points / hotpaths / external I/O

Dependencies
------------
    pip install tree-sitter msgpack
    # language grammars (install whichever you need):
    pip install tree-sitter-python tree-sitter-javascript tree-sitter-typescript
    pip install tree-sitter-cpp tree-sitter-java tree-sitter-go tree-sitter-rust
"""

from __future__ import annotations

import hashlib
import os
import time
import warnings
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional

import msgpack

# ---------------------------------------------------------------------------
# Optional tree-sitter language imports
# ---------------------------------------------------------------------------
def _try_import(module_name: str):
    try:
        import importlib
        mod = importlib.import_module(module_name)
        return mod
    except ImportError:
        return None

_ts_python     = _try_import("tree_sitter_python")
_ts_javascript = _try_import("tree_sitter_javascript")
_ts_typescript = _try_import("tree_sitter_typescript")
_ts_cpp        = _try_import("tree_sitter_cpp")
_ts_java       = _try_import("tree_sitter_java")
_ts_go         = _try_import("tree_sitter_go")
_ts_rust       = _try_import("tree_sitter_rust")

try:
    from tree_sitter import Language, Parser
    try:
        from tree_sitter import QueryCursor as _TSQueryCursor
    except ImportError:
        _TSQueryCursor = None
    try:
        from tree_sitter import Query as _TSQuery
    except ImportError:
        _TSQuery = None
    _TREE_SITTER_AVAILABLE = True
except ImportError:
    _TSQuery = None
    _TSQueryCursor = None
    _TREE_SITTER_AVAILABLE = False


def _make_query(lang: "Language", query_str: str):
    """Create a tree-sitter Query. Works on 0.21 through 0.25+."""
    if _TSQuery is not None:
        try:
            return _TSQuery(lang, query_str)
        except Exception:
            pass
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        return lang.query(query_str)


def _run_query(query, root_node):
    """
    Return (captures_result, matches_result) using whichever API is available.

    tree-sitter 0.25+: QueryCursor(query).captures(node) / .matches(node)
    tree-sitter <0.25: query.captures(node) / query.matches(node)
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        # 0.25+: execution lives on QueryCursor
        if _TSQueryCursor is not None:
            try:
                cursor = _TSQueryCursor(query)
                caps = cursor.captures(root_node) if hasattr(cursor, "captures") else None
                mats = cursor.matches(root_node) if hasattr(cursor, "matches") else None
                return caps, mats
            except Exception:
                pass
        # <0.25: execution lives on Query
        caps = query.captures(root_node) if hasattr(query, "captures") else None
        mats = query.matches(root_node) if hasattr(query, "matches") else None
        return caps, mats


def _query_captures(query, root_node):
    """
    Yield (node, capture_name) pairs. Works on all tree-sitter versions.
    """
    caps, _ = _run_query(query, root_node)
    if caps is None:
        return
    if isinstance(caps, dict):
        # dict[str, list[Node]]  (0.25 QueryCursor style)
        for name, nodes in caps.items():
            for node in (nodes if isinstance(nodes, list) else [nodes]):
                yield node, name
    elif isinstance(caps, list):
        # list[(Node, str)]  (old style)
        for item in caps:
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            a, b = item
            if hasattr(a, "start_byte"):
                yield a, b
            elif hasattr(b, "start_byte"):
                yield b, a


def _query_matches(query, root_node):
    """
    Yield (pattern_idx, captures_dict) pairs. Works on all tree-sitter versions.
    """
    _, mats = _run_query(query, root_node)
    if not mats:
        return
    for item in mats:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        a, b = item
        if isinstance(b, dict):
            yield a, b
        elif isinstance(a, dict):
            yield b, a


# ---------------------------------------------------------------------------
# Data records (mirror the C++ structs)
# ---------------------------------------------------------------------------

@dataclass
class FileRecord:
    relative_path: str
    file_type: str
    language: str
    existence_state: str
    stable_id: str
    file_size: int
    last_modified: int  # unix timestamp


@dataclass
class SymbolRecord:
    symbol_name: str
    symbol_type: str
    file_path: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    visibility: str
    parent_symbol: str


@dataclass
class RelationshipRecord:
    source_symbol: str
    target_symbol: str
    relationship_type: str
    source_file: str
    target_file: str
    source_line: int


@dataclass
class BoundaryRecord:
    symbol_name: str
    boundary_type: str
    file_path: str
    line_number: int
    category: str
    risk_level: str


# ---------------------------------------------------------------------------
# Extension maps  (mirrors the C++ unordered_maps)
# ---------------------------------------------------------------------------

CODE_EXTENSIONS = {
    ".py", ".java", ".js", ".ts", ".jsx", ".tsx",
    ".cpp", ".cc", ".cxx", ".h", ".hpp", ".hxx", ".c",
    ".css", ".html", ".json", ".xml", ".yaml", ".yml",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala",
}

EXT_TO_TYPE: Dict[str, str] = {
    ".py": "code",    ".java": "code",  ".js": "code",
    ".ts": "code",    ".jsx": "code",   ".tsx": "code",
    ".cpp": "code",   ".cc": "code",    ".cxx": "code",
    ".c": "code",     ".h": "code",     ".hpp": "code",
    ".go": "code",    ".rs": "code",    ".rb": "code",
    ".php": "code",   ".swift": "code", ".kt": "code",
    ".scala": "code", ".json": "config",".xml": "config",
    ".yaml": "config",".yml": "config", ".html": "markup",
    ".css": "markup",
}

EXT_TO_LANGUAGE: Dict[str, str] = {
    ".py": "python",      ".java": "java",       ".js": "javascript",
    ".ts": "typescript",  ".jsx": "javascript",  ".tsx": "typescript",
    ".cpp": "cpp",        ".cc": "cpp",           ".cxx": "cpp",
    ".c": "c",            ".h": "cpp",            ".hpp": "cpp",
    ".hxx": "cpp",        ".go": "go",            ".rs": "rust",
    ".rb": "ruby",        ".php": "php",          ".swift": "swift",
    ".kt": "kotlin",      ".scala": "scala",      ".json": "json",
    ".xml": "xml",        ".yaml": "yaml",        ".yml": "yaml",
    ".html": "html",      ".css": "css",
}


# ---------------------------------------------------------------------------
# Tree-sitter query strings (mirrors get_query_for_language /
#   get_relationship_query / get_boundary_query)
# ---------------------------------------------------------------------------

SYMBOL_QUERIES: Dict[str, str] = {
    "python": """
        (function_definition
            name: (identifier) @function.name) @function.def
        (class_definition
            name: (identifier) @class.name) @class.def
        (assignment
            left: (identifier) @constant.name
            right: (_) @constant.value) @constant.def
    """,
    "javascript": """
        (function_declaration
            name: (identifier) @function.name) @function.def
        (class_declaration
            name: (identifier) @class.name) @class.def
        (method_definition
            name: (property_identifier) @method.name) @method.def
        (variable_declarator
            name: (identifier) @function.name
            value: (arrow_function)) @function.def
        (variable_declarator
            name: (identifier) @function.name
            value: (function_expression)) @function.def
    """,
    "typescript": """
        (function_declaration
            name: (identifier) @function.name) @function.def
        (class_declaration
            name: (type_identifier) @class.name) @class.def
        (method_definition
            name: (property_identifier) @method.name) @method.def
        (interface_declaration
            name: (type_identifier) @interface.name) @interface.def
        (variable_declarator
            name: (identifier) @function.name
            value: (arrow_function)) @function.def
        (variable_declarator
            name: (identifier) @function.name
            value: (function_expression)) @function.def
    """,
    "cpp": """
        (function_definition
            declarator: (function_declarator
                declarator: (identifier) @function.name)) @function.def
        (class_specifier
            name: (type_identifier) @class.name) @class.def
        (struct_specifier
            name: (type_identifier) @struct.name) @struct.def
    """,
    "java": """
        (method_declaration
            name: (identifier) @method.name) @method.def
        (class_declaration
            name: (identifier) @class.name) @class.def
        (interface_declaration
            name: (identifier) @interface.name) @interface.def
    """,
}
SYMBOL_QUERIES["c"] = SYMBOL_QUERIES["cpp"]

RELATIONSHIP_QUERIES: Dict[str, str] = {
    "python": """
        (import_statement
            name: (dotted_name) @import.name) @import
        (import_from_statement
            module_name: (dotted_name) @import.module) @import.from
        (call
            function: (identifier) @call.function) @call
        (call
            function: (attribute
                attribute: (identifier) @call.method)) @call.method
        (class_definition
            superclasses: (argument_list
                (identifier) @class.parent)) @inherit
        (assignment
            left: (identifier) @write.target) @write
    """,
    "javascript": """
        (import_statement
            source: (string) @import.source) @import
        (call_expression
            function: (identifier) @call.function) @call
        (call_expression
            function: (member_expression
                property: (property_identifier) @call.method)) @call.method
        (class_declaration
            (class_heritage
                (identifier) @class.parent)) @inherit
        (variable_declarator
            name: (identifier) @write.target) @write
        (interface_declaration
            (extends_type_clause
                (identifier) @interface.parent)) @implement
    """,
    "typescript": """
        (import_statement
            source: (string) @import.source) @import
        (call_expression
            function: (identifier) @call.function) @call
        (call_expression
            function: (member_expression
                property: (property_identifier) @call.method)) @call.method
        (class_declaration
            (class_heritage
                (identifier) @class.parent)) @inherit
        (variable_declarator
            name: (identifier) @write.target) @write
        (interface_declaration
            (extends_type_clause
                (identifier) @interface.parent)) @implement
    """,
    "cpp": """
        (preproc_include
            path: (string_literal) @import.path) @include
        (call_expression
            function: (identifier) @call.function) @call
        (call_expression
            function: (field_expression
                field: (field_identifier) @call.method)) @call.method
        (base_class_clause
            (type_identifier) @class.parent) @inherit
        (assignment_expression
            left: (identifier) @write.target) @write
    """,
    "java": """
        (import_declaration
            (scoped_identifier) @import.name) @import
        (method_invocation
            name: (identifier) @call.function) @call
        (method_invocation
            name: (identifier) @call.method) @call.method
        (superclass
            (type_identifier) @class.parent) @inherit
        (super_interfaces
            (type_list
                (type_identifier) @interface.parent)) @implement
        (assignment_expression
            left: (identifier) @write.target) @write
    """,
    "go": """
        (import_declaration
            (import_spec
                path: (interpreted_string_literal) @import.path)) @import
        (call_expression
            function: (identifier) @call.function) @call
        (call_expression
            function: (selector_expression
                field: (field_identifier) @call.method)) @call.method
        (field_declaration
            type: (type_identifier) @embed.type) @embed
        (assignment_statement
            left: (expression_list
                (identifier) @write.target)) @write
    """,
    "rust": """
        (use_declaration
            argument: (scoped_identifier) @import.name) @import
        (call_expression
            function: (identifier) @call.function) @call
        (call_expression
            function: (field_expression
                field: (field_identifier) @call.method)) @call.method
        (trait_bounds
            (type_identifier) @trait.parent) @implement
        (assignment_expression
            left: (identifier) @write.target) @write
    """,
    "ruby": """
        (call
            method: (identifier) @require.name
            arguments: (argument_list
                (string) @import.path)) @require
        (call
            method: (identifier) @call.function) @call
        (call
            receiver: (identifier)
            method: (identifier) @call.method) @call.method
        (class
            superclass: (superclass
                (identifier) @class.parent)) @inherit
        (assignment
            left: (identifier) @write.target) @write
    """,
    "php": """
        (namespace_use_declaration
            (namespace_use_clause
                (qualified_name) @import.name)) @import
        (function_call_expression
            function: (name) @call.function) @call
        (member_call_expression
            name: (name) @call.method) @call.method
        (base_clause
            (qualified_name) @class.parent) @inherit
        (class_interface_clause
            (qualified_name) @interface.parent) @implement
        (assignment_expression
            left: (variable_name) @write.target) @write
    """,
    "swift": """
        (import_declaration
            (identifier) @import.name) @import
        (call_expression
            (simple_identifier) @call.function) @call
        (call_expression
            (navigation_expression
                (navigation_suffix
                    (simple_identifier) @call.method))) @call.method
        (type_inheritance_clause
            (user_type
                (type_identifier) @class.parent)) @inherit
        (assignment
            (simple_identifier) @write.target) @write
    """,
    "kotlin": """
        (import_header
            (identifier) @import.name) @import
        (call_expression
            (simple_identifier) @call.function) @call
        (call_expression
            (navigation_expression
                (navigation_suffix
                    (simple_identifier) @call.method))) @call.method
        (delegation_specifier
            (user_type
                (type_identifier) @class.parent)) @inherit
        (assignment
            (simple_identifier) @write.target) @write
    """,
    "scala": """
        (import_declaration
            (stable_identifier) @import.name) @import
        (call_expression
            function: (identifier) @call.function) @call
        (call_expression
            function: (field_expression
                field: (identifier) @call.method)) @call.method
        (extends_clause
            (template_body
                (identifier) @class.parent)) @inherit
        (assignment_expression
            left: (identifier) @write.target) @write
    """,
}
RELATIONSHIP_QUERIES["c"] = RELATIONSHIP_QUERIES["cpp"]

BOUNDARY_QUERIES: Dict[str, str] = {
    "python": """
        (function_definition
            name: (identifier) @function.name)
        (call
            function: (attribute
                attribute: (identifier) @io.method))
        (call
            function: (identifier) @call.name)
        (decorator
            (identifier) @decorator.name)
    """,
    "javascript": """
        (call_expression
            function: (member_expression
                object: (identifier) @server.object
                property: (property_identifier) @server.method)) @entry.server
        (function_declaration
            name: (identifier) @function.name) @function.def
        (call_expression
            function: (identifier) @call.name) @call.direct
        (call_expression
            function: (member_expression
                property: (property_identifier) @method.name)) @external.call
    """,
    "java": """
        (method_declaration
            modifiers: (modifiers) @modifiers
            type: (void_type)
            name: (identifier) @method.name
            parameters: (formal_parameters)) @entry.main
        (method_invocation
            object: (identifier) @object.name
            name: (identifier) @method.name) @external.call
    """,
    "cpp": """
        (function_definition
            type: (primitive_type)
            declarator: (function_declarator
                declarator: (identifier) @function.name)) @entry.main
        (call_expression
            function: (identifier) @call.name) @external.call
    """,
    "go": """
        (function_declaration
            name: (identifier) @function.name) @function.def
        (call_expression
            function: (selector_expression
                operand: (identifier) @package.name
                field: (field_identifier) @method.name)) @external.call
    """,
    "rust": """
        (function_item
            name: (identifier) @function.name) @function.def
        (call_expression
            function: (scoped_identifier) @call.name) @external.call
    """,
}
BOUNDARY_QUERIES["typescript"] = BOUNDARY_QUERIES["javascript"]
BOUNDARY_QUERIES["c"] = BOUNDARY_QUERIES["cpp"]


# ---------------------------------------------------------------------------
# Hotpath / entry-point patterns
# ---------------------------------------------------------------------------

ENTRY_POINT_PATTERNS = {
    "main", "index", "app", "server", "cli",
    "run", "start", "manage", "launcher", "bootstrap",
}

HOTPATH_PATTERNS = {
    "auth", "login", "verify", "token", "session",
    "authenticate", "route", "router", "endpoint", "handler",
    "config", "settings", "setup", "init", "configure",
    "middleware", "guard", "policy", "permission",
}

FILESYSTEM_PATTERNS = {
    "open", "read", "write", "file", "fs",
    "path", "directory", "mkdir", "remove", "stat",
    "exists", "readfile", "writefile",
}

NETWORK_PATTERNS = {
    "http", "socket", "fetch", "request", "get", "post", "connect",
    "listen", "server", "client", "axios", "urllib", "requests",
}

DATABASE_PATTERNS = {
    "query", "execute", "database", "db", "sql", "connection",
    "connect", "cursor", "transaction", "commit", "select", "insert",
}

ENV_PATTERNS = {
    "environ", "getenv", "setenv", "env", "environment", "config",
}


# ---------------------------------------------------------------------------
# RaysBuilder
# ---------------------------------------------------------------------------

class RaysBuilder:
    def __init__(self, project_root: str) -> None:
        self.project_root = Path(project_root)

        self.file_registry:         List[FileRecord]         = []
        self.symbol_registry:       List[SymbolRecord]       = []
        self.relationship_registry: List[RelationshipRecord] = []
        self.boundary_registry:     List[BoundaryRecord]     = []

        self._symbol_to_file: Dict[str, str] = {}
        self._lang_cache:     Dict[str, Optional[Language]] = {}

    # ------------------------------------------------------------------
    # Tree-sitter language / parser helpers
    # ------------------------------------------------------------------

    def _get_language(self, language: str) -> Optional["Language"]:
        if not _TREE_SITTER_AVAILABLE:
            return None
        if language in self._lang_cache:
            return self._lang_cache[language]

        lang_obj = None
        try:
            mod_map = {
                "python":     _ts_python,
                "javascript": _ts_javascript,
                "typescript": _ts_typescript,
                "cpp":        _ts_cpp,
                "c":          _ts_cpp,
                "java":       _ts_java,
                "go":         _ts_go,
                "rust":       _ts_rust,
            }
            mod = mod_map.get(language)
            if mod is not None:
                lang_obj = Language(mod.language())
        except Exception:
            lang_obj = None

        self._lang_cache[language] = lang_obj
        return lang_obj

    def _make_parser(self, language: str) -> Optional["Parser"]:
        lang = self._get_language(language)
        if lang is None:
            return None
        try:
            # tree-sitter >= 0.22: Parser(language)
            parser = Parser(lang)
        except TypeError:
            # tree-sitter < 0.22: Parser() then set_language()
            parser = Parser()
            parser.set_language(lang)
        return parser

    # ------------------------------------------------------------------
    # Visibility / parent-symbol helpers (mirrors C++ private methods)
    # ------------------------------------------------------------------

    @staticmethod
    def _determine_visibility(node, source_bytes: bytes) -> str:
        parent = node.parent
        while parent is not None:
            pt = parent.type
            if pt in ("public_field_definition", "public_method_definition"):
                return "public"
            if pt in ("private_field_definition", "private_method_definition"):
                return "private"
            if pt in ("protected_field_definition", "protected_method_definition"):
                return "protected"
            parent = parent.parent

        start_byte = node.start_byte
        if start_byte > 10:
            prefix = source_bytes[start_byte - 10: start_byte].decode("utf-8", errors="replace")
            if "export" in prefix:
                return "exported"
            if "public" in prefix:
                return "public"
            if "private" in prefix:
                return "private"

        return "public"

    @staticmethod
    def _find_parent_symbol(node) -> str:
        parent = node.parent
        class_types = {
            "class_definition", "class_declaration",
            "class_specifier", "interface_declaration",
        }
        while parent is not None:
            if parent.type in class_types:
                for child in parent.children:
                    if child.type in ("identifier", "type_identifier"):
                        return child.text.decode("utf-8", errors="replace") if child.text else ""
            parent = parent.parent
        return ""

    # ------------------------------------------------------------------
    # File registry
    # ------------------------------------------------------------------

    def build_file_registry(self) -> None:
        self.file_registry.clear()

        for entry in self.project_root.rglob("*"):
            if not entry.is_file():
                continue

            ext = entry.suffix
            if ext not in CODE_EXTENSIONS:
                continue

            rel = entry.relative_to(self.project_root)
            rel_str = str(rel)

            # Skip anything inside .rays/
            if rel_str.startswith(".rays"):
                continue

            record = FileRecord(
                relative_path   = rel_str,
                file_type       = EXT_TO_TYPE.get(ext, "unknown"),
                language        = EXT_TO_LANGUAGE.get(ext, "unknown"),
                existence_state = "existing",
                stable_id       = self._compute_file_hash(entry),
                file_size       = entry.stat().st_size,
                last_modified   = int(entry.stat().st_mtime),
            )
            self.file_registry.append(record)

    def write_to_msgpack(self) -> None:
        rays_dir = self.project_root / ".rays"
        rays_dir.mkdir(exist_ok=True)
        output_file = rays_dir / "files.msgpack"
        with open(output_file, "wb") as f:
            msgpack.pack([asdict(r) for r in self.file_registry], f)

    # ------------------------------------------------------------------
    # Symbol registry
    # ------------------------------------------------------------------

    def build_symbol_registry(self) -> None:
        self.symbol_registry.clear()

        for fr in self.file_registry:
            if fr.file_type != "code":
                continue
            self._extract_symbols_from_file(fr.relative_path, fr.language)

    def _extract_symbols_from_file(self, file_path: str, language: str) -> None:
        query_str = SYMBOL_QUERIES.get(language, "")
        if not query_str:
            return

        parser = self._make_parser(language)
        if parser is None:
            return

        abs_path = self.project_root / file_path
        try:
            source_bytes = abs_path.read_bytes()
        except OSError:
            return

        tree = parser.parse(source_bytes)
        if tree is None:
            print(f"[Debug] Failed to parse {file_path}")
            return

        lang = self._get_language(language)
        try:
            query = _make_query(lang, query_str)
        except Exception as e:
            print(f"[Debug] Query creation failed for {file_path}: {e}")
            return

        for capture_node, capture_name in _query_captures(query, tree.root_node):
            if ".name" not in capture_name:
                continue

            sb = capture_node.start_byte
            eb = capture_node.end_byte
            symbol_name = source_bytes[sb:eb].decode("utf-8", errors="replace")

            sp = capture_node.start_point   # (row, col)
            ep = capture_node.end_point

            if "function" in capture_name:
                sym_type = "function"
            elif "class" in capture_name:
                sym_type = "class"
            elif "method" in capture_name:
                sym_type = "method"
            elif "interface" in capture_name:
                sym_type = "interface"
            elif "constant" in capture_name:
                sym_type = "constant"
            elif "struct" in capture_name:
                sym_type = "struct"
            else:
                sym_type = "unknown"

            record = SymbolRecord(
                symbol_name   = symbol_name,
                symbol_type   = sym_type,
                file_path     = file_path,
                start_line    = sp[0] + 1,
                end_line      = ep[0] + 1,
                start_byte    = sb,
                end_byte      = eb,
                visibility    = self._determine_visibility(capture_node, source_bytes),
                parent_symbol = self._find_parent_symbol(capture_node),
            )
            self.symbol_registry.append(record)

    def write_symbols_to_msgpack(self) -> None:
        rays_dir = self.project_root / ".rays"
        rays_dir.mkdir(exist_ok=True)
        output_file = rays_dir / "symbols.msgpack"
        with open(output_file, "wb") as f:
            msgpack.pack([asdict(r) for r in self.symbol_registry], f)

    # ------------------------------------------------------------------
    # Relationship registry
    # ------------------------------------------------------------------

    def build_relationship_registry(self) -> None:
        self.relationship_registry.clear()
        self._build_symbol_map()

        for fr in self.file_registry:
            if fr.file_type != "code":
                continue
            self._extract_relationships_from_file(fr.relative_path, fr.language)

    def _build_symbol_map(self) -> None:
        self._symbol_to_file.clear()
        for sym in self.symbol_registry:
            if sym.parent_symbol:
                key = f"{sym.parent_symbol}::{sym.symbol_name}"
                self._symbol_to_file[key] = sym.file_path
            self._symbol_to_file[sym.symbol_name] = sym.file_path

    def _resolve_target_file(self, target_symbol: str) -> str:
        return self._symbol_to_file.get(target_symbol, "")

    def _extract_relationships_from_file(self, file_path: str, language: str) -> None:
        query_str = RELATIONSHIP_QUERIES.get(language, "")
        if not query_str:
            return

        parser = self._make_parser(language)
        if parser is None:
            return

        abs_path = self.project_root / file_path
        try:
            source_bytes = abs_path.read_bytes()
        except OSError:
            return

        tree = parser.parse(source_bytes)
        if tree is None:
            return

        lang = self._get_language(language)
        try:
            query = _make_query(lang, query_str)
        except Exception:
            return

        for pattern_idx, captures_dict in _query_matches(query, tree.root_node):
            relationship_type = ""
            target_symbol     = ""
            source_line       = 0

            # captures_dict maps capture_name -> list[Node]
            for capture_name, nodes in captures_dict.items():
                for node in (nodes if isinstance(nodes, list) else [nodes]):
                    sb = node.start_byte
                    eb = node.end_byte
                    text = source_bytes[sb:eb].decode("utf-8", errors="replace").strip(" \n\r\t\"'")
                    source_line = node.start_point[0] + 1

                    if "import" in capture_name or "require" in capture_name:
                        relationship_type = "imports"
                        target_symbol = text
                    elif "call.function" in capture_name:
                        relationship_type = "calls"
                        target_symbol = text
                    elif "call.method" in capture_name:
                        relationship_type = "calls"
                        target_symbol = text
                    elif "class.parent" in capture_name:
                        relationship_type = "extends"
                        target_symbol = text
                    elif "interface.parent" in capture_name:
                        relationship_type = "implements"
                        target_symbol = text
                    elif "trait.parent" in capture_name:
                        relationship_type = "implements"
                        target_symbol = text
                    elif "embed" in capture_name:
                        relationship_type = "embeds"
                        target_symbol = text
                    elif "write.target" in capture_name:
                        relationship_type = "writes"
                        target_symbol = text

            if relationship_type and target_symbol:
                record = RelationshipRecord(
                    source_symbol     = file_path,
                    target_symbol     = target_symbol,
                    relationship_type = relationship_type,
                    source_file       = file_path,
                    target_file       = self._resolve_target_file(target_symbol),
                    source_line       = source_line,
                )
                self.relationship_registry.append(record)

    def write_relationships_to_msgpack(self) -> None:
        rays_dir = self.project_root / ".rays"
        rays_dir.mkdir(exist_ok=True)
        output_file = rays_dir / "relationships.msgpack"
        with open(output_file, "wb") as f:
            msgpack.pack([asdict(r) for r in self.relationship_registry], f)

    # ------------------------------------------------------------------
    # Boundary registry
    # ------------------------------------------------------------------

    @staticmethod
    def _is_entry_point_file(filename: str) -> bool:
        lower = filename.lower()
        return any(p in lower for p in ENTRY_POINT_PATTERNS)

    @staticmethod
    def _is_hotpath_symbol(symbol_name: str) -> bool:
        lower = symbol_name.lower()
        return any(p in lower for p in HOTPATH_PATTERNS)

    @staticmethod
    def categorize_boundary(symbol_name: str, _context: str = "") -> str:
        lower = symbol_name.lower()
        if any(p in lower for p in FILESYSTEM_PATTERNS):
            return "filesystem"
        if any(p in lower for p in NETWORK_PATTERNS):
            return "network"
        if any(p in lower for p in DATABASE_PATTERNS):
            return "database"
        if any(p in lower for p in ENV_PATTERNS):
            return "environment"
        return "unknown"

    @staticmethod
    def assess_risk_level(boundary_type: str, category: str) -> str:
        if boundary_type == "entry_point":
            return "critical"
        if category in ("network", "database"):
            return "high"
        if category in ("filesystem", "environment"):
            return "medium"
        if boundary_type == "hotpath":
            return "high"
        return "low"

    def build_boundary_registry(self) -> None:
        self.boundary_registry.clear()

        # Entry-point files
        for fr in self.file_registry:
            filename = Path(fr.relative_path).name
            if self._is_entry_point_file(filename):
                self.boundary_registry.append(BoundaryRecord(
                    symbol_name   = filename,
                    boundary_type = "entry_point",
                    file_path     = fr.relative_path,
                    line_number   = 1,
                    category      = "application_entry",
                    risk_level    = "critical",
                ))

        # main / __main__ symbols and hotpath symbols
        for sym in self.symbol_registry:
            if sym.symbol_name in ("main", "__main__"):
                self.boundary_registry.append(BoundaryRecord(
                    symbol_name   = sym.symbol_name,
                    boundary_type = "entry_point",
                    file_path     = sym.file_path,
                    line_number   = sym.start_line,
                    category      = "main_function",
                    risk_level    = "critical",
                ))

            if self._is_hotpath_symbol(sym.symbol_name):
                self.boundary_registry.append(BoundaryRecord(
                    symbol_name   = sym.symbol_name,
                    boundary_type = "hotpath",
                    file_path     = sym.file_path,
                    line_number   = sym.start_line,
                    category      = "critical_path",
                    risk_level    = "high",
                ))

        # External boundaries from relationships
        for rel in self.relationship_registry:
            category = self.categorize_boundary(rel.target_symbol)
            if category != "unknown":
                self.boundary_registry.append(BoundaryRecord(
                    symbol_name   = rel.target_symbol,
                    boundary_type = "external_boundary",
                    file_path     = rel.source_file,
                    line_number   = rel.source_line,
                    category      = category,
                    risk_level    = self.assess_risk_level("external_boundary", category),
                ))

        # Per-file boundary extraction via tree-sitter
        for fr in self.file_registry:
            self._extract_boundaries_from_file(fr.relative_path, fr.language)

    def _extract_boundaries_from_file(self, file_path: str, language: str) -> None:
        query_str = BOUNDARY_QUERIES.get(language, RELATIONSHIP_QUERIES.get(language, ""))
        if not query_str:
            return

        parser = self._make_parser(language)
        if parser is None:
            return

        abs_path = self.project_root / file_path
        try:
            source_bytes = abs_path.read_bytes()
        except OSError:
            return

        tree = parser.parse(source_bytes)
        if tree is None:
            return

        lang = self._get_language(language)
        try:
            query = _make_query(lang, query_str)
        except Exception:
            return

        filename = Path(file_path).name
        is_entry_file = self._is_entry_point_file(filename)

        for pattern_idx, captures_dict in _query_matches(query, tree.root_node):
            symbol_name   = ""
            boundary_type = ""
            line_number   = 0

            for capture_name, nodes in captures_dict.items():
                for node in (nodes if isinstance(nodes, list) else [nodes]):
                    sb = node.start_byte
                    eb = node.end_byte
                    text = source_bytes[sb:eb].decode("utf-8", errors="replace")
                    line_number = node.start_point[0] + 1

                    if "function.name" in capture_name or "method.name" in capture_name:
                        symbol_name = text
                        if text in ("main", "__main__"):
                            boundary_type = "entry_point"
                        elif is_entry_file:
                            boundary_type = "entry_point"
                        elif self._is_hotpath_symbol(text):
                            boundary_type = "hotpath"

                    elif "call.name" in capture_name or "io.method" in capture_name or "method.name" in capture_name:
                        symbol_name = text
                        cat = self.categorize_boundary(text)
                        if cat != "unknown":
                            boundary_type = "external_boundary"

                    elif "decorator" in capture_name:
                        symbol_name = text
                        if "route" in text or "app" in text:
                            boundary_type = "hotpath"

                    elif capture_name == "main.check":
                        if text == "__name__":
                            boundary_type = "entry_point"
                            symbol_name   = "__main__"

            if symbol_name and boundary_type:
                record = BoundaryRecord(
                    symbol_name   = symbol_name,
                    boundary_type = boundary_type,
                    file_path     = file_path,
                    line_number   = line_number,
                    category      = self.categorize_boundary(symbol_name),
                    risk_level    = self.assess_risk_level(boundary_type, self.categorize_boundary(symbol_name)),
                )
                self.boundary_registry.append(record)

        # Also add hotpath symbols from symbol_registry for this file
        for sym in self.symbol_registry:
            if sym.file_path == file_path and self._is_hotpath_symbol(sym.symbol_name):
                self.boundary_registry.append(BoundaryRecord(
                    symbol_name   = sym.symbol_name,
                    boundary_type = "hotpath",
                    file_path     = file_path,
                    line_number   = sym.start_line,
                    category      = "critical_path",
                    risk_level    = "high",
                ))

    def write_boundaries_to_msgpack(self) -> None:
        rays_dir = self.project_root / ".rays"
        rays_dir.mkdir(exist_ok=True)
        output_file = rays_dir / "boundaries.msgpack"
        with open(output_file, "wb") as f:
            msgpack.pack([asdict(r) for r in self.boundary_registry], f)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_file_hash(filepath: Path) -> str:
        md5 = hashlib.md5()
        try:
            with open(filepath, "rb") as f:
                while chunk := f.read(8192):
                    md5.update(chunk)
        except OSError:
            return ""
        return md5.hexdigest()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <project_root>")
        sys.exit(1)

    root = sys.argv[1]
    builder = RaysBuilder(root)

    print("[rays] Building file registry ...")
    builder.build_file_registry()
    builder.write_to_msgpack()
    print(f"  -> {len(builder.file_registry)} files indexed")

    print("[rays] Building symbol registry ...")
    builder.build_symbol_registry()
    builder.write_symbols_to_msgpack()
    print(f"  -> {len(builder.symbol_registry)} symbols extracted")

    print("[rays] Building relationship registry ...")
    builder.build_relationship_registry()
    builder.write_relationships_to_msgpack()
    print(f"  -> {len(builder.relationship_registry)} relationships extracted")

    print("[rays] Building boundary registry ...")
    builder.build_boundary_registry()
    builder.write_boundaries_to_msgpack()
    print(f"  -> {len(builder.boundary_registry)} boundaries extracted")

    print("[rays] Done. Output written to", Path(root) / ".rays")
