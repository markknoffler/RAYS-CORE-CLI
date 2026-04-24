"""
read_symbols.py  —  Python equivalent of read_symbols.cpp
Reads and prints .rays/symbols.msgpack
Usage: python read_symbols.py <project_root>
"""
import sys
from pathlib import Path
import msgpack

def main():
    test_path = sys.argv[1] if len(sys.argv) > 1 else \
        "/Users/samreedhbhuyan/Desktop/Win_C/RAYS/YOLO_model_everything/RAYS_V5/trial_codebases/alphafold"

    msgpack_file = Path(test_path) / ".rays" / "symbols.msgpack"

    if not msgpack_file.exists():
        print(f"Error: {msgpack_file} does not exist!")
        print("Run 'python rays_generator.py' first to generate it.")
        sys.exit(1)

    with open(msgpack_file, "rb") as f:
        symbol_registry = msgpack.unpack(f, raw=False)

    print("==================================================")
    print(f"Total symbols found: {len(symbol_registry)}")
    print("==================================================\n")

    for record in symbol_registry:
        print(f"Symbol: {record['symbol_name']}")
        print(f"  Type:       {record['symbol_type']}")
        print(f"  File:       {record['file_path']}")
        print(f"  Location:   Line {record['start_line']}-{record['end_line']}")
        print(f"  Byte Range: {record['start_byte']}-{record['end_byte']}")
        print(f"  Visibility: {record['visibility']}")
        if record.get('parent_symbol'):
            print(f"  Parent:     {record['parent_symbol']}")
        print("--------------------------------------------------")

    print(f"\nTotal: {len(symbol_registry)} symbols")

if __name__ == "__main__":
    main()
