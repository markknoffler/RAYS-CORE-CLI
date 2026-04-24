#include "rays_generator.cpp"
#include <iostream>

int main(int argc, char *argv[]) {
  std::string test_path =
      "/Users/samreedhbhuyan/Desktop/Win_C/RAYS/YOLO_model_everything/RAYS_V5/"
      "trial_codebases/full_stack";

  if (argc > 1) {
    test_path = argv[1];
  }

  std::cout << "Building registry for: " << test_path << std::endl;

  RaysBuilder builder(test_path);

  builder.build_file_registry();
  builder.write_to_msgpack();

  std::cout << "Done! Created .rays/files.msgpack" << std::endl;

  std::cout << "\nBuilding symbol registry..." << std::endl;

  builder.build_symbol_registry();
  builder.write_symbols_to_msgpack();

  std::cout << "Done! Created .rays/symbols.msgpack" << std::endl;

  std::cout << "\nBuilding relationship registry..." << std::endl;

  builder.build_relationship_registry();
  builder.write_relationships_to_msgpack();

  std::cout << "Done! Created .rays/relationships.msgpack" << std::endl;

  std::cout << "\nBuilding boundary registry..." << std::endl;

  builder.build_boundary_registry();
  builder.write_boundaries_to_msgpack();

  std::cout << "Done! Created .rays/boundaries.msgpack" << std::endl;

  return 0;
}
