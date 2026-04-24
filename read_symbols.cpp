#include "rays_generator.cpp"
#include <iostream>
#include <fstream>

int main() {
    std::string test_path = "/Users/samreedhbhuyan/Desktop/Win_C/RAYS/YOLO_model_everything/RAYS_V5/trial_codebases/alphafold";
    
    fs::path msgpack_file = fs::path(test_path) / ".rays" / "symbols.msgpack";
    
    if (!fs::exists(msgpack_file)) {
        std::cout << "Error: " << msgpack_file << " does not exist!" << std::endl;
        std::cout << "Run './test_rays' first to generate it." << std::endl;
        return 1;
    }
    
    std::ifstream ifs(msgpack_file, std::ios::binary);
    
    std::string buffer_str((std::istreambuf_iterator<char>(ifs)), std::istreambuf_iterator<char>());
    
    msgpack::object_handle oh = msgpack::unpack(buffer_str.data(), buffer_str.size());
    
    msgpack::object obj = oh.get();
    
    std::vector<SymbolRecord> symbol_registry;
    obj.convert(symbol_registry);
    
    std::cout << "==================================================" << std::endl;
    std::cout << "Total symbols found: " << symbol_registry.size() << std::endl;
    std::cout << "==================================================" << std::endl << std::endl;
    
    for (const auto& record : symbol_registry) {
        std::cout << "Symbol: " << record.symbol_name << std::endl;
        std::cout << "  Type: " << record.symbol_type << std::endl;
        std::cout << "  File: " << record.file_path << std::endl;
        std::cout << "  Location: Line " << record.start_line << "-" << record.end_line << std::endl;
        std::cout << "  Byte Range: " << record.start_byte << "-" << record.end_byte << std::endl;
        std::cout << "  Visibility: " << record.visibility << std::endl;
        
        if (!record.parent_symbol.empty()) {
            std::cout << "  Parent: " << record.parent_symbol << std::endl;
        }
        
        std::cout << "--------------------------------------------------" << std::endl;
    }
    
    std::cout << std::endl << "Total: " << symbol_registry.size() << " symbols" << std::endl;
    
    return 0;
}

