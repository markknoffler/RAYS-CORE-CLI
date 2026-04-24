"""
read_rays.py  —  Python equivalent of read_rays.cpp
Reads and prints .rays/files.msgpack
Usage: python read_rays.py <project_root>
"""
import sys
from pathlib import Path
from datetime import datetime
import msgpack

def main():
    test_path = sys.argv[1] if len(sys.argv) > 1 else \
        "/Users/samreedhbhuyan/Desktop/Win_C/RAYS/YOLO_model_everything/RAYS_V5/trial_codebases/alphafold"

    msgpack_file = Path(test_path) / ".rays" / "files.msgpack"

    if not msgpack_file.exists():
        print(f"Error: {msgpack_file} does not exist!")
        print("Run 'python rays_generator.py' first to generate it.")
        sys.exit(1)

    with open(msgpack_file, "rb") as f:
        file_registry = msgpack.unpack(f, raw=False)

    print("==================================================")
    print(f"Total files found: {len(file_registry)}")
    print("==================================================\n")

    for record in file_registry:
        print(f"File: {record['relative_path']}")
        print(f"  Type:     {record['file_type']}")
        print(f"  Language: {record['language']}")
        print(f"  State:    {record['existence_state']}")
        print(f"  Hash:     {record['stable_id']}")
        print(f"  Size:     {record['file_size']} bytes")
        ts = record['last_modified']
        print(f"  Modified: {datetime.fromtimestamp(ts).strftime('%a %b %d %H:%M:%S %Y')}")
        print("--------------------------------------------------")

    print(f"\nTotal: {len(file_registry)} files")

if __name__ == "__main__":
    main()
