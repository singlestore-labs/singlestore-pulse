import time

start = time.time()
import pulse_otel
print(f"Import time: {time.time() - start:.4f} sec")

start = time.time()
from pulse_otel import Pulse, pulse_agent
print(f"From import time: {time.time() - start:.4f} sec")

start = time.time()
_ = Pulse(
	otel_collector_endpoint="http://localhost:4317",
)
print(f"Init time: {time.time() - start:.4f} sec")
