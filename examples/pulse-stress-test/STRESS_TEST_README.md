# Pulse and OpenTelemetry Collector  Stress Test Configuration

This directory contains comprehensive stress testing tools for the Pulse and OpenTelemetry collector and trace generation.

## F### Performance Expectations

### Baseline Performance (approximate):
- **5000 spans**: Should complete in 30-60 seconds
- **10 concurrent traces**: Should complete in 1-2 minutes
- **Long-running traces**: Should maintain <100MB memory usage
- **Memory stress**: Should handle 50MB+ spans without crashes
- **50-level nesting**: Should complete in 10-30 seconds (NEW!)
- **100-level nesting**: May hit recursion limits (expected behavior) (NEW!)

### Nesting Performance Guidelines:
- **Levels 1-25**: Full operations with normal performance
- **Levels 26-50**: Moderate operations with slight performance reduction  
- **Levels 51-75**: Lightweight operations with noticeable performance impact
- **Levels 76+**: Minimal operations, may approach system limits `stress_test_agent.py` - Main stress testing file with comprehensive scenarios
- `stress_test_runner.py` - Quick runner script for individual test scenarios
- `stress_test_config.py` - Configuration and monitoring utilities

## Test Scenarios

### 1. Long-Running Traces
Tests the collector's ability to handle traces that remain active for extended periods:
- **Duration**: 2-10 minutes per trace
- **Purpose**: Test memory management and resource usage over time
- **Spans**: Periodic spans created every 10 seconds
- **Nesting**: Multiple levels of nested spans

### 2. Massive Span Traces (5000+ spans)
Tests the collector's ability to handle traces with exceptionally high span counts:
- **Span Count**: 5,000 - 10,000 spans per trace
- **Purpose**: Stress test processing capabilities and memory usage
- **Nesting**: 3+ levels of nested operations
- **Data**: Realistic span attributes and logs

### 3. Concurrent Traces
Tests the collector under concurrent load:
- **Concurrency**: 5-20 concurrent traces
- **Spans per trace**: 200-1000 spans
- **Purpose**: Test throughput and concurrent processing
- **Threading**: Uses ThreadPoolExecutor for true concurrency

### 4. Memory Stress Tests
Tests memory handling with large span data:
- **Data size**: 10-100MB per span
- **Purpose**: Test memory limits and garbage collection
- **Spans**: 10-50 spans with large payloads

### 5. Deep Nesting Tests (NEW!)
Tests the collector's ability to handle deeply nested span structures:
- **Nesting Depth**: 50+ levels of nested spans
- **Purpose**: Test stack depth limits and recursive processing
- **Operations**: 3 operations per nesting level
- **Scaling**: Reduced operations at deeper levels to prevent stack overflow

### 6. Extreme Nesting Tests (NEW!)
Tests the absolute limits of span nesting:
- **Nesting Depth**: 100+ levels (with caution!)
- **Purpose**: Find the breaking point for deep nesting
- **Safety**: Minimal operations to prevent system crashes
- **Error Handling**: Graceful handling of recursion limits

## Usage

### Using the main stress test agent:
```bash
python stress_test_agent.py
```

### Using the quick runner:
```bash
# Run specific test
python stress_test_runner.py massive

# Run deep nesting test (50 levels)
python stress_test_runner.py deep-nesting

# Run extreme nesting test (100 levels)
python stress_test_runner.py extreme-nesting

# Run custom nesting depth
python stress_test_runner.py custom-nesting

# Run all quick tests
python stress_test_runner.py all-quick

# Run all tests including heavy ones
python stress_test_runner.py all-heavy
```

### Using the test framework:
```bash
python test_framework.py
```

### Available quick runner commands:
- `quick-long` - 2-minute long-running trace
- `massive` - 5,000 spans trace  
- `concurrent` - 5 concurrent traces with 200 spans each
- `extreme` - 10,000 spans trace (heavy)
- `endurance` - 10-minute long trace (heavy)
- `memory` - Memory stress test
- `deep-nesting` - 50 levels of nested spans (NEW!)
- `extreme-nesting` - 100 levels of nested spans (heavy, NEW!)
- `custom-nesting` - Custom nesting depth (NEW!)
- `all-quick` - All quick tests
- `all-heavy` - All tests including heavy ones

## Monitoring

The tests generate extensive logging and telemetry data. Monitor:

### OpenTelemetry Collector Metrics:
- **Memory usage**: Watch for memory leaks during long-running traces
- **CPU usage**: Monitor processing overhead with high span counts
- **Queue depths**: Check for backpressure with concurrent traces
- **Export rates**: Verify traces are being exported without drops

### Application Metrics:
- Trace completion times
- Span creation rates
- Error rates
- Resource usage

## Expected Behavior

### Long-Running Traces:
- ✅ Collector should maintain stable memory usage
- ✅ No trace drops or timeouts
- ✅ Consistent export performance

### Massive Span Traces:
- ✅ All 5000+ spans should be processed
- ✅ Memory should be released after trace completion
- ✅ No span truncation or drops

### Deep Nesting Traces:
- ✅ All 50+ nesting levels should be processed
- ✅ No stack overflow errors for reasonable depths
- ✅ Proper parent-child span relationships maintained
- ✅ Performance should degrade gracefully with depth

### Extreme Nesting Traces:
- ⚠️ May hit language recursion limits (expected)
- ✅ Should handle errors gracefully without crashes
- ✅ Should provide meaningful error messages
- ✅ System should remain stable after failure

### Concurrent Traces:
- ✅ All concurrent traces should complete
- ✅ No cross-trace contamination
- ✅ Maintained performance under load

## Troubleshooting

### High Memory Usage:
- Check collector memory limits
- Verify batch processing settings
- Monitor garbage collection

### Dropped Traces:
- Check collector queue sizes
- Verify export endpoint availability
- Monitor network connectivity

### Slow Performance:
- Check CPU usage during processing
- Verify collector configuration
- Monitor export batch sizes

## Configuration

Ensure your OpenTelemetry collector is configured for high throughput:

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 1s
    send_batch_size: 1024
    send_batch_max_size: 2048

exporters:
  # Your exporters configuration

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [your_exporter]
```

## Performance Expectations

### Baseline Performance (approximate):
- **5000 spans**: Should complete in 30-60 seconds
- **10 concurrent traces**: Should complete in 1-2 minutes
- **Long-running traces**: Should maintain <100MB memory usage
- **Memory stress**: Should handle 50MB+ spans without crashes
