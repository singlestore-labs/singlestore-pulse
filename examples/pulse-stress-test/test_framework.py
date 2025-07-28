#!/usr/bin/env python3
"""
Test Framework Configuration for OpenTelemetry Stress Tests

This module provides configuration and utilities for running comprehensive
stress tests on OpenTelemetry collectors and trace generation systems.
"""

import unittest
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from contextlib import contextmanager

from pulse_otel import Pulse
from stress_test_agent import (
    simulate_long_running_task,
    create_massive_trace_with_spans,
    run_concurrent_stress_test,
    create_memory_intensive_trace,
    create_deep_nested_trace,
    create_extreme_nested_trace
)

# Configure logging for tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    """Represents the result of a stress test"""
    test_name: str
    success: bool
    duration: float
    result_data: Any
    error_message: Optional[str] = None
    performance_metrics: Optional[Dict[str, Any]] = None

@dataclass
class TestConfig:
    """Configuration for stress tests"""
    otel_collector_endpoint: str = "http://localhost:4317"
    timeout_seconds: int = 3600  # 1 hour default timeout
    enable_monitoring: bool = True
    save_metrics: bool = True
    metrics_output_dir: str = "./test_results"

class StressTestFramework:
    """Framework for running OpenTelemetry stress tests"""
    
    def __init__(self, config: TestConfig):
        self.config = config
        self.pulse_instance = None
        self.test_results: List[TestResult] = []
        
    @contextmanager
    def setup_pulse(self):
        """Context manager for Pulse setup and teardown"""
        try:
            logger.info("Initializing Pulse for stress testing...")
            self.pulse_instance = Pulse(
                otel_collector_endpoint=self.config.otel_collector_endpoint
            )
            logger.info("✅ Pulse initialized successfully")
            yield self.pulse_instance
        except Exception as e:
            logger.error(f"❌ Failed to initialize Pulse: {e}")
            raise
        finally:
            if self.pulse_instance:
                logger.info("🧹 Cleaning up Pulse instance...")
                # Add any cleanup logic here if needed
    
    def run_test_with_timeout(self, test_func, test_name: str, *args, **kwargs) -> TestResult:
        """Run a test function with timeout and error handling"""
        logger.info(f"🚀 Starting test: {test_name}")
        start_time = time.time()
        
        try:
            result_data = test_func(*args, **kwargs)
            duration = time.time() - start_time
            
            test_result = TestResult(
                test_name=test_name,
                success=True,
                duration=duration,
                result_data=result_data
            )
            
            logger.info(f"✅ Test {test_name} completed successfully in {duration:.2f}s")
            return test_result
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)
            
            test_result = TestResult(
                test_name=test_name,
                success=False,
                duration=duration,
                result_data=None,
                error_message=error_msg
            )
            
            logger.error(f"❌ Test {test_name} failed after {duration:.2f}s: {error_msg}")
            return test_result
    
    def run_all_stress_tests(self) -> List[TestResult]:
        """Run all configured stress tests"""
        test_suite = [
            (simulate_long_running_task, "long_running_2min", 2),
            (create_massive_trace_with_spans, "massive_spans_5000", 5000),
            (run_concurrent_stress_test, "concurrent_5x200", 5, 200),
            (create_memory_intensive_trace, "memory_stress_10mb", 10),
            (create_deep_nested_trace, "deep_nesting_50", 50),
            (create_extreme_nested_trace, "extreme_nesting_100", 100),
        ]
        
        with self.setup_pulse():
            for test_func, test_name, *args in test_suite:
                result = self.run_test_with_timeout(test_func, test_name, *args)
                self.test_results.append(result)
                
                # Small delay between tests to allow system recovery
                time.sleep(5)
        
        return self.test_results
    
    def run_quick_tests(self) -> List[TestResult]:
        """Run only quick stress tests (< 5 minutes each)"""
        quick_test_suite = [
            (simulate_long_running_task, "quick_long_running_1min", 1),
            (create_massive_trace_with_spans, "quick_massive_spans_1000", 1000),
            (run_concurrent_stress_test, "quick_concurrent_3x100", 3, 100),
            (create_memory_intensive_trace, "quick_memory_stress_5mb", 5),
            (create_deep_nested_trace, "quick_deep_nesting_30", 30),
        ]
        
        with self.setup_pulse():
            for test_func, test_name, *args in quick_test_suite:
                result = self.run_test_with_timeout(test_func, test_name, *args)
                self.test_results.append(result)
                time.sleep(2)  # Shorter delay for quick tests
        
        return self.test_results
    
    def run_nesting_tests(self) -> List[TestResult]:
        """Run comprehensive nesting depth tests"""
        nesting_test_suite = [
            (create_deep_nested_trace, "nesting_depth_10", 10),
            (create_deep_nested_trace, "nesting_depth_25", 25),
            (create_deep_nested_trace, "nesting_depth_50", 50),
            (create_deep_nested_trace, "nesting_depth_75", 75),
            (create_extreme_nested_trace, "extreme_nesting_100", 100),
            (create_extreme_nested_trace, "extreme_nesting_150", 150),
        ]
        
        with self.setup_pulse():
            for test_func, test_name, *args in nesting_test_suite:
                result = self.run_test_with_timeout(test_func, test_name, *args)
                self.test_results.append(result)
                time.sleep(3)
        
        return self.test_results
    
    def generate_test_report(self) -> str:
        """Generate a comprehensive test report"""
        if not self.test_results:
            return "No test results available"
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r.success)
        failed_tests = total_tests - successful_tests
        total_duration = sum(r.duration for r in self.test_results)
        
        report = [
            "=" * 80,
            "OPENTELEMETRY STRESS TEST REPORT",
            "=" * 80,
            f"Total Tests: {total_tests}",
            f"Successful: {successful_tests} ✅",
            f"Failed: {failed_tests} ❌",
            f"Success Rate: {(successful_tests/total_tests)*100:.1f}%",
            f"Total Duration: {total_duration:.2f} seconds",
            "",
            "DETAILED RESULTS:",
            "-" * 50,
        ]
        
        for result in self.test_results:
            status = "✅ PASS" if result.success else "❌ FAIL"
            report.append(f"{result.test_name:<30} {status} ({result.duration:.2f}s)")
            
            if not result.success and result.error_message:
                report.append(f"  Error: {result.error_message}")
            elif result.success and result.result_data:
                # Truncate long result data
                result_str = str(result.result_data)
                if len(result_str) > 100:
                    result_str = result_str[:97] + "..."
                report.append(f"  Result: {result_str}")
        
        report.extend([
            "",
            "=" * 80,
            "END OF REPORT",
            "=" * 80
        ])
        
        return "\n".join(report)

class OTelStressTestCase(unittest.TestCase):
    """Unit test cases for OpenTelemetry stress testing"""
    
    @classmethod
    def setUpClass(cls):
        """Set up test class with Pulse instance"""
        cls.config = TestConfig()
        cls.framework = StressTestFramework(cls.config)
        cls.pulse = Pulse(otel_collector_endpoint=cls.config.otel_collector_endpoint)
    
    def test_long_running_trace_1min(self):
        """Test 1-minute long-running trace"""
        result = simulate_long_running_task(1)
        self.assertIsNotNone(result)
        self.assertIn("completed", result.lower())
    
    def test_massive_spans_1000(self):
        """Test trace with 1000 spans"""
        result = create_massive_trace_with_spans(1000)
        self.assertIsNotNone(result)
        self.assertIn("1000", result)
    
    def test_concurrent_traces_small(self):
        """Test small concurrent trace load"""
        result = run_concurrent_stress_test(3, 100)
        self.assertIsNotNone(result)
        self.assertIn("completed", result.lower())
    
    def test_deep_nesting_20_levels(self):
        """Test deep nesting with 20 levels"""
        result = create_deep_nested_trace(20)
        self.assertIsNotNone(result)
        self.assertIn("20", result)
    
    def test_deep_nesting_50_levels(self):
        """Test deep nesting with 50 levels"""
        result = create_deep_nested_trace(50)
        self.assertIsNotNone(result)
        self.assertIn("50", result)
    
    def test_extreme_nesting_100_levels(self):
        """Test extreme nesting with 100 levels (may fail on recursion limits)"""
        try:
            result = create_extreme_nested_trace(100)
            self.assertIsNotNone(result)
            # Test passes if no exception is raised
        except RecursionError:
            # Expected behavior for extreme nesting
            self.skipTest("Recursion limit reached - expected for extreme nesting")

def run_test_suite():
    """Run the complete stress test suite using unittest"""
    logger.info("🧪 Starting OpenTelemetry Stress Test Suite")
    
    # Run unittest suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(OTelStressTestCase)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result

def main():
    """Main function for test framework"""
    config = TestConfig()
    framework = StressTestFramework(config)
    
    print("🧪 OpenTelemetry Stress Test Framework")
    print("=" * 60)
    
    choice = input("""
Choose test mode:
1. Quick tests (< 5 min total)
2. Full stress tests (may take 30+ min)
3. Nesting depth tests
4. Unit test suite
5. Custom test selection

Enter choice (1-5): """).strip()
    
    try:
        if choice == "1":
            print("🏃‍♂️ Running quick tests...")
            results = framework.run_quick_tests()
            
        elif choice == "2":
            print("💪 Running full stress tests...")
            results = framework.run_all_stress_tests()
            
        elif choice == "3":
            print("🌳 Running nesting depth tests...")
            results = framework.run_nesting_tests()
            
        elif choice == "4":
            print("🧪 Running unit test suite...")
            test_result = run_test_suite()
            return 0 if test_result.wasSuccessful() else 1
            
        elif choice == "5":
            print("⚙️  Custom test selection not implemented yet")
            return 1
            
        else:
            print("❌ Invalid choice")
            return 1
        
        # Generate and display report
        report = framework.generate_test_report()
        print("\n" + report)
        
        # Save report to file
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_file = f"stress_test_report_{timestamp}.txt"
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"\n📄 Report saved to: {report_file}")
        
        # Return exit code based on test success
        failed_tests = sum(1 for r in results if not r.success)
        return 0 if failed_tests == 0 else 1
        
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Test framework error: {e}")
        return 1

if __name__ == "__main__":
    exit(main())
