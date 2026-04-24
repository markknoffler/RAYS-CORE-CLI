#include "rays_generator.cpp"
#include <iostream>
#include <fstream>
#include <ctime>

int main() {
    std::string test_path = "/Users/samreedhbhuyan/Desktop/Win_C/RAYS/YOLO_model_everything/RAYS_V5/trial_codebases/alphafold";
    
    fs::path msgpack_file = fs::path(test_path) / ".rays" / "files.msgpack";
    
    if (!fs::exists(msgpack_file)) {
        std::cout << "Error: " << msgpack_file << " does not exist!" << std::endl;
        return 1;
    }
    
    std::ifstream ifs(msgpack_file, std::ios::binary);
    
    std::string buffer_str((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
    
    msgpack::object_handle oh = msgpack::unpack(buffer_str.data(), buffer_str.size());
    
    msgpack::object obj = oh.get();
    
    std::vector<FileRecord> file_registry;
    obj.convert(file_registry);
    
    std::cout << "==================================================" << std::endl;
    std::cout << "Total files found: " << file_registry.size() << std::endl;
    std::cout << "==================================================" << std::endl << std::endl;
    
    for (const auto& record : file_registry) {
        std::cout << "File: " << record.relative_path << std::endl;
        std::cout << "  Type: " << record.file_type << std::endl;
        std::cout << "  Language: " << record.language << std::endl;
        std::cout << "  State: " << record.existence_state << std::endl;
        std::cout << "  Hash: " << record.stable_id << std::endl;
        std::cout << "  Size: " << record.file_size << " bytes" << std::endl;
        
        std::time_t t = record.last_modified;
        std::cout << "  Modified: " << std::ctime(&t);
        
        std::cout << "--------------------------------------------------" << std::endl;
    }
    
    std::cout << std::endl << "Total: " << file_registry.size() << " files" << std::endl;
    
    return 0;
}

