#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <msgpack.hpp>
#include <openssl/md5.h>
#include <sstream>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <vector>

#include <tree_sitter/api.h>

extern "C" {
TSLanguage *tree_sitter_python();
TSLanguage *tree_sitter_javascript();
TSLanguage *tree_sitter_cpp();
TSLanguage *tree_sitter_java();
TSLanguage *tree_sitter_typescript();
TSLanguage *tree_sitter_go();
TSLanguage *tree_sitter_rust();
}

namespace fs = std::filesystem;

struct FileRecord {
  std::string relative_path;
  std::string file_type;
  std::string language;
  std::string existence_state;
  std::string stable_id;
  size_t file_size;
  std::time_t last_modified;

  MSGPACK_DEFINE_MAP(relative_path, file_type, language, existence_state,
                     stable_id, file_size, last_modified);
};

struct SymbolRecord {
  std::string symbol_name;
  std::string symbol_type;
  std::string file_path;
  int start_line;
  int end_line;
  int start_byte;
  int end_byte;
  std::string visibility;
  std::string parent_symbol;

  MSGPACK_DEFINE_MAP(symbol_name, symbol_type, file_path, start_line, end_line,
                     start_byte, end_byte, visibility, parent_symbol);
};

struct RelationshipRecord {
  std::string source_symbol;
  std::string target_symbol;
  std::string relationship_type;
  std::string source_file;
  std::string target_file;
  int source_line;

  MSGPACK_DEFINE_MAP(source_symbol, target_symbol, relationship_type,
                     source_file, target_file, source_line);
};

struct BoundaryRecord {
  std::string symbol_name;
  std::string boundary_type;
  std::string file_path;
  int line_number;
  std::string category;
  std::string risk_level;

  MSGPACK_DEFINE_MAP(symbol_name, boundary_type, file_path, line_number,
                     category, risk_level);
};

class RaysBuilder {
private:
  std::vector<SymbolRecord> symbol_registry;

  TSLanguage *get_language_parser(const std::string &language) {
    if (language == "python")
      return tree_sitter_python();
    if (language == "javascript")
      return tree_sitter_javascript();
    if (language == "typescript")
      return tree_sitter_typescript();
    if (language == "cpp" || language == "c")
      return tree_sitter_cpp();
    if (language == "java")
      return tree_sitter_java();
    if (language == "go")
      return tree_sitter_go();
    if (language == "rust")
      return tree_sitter_rust();
    return nullptr;
  }

  std::string get_query_for_language(const std::string &language) {
    if (language == "python") {
      return R"(
                (function_definition 
                    name: (identifier) @function.name) @function.def
                (class_definition 
                    name: (identifier) @class.name) @class.def
                (assignment
                    left: (identifier) @constant.name
                    right: (_) @constant.value) @constant.def
            )";
    }
    if (language == "javascript") {
      return R"(
                (function_declaration 
                    name: (identifier) @function.name) @function.def
                (class_declaration 
                    name: (identifier) @class.name) @class.def
                (method_definition 
                    name: (property_identifier) @method.name) @method.def
                (variable_declarator
                    name: (identifier) @function.name
                    value: (arrow_function)) @function.def
                (variable_declarator
                    name: (identifier) @function.name
                    value: (function_expression)) @function.def
            )";
    }
    if (language == "typescript") {
      return R"(
                (function_declaration 
                    name: (identifier) @function.name) @function.def
                (class_declaration 
                    name: (type_identifier) @class.name) @class.def
                (method_definition 
                    name: (property_identifier) @method.name) @method.def
                (interface_declaration 
                    name: (type_identifier) @interface.name) @interface.def
                (variable_declarator
                    name: (identifier) @function.name
                    value: (arrow_function)) @function.def
                (variable_declarator
                    name: (identifier) @function.name
                    value: (function_expression)) @function.def
            )";
    }
    if (language == "cpp" || language == "c") {
      return R"(
                (function_definition 
                    declarator: (function_declarator 
                        declarator: (identifier) @function.name)) @function.def
                (class_specifier 
                    name: (type_identifier) @class.name) @class.def
                (struct_specifier 
                    name: (type_identifier) @struct.name) @struct.def
            )";
    }
    if (language == "java") {
      return R"(
                (method_declaration 
                    name: (identifier) @method.name) @method.def
                (class_declaration 
                    name: (identifier) @class.name) @class.def
                (interface_declaration 
                    name: (identifier) @interface.name) @interface.def
            )";
    }
    return "";
  }

  std::string determine_visibility(TSNode node,
                                   const std::string &source_code) {
    TSNode parent = ts_node_parent(node);

    while (!ts_node_is_null(parent)) {
      std::string parent_type = ts_node_type(parent);

      if (parent_type == "public_field_definition" ||
          parent_type == "public_method_definition") {
        return "public";
      }
      if (parent_type == "private_field_definition" ||
          parent_type == "private_method_definition") {
        return "private";
      }
      if (parent_type == "protected_field_definition" ||
          parent_type == "protected_method_definition") {
        return "protected";
      }

      parent = ts_node_parent(parent);
    }

    uint32_t start_byte = ts_node_start_byte(node);
    if (start_byte > 10) {
      std::string prefix = source_code.substr(start_byte - 10, 10);
      if (prefix.find("export") != std::string::npos)
        return "exported";
      if (prefix.find("public") != std::string::npos)
        return "public";
      if (prefix.find("private") != std::string::npos)
        return "private";
    }

    return "public";
  }

  std::string find_parent_symbol(TSNode node) {
    TSNode parent = ts_node_parent(node);

    while (!ts_node_is_null(parent)) {
      std::string parent_type = ts_node_type(parent);

      if (parent_type == "class_definition" ||
          parent_type == "class_declaration" ||
          parent_type == "class_specifier" ||
          parent_type == "interface_declaration") {

        uint32_t child_count = ts_node_child_count(parent);
        for (uint32_t i = 0; i < child_count; i++) {
          TSNode child = ts_node_child(parent, i);
          std::string child_type = ts_node_type(child);

          if (child_type == "identifier" || child_type == "type_identifier") {
            uint32_t start = ts_node_start_byte(child);
            uint32_t end = ts_node_end_byte(child);
            return std::string(ts_node_string(child));
          }
        }
      }

      parent = ts_node_parent(parent);
    }

    return "";
  }

  void extract_symbols_from_file(const std::string &file_path,
                                 const std::string &language) {

    TSLanguage *lang = get_language_parser(language);
    if (!lang)
      return;

    std::ifstream file(fs::path(project_root) / file_path);
    if (!file.is_open())
      return;

    std::string source_code((std::istreambuf_iterator<char>(file)),
                            std::istreambuf_iterator<char>());

    TSParser *parser = ts_parser_new();
    ts_parser_set_language(parser, lang);

    TSTree *tree = ts_parser_parse_string(parser, nullptr, source_code.c_str(),
                                          source_code.length());

    if (!tree) {
      std::cout << "[Debug] Failed to parse string for " << file_path
                << std::endl;
      ts_parser_delete(parser);
      return;
    }

    std::string query_string = get_query_for_language(language);
    if (query_string.empty()) {
      std::cout << "[Debug] Query string empty for lang " << language
                << std::endl;
      ts_tree_delete(tree);
      ts_parser_delete(parser);
      return;
    }

    uint32_t error_offset;
    TSQueryError error_type;
    TSQuery *query =
        ts_query_new(lang, query_string.c_str(), query_string.length(),
                     &error_offset, &error_type);

    if (!query) {
      std::cout << "[Debug] Query creation failed for " << file_path
                << " at offset " << error_offset << " error type " << error_type
                << std::endl;
      ts_tree_delete(tree);
      ts_parser_delete(parser);
      return;
    }

    TSNode root_node = ts_tree_root_node(tree);
    TSQueryCursor *cursor = ts_query_cursor_new();
    ts_query_cursor_exec(cursor, query, root_node);

    TSQueryMatch match;
    while (ts_query_cursor_next_match(cursor, &match)) {
      for (uint16_t i = 0; i < match.capture_count; i++) {
        TSQueryCapture capture = match.captures[i];
        TSNode node = capture.node;

        uint32_t capture_name_len;
        const char *capture_name = ts_query_capture_name_for_id(
            query, capture.index, &capture_name_len);

        std::string capture_str(capture_name, capture_name_len);

        if (capture_str.find(".name") != std::string::npos) {
          uint32_t start_byte = ts_node_start_byte(node);
          uint32_t end_byte = ts_node_end_byte(node);

          std::string symbol_name =
              source_code.substr(start_byte, end_byte - start_byte);

          TSPoint start_point = ts_node_start_point(node);
          TSPoint end_point = ts_node_end_point(node);

          SymbolRecord record;
          record.symbol_name = symbol_name;
          record.file_path = file_path;
          record.start_line = start_point.row + 1;
          record.end_line = end_point.row + 1;
          record.start_byte = start_byte;
          record.end_byte = end_byte;
          record.visibility = determine_visibility(node, source_code);
          record.parent_symbol = find_parent_symbol(node);

          if (capture_str.find("function") != std::string::npos) {
            record.symbol_type = "function";
          } else if (capture_str.find("class") != std::string::npos) {
            record.symbol_type = "class";
          } else if (capture_str.find("method") != std::string::npos) {
            record.symbol_type = "method";
          } else if (capture_str.find("interface") != std::string::npos) {
            record.symbol_type = "interface";
          } else if (capture_str.find("constant") != std::string::npos) {
            record.symbol_type = "constant";
          } else if (capture_str.find("struct") != std::string::npos) {
            record.symbol_type = "struct";
          } else {
            record.symbol_type = "unknown";
          }

          symbol_registry.push_back(record);
        }
      }
    }

    ts_query_cursor_delete(cursor);
    ts_query_delete(query);
    ts_tree_delete(tree);
    ts_parser_delete(parser);
  }

  std::string project_root;
  std::vector<FileRecord> file_registry;

  std::unordered_set<std::string> code_extensions = {
      ".py",   ".java", ".js",    ".ts",   ".jsx",  ".tsx", ".cpp",
      ".cc",   ".cxx",  ".h",     ".hpp",  ".hxx",  ".c",   ".css",
      ".html", ".json", ".xml",   ".yaml", ".yml",  ".go",  ".rs",
      ".rb",   ".php",  ".swift", ".kt",   ".scala"};

  std::unordered_map<std::string, std::string> extension_to_type = {
      {".py", "code"},     {".java", "code"},   {".js", "code"},
      {".ts", "code"},     {".jsx", "code"},    {".tsx", "code"},
      {".cpp", "code"},    {".cc", "code"},     {".cxx", "code"},
      {".c", "code"},      {".h", "code"},      {".hpp", "code"},
      {".go", "code"},     {".rs", "code"},     {".rb", "code"},
      {".php", "code"},    {".swift", "code"},  {".kt", "code"},
      {".scala", "code"},  {".json", "config"}, {".xml", "config"},
      {".yaml", "config"}, {".yml", "config"},  {".html", "markup"},
      {".css", "markup"}};

  std::unordered_map<std::string, std::string> extension_to_language = {
      {".py", "python"},     {".java", "java"},      {".js", "javascript"},
      {".ts", "typescript"}, {".jsx", "javascript"}, {".tsx", "typescript"},
      {".cpp", "cpp"},       {".cc", "cpp"},         {".cxx", "cpp"},
      {".c", "c"},           {".h", "cpp"},          {".hpp", "cpp"},
      {".hxx", "cpp"},       {".go", "go"},          {".rs", "rust"},
      {".rb", "ruby"},       {".php", "php"},        {".swift", "swift"},
      {".kt", "kotlin"},     {".scala", "scala"},    {".json", "json"},
      {".xml", "xml"},       {".yaml", "yaml"},      {".yml", "yaml"},
      {".html", "html"},     {".css", "css"}};

  std::string compute_file_hash(const fs::path &filepath) {
    std::ifstream file(filepath, std::ios::binary);
    if (!file.is_open()) {
      return "";
    }

    MD5_CTX md5Context;
    MD5_Init(&md5Context);

    char buffer[8192];
    while (file.good()) {
      file.read(buffer, sizeof(buffer));
      MD5_Update(&md5Context, buffer, file.gcount());
    }

    unsigned char result[MD5_DIGEST_LENGTH];
    MD5_Final(result, &md5Context);

    std::stringstream ss;
    for (int i = 0; i < MD5_DIGEST_LENGTH; i++) {
      ss << std::hex << std::setw(2) << std::setfill('0')
         << static_cast<int>(result[i]);
    }
    return ss.str();
  }

  std::string classify_file_type(const std::string &ext) {
    auto it = extension_to_type.find(ext);
    return (it != extension_to_type.end()) ? it->second : "unknown";
  }

  std::string detect_language(const std::string &ext) {
    auto it = extension_to_language.find(ext);
    return (it != extension_to_language.end()) ? it->second : "unknown";
  }

  std::vector<RelationshipRecord> relationship_registry;
  std::unordered_map<std::string, std::string> symbol_to_file;

  std::string get_relationship_query(const std::string &language) {
    if (language == "python") {
      return R"(
                (import_statement 
                    name: (dotted_name) @import.name) @import
                (import_from_statement 
                    module_name: (dotted_name) @import.module) @import.from
                (call 
                    function: (identifier) @call.function) @call
                (call 
                    function: (attribute 
                        attribute: (identifier) @call.method)) @call.method
                (class_definition 
                    superclasses: (argument_list 
                        (identifier) @class.parent)) @inherit
                (assignment
                    left: (identifier) @write.target) @write
            )";
    }
    if (language == "javascript" || language == "typescript") {
      return R"(
                (import_statement 
                    source: (string) @import.source) @import
                (call_expression 
                    function: (identifier) @call.function) @call
                (call_expression 
                    function: (member_expression 
                        property: (property_identifier) @call.method)) @call.method
                (class_declaration 
                    (class_heritage 
                        (identifier) @class.parent)) @inherit
                (variable_declarator 
                    name: (identifier) @write.target) @write
                (interface_declaration
                    (extends_type_clause
                        (identifier) @interface.parent)) @implement
            )";
    }
    if (language == "cpp" || language == "c") {
      return R"(
                (preproc_include 
                    path: (string_literal) @import.path) @include
                (call_expression 
                    function: (identifier) @call.function) @call
                (call_expression 
                    function: (field_expression 
                        field: (field_identifier) @call.method)) @call.method
                (base_class_clause 
                    (type_identifier) @class.parent) @inherit
                (assignment_expression 
                    left: (identifier) @write.target) @write
            )";
    }
    if (language == "java") {
      return R"(
                (import_declaration 
                    (scoped_identifier) @import.name) @import
                (method_invocation 
                    name: (identifier) @call.function) @call
                (method_invocation 
                    name: (identifier) @call.method) @call.method
                (superclass 
                    (type_identifier) @class.parent) @inherit
                (super_interfaces
                    (type_list
                        (type_identifier) @interface.parent)) @implement
                (assignment_expression 
                    left: (identifier) @write.target) @write
            )";
    }
    if (language == "go") {
      return R"(
                (import_declaration 
                    (import_spec 
                        path: (interpreted_string_literal) @import.path)) @import
                (call_expression 
                    function: (identifier) @call.function) @call
                (call_expression 
                    function: (selector_expression 
                        field: (field_identifier) @call.method)) @call.method
                (field_declaration 
                    type: (type_identifier) @embed.type) @embed
                (assignment_statement 
                    left: (expression_list 
                        (identifier) @write.target)) @write
            )";
    }
    if (language == "rust") {
      return R"(
                (use_declaration 
                    argument: (scoped_identifier) @import.name) @import
                (call_expression 
                    function: (identifier) @call.function) @call
                (call_expression 
                    function: (field_expression 
                        field: (field_identifier) @call.method)) @call.method
                (trait_bounds
                    (type_identifier) @trait.parent) @implement
                (assignment_expression 
                    left: (identifier) @write.target) @write
            )";
    }
    if (language == "ruby") {
      return R"(
                (call 
                    method: (identifier) @require.name
                    arguments: (argument_list 
                        (string) @import.path)) @require
                (call 
                    method: (identifier) @call.function) @call
                (call 
                    receiver: (identifier)
                    method: (identifier) @call.method) @call.method
                (class 
                    superclass: (superclass 
                        (identifier) @class.parent)) @inherit
                (assignment 
                    left: (identifier) @write.target) @write
            )";
    }
    if (language == "php") {
      return R"(
                (namespace_use_declaration 
                    (namespace_use_clause 
                        (qualified_name) @import.name)) @import
                (function_call_expression 
                    function: (name) @call.function) @call
                (member_call_expression 
                    name: (name) @call.method) @call.method
                (base_clause 
                    (qualified_name) @class.parent) @inherit
                (class_interface_clause
                    (qualified_name) @interface.parent) @implement
                (assignment_expression 
                    left: (variable_name) @write.target) @write
            )";
    }
    if (language == "swift") {
      return R"(
                (import_declaration 
                    (identifier) @import.name) @import
                (call_expression 
                    (simple_identifier) @call.function) @call
                (call_expression 
                    (navigation_expression 
                        (navigation_suffix 
                            (simple_identifier) @call.method))) @call.method
                (type_inheritance_clause 
                    (user_type 
                        (type_identifier) @class.parent)) @inherit
                (assignment 
                    (simple_identifier) @write.target) @write
            )";
    }
    if (language == "kotlin") {
      return R"(
                (import_header 
                    (identifier) @import.name) @import
                (call_expression 
                    (simple_identifier) @call.function) @call
                (call_expression 
                    (navigation_expression 
                        (navigation_suffix 
                            (simple_identifier) @call.method))) @call.method
                (delegation_specifier 
                    (user_type 
                        (type_identifier) @class.parent)) @inherit
                (assignment 
                    (simple_identifier) @write.target) @write
            )";
    }
    if (language == "scala") {
      return R"(
                (import_declaration 
                    (stable_identifier) @import.name) @import
                (call_expression 
                    function: (identifier) @call.function) @call
                (call_expression 
                    function: (field_expression 
                        field: (identifier) @call.method)) @call.method
                (extends_clause 
                    (template_body 
                        (identifier) @class.parent)) @inherit
                (assignment_expression 
                    left: (identifier) @write.target) @write
            )";
    }
    return "";
  }

  void build_symbol_map() {
    symbol_to_file.clear();
    for (const auto &symbol : symbol_registry) {
      std::string key = symbol.symbol_name;
      if (!symbol.parent_symbol.empty()) {
        key = symbol.parent_symbol + "::" + symbol.symbol_name;
      }
      symbol_to_file[key] = symbol.file_path;
      symbol_to_file[symbol.symbol_name] = symbol.file_path;
    }
  }

  std::string resolve_target_file(const std::string &target_symbol) {
    auto it = symbol_to_file.find(target_symbol);
    if (it != symbol_to_file.end()) {
      return it->second;
    }
    return "";
  }

  void extract_relationships_from_file(const std::string &file_path,
                                       const std::string &language) {

    TSLanguage *lang = get_language_parser(language);
    if (!lang)
      return;

    std::ifstream file(fs::path(project_root) / file_path);
    if (!file.is_open())
      return;

    std::string source_code((std::istreambuf_iterator<char>(file)),
                            std::istreambuf_iterator<char>());

    TSParser *parser = ts_parser_new();
    ts_parser_set_language(parser, lang);

    TSTree *tree = ts_parser_parse_string(parser, nullptr, source_code.c_str(),
                                          source_code.length());

    if (!tree) {
      ts_parser_delete(parser);
      return;
    }

    std::string query_string = get_relationship_query(language);
    if (query_string.empty()) {
      ts_tree_delete(tree);
      ts_parser_delete(parser);
      return;
    }

    uint32_t error_offset;
    TSQueryError error_type;
    TSQuery *query =
        ts_query_new(lang, query_string.c_str(), query_string.length(),
                     &error_offset, &error_type);

    if (!query) {
      ts_tree_delete(tree);
      ts_parser_delete(parser);
      return;
    }

    TSNode root_node = ts_tree_root_node(tree);
    TSQueryCursor *cursor = ts_query_cursor_new();
    ts_query_cursor_exec(cursor, query, root_node);

    TSQueryMatch match;
    while (ts_query_cursor_next_match(cursor, &match)) {
      std::string relationship_type;
      std::string target_symbol;
      int source_line = 0;

      for (uint16_t i = 0; i < match.capture_count; i++) {
        TSQueryCapture capture = match.captures[i];
        TSNode node = capture.node;

        uint32_t capture_name_len;
        const char *capture_name = ts_query_capture_name_for_id(
            query, capture.index, &capture_name_len);

        std::string capture_str(capture_name, capture_name_len);

        uint32_t start_byte = ts_node_start_byte(node);
        uint32_t end_byte = ts_node_end_byte(node);

        std::string text =
            source_code.substr(start_byte, end_byte - start_byte);

        text.erase(0, text.find_first_not_of(" \n\r\t\"'"));
        text.erase(text.find_last_not_of(" \n\r\t\"'") + 1);

        TSPoint start_point = ts_node_start_point(node);
        source_line = start_point.row + 1;

        if (capture_str.find("import") != std::string::npos ||
            capture_str.find("require") != std::string::npos) {
          relationship_type = "imports";
          target_symbol = text;
        } else if (capture_str.find("call.function") != std::string::npos) {
          relationship_type = "calls";
          target_symbol = text;
        } else if (capture_str.find("call.method") != std::string::npos) {
          relationship_type = "calls";
          target_symbol = text;
        } else if (capture_str.find("class.parent") != std::string::npos) {
          relationship_type = "extends";
          target_symbol = text;
        } else if (capture_str.find("interface.parent") != std::string::npos) {
          relationship_type = "implements";
          target_symbol = text;
        } else if (capture_str.find("trait.parent") != std::string::npos) {
          relationship_type = "implements";
          target_symbol = text;
        } else if (capture_str.find("embed") != std::string::npos) {
          relationship_type = "embeds";
          target_symbol = text;
        } else if (capture_str.find("write.target") != std::string::npos) {
          relationship_type = "writes";
          target_symbol = text;
        }
      }

      if (!relationship_type.empty() && !target_symbol.empty()) {
        RelationshipRecord record;
        record.source_symbol = file_path;
        record.target_symbol = target_symbol;
        record.relationship_type = relationship_type;
        record.source_file = file_path;
        record.target_file = resolve_target_file(target_symbol);
        record.source_line = source_line;

        relationship_registry.push_back(record);
      }
    }

    ts_query_cursor_delete(cursor);
    ts_query_delete(query);
    ts_tree_delete(tree);
    ts_parser_delete(parser);
  }

  std::vector<BoundaryRecord> boundary_registry;

  bool is_entry_point_file(const std::string &filename) {
    std::vector<std::string> entry_patterns = {
        "main", "index", "app",    "server",   "cli",
        "run",  "start", "manage", "launcher", "bootstrap"};

    std::string lower_name = filename;
    std::transform(lower_name.begin(), lower_name.end(), lower_name.begin(),
                   ::tolower);

    for (const auto &pattern : entry_patterns) {
      if (lower_name.find(pattern) != std::string::npos) {
        return true;
      }
    }
    return false;
  }

  bool is_hotpath_symbol(const std::string &symbol_name) {
    std::vector<std::string> hotpath_patterns = {
        "auth",         "login",    "verify", "token",     "session",
        "authenticate", "route",    "router", "endpoint",  "handler",
        "config",       "settings", "setup",  "init",      "configure",
        "middleware",   "guard",    "policy", "permission"};

    std::string lower_name = symbol_name;
    std::transform(lower_name.begin(), lower_name.end(), lower_name.begin(),
                   ::tolower);

    for (const auto &pattern : hotpath_patterns) {
      if (lower_name.find(pattern) != std::string::npos) {
        return true;
      }
    }
    return false;
  }

  std::string get_boundary_query(const std::string &language) {
    if (language == "python") {
      return R"(
                (if_statement
                    condition: (comparison_operator
                        left: (identifier) @main.check)
                    consequence: (block
                        (expression_statement
                            (call)))) @entry.main
                (function_definition
                    name: (identifier) @function.name) @function.def
                (call
                    function: (attribute
                        object: (identifier) @io.object
                        attribute: (identifier) @io.method)) @external.call
                (call
                    function: (identifier) @call.name) @call.direct
                (decorated_definition
                    (decorator
                        (identifier) @decorator.name)) @decorated
            )";
    }
    if (language == "javascript" || language == "typescript") {
      return R"(
                (call_expression
                    function: (member_expression
                        object: (identifier) @server.object
                        property: (property_identifier) @server.method)) @entry.server
                (function_declaration
                    name: (identifier) @function.name) @function.def
                (call_expression
                    function: (identifier) @call.name) @call.direct
                (call_expression
                    function: (member_expression
                        property: (property_identifier) @method.name)) @external.call
            )";
    }
    if (language == "java") {
      return R"(
                (method_declaration
                    modifiers: (modifiers) @modifiers
                    type: (void_type)
                    name: (identifier) @method.name
                    parameters: (formal_parameters)) @entry.main
                (method_invocation
                    object: (identifier) @object.name
                    name: (identifier) @method.name) @external.call
            )";
    }
    if (language == "cpp" || language == "c") {
      return R"(
                (function_definition
                    type: (primitive_type)
                    declarator: (function_declarator
                        declarator: (identifier) @function.name)) @entry.main
                (call_expression
                    function: (identifier) @call.name) @external.call
            )";
    }
    if (language == "go") {
      return R"(
                (function_declaration
                    name: (identifier) @function.name) @function.def
                (call_expression
                    function: (selector_expression
                        operand: (identifier) @package.name
                        field: (field_identifier) @method.name)) @external.call
            )";
    }
    if (language == "rust") {
      return R"(
                (function_item
                    name: (identifier) @function.name) @function.def
                (call_expression
                    function: (scoped_identifier) @call.name) @external.call
            )";
    }
    return get_relationship_query(language);
  }

  std::string categorize_boundary(const std::string &symbol_name,
                                  const std::string &context) {
    std::string lower = symbol_name;
    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);

    std::vector<std::string> filesystem_patterns = {
        "open",   "read",      "write",    "file",   "fs",
        "path",   "directory", "mkdir",    "remove", "stat",
        "exists", "readfile",  "writefile"};

    std::vector<std::string> network_patterns = {
        "http",   "socket", "fetch",  "request", "get",    "post",    "connect",
        "listen", "server", "client", "axios",   "urllib", "requests"};

    std::vector<std::string> database_patterns = {
        "query",   "execute", "database",    "db",     "sql",    "connection",
        "connect", "cursor",  "transaction", "commit", "select", "insert"};

    std::vector<std::string> env_patterns = {
        "environ", "getenv", "setenv", "env", "environment", "config"};

    for (const auto &p : filesystem_patterns) {
      if (lower.find(p) != std::string::npos)
        return "filesystem";
    }
    for (const auto &p : network_patterns) {
      if (lower.find(p) != std::string::npos)
        return "network";
    }
    for (const auto &p : database_patterns) {
      if (lower.find(p) != std::string::npos)
        return "database";
    }
    for (const auto &p : env_patterns) {
      if (lower.find(p) != std::string::npos)
        return "environment";
    }

    return "unknown";
  }

  std::string assess_risk_level(const std::string &boundary_type,
                                const std::string &category) {
    if (boundary_type == "entry_point") {
      return "critical";
    }
    if (category == "network" || category == "database") {
      return "high";
    }
    if (category == "filesystem" || category == "environment") {
      return "medium";
    }
    if (boundary_type == "hotpath") {
      return "high";
    }
    return "low";
  }

  void extract_boundaries_from_file(const std::string &file_path,
                                    const std::string &language) {

    TSLanguage *lang = get_language_parser(language);
    if (!lang)
      return;

    std::ifstream file(fs::path(project_root) / file_path);
    if (!file.is_open())
      return;

    std::string source_code((std::istreambuf_iterator<char>(file)),
                            std::istreambuf_iterator<char>());

    TSParser *parser = ts_parser_new();
    ts_parser_set_language(parser, lang);

    TSTree *tree = ts_parser_parse_string(parser, nullptr, source_code.c_str(),
                                          source_code.length());

    if (!tree) {
      ts_parser_delete(parser);
      return;
    }

    std::string query_string = get_boundary_query(language);
    if (query_string.empty()) {
      ts_tree_delete(tree);
      ts_parser_delete(parser);
      return;
    }

    uint32_t error_offset;
    TSQueryError error_type;
    TSQuery *query =
        ts_query_new(lang, query_string.c_str(), query_string.length(),
                     &error_offset, &error_type);

    if (!query) {
      ts_tree_delete(tree);
      ts_parser_delete(parser);
      return;
    }

    TSNode root_node = ts_tree_root_node(tree);
    TSQueryCursor *cursor = ts_query_cursor_new();
    ts_query_cursor_exec(cursor, query, root_node);

    fs::path fpath(file_path);
    std::string filename = fpath.filename().string();
    bool is_entry_file = is_entry_point_file(filename);

    TSQueryMatch match;
    while (ts_query_cursor_next_match(cursor, &match)) {
      std::string symbol_name;
      std::string boundary_type;
      int line_number = 0;

      for (uint16_t i = 0; i < match.capture_count; i++) {
        TSQueryCapture capture = match.captures[i];
        TSNode node = capture.node;

        uint32_t capture_name_len;
        const char *capture_name = ts_query_capture_name_for_id(
            query, capture.index, &capture_name_len);

        std::string capture_str(capture_name, capture_name_len);

        uint32_t start_byte = ts_node_start_byte(node);
        uint32_t end_byte = ts_node_end_byte(node);
        std::string text =
            source_code.substr(start_byte, end_byte - start_byte);

        TSPoint start_point = ts_node_start_point(node);
        line_number = start_point.row + 1;

        if (capture_str.find("function.name") != std::string::npos ||
            capture_str.find("method.name") != std::string::npos) {
          symbol_name = text;

          if (text == "main" || text == "__main__") {
            boundary_type = "entry_point";
          } else if (is_entry_file) {
            boundary_type = "entry_point";
          } else if (is_hotpath_symbol(text)) {
            boundary_type = "hotpath";
          }
        } else if (capture_str.find("call.name") != std::string::npos ||
                   capture_str.find("io.method") != std::string::npos ||
                   capture_str.find("method.name") != std::string::npos) {
          symbol_name = text;

          std::string cat = categorize_boundary(text, "");
          if (cat != "unknown") {
            boundary_type = "external_boundary";
          }
        } else if (capture_str.find("decorator") != std::string::npos) {
          symbol_name = text;
          if (text.find("route") != std::string::npos ||
              text.find("app") != std::string::npos) {
            boundary_type = "hotpath";
          }
        } else if (capture_str == "main.check") {
          if (text == "__name__") {
            boundary_type = "entry_point";
            symbol_name = "__main__";
          }
        }
      }

      if (!symbol_name.empty() && !boundary_type.empty()) {
        BoundaryRecord record;
        record.symbol_name = symbol_name;
        record.boundary_type = boundary_type;
        record.file_path = file_path;
        record.line_number = line_number;
        record.category = categorize_boundary(symbol_name, "");
        record.risk_level = assess_risk_level(boundary_type, record.category);

        boundary_registry.push_back(record);
      }
    }

    for (const auto &sym : symbol_registry) {
      if (sym.file_path == file_path && is_hotpath_symbol(sym.symbol_name)) {
        BoundaryRecord record;
        record.symbol_name = sym.symbol_name;
        record.boundary_type = "hotpath";
        record.file_path = file_path;
        record.line_number = sym.start_line;
        record.category = "critical_path";
        record.risk_level = "high";

        boundary_registry.push_back(record);
      }
    }

    ts_query_cursor_delete(cursor);
    ts_query_delete(query);
    ts_tree_delete(tree);
    ts_parser_delete(parser);
  }

public:
  RaysBuilder(const std::string &root) : project_root(root) {}

  void build_symbol_registry() {
    symbol_registry.clear();

    for (const auto &file_record : file_registry) {
      if (file_record.file_type != "code") {
        continue;
      }

      extract_symbols_from_file(file_record.relative_path,
                                file_record.language);
    }
  }

  void write_symbols_to_msgpack() {
    fs::path rays_dir = fs::path(project_root) / ".rays";

    if (!fs::exists(rays_dir)) {
      fs::create_directory(rays_dir);
    }

    fs::path output_file = rays_dir / "symbols.msgpack";

    msgpack::sbuffer buffer;
    msgpack::pack(buffer, symbol_registry);

    std::ofstream ofs(output_file, std::ios::binary);
    ofs.write(buffer.data(), buffer.size());
    ofs.close();
  }

  void build_file_registry() {
    file_registry.clear();

    for (const auto &entry : fs::recursive_directory_iterator(project_root)) {
      if (!entry.is_regular_file()) {
        continue;
      }

      std::string ext = entry.path().extension().string();

      if (code_extensions.find(ext) == code_extensions.end()) {
        continue;
      }

      std::string rel_path = fs::relative(entry.path(), project_root).string();

      if (rel_path.find(".rays") == 0) {
        continue;
      }

      FileRecord record;
      record.relative_path = rel_path;
      record.file_type = classify_file_type(ext);
      record.language = detect_language(ext);
      record.existence_state = "existing";
      record.stable_id = compute_file_hash(entry.path());
      record.file_size = fs::file_size(entry.path());
      auto ftime = fs::last_write_time(entry.path());
      auto sctp =
          std::chrono::time_point_cast<std::chrono::system_clock::duration>(
              ftime - fs::file_time_type::clock::now() +
              std::chrono::system_clock::now());
      record.last_modified = std::chrono::system_clock::to_time_t(sctp);

      file_registry.push_back(record);
    }
  }

  void write_to_msgpack() {
    fs::path rays_dir = fs::path(project_root) / ".rays";

    if (!fs::exists(rays_dir)) {
      fs::create_directory(rays_dir);
    }

    fs::path output_file = rays_dir / "files.msgpack";

    msgpack::sbuffer buffer;
    msgpack::pack(buffer, file_registry);

    std::ofstream ofs(output_file, std::ios::binary);
    ofs.write(buffer.data(), buffer.size());
    ofs.close();
  }

public:
  void build_relationship_registry() {
    relationship_registry.clear();

    build_symbol_map();

    for (const auto &file_record : file_registry) {
      if (file_record.file_type != "code") {
        continue;
      }

      extract_relationships_from_file(file_record.relative_path,
                                      file_record.language);
    }
  }

  void write_relationships_to_msgpack() {
    fs::path rays_dir = fs::path(project_root) / ".rays";

    if (!fs::exists(rays_dir)) {
      fs::create_directory(rays_dir);
    }

    fs::path output_file = rays_dir / "relationships.msgpack";

    msgpack::sbuffer buffer;
    msgpack::pack(buffer, relationship_registry);

    std::ofstream ofs(output_file, std::ios::binary);
    ofs.write(buffer.data(), buffer.size());
    ofs.close();
  }

  void build_boundary_registry() {
    boundary_registry.clear();

    for (const auto &file_record : file_registry) {
      fs::path fpath(file_record.relative_path);
      std::string filename = fpath.filename().string();

      if (is_entry_point_file(filename)) {
        BoundaryRecord record;
        record.symbol_name = filename;
        record.boundary_type = "entry_point";
        record.file_path = file_record.relative_path;
        record.line_number = 1;
        record.category = "application_entry";
        record.risk_level = "critical";
        boundary_registry.push_back(record);
      }
    }

    for (const auto &symbol : symbol_registry) {
      if (symbol.symbol_name == "main" || symbol.symbol_name == "__main__") {
        BoundaryRecord record;
        record.symbol_name = symbol.symbol_name;
        record.boundary_type = "entry_point";
        record.file_path = symbol.file_path;
        record.line_number = symbol.start_line;
        record.category = "main_function";
        record.risk_level = "critical";
        boundary_registry.push_back(record);
      }

      if (is_hotpath_symbol(symbol.symbol_name)) {
        BoundaryRecord record;
        record.symbol_name = symbol.symbol_name;
        record.boundary_type = "hotpath";
        record.file_path = symbol.file_path;
        record.line_number = symbol.start_line;
        record.category = "critical_path";
        record.risk_level = "high";
        boundary_registry.push_back(record);
      }
    }

    for (const auto &rel : relationship_registry) {
      std::string category = categorize_boundary(rel.target_symbol, "");

      if (category != "unknown") {
        BoundaryRecord record;
        record.symbol_name = rel.target_symbol;
        record.boundary_type = "external_boundary";
        record.file_path = rel.source_file;
        record.line_number = rel.source_line;
        record.category = category;
        record.risk_level = assess_risk_level("external_boundary", category);
        boundary_registry.push_back(record);
      }
    }
  }

  void write_boundaries_to_msgpack() {
    fs::path rays_dir = fs::path(project_root) / ".rays";

    if (!fs::exists(rays_dir)) {
      fs::create_directory(rays_dir);
    }

    fs::path output_file = rays_dir / "boundaries.msgpack";

    msgpack::sbuffer buffer;
    msgpack::pack(buffer, boundary_registry);

    std::ofstream ofs(output_file, std::ios::binary);
    ofs.write(buffer.data(), buffer.size());
    ofs.close();
  }
};
