"""diagnose_ts.py v3 — probes for QueryCursor and all other 0.25 execution APIs"""
import sys, warnings, importlib.metadata, inspect
print("tree-sitter:", importlib.metadata.version("tree-sitter"))

import tree_sitter_python as tsp
from tree_sitter import Language, Parser
raw = tsp.language()
lang = raw if isinstance(raw, Language) else Language(raw)
try:
    parser = Parser(lang)
except TypeError:
    parser = Parser(); parser.set_language(lang)

src = b"def foo(x):\n    return x\n\nclass Bar:\n    def method(self): pass\n"
tree = parser.parse(src)
root = tree.root_node

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    query = lang.query("(function_definition name: (identifier) @function.name)")

# ── What's in the tree_sitter module? ────────────────────────────────────────
import tree_sitter as ts_mod
print("\n--- tree_sitter module exports ---")
print([x for x in dir(ts_mod) if not x.startswith("_")])

# ── Try every possible execution object ──────────────────────────────────────
for name in ["QueryCursor", "Node", "Query"]:
    cls = getattr(ts_mod, name, None)
    if cls is None:
        print(f"\n{name}: NOT in module")
        continue
    print(f"\n{name}: {cls}")
    print(f"  dir: {[x for x in dir(cls) if not x.startswith('_')]}")

# ── Try QueryCursor if it exists ─────────────────────────────────────────────
QueryCursor = getattr(ts_mod, "QueryCursor", None)
if QueryCursor:
    print("\n--- Trying QueryCursor ---")
    # Try different constructor signatures
    for args, kwargs in [
        ((query,), {}),
        ((query, root), {}),
        ((root,), {}),
    ]:
        try:
            cur = QueryCursor(*args, **kwargs)
            print(f"  QueryCursor{args} OK: {cur}")
            print(f"  cursor dir: {[x for x in dir(cur) if not x.startswith('_')]}")
            # Try to execute
            for method in ["exec", "execute", "captures", "matches", "set_point_range"]:
                fn = getattr(cur, method, None)
                if fn:
                    print(f"  has .{method}()")
                    if method in ("exec", "execute"):
                        try:
                            fn(root)
                            print(f"    .{method}(root) OK")
                            # now try captures/matches
                            for m2 in ["captures", "matches"]:
                                fn2 = getattr(cur, m2, None)
                                if fn2:
                                    try:
                                        r = fn2()
                                        print(f"    .{m2}() -> type={type(r)} repr={repr(r)[:200]}")
                                    except Exception as e:
                                        print(f"    .{m2}() FAILED: {e}")
                        except Exception as e:
                            print(f"    .{method}(root) FAILED: {e}")
            break
        except Exception as e:
            print(f"  QueryCursor{args} FAILED: {e}")

# ── Inspect tree.root_node fully ─────────────────────────────────────────────
print(f"\n--- Node full dir ---")
print([x for x in dir(root) if not x.startswith("_")])

print("\n" + "="*60)
