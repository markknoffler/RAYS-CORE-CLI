# Compiler settings
CXX = g++
CXXFLAGS = -std=c++17

# Library paths (Homebrew)
OPENSSL_PATH = $(shell brew --prefix openssl@3)
MSGPACK_PATH = $(shell brew --prefix msgpack-cxx)
BOOST_PATH = $(shell brew --prefix boost)
TREESITTER_PATH = $(shell brew --prefix tree-sitter)
YAML_PATH = $(shell brew --prefix yaml-cpp)
CURL_PATH = $(shell brew --prefix curl)
JSON_PATH = $(shell brew --prefix nlohmann-json)
HOMEBREW_LIB = $(shell brew --prefix)/lib

# Include paths
INCLUDES = -I$(OPENSSL_PATH)/include \
           -I$(MSGPACK_PATH)/include \
           -I$(BOOST_PATH)/include \
           -I$(TREESITTER_PATH)/include \
           -I$(YAML_PATH)/include \
           -I$(JSON_PATH)/include

# Library linking
LIBS = -L$(OPENSSL_PATH)/lib \
       -L$(TREESITTER_PATH)/lib \
       -L$(YAML_PATH)/lib \
       -L$(CURL_PATH)/lib \
       -L$(HOMEBREW_LIB) \
       -lssl -lcrypto -ltree-sitter -lyaml-cpp -lcurl \
       -ltree-sitter-python \
       -ltree-sitter-javascript \
       -ltree-sitter-typescript \
       -ltree-sitter-cpp \
       -ltree-sitter-java \
       -ltree-sitter-go \
       -ltree-sitter-rust

# Default target
all: test_rays chunks_generator

# 1. Main RAYS Graph Generator (rays_generator)
rays_generator: test_rays.cpp rays_generator.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) test_rays.cpp -o rays_generator $(LIBS)

test_rays: test_rays.cpp rays_generator.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) test_rays.cpp -o test_rays $(LIBS)

# 2. Vector Chunk Generator (chunks_generator)
# NOTE: Links ai_client.cpp because it needs to call Ollama/Gemini
chunks_generator: chunks_generator.cpp ai_client.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) chunks_generator.cpp ai_client.cpp -o chunks_generator $(LIBS)

# Reader utilities (Debug tools)
read_rays: read_rays.cpp rays_generator.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) read_rays.cpp -o read_rays $(LIBS)

read_symbols: read_symbols.cpp rays_generator.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) read_symbols.cpp -o read_symbols $(LIBS)

read_relationships: read_relationships.cpp rays_generator.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) read_relationships.cpp -o read_relationships $(LIBS)

read_boundaries: read_boundaries.cpp rays_generator.cpp
	$(CXX) $(CXXFLAGS) $(INCLUDES) read_boundaries.cpp -o read_boundaries $(LIBS)

# --- RUN COMMANDS ---

# Run the main graph builder (local test)
run: test_rays
	./test_rays

# Run the chunk generator (This creates the vector DB)
generate_chunks: chunks_generator
	@if [ -z "$(CODEBASE_PATH)" ]; then \
		echo "Error: CODEBASE_PATH not set. Usage: make generate_chunks CODEBASE_PATH=/path/to/codebase"; \
		exit 1; \
	fi
	./chunks_generator $(CODEBASE_PATH)

# Debug readers
read_files: read_rays
	./read_rays

read_syms: read_symbols
	./read_symbols

read_rels: read_relationships
	./read_relationships

read_bounds: read_boundaries
	./read_boundaries

# Clean target
clean:
	rm -f test_rays chunks_generator \
	      read_rays read_symbols read_relationships read_boundaries

# Help target
help:
	@echo "Available targets:"
	@echo "  all                  - Build test_rays and chunks_generator (default)"
	@echo "  test_rays            - Build the main RAYS graph generator"
	@echo "  chunks_generator     - Build the vector DB generator"
	@echo "  run                  - Run test_rays (local test)"
	@echo "  generate_chunks      - Run the vector generator on a codebase"
	@echo "                         Usage: make generate_chunks CODEBASE_PATH=/path/to/code"
	@echo "  read_rays            - Build and run file reader"
	@echo "  read_symbols         - Build and run symbol reader"
	@echo "  read_relationships   - Build and run relationship reader"
	@echo "  read_boundaries      - Build and run boundary reader"
	@echo "  clean                - Remove all built executables"
	@echo "  help                 - Show this help message"

.PHONY: all clean run read_files read_syms read_rels read_bounds generate_chunks help

