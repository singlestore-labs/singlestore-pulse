from dotenv import load_dotenv
import os
import datetime
import json
import time
import threading
import concurrent.futures
import asyncio
from typing import List, Dict, Any

from openai import OpenAI

from opentelemetry.sdk._logs import LoggingHandler

from pulse_otel import Pulse, pulse_agent, pulse_tool, observe

import logging
from tenacity import retry, stop_after_attempt, wait_fixed

logger = logging.getLogger("stress_test_app")
logger.setLevel(logging.DEBUG)

def get_configs():
    """
    Reads and returns configurations from the .env file.
    """
    load_dotenv()  # Load environment variables from .env file
    configs = {
        "perma_auth_token": os.getenv("perma_auth_token"),
        "api_uri": os.getenv("api_uri"),
        "model_name": os.getenv("model_name"),
    }
    return configs


# ==================== STRESS TEST SCENARIO 1: LONG-RUNNING TRACES ====================

@pulse_tool(name="long_running_computation")
def simulate_long_running_task(duration_minutes: int = 5):
    """
    Simulates a long-running computation that keeps a trace active for extended periods
    """
    logger.info(f"Starting long-running task for {duration_minutes} minutes")
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    step = 0
    while time.time() < end_time:
        step += 1
        # Simulate periodic work with nested spans
        perform_periodic_work(step)
        time.sleep(10)  # Wait 10 seconds between operations
    
    logger.info(f"Completed long-running task after {duration_minutes} minutes")
    return f"Long-running task completed after {duration_minutes} minutes with {step} steps"

@pulse_agent(name="periodic_work")
def perform_periodic_work(step: int):
    """
    Performs periodic work within a long-running trace
    """
    logger.debug(f"Performing periodic work step {step}")
    
    # Simulate some CPU-bound work
    result = 0
    for i in range(10000):
        result += i * step
    
    # Simulate some I/O operations
    simulate_io_operation(step)
    
    return result

@pulse_agent(name="io_operation")
def simulate_io_operation(step: int):
    """
    Simulates I/O operations within periodic work
    """
    logger.debug(f"Simulating I/O operation for step {step}")
    time.sleep(0.1)  # Simulate I/O delay
    return f"I/O completed for step {step}"


# ==================== STRESS TEST SCENARIO 2: TRACES WITH 5000+ SPANS ====================

@pulse_tool(name="massive_span_generator")
def create_massive_trace_with_spans(num_spans: int = 5000):
    """
    Creates a trace with an exceptionally large number of spans
    """
    logger.info(f"Starting creation of trace with {num_spans} spans")
    
    start_time = time.time()
    results = []
    
    for i in range(num_spans):
        result = create_nested_span_operation(i, num_spans)
        results.append(result)
        
        # Log progress every 500 spans
        if i % 500 == 0:
            logger.info(f"Created {i}/{num_spans} spans")
    
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info(f"Completed creation of {num_spans} spans in {duration:.2f} seconds")
    return f"Created {num_spans} spans in {duration:.2f} seconds"

@pulse_agent(name="nested_span_operation")
def create_nested_span_operation(span_index: int, total_spans: int):
    """
    Creates nested span operations to stress test the collector
    """
    # Create multiple levels of nesting
    level1_result = level1_operation(span_index)
    level2_result = level2_operation(span_index)
    level3_result = level3_operation(span_index)
    
    return {
        "span_index": span_index,
        "level1": level1_result,
        "level2": level2_result,
        "level3": level3_result,
        "progress": f"{span_index}/{total_spans}"
    }

@pulse_agent(name="level1_operation")
def level1_operation(index: int):
    """Level 1 nested operation"""
    logger.debug(f"Level 1 operation for span {index}")
    # Simulate some computation
    result = sum(range(index % 100))
    return f"Level1-{index}-{result}"

@pulse_agent(name="level2_operation")
def level2_operation(index: int):
    """Level 2 nested operation"""
    logger.debug(f"Level 2 operation for span {index}")
    # Create even deeper nesting
    sub_result = level2_sub_operation(index)
    return f"Level2-{index}-{sub_result}"

@pulse_agent(name="level2_sub_operation")
def level2_sub_operation(index: int):
    """Sub-operation within level 2"""
    return f"SubLevel2-{index}-{index * 2}"

@pulse_agent(name="level3_operation")
def level3_operation(index: int):
    """Level 3 nested operation with multiple sub-operations"""
    logger.debug(f"Level 3 operation for span {index}")
    
    # Create multiple sub-spans
    sub_results = []
    for sub_index in range(3):  # Create 3 sub-spans for each level 3 operation
        sub_result = level3_sub_operation(index, sub_index)
        sub_results.append(sub_result)
    
    return f"Level3-{index}-{sub_results}"

@pulse_agent(name="level3_sub_operation")
def level3_sub_operation(parent_index: int, sub_index: int):
    """Sub-operation within level 3"""
    # Add some attributes and logs to make spans more realistic
    logger.debug(f"Level 3 sub-operation {sub_index} for parent {parent_index}")
    
    # Simulate some work
    computation_result = (parent_index * sub_index) % 1000
    return f"SubLevel3-{parent_index}-{sub_index}-{computation_result}"


# ==================== CONCURRENT STRESS TESTING ====================

@pulse_tool(name="concurrent_stress_test")
def run_concurrent_stress_test(num_concurrent_traces: int = 10, spans_per_trace: int = 500):
    """
    Runs multiple traces concurrently to stress test the collector
    """
    logger.info(f"Starting concurrent stress test with {num_concurrent_traces} traces, {spans_per_trace} spans each")
    
    start_time = time.time()
    
    # Use ThreadPoolExecutor to run multiple traces concurrently
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_concurrent_traces) as executor:
        futures = []
        
        for trace_id in range(num_concurrent_traces):
            future = executor.submit(create_concurrent_trace, trace_id, spans_per_trace)
            futures.append(future)
        
        # Wait for all traces to complete
        results = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                logger.error(f"Concurrent trace generated an exception: {exc}")
                results.append(f"Error: {exc}")
    
    end_time = time.time()
    duration = end_time - start_time
    
    total_spans = num_concurrent_traces * spans_per_trace
    logger.info(f"Completed concurrent stress test: {total_spans} total spans in {duration:.2f} seconds")
    
    return f"Concurrent test completed: {num_concurrent_traces} traces with {spans_per_trace} spans each in {duration:.2f} seconds"

@pulse_agent(name="concurrent_trace")
def create_concurrent_trace(trace_id: int, num_spans: int):
    """
    Creates a single trace with multiple spans as part of concurrent testing
    """
    logger.info(f"Starting concurrent trace {trace_id} with {num_spans} spans")
    
    results = []
    for span_index in range(num_spans):
        result = concurrent_span_operation(trace_id, span_index)
        results.append(result)
        
        # Small delay between spans to simulate realistic workload
        time.sleep(0.001)  # 1ms delay
    
    logger.info(f"Completed concurrent trace {trace_id}")
    return f"Trace {trace_id} completed with {num_spans} spans"

@pulse_agent(name="concurrent_span_operation")
def concurrent_span_operation(trace_id: int, span_index: int):
    """
    Individual span operation for concurrent testing
    """
    # Add trace and span identifiers as attributes
    logger.debug(f"Concurrent span operation: trace {trace_id}, span {span_index}")
    
    # Simulate some work
    work_result = perform_mock_work(trace_id, span_index)
    
    return f"T{trace_id}S{span_index}: {work_result}"

@pulse_agent(name="mock_work")
def perform_mock_work(trace_id: int, span_index: int):
    """
    Performs mock work to make spans more realistic
    """
    # Simulate database query
    query_result = simulate_db_query(trace_id, span_index)
    
    # Simulate API call
    api_result = simulate_api_call(trace_id, span_index)
    
    # Simulate computation
    computation = (trace_id * span_index) % 1000
    
    return f"DB:{query_result},API:{api_result},COMP:{computation}"

@pulse_agent(name="db_query")
def simulate_db_query(trace_id: int, span_index: int):
    """Simulates a database query"""
    time.sleep(0.001)  # Simulate DB latency
    return f"db_result_{trace_id}_{span_index}"

@pulse_agent(name="api_call")
def simulate_api_call(trace_id: int, span_index: int):
    """Simulates an API call"""
    time.sleep(0.002)  # Simulate API latency
    return f"api_result_{trace_id}_{span_index}"


# ==================== MEMORY STRESS TESTING ====================

@pulse_tool(name="memory_stress_test")
def create_memory_intensive_trace(data_size_mb: int = 100):
    """
    Creates traces with large amounts of data to test memory handling
    """
    logger.info(f"Starting memory stress test with {data_size_mb}MB of data per span")
    
    # Create large data payload
    large_data = "x" * (data_size_mb * 1024 * 1024)  # Create MB-sized string
    
    results = []
    for i in range(10):  # Create 10 spans with large data
        result = process_large_data(i, large_data[:1000])  # Truncate for logging
        results.append(result)
        logger.info(f"Processed large data span {i}")
    
    return f"Memory stress test completed with {len(results)} spans"

@pulse_agent(name="large_data_processing")
def process_large_data(index: int, data_sample: str):
    """
    Processes large amounts of data within a span
    """
    logger.debug(f"Processing large data for span {index}")
    
    # Simulate processing large data
    processed_length = len(data_sample)
    checksum = sum(ord(c) for c in data_sample[:100])  # Simple checksum
    
    return f"Span {index}: processed {processed_length} bytes, checksum {checksum}"


# ==================== DEEP NESTING STRESS TESTING ====================

@pulse_tool(name="deep_nesting_stress_test")
def create_deep_nested_trace(nesting_depth: int = 50):
    """
    Creates a trace with deeply nested spans to test stack depth limits
    """
    logger.info(f"Starting deep nesting stress test with {nesting_depth} levels of nesting")
    
    start_time = time.time()
    
    # Start the recursive nesting
    result = create_recursive_nested_spans(1, nesting_depth)
    
    end_time = time.time()
    duration = end_time - start_time
    
    logger.info(f"Completed deep nesting trace with {nesting_depth} levels in {duration:.2f} seconds")
    return f"Deep nesting trace completed: {nesting_depth} levels in {duration:.2f} seconds"

@pulse_agent(name="recursive_nested_spans")
def create_recursive_nested_spans(current_level: int, max_depth: int):
    """
    Recursively creates nested spans to test deep nesting capabilities
    """
    logger.debug(f"Creating nested span at level {current_level}/{max_depth}")
    
    # Perform some work at this level
    level_work_result = perform_level_work(current_level, max_depth)
    
    # Add multiple operations at each level to make it more realistic
    operation_results = []
    for operation_index in range(3):  # 3 operations per level
        operation_result = perform_nested_operation(current_level, operation_index)
        operation_results.append(operation_result)
    
    # Continue nesting if we haven't reached max depth
    if current_level < max_depth:
        nested_result = create_recursive_nested_spans(current_level + 1, max_depth)
        return {
            "level": current_level,
            "max_depth": max_depth,
            "level_work": level_work_result,
            "operations": operation_results,
            "nested_result": nested_result
        }
    else:
        # Base case - deepest level reached
        logger.info(f"Reached maximum nesting depth: {max_depth}")
        return {
            "level": current_level,
            "max_depth": max_depth,
            "level_work": level_work_result,
            "operations": operation_results,
            "final_depth_reached": True
        }

@pulse_agent(name="level_work")
def perform_level_work(level: int, max_depth: int):
    """
    Performs work specific to each nesting level
    """
    logger.debug(f"Performing level work at depth {level}/{max_depth}")
    
    # Simulate different types of work based on level
    if level <= 10:
        # Early levels: lightweight operations
        work_type = "lightweight"
        computation = sum(range(level * 10))
    elif level <= 25:
        # Mid levels: moderate operations
        work_type = "moderate"
        computation = sum(range(level * 50))
        time.sleep(0.001)  # Small delay
    else:
        # Deep levels: minimal operations to avoid stack overflow
        work_type = "minimal"
        computation = level * level
    
    return f"Level{level}_{work_type}_work={computation}"

@pulse_agent(name="nested_operation")
def perform_nested_operation(level: int, operation_index: int):
    """
    Performs individual operations within each nesting level
    """
    logger.debug(f"Nested operation {operation_index} at level {level}")
    
    # Create sub-operations with different patterns
    if operation_index == 0:
        # Database-like operation
        result = simulate_nested_db_operation(level, operation_index)
    elif operation_index == 1:
        # Computation operation
        result = simulate_nested_computation(level, operation_index)
    else:
        # I/O operation
        result = simulate_nested_io_operation(level, operation_index)
    
    return f"L{level}Op{operation_index}:{result}"

@pulse_agent(name="nested_db_operation")
def simulate_nested_db_operation(level: int, operation_index: int):
    """Simulates database operations at nested levels"""
    # Lighter operations at deeper levels to prevent resource exhaustion
    if level > 40:
        time.sleep(0.0001)  # Minimal delay for deep levels
    else:
        time.sleep(0.001)   # Small delay for shallow levels
    
    return f"db_nested_L{level}_Op{operation_index}_result"

@pulse_agent(name="nested_computation")
def simulate_nested_computation(level: int, operation_index: int):
    """Simulates computational operations at nested levels"""
    # Reduce computation complexity at deeper levels
    if level > 40:
        result = level + operation_index
    elif level > 20:
        result = sum(range(min(10, level)))
    else:
        result = sum(range(min(50, level * 2)))
    
    return f"comp_nested_L{level}_Op{operation_index}_{result}"

@pulse_agent(name="nested_io_operation")
def simulate_nested_io_operation(level: int, operation_index: int):
    """Simulates I/O operations at nested levels"""
    # Very light I/O simulation at deep levels
    if level > 35:
        delay = 0.0001
    elif level > 20:
        delay = 0.001
    else:
        delay = 0.002
    
    time.sleep(delay)
    return f"io_nested_L{level}_Op{operation_index}_completed"

# Special test for extreme nesting
@pulse_tool(name="extreme_nesting_test")
def create_extreme_nested_trace(nesting_depth: int = 100):
    """
    Creates an extremely deep nested trace (100+ levels) with minimal operations
    WARNING: This test pushes the limits of stack depth and should be used carefully
    """
    logger.warning(f"Starting EXTREME nesting test with {nesting_depth} levels - use with caution!")
    
    start_time = time.time()
    
    try:
        result = create_minimal_recursive_spans(1, nesting_depth)
        success = True
    except RecursionError as e:
        logger.error(f"RecursionError at depth {nesting_depth}: {e}")
        result = f"RecursionError encountered at depth {nesting_depth}"
        success = False
    except Exception as e:
        logger.error(f"Error during extreme nesting: {e}")
        result = f"Error: {e}"
        success = False
    
    end_time = time.time()
    duration = end_time - start_time
    
    status = "SUCCESS" if success else "FAILED"
    logger.info(f"Extreme nesting test {status}: {nesting_depth} levels in {duration:.2f} seconds")
    
    return f"Extreme nesting test {status}: {nesting_depth} levels in {duration:.2f} seconds. Result: {result}"

@pulse_agent(name="minimal_recursive_spans")
def create_minimal_recursive_spans(current_level: int, max_depth: int):
    """
    Creates minimal recursive spans for extreme depth testing
    """
    # Minimal logging and work to reduce stack pressure
    if current_level % 10 == 0:  # Log only every 10th level
        logger.debug(f"Minimal span at level {current_level}/{max_depth}")
    
    # Minimal work per level
    simple_result = current_level * 2
    
    if current_level < max_depth:
        # Continue recursion with minimal overhead
        nested_result = create_minimal_recursive_spans(current_level + 1, max_depth)
        return f"L{current_level}:{simple_result}->({nested_result})"
    else:
        # Base case
        return f"FINAL_L{current_level}:{simple_result}"


# ==================== MAIN AGENT FUNCTIONS ====================

# Define available tools for stress testing
stress_test_tools = [
    {
        "type": "function",
        "function": {
            "name": "long_running_computation",
            "description": "Run a long-duration trace to test collector endurance",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Duration in minutes for the long-running task"
                    }
                },
                "required": ["duration_minutes"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "massive_span_generator",
            "description": "Create a trace with thousands of spans",
            "parameters": {
                "type": "object",
                "properties": {
                    "num_spans": {
                        "type": "integer",
                        "description": "Number of spans to create (default 5000)"
                    }
                },
                "required": ["num_spans"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "concurrent_stress_test",
            "description": "Run multiple traces concurrently",
            "parameters": {
                "type": "object",
                "properties": {
                    "num_concurrent_traces": {
                        "type": "integer",
                        "description": "Number of concurrent traces to run"
                    },
                    "spans_per_trace": {
                        "type": "integer", 
                        "description": "Number of spans per trace"
                    }
                },
                "required": ["num_concurrent_traces", "spans_per_trace"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "memory_stress_test",
            "description": "Create memory-intensive traces",
            "parameters": {
                "type": "object",
                "properties": {
                    "data_size_mb": {
                        "type": "integer",
                        "description": "Size of data in MB to include in each span"
                    }
                },
                "required": ["data_size_mb"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "deep_nesting_stress_test",
            "description": "Create a trace with deeply nested spans (50 levels)",
            "parameters": {
                "type": "object",
                "properties": {
                    "nesting_depth": {
                        "type": "integer",
                        "description": "Depth of nesting levels (default 50)"
                    }
                },
                "required": ["nesting_depth"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extreme_nesting_test",
            "description": "Create an extremely deep nested trace (100+ levels) - use with caution",
            "parameters": {
                "type": "object",
                "properties": {
                    "nesting_depth": {
                        "type": "integer",
                        "description": "Extreme nesting depth (default 100)"
                    }
                },
                "required": ["nesting_depth"]
            }
        }
    }
]

# @retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
@pulse_agent(name="StressTestAgent")
def stress_test_agent(prompt):
    """
    Agent function to handle stress test requests
    """
    messages = [{"role": "user", "content": prompt}]
    
    configs = get_configs()
    client = OpenAI(
        api_key=configs["perma_auth_token"],
        base_url=configs["api_uri"],
    )
    
    # Make a chat completion request with stress test tools
    response = client.chat.completions.create(
        model=configs["model_name"],
        messages=messages,
        tools=stress_test_tools,
        tool_choice="auto",
        extra_headers={"X-Session-ID": f"stress_test_session_{int(time.time())}"},
    )
    
    # Check if the response involves a tool call
    if response.choices[0].message.tool_calls:
        for tool_call in response.choices[0].message.tool_calls:
            if tool_call.function.name == "long_running_computation":
                arguments = json.loads(tool_call.function.arguments)
                duration_minutes = arguments.get("duration_minutes", 5)
                result = simulate_long_running_task(duration_minutes)
                
            elif tool_call.function.name == "massive_span_generator":
                arguments = json.loads(tool_call.function.arguments)
                num_spans = arguments.get("num_spans", 5000)
                print(f"Creating massive trace with {num_spans} spans...")
                result = create_massive_trace_with_spans(num_spans)
                
            elif tool_call.function.name == "concurrent_stress_test":
                arguments = json.loads(tool_call.function.arguments)
                num_concurrent_traces = arguments.get("num_concurrent_traces", 10)
                spans_per_trace = arguments.get("spans_per_trace", 500)
                result = run_concurrent_stress_test(num_concurrent_traces, spans_per_trace)
                
            elif tool_call.function.name == "memory_stress_test":
                arguments = json.loads(tool_call.function.arguments)
                data_size_mb = arguments.get("data_size_mb", 100)
                result = create_memory_intensive_trace(data_size_mb)
                
            elif tool_call.function.name == "deep_nesting_stress_test":
                arguments = json.loads(tool_call.function.arguments)
                nesting_depth = arguments.get("nesting_depth", 50)
                result = create_deep_nested_trace(nesting_depth)
                
            elif tool_call.function.name == "extreme_nesting_test":
                arguments = json.loads(tool_call.function.arguments)
                nesting_depth = arguments.get("nesting_depth", 100)
                result = create_extreme_nested_trace(nesting_depth)
            
            return result
    else:
        return response.choices[0].message.content


def run_all_stress_tests():
    """
    Runs all stress test scenarios
    """
    print("=" * 80)
    print("Starting Comprehensive OpenTelemetry Collector Stress Tests")
    print("=" * 80)
    
    # Test 1: Long-running trace (5 minutes)
    print("\n" + "=" * 50)
    print("TEST 1: Long-Running Trace (5 minutes)")
    print("=" * 50)
    result1 = stress_test_agent("Run a long computation task for 5 minutes to test collector endurance")
    print(f"Result: {result1}")
    
    # Test 2: Massive span trace (5000 spans)
    print("\n" + "=" * 50)
    print("TEST 2: Massive Span Trace (5000 spans)")
    print("=" * 50)
    result2 = stress_test_agent("Create a trace with exactly 5000 spans to stress test span processing")
    print(f"Result: {result2}")
    
    # Test 3: Concurrent traces
    print("\n" + "=" * 50)
    print("TEST 3: Concurrent Traces (10 traces, 500 spans each)")
    print("=" * 50)
    result3 = stress_test_agent("Run 10 concurrent traces with 500 spans each")
    print(f"Result: {result3}")
    
    # Test 4: Memory stress test
    print("\n" + "=" * 50)
    print("TEST 4: Memory Stress Test")
    print("=" * 50)
    result4 = stress_test_agent("Create memory-intensive traces with 50MB of data per span")
    print(f"Result: {result4}")
    
    # Test 5: Deep nesting stress test (50 levels)
    print("\n" + "=" * 50)
    print("TEST 5: Deep Nesting Stress Test (50 levels)")
    print("=" * 50)
    result5 = stress_test_agent("Create a deeply nested trace with 50 levels of nesting")
    print(f"Result: {result5}")
    
    # Test 6: Extreme nesting test (100 levels) - Optional
    print("\n" + "=" * 50)
    print("TEST 6: Extreme Nesting Test (100 levels) - OPTIONAL")
    print("=" * 50)
    print("⚠️  Warning: This test may hit recursion limits!")
    user_input = input("Run extreme nesting test? (y/N): ")
    if user_input.lower() == 'y':
        result6 = stress_test_agent("Create an extremely nested trace with 100 levels - use caution")
        print(f"Result: {result6}")
    else:
        print("Skipped extreme nesting test")
    
    print("\n" + "=" * 80)
    print("All Stress Tests Completed!")
    print("=" * 80)


def main():
    """
    Main function to initialize Pulse and run stress tests
    """
    print("Initializing OpenTelemetry Pulse for Stress Testing...")
    
    # Initialize Pulse with OTEL collector
    _ = Pulse(
        otel_collector_endpoint="http://localhost:4317",
    )
    
    print("Pulse initialized. Starting stress tests...")
    
    # You can run individual tests or all tests
    choice = input("Choose test type:\n1. All tests\n2. Long-running trace only\n3. Massive spans only\n4. Concurrent traces only\n5. Memory stress only\n6. Deep nesting (50 levels)\n7. Extreme nesting (100 levels)\nEnter choice (1-7): ")
    
    if choice == "1":
        run_all_stress_tests()
    elif choice == "2":
        result = stress_test_agent("Run a long computation task for 5 minutes")
        print(f"Long-running trace result: {result}")
    elif choice == "3":
        result = stress_test_agent("Create a trace with exactly 5000 spans")
        print(f"Massive spans result: {result}")
    elif choice == "4":
        result = stress_test_agent("Run 5 concurrent traces with 1000 spans each")
        print(f"Concurrent traces result: {result}")
    elif choice == "5":
        result = stress_test_agent("Create memory-intensive traces with 25MB data per span")
        print(f"Memory stress result: {result}")
    elif choice == "6":
        result = stress_test_agent("Create a deeply nested trace with 50 levels of nesting")
        print(f"Deep nesting result: {result}")
    elif choice == "7":
        print("⚠️  Warning: Extreme nesting test may hit recursion limits!")
        confirm = input("Continue with extreme nesting test? (y/N): ")
        if confirm.lower() == 'y':
            result = stress_test_agent("Create an extremely nested trace with 100 levels")
            print(f"Extreme nesting result: {result}")
        else:
            print("Extreme nesting test cancelled.")
    else:
        print("Invalid choice. Running all tests...")
        run_all_stress_tests()


if __name__ == "__main__":
    main()
