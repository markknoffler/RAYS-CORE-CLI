"""
read_boundaries.py  —  Python equivalent of read_boundaries.cpp
Reads and prints .rays/boundaries.msgpack
Usage: python read_boundaries.py <project_root>
"""
import sys
from pathlib import Path
import msgpack

def main():
    test_path = sys.argv[1] if len(sys.argv) > 1 else \
        "/Users/samreedhbhuyan/Desktop/Win_C/RAYS/YOLO_model_everything/RAYS_V5/trial_codebases/alphafold"

    msgpack_file = Path(test_path) / ".rays" / "boundaries.msgpack"

    if not msgpack_file.exists():
        print(f"Error: {msgpack_file} does not exist!")
        print("Run 'python rays_generator.py' first to generate it.")
        sys.exit(1)

    with open(msgpack_file, "rb") as f:
        boundary_registry = msgpack.unpack(f, raw=False)

    print("==================================================")
    print(f"Total boundaries found: {len(boundary_registry)}")
    print("==================================================\n")

    for record in boundary_registry:
        print(f"Symbol: {record['symbol_name']}")
        print(f"  Boundary Type: {record['boundary_type']}")
        print(f"  File:          {record['file_path']}")
        print(f"  Line:          {record['line_number']}")
        print(f"  Category:      {record['category']}")
        print(f"  Risk Level:    {record['risk_level']}")
        print("--------------------------------------------------")

    print(f"\nTotal: {len(boundary_registry)} boundaries")

if __name__ == "__main__":
    main()
