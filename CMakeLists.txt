cmake_minimum_required(VERSION 3.14)
project(VolumeViewer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)

# --- Dependencies ---

# GLFW
FetchContent_Declare(
    glfw
    GIT_REPOSITORY https://github.com/glfw/glfw
    GIT_TAG 3.3.8
)
FetchContent_MakeAvailable(glfw)

# GLM
FetchContent_Declare(
    glm
    GIT_REPOSITORY https://github.com/g-truc/glm
    GIT_TAG 0.9.9.8
)
FetchContent_MakeAvailable(glm)

# GLAD (Generated loader)
# We will use a local glad.c/.h for simplicity or fetch a cmake-ready one.
# For now, let's assume we can fetch a version or use a header-only loader like gl3w or just glad.
# Actually, the easiest way for glad in CMake is often just to include the files. 
# I'll create a vendor/glad directory and simply write the files there in a subsequent step, 
# or use a repo that provides it.
FetchContent_Declare(
    glad
    GIT_REPOSITORY https://github.com/Dav1dde/glad
    GIT_TAG v0.1.36
)
FetchContent_MakeAvailable(glad)

# ImGui
FetchContent_Declare(
    imgui
    GIT_REPOSITORY https://github.com/ocornut/imgui
    GIT_TAG v1.89.9
)
FetchContent_MakeAvailable(imgui)

# --- Sources ---
file(GLOB_RECURSE SOURCES "src/*.cpp" "src/*.c")

add_executable(VolumeViewer ${SOURCES})

# --- Include Directories ---
target_include_directories(VolumeViewer PRIVATE 
    src 
    ${glfw_SOURCE_DIR}/include
    ${glm_SOURCE_DIR}
    ${glad_SOURCE_DIR}/include
    ${imgui_SOURCE_DIR}
    ${imgui_SOURCE_DIR}/backends
)

# --- Linking ---
target_link_libraries(VolumeViewer PRIVATE 
    glfw 
    glad
)

# ImGui needs implementation files added to the target
target_sources(VolumeViewer PRIVATE
    ${imgui_SOURCE_DIR}/imgui.cpp
    ${imgui_SOURCE_DIR}/imgui_draw.cpp
    ${imgui_SOURCE_DIR}/imgui_tables.cpp
    ${imgui_SOURCE_DIR}/imgui_widgets.cpp
    ${imgui_SOURCE_DIR}/imgui_demo.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_glfw.cpp
    ${imgui_SOURCE_DIR}/backends/imgui_impl_opengl3.cpp
)

# Windows specific
if(WIN32)
    target_compile_definitions(VolumeViewer PRIVATE _CRT_SECURE_NO_WARNINGS)
endif()
