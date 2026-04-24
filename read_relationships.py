"""
read_relationships.py  —  Python equivalent of read_relationships.cpp
Reads and prints .rays/relationships.msgpack
Usage: python read_relationships.py <project_root>
"""
import sys
from pathlib import Path
import msgpack

def main():
    test_path = sys.argv[1] if len(sys.argv) > 1 else \
        "/Users/samreedhbhuyan/Desktop/Win_C/RAYS/YOLO_model_everything/RAYS_V5/trial_codebases/alphafold"

    msgpack_file = Path(test_path) / ".rays" / "relationships.msgpack"

    if not msgpack_file.exists():
        print(f"Error: {msgpack_file} does not exist!")
        print("Run 'python rays_generator.py' first to generate it.")
        sys.exit(1)

    with open(msgpack_file, "rb") as f:
        relationship_registry = msgpack.unpack(f, raw=False)

    print("==================================================")
    print(f"Total relationships found: {len(relationship_registry)}")
    print("==================================================\n")

    for record in relationship_registry:
        print(f"Relationship: {record['relationship_type']}")
        print(f"  Source:      {record['source_symbol']}")
        print(f"  Target:      {record['target_symbol']}")
        print(f"  Source File: {record['source_file']}")
        if record.get('target_file'):
            print(f"  Target File: {record['target_file']}")
        print(f"  Line:        {record['source_line']}")
        print("--------------------------------------------------")

    print(f"\nTotal: {len(relationship_registry)} relationships")

if __name__ == "__main__":
    main()
