cmake_minimum_required(VERSION 3.20)
project(event_queue_tests CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)
FetchContent_Declare(googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.18.0.tar.gz
  DOWNLOAD_EXTRACT_TIMESTAMP TRUE)
FetchContent_MakeAvailable(googletest)

add_executable(test_event_queue test_event_queue.cpp)
target_compile_options(test_event_queue PRIVATE -Wall -Wextra -fsanitize=address,undefined -fno-omit-frame-pointer)
target_link_options(test_event_queue PRIVATE -fsanitize=address,undefined)
target_link_libraries(test_event_queue GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(test_event_queue)
