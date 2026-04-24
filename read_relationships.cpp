#include "rays_generator.cpp"
#include <iostream>
#include <fstream>

int main() {
    std::string test_path = "/Users/samreedhbhuyan/Desktop/Win_C/RAYS/YOLO_model_everything/RAYS_V5/trial_codebases/alphafold";
    
    fs::path msgpack_file = fs::path(test_path) / ".rays" / "relationships.msgpack";
    
    if (!fs::exists(msgpack_file)) {
        std::cout << "Error: " << msgpack_file << " does not exist!" << std::endl;
        std::cout << "Run './test_rays' first to generate it." << std::endl;
        return 1;
    }
    
    std::ifstream ifs(msgpack_file, std::ios::binary);
    
    std::string buffer_str((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
    
    msgpack::object_handle oh = msgpack::unpack(buffer_str.data(), buffer_str.size());
    
    msgpack::object obj = oh.get();
    
    std::vector<RelationshipRecord> relationship_registry;
    obj.convert(relationship_registry);
    
    std::cout << "==================================================" << std::endl;
    std::cout << "Total relationships found: " << relationship_registry.size() << std::endl;
    std::cout << "==================================================" << std::endl << std::endl;
    
    for (const auto& record : relationship_registry) {
        std::cout << "Relationship: " << record.relationship_type << std::endl;
        std::cout << "  Source: " << record.source_symbol << std::endl;
        std::cout << "  Target: " << record.target_symbol << std::endl;
        std::cout << "  Source File: " << record.source_file << std::endl;
        if (!record.target_file.empty()) {
            std::cout << "  Target File: " << record.target_file << std::endl;
        }
        std::cout << "  Line: " << record.source_line << std::endl;
        std::cout << "--------------------------------------------------" << std::endl;
    }
    
    std::cout << std::endl << "Total: " << relationship_registry.size() << " relationships" << std::endl;
    
    return 0;
}

