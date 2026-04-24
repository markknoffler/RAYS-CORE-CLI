#include "rays_generator.cpp"
#include <iostream>
#include <fstream>

int main() {
    std::string test_path = "/Users/samreedhbhuyan/Desktop/Win_C/RAYS/YOLO_model_everything/RAYS_V5/trial_codebases/alphafold";
    
    fs::path msgpack_file = fs::path(test_path) / ".rays" / "boundaries.msgpack";
    
    if (!fs::exists(msgpack_file)) {
        std::cout << "Error: " << msgpack_file << " does not exist!" << std::endl;
        std::cout << "Run './test_rays' first to generate it." << std::endl;
        return 1;
    }
    
    std::ifstream ifs(msgpack_file, std::ios::binary);
    std::string buffer_str((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
    
    msgpack::object_handle oh = msgpack::unpack(buffer_str.data(), buffer_str.size());
    msgpack::object obj = oh.get();
    
    std::vector<BoundaryRecord> boundary_registry;
    obj.convert(boundary_registry);
    
    std::cout << "==================================================" << std::endl;
    std::cout << "Total boundaries found: " << boundary_registry.size() << std::endl;
    std::cout << "==================================================" << std::endl << std::endl;
    
    for (const auto& record : boundary_registry) {
        std::cout << "Symbol: " << record.symbol_name << std::endl;
        std::cout << "  Boundary Type: " << record.boundary_type << std::endl;
        std::cout << "  File: " << record.file_path << std::endl;
        std::cout << "  Line: " << record.line_number << std::endl;
        std::cout << "  Category: " << record.category << std::endl;
        std::cout << "  Risk Level: " << record.risk_level << std::endl;
        std::cout << "--------------------------------------------------" << std::endl;
    }
    
    std::cout << std::endl << "Total: " << boundary_registry.size() << " boundaries" << std::endl;
    
    return 0;
}

