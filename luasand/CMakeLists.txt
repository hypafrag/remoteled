cmake_minimum_required(VERSION 3.10)

project(luasand)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 14)

set(SOURCE_FILES main.cpp perlin.cpp)

if (EXISTS /usr/lib/lua5.3)
    link_directories(/usr/lib/lua5.3)
endif()

add_executable(luasand ${SOURCE_FILES})
target_link_libraries(luasand lua ssl crypto websockets pthread)
