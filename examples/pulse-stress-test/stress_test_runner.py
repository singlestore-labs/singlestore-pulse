#!/usr/bin/env python3
"""
Quick runner script for OpenTelemetry stress tests
Usage: python stress_test_runner.py [test_type]
"""

import sys
import time
from stress_test_agent import (
    Pulse, simulate_long_running_task, create_massive_trace_with_spans, 
    run_concurrent_stress_test, create_memory_intensive_trace,
    create_deep_nested_trace, create_extreme_nested_trace
)

def run_quick_long_trace_test():
    """Quick test for long-running traces (2 minutes)"""
    print("🕐 Running Long-Running Trace Test (2 minutes)...")
    start = time.time()
    result = simulate_long_running_task(2)  # 2 minutes
    duration = time.time() - start
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📊 Result: {result}")
    return result

def run_massive_spans_test():
    """Test with 5000 spans"""
    print("📈 Running Massive Spans Test (5000 spans)...")
    start = time.time()
    result = create_massive_trace_with_spans(5000)
    duration = time.time() - start
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📊 Result: {result}")
    return result

def run_quick_concurrent_test():
    """Quick concurrent test with fewer traces"""
    print("⚡ Running Quick Concurrent Test (5 traces, 200 spans each)...")
    start = time.time()
    result = run_concurrent_stress_test(5, 200)
    duration = time.time() - start
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📊 Result: {result}")
    return result

def run_extreme_spans_test():
    """Extreme test with 10,000 spans"""
    print("🚀 Running Extreme Spans Test (10,000 spans)...")
    print("⚠️  Warning: This will generate a very large trace!")
    confirm = input("Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("Test cancelled.")
        return
    
    start = time.time()
    result = create_massive_trace_with_spans(10000)
    duration = time.time() - start
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📊 Result: {result}")
    return result

def run_endurance_test():
    """Long endurance test (10 minutes)"""
    print("🏃‍♂️ Running Endurance Test (10 minutes)...")
    print("⚠️  Warning: This will run for 10 minutes!")
    confirm = input("Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("Test cancelled.")
        return
        
    start = time.time()
    result = simulate_long_running_task(10)  # 10 minutes
    duration = time.time() - start
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📊 Result: {result}")
    return result

def run_memory_test():
    """Memory stress test"""
    print("💾 Running Memory Stress Test...")
    start = time.time()
    result = create_memory_intensive_trace(10)  # 10MB per span
    duration = time.time() - start
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📊 Result: {result}")
    return result

def run_deep_nesting_test():
    """Deep nesting test with 50 levels"""
    print("🌳 Running Deep Nesting Test (50 levels)...")
    start = time.time()
    result = create_deep_nested_trace(50)
    duration = time.time() - start
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📊 Result: {result}")
    return result

def run_extreme_nesting_test():
    """Extreme nesting test with 100+ levels"""
    print("🚀 Running Extreme Nesting Test (100 levels)...")
    print("⚠️  Warning: This may hit recursion limits!")
    confirm = input("Continue? (y/N): ")
    if confirm.lower() != 'y':
        print("Test cancelled.")
        return
    
    start = time.time()
    result = create_extreme_nested_trace(100)
    duration = time.time() - start
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📊 Result: {result}")
    return result

def run_custom_nesting_test():
    """Custom nesting depth test"""
    print("⚙️  Running Custom Nesting Test...")
    try:
        depth = int(input("Enter nesting depth (1-200): "))
        if depth < 1 or depth > 200:
            print("❌ Invalid depth. Using default 50.")
            depth = 50
    except ValueError:
        print("❌ Invalid input. Using default 50.")
        depth = 50
    
    print(f"🌳 Creating trace with {depth} levels of nesting...")
    start = time.time()
    
    if depth > 80:
        result = create_extreme_nested_trace(depth)
    else:
        result = create_deep_nested_trace(depth)
    
    duration = time.time() - start
    print(f"✅ Completed in {duration:.2f} seconds")
    print(f"📊 Result: {result}")
    return result

def main():
    """Main runner function"""
    print("🧪 OpenTelemetry Collector Stress Test Runner")
    print("=" * 60)
    
    # Initialize Pulse
    print("🔧 Initializing Pulse...")
    _ = Pulse(otel_collector_endpoint="http://localhost:4317")
    print("✅ Pulse initialized!")
    
    if len(sys.argv) > 1:
        test_type = sys.argv[1].lower()
    else:
        print("\nAvailable tests:")
        print("1. quick-long     - 2-minute long-running trace")
        print("2. massive        - 5,000 spans trace")
        print("3. concurrent     - 5 concurrent traces")
        print("4. extreme        - 10,000 spans trace (⚠️  Heavy)")
        print("5. endurance      - 10-minute long trace (⚠️  Long)")
        print("6. memory         - Memory stress test")
        print("7. deep-nesting   - 50 levels of nested spans")
        print("8. extreme-nesting - 100 levels of nested spans (⚠️  Heavy)")
        print("9. custom-nesting - Custom nesting depth")
        print("10. all-quick     - Run all quick tests")
        print("11. all-heavy     - Run all tests including heavy ones")
        
        test_type = input("\nEnter test type (1-11 or name): ").strip()
    
    # Map choices
    test_map = {
        "1": "quick-long", "quick-long": "quick-long",
        "2": "massive", "massive": "massive", 
        "3": "concurrent", "concurrent": "concurrent",
        "4": "extreme", "extreme": "extreme",
        "5": "endurance", "endurance": "endurance",
        "6": "memory", "memory": "memory",
        "7": "deep-nesting", "deep-nesting": "deep-nesting",
        "8": "extreme-nesting", "extreme-nesting": "extreme-nesting",
        "9": "custom-nesting", "custom-nesting": "custom-nesting",
        "10": "all-quick", "all-quick": "all-quick",
        "11": "all-heavy", "all-heavy": "all-heavy"
    }
    
    test_choice = test_map.get(test_type, test_type)
    
    print(f"\n🚀 Starting test: {test_choice}")
    print("=" * 60)
    
    total_start = time.time()
    
    try:
        if test_choice == "quick-long":
            run_quick_long_trace_test()
            
        elif test_choice == "massive":
            run_massive_spans_test()
            
        elif test_choice == "concurrent":
            run_quick_concurrent_test()
            
        elif test_choice == "extreme":
            run_extreme_spans_test()
            
        elif test_choice == "endurance":
            run_endurance_test()
            
        elif test_choice == "memory":
            run_memory_test()
            
        elif test_choice == "deep-nesting":
            run_deep_nesting_test()
            
        elif test_choice == "extreme-nesting":
            run_extreme_nesting_test()
            
        elif test_choice == "custom-nesting":
            run_custom_nesting_test()
            
        elif test_choice == "all-quick":
            print("🏃‍♂️ Running all quick tests...")
            run_quick_long_trace_test()
            print("\n" + "-" * 40)
            run_massive_spans_test()  
            print("\n" + "-" * 40)
            run_quick_concurrent_test()
            print("\n" + "-" * 40)
            run_memory_test()
            print("\n" + "-" * 40)
            run_deep_nesting_test()
            
        elif test_choice == "all-heavy":
            print("💪 Running all tests including heavy ones...")
            run_quick_long_trace_test()
            print("\n" + "-" * 40)
            run_massive_spans_test()
            print("\n" + "-" * 40)
            run_quick_concurrent_test()
            print("\n" + "-" * 40)
            run_memory_test()
            print("\n" + "-" * 40)
            run_deep_nesting_test()
            print("\n" + "-" * 40)
            run_extreme_spans_test()
            print("\n" + "-" * 40)
            run_endurance_test()
            print("\n" + "-" * 40)
            run_extreme_nesting_test()
            
        else:
            print(f"❌ Unknown test type: {test_choice}")
            return 1
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return 1
    
    total_duration = time.time() - total_start
    print(f"\n🎉 All tests completed successfully!")
    print(f"⏱️  Total execution time: {total_duration:.2f} seconds")
    
    return 0

if __name__ == "__main__":
    exit(main())
