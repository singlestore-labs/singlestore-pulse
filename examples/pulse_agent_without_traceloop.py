from pulse_otel import Pulse, traced_function

@traced_function
def divide(a, b):
    return a / b

if __name__ == "__main__":

	_ = Pulse(
		otel_collector_endpoint="http://localhost:4317",
		without_traceloop=True,	
		write_to_file=True,
	)

	try:
		result1 = divide(10, 2)
		print(f"Result: {result1}")

		result2 = divide(10, 0)  # This will raise an exception
		print(f"Result: {result2}")
	except ZeroDivisionError as e:
		print(f"Caught an exception: {e}")


