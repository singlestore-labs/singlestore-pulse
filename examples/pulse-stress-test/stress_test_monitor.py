#!/usr/bin/env python3
"""
Monitoring utilities for OpenTelemetry stress tests
"""

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    print("⚠️  psutil not available. Install with: pip install psutil")
    PSUTIL_AVAILABLE = False

import time
import json
import threading
from datetime import datetime
from typing import Dict, List, Any
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    print("⚠️  requests not available. Install with: pip install requests")
    REQUESTS_AVAILABLE = False

from dataclasses import dataclass
from collections import defaultdict

@dataclass
class PerformanceMetrics:
    timestamp: datetime
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    active_threads: int
    open_files: int

class StressTestMonitor:
    """Monitor system resources during stress tests"""
    
    def __init__(self, monitor_interval: int = 5):
        self.monitor_interval = monitor_interval
        self.metrics: List[PerformanceMetrics] = []
        self.monitoring = False
        self.monitor_thread = None
        self.start_time = None
        
    def start_monitoring(self):
        """Start monitoring system resources"""
        if not PSUTIL_AVAILABLE:
            print("❌ Cannot start monitoring: psutil not available")
            return
            
        if self.monitoring:
            print("⚠️  Monitoring already started")
            return
            
        self.monitoring = True
        self.start_time = datetime.now()
        self.metrics = []
        
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        print(f"📊 Started monitoring (interval: {self.monitor_interval}s)")
        
    def stop_monitoring(self):
        """Stop monitoring and return metrics"""
        if not self.monitoring:
            print("⚠️  Monitoring not started")
            return []
            
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=10)
            
        duration = datetime.now() - self.start_time
        print(f"📊 Stopped monitoring (duration: {duration.total_seconds():.1f}s)")
        
        return self.get_metrics_summary()
        
    def _monitor_loop(self):
        """Internal monitoring loop"""
        process = psutil.Process()
        
        while self.monitoring:
            try:
                # Get current metrics
                cpu_percent = process.cpu_percent()
                memory_info = process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024  # Convert to MB
                memory_percent = process.memory_percent()
                
                # Get thread and file descriptor counts
                try:
                    active_threads = process.num_threads()
                except:
                    active_threads = -1
                    
                try:
                    open_files = process.num_fds() if hasattr(process, 'num_fds') else len(process.open_files())
                except:
                    open_files = -1
                
                # Store metrics
                metrics = PerformanceMetrics(
                    timestamp=datetime.now(),
                    cpu_percent=cpu_percent,
                    memory_mb=memory_mb,
                    memory_percent=memory_percent,
                    active_threads=active_threads,
                    open_files=open_files
                )
                
                self.metrics.append(metrics)
                
                # Print real-time stats
                print(f"📈 CPU: {cpu_percent:5.1f}% | Memory: {memory_mb:6.1f}MB ({memory_percent:4.1f}%) | Threads: {active_threads:3d} | Files: {open_files:3d}")
                
            except Exception as e:
                print(f"❌ Monitoring error: {e}")
                
            time.sleep(self.monitor_interval)
            
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of collected metrics"""
        if not self.metrics:
            return {"error": "No metrics collected"}
            
        cpu_values = [m.cpu_percent for m in self.metrics]
        memory_values = [m.memory_mb for m in self.metrics]
        memory_percent_values = [m.memory_percent for m in self.metrics]
        thread_values = [m.active_threads for m in self.metrics if m.active_threads > 0]
        file_values = [m.open_files for m in self.metrics if m.open_files > 0]
        
        summary = {
            "monitoring_duration_seconds": (self.metrics[-1].timestamp - self.metrics[0].timestamp).total_seconds(),
            "sample_count": len(self.metrics),
            "cpu_percent": {
                "min": min(cpu_values),
                "max": max(cpu_values),
                "avg": sum(cpu_values) / len(cpu_values),
            },
            "memory_mb": {
                "min": min(memory_values),
                "max": max(memory_values),
                "avg": sum(memory_values) / len(memory_values),
                "peak_increase": max(memory_values) - min(memory_values),
            },
            "memory_percent": {
                "min": min(memory_percent_values),
                "max": max(memory_percent_values),
                "avg": sum(memory_percent_values) / len(memory_percent_values),
            }
        }
        
        if thread_values:
            summary["threads"] = {
                "min": min(thread_values),
                "max": max(thread_values),
                "avg": sum(thread_values) / len(thread_values),
            }
            
        if file_values:
            summary["open_files"] = {
                "min": min(file_values),
                "max": max(file_values),
                "avg": sum(file_values) / len(file_values),
            }
            
        return summary
        
    def save_metrics(self, filename: str):
        """Save metrics to JSON file"""
        data = {
            "summary": self.get_metrics_summary(),
            "raw_metrics": [
                {
                    "timestamp": m.timestamp.isoformat(),
                    "cpu_percent": m.cpu_percent,
                    "memory_mb": m.memory_mb,
                    "memory_percent": m.memory_percent,
                    "active_threads": m.active_threads,
                    "open_files": m.open_files,
                }
                for m in self.metrics
            ]
        }
        
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
            
        print(f"💾 Saved metrics to {filename}")

class OTelCollectorMonitor:
    """Monitor OpenTelemetry Collector metrics"""
    
    def __init__(self, collector_metrics_url: str = "http://localhost:8888/metrics"):
        self.collector_metrics_url = collector_metrics_url
        self.baseline_metrics = None
        
    def check_collector_health(self) -> bool:
        """Check if OpenTelemetry Collector is accessible"""
        if not REQUESTS_AVAILABLE:
            print("⚠️  Cannot check collector health: requests not available")
            return False
            
        try:
            response = requests.get(self.collector_metrics_url, timeout=5)
            return response.status_code == 200
        except:
            return False
            
    def get_collector_metrics(self) -> Dict[str, Any]:
        """Get current collector metrics"""
        if not REQUESTS_AVAILABLE:
            return {"error": "requests library not available"}
            
        try:
            response = requests.get(self.collector_metrics_url, timeout=10)
            if response.status_code != 200:
                return {"error": f"HTTP {response.status_code}"}
                
            # Parse Prometheus metrics (simplified)
            metrics = {}
            for line in response.text.split('\n'):
                if line.startswith('#') or not line.strip():
                    continue
                    
                if ' ' in line:
                    metric_name, value = line.rsplit(' ', 1)
                    try:
                        metrics[metric_name] = float(value)
                    except ValueError:
                        pass
                        
            return metrics
            
        except Exception as e:
            return {"error": str(e)}
            
    def capture_baseline(self):
        """Capture baseline metrics before stress test"""
        self.baseline_metrics = self.get_collector_metrics()
        if "error" not in self.baseline_metrics:
            print("📊 Captured baseline collector metrics")
        else:
            print(f"⚠️  Could not capture baseline: {self.baseline_metrics['error']}")
            
    def compare_with_baseline(self) -> Dict[str, Any]:
        """Compare current metrics with baseline"""
        if not self.baseline_metrics or "error" in self.baseline_metrics:
            return {"error": "No valid baseline metrics"}
            
        current_metrics = self.get_collector_metrics()
        if "error" in current_metrics:
            return current_metrics
            
        comparison = {}
        for metric_name in self.baseline_metrics:
            if metric_name in current_metrics:
                baseline_value = self.baseline_metrics[metric_name]
                current_value = current_metrics[metric_name]
                difference = current_value - baseline_value
                
                comparison[metric_name] = {
                    "baseline": baseline_value,
                    "current": current_value,
                    "difference": difference,
                    "percent_change": (difference / baseline_value * 100) if baseline_value != 0 else 0
                }
                
        return comparison

def run_monitored_stress_test(test_function, test_name: str, *args, **kwargs):
    """Run a stress test with monitoring"""
    print(f"🧪 Starting monitored stress test: {test_name}")
    print("=" * 60)
    
    # Initialize monitors
    system_monitor = StressTestMonitor(monitor_interval=2)
    collector_monitor = OTelCollectorMonitor()
    
    # Check collector health
    if collector_monitor.check_collector_health():
        print("✅ OpenTelemetry Collector is accessible")
        collector_monitor.capture_baseline()
    else:
        print("⚠️  OpenTelemetry Collector metrics not accessible")
    
    # Start monitoring
    system_monitor.start_monitoring()
    
    try:
        # Run the actual stress test
        print(f"🚀 Running {test_name}...")
        start_time = time.time()
        
        result = test_function(*args, **kwargs)
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"✅ {test_name} completed in {duration:.2f} seconds")
        print(f"📊 Result: {result}")
        
    except Exception as e:
        print(f"❌ {test_name} failed: {e}")
        result = f"Error: {e}"
        duration = time.time() - start_time
        
    finally:
        # Stop monitoring and get results
        print("\n📊 Collecting monitoring results...")
        system_summary = system_monitor.stop_monitoring()
        
        # Save detailed metrics
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        metrics_filename = f"stress_test_metrics_{test_name}_{timestamp}.json"
        system_monitor.save_metrics(metrics_filename)
        
        # Compare collector metrics
        collector_comparison = collector_monitor.compare_with_baseline()
        
        # Print summary
        print("\n" + "=" * 60)
        print(f"📈 MONITORING SUMMARY - {test_name}")
        print("=" * 60)
        print(f"⏱️  Duration: {duration:.2f} seconds")
        print(f"🖥️  CPU Peak: {system_summary.get('cpu_percent', {}).get('max', 'N/A'):.1f}%")
        print(f"💾 Memory Peak: {system_summary.get('memory_mb', {}).get('max', 'N/A'):.1f} MB")
        print(f"📊 Memory Increase: {system_summary.get('memory_mb', {}).get('peak_increase', 'N/A'):.1f} MB")
        
        if "error" not in collector_comparison:
            print("🔍 Collector Metrics Changes:")
            for metric, data in list(collector_comparison.items())[:5]:  # Show top 5 changes
                if abs(data['difference']) > 0.1:  # Only show significant changes
                    print(f"   {metric}: {data['difference']:+.2f} ({data['percent_change']:+.1f}%)")
        
        print(f"💾 Detailed metrics saved to: {metrics_filename}")
        print("=" * 60)
        
        return {
            "result": result,
            "duration": duration,
            "system_metrics": system_summary,
            "collector_metrics": collector_comparison,
            "metrics_file": metrics_filename
        }

if __name__ == "__main__":
    # Example usage
    from stress_test_agent import create_massive_trace_with_spans, simulate_long_running_task
    from pulse_otel import Pulse
    
    print("🔧 Initializing Pulse...")
    _ = Pulse(otel_collector_endpoint="http://localhost:4317")
    
    # Run a monitored test
    test_result = run_monitored_stress_test(
        create_massive_trace_with_spans,
        "massive_spans_1000",
        1000  # 1000 spans
    )
    
    print(f"\n🎉 Test completed: {test_result['result']}")
