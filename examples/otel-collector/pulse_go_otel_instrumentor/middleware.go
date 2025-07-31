package pulse_otel

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/propagation"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	"go.opentelemetry.io/otel/trace"
)

// HTTPMiddleware provides HTTP instrumentation middleware
type HTTPMiddleware struct {
	pulseTraceManager *PulseTraceManager
	serviceName       string
}

// NewHTTPMiddleware creates a new HTTP middleware with project support
func NewHTTPMiddleware(serviceName string, baseConfig *Config) *HTTPMiddleware {
	// Set up global OpenTelemetry providers so instrumented libraries can use them
	setupGlobalOTelProviders(baseConfig)

	return &HTTPMiddleware{
		pulseTraceManager: NewPulseTraceManager(baseConfig),
		serviceName:       serviceName,
	}
}

// setupGlobalOTelProviders configures global OpenTelemetry providers
func setupGlobalOTelProviders(baseConfig *Config) {
	// Create a default tracer provider for global use
	defaultProvider, err := NewPulseTraceManager(baseConfig).GetTracerProvider("default")
	if err == nil {
		// Set the global tracer provider so instrumented libraries can use it
		otel.SetTracerProvider(defaultProvider.traceProvider)
	}

	// Set the global text map propagator for context propagation
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))
}

// GetPulseTraceManager returns the pulse trace manager instance
func (m *HTTPMiddleware) GetPulseTraceManager() *PulseTraceManager {
	return m.pulseTraceManager
}

// Shutdown gracefully shuts down the middleware and its project manager
func (m *HTTPMiddleware) Shutdown(ctx context.Context) error {
	return m.pulseTraceManager.Shutdown(ctx)
}

// Handler wraps an http.Handler with opentelemetry instrumentation
func (m *HTTPMiddleware) Handler(handler http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Extract project ID from header first
		projectID := r.Header.Get("singlestore-project-id")

		// If not found in header, check JSON body
		if projectID == "" {
			projectID = m.extractProjectIDFromBody(r)
		}

		fmt.Println("Project ID extracted:", projectID)

		// Get project-specific tracer provider
		provider, err := m.pulseTraceManager.GetTracerProvider(projectID)
		if err != nil {
			// Log error and use default behavior
			fmt.Printf("Error getting project provider for %s: %v\n", projectID, err)
			handler.ServeHTTP(w, r)
			return
		}

		// Check and update collector reachability safely
		isCollectorReachable, err := m.pulseTraceManager.CheckAndUpdateCollectorReachability(projectID)
		if err != nil {
			fmt.Printf("Error checking collector reachability for project %s: %v\n", projectID, err)
			handler.ServeHTTP(w, r)
			return
		}

		fmt.Println("isCollectorReachable:", isCollectorReachable)
		if !isCollectorReachable {
			// If collector is not reachable, skip tracing
			handler.ServeHTTP(w, r)
			return
		}

		tracer := provider.traceProvider.Tracer(m.serviceName)

		// Extract any existing trace context from incoming request headers
		ctx := otel.GetTextMapPropagator().Extract(r.Context(), propagation.HeaderCarrier(r.Header))

		spanName := fmt.Sprintf("%s %s", r.Method, r.URL.Path)
		ctx, span := tracer.Start(ctx, spanName,
			trace.WithSpanKind(trace.SpanKindServer),
			trace.WithAttributes(
				semconv.HTTPRoute(r.URL.Path),
				attribute.String("project.id", projectID),
			),
		)
		defer span.End()

		// IMPORTANT: Set the global tracer provider to the project-specific one
		// This ensures that any instrumented library will use the correct tracer provider
		otel.SetTracerProvider(provider.traceProvider)

		wrappedWriter := &responseWriter{
			ResponseWriter: w,
			statusCode:     http.StatusOK,
		}

		// Execute the handler with the instrumented context
		// The context now contains the active span that instrumented libraries can use
		r = r.WithContext(ctx)
		start := time.Now()
		handler.ServeHTTP(wrappedWriter, r)
		duration := time.Since(start)

		// Add response attributes
		span.SetAttributes(
			attribute.Float64("http.duration_ms", float64(duration.Nanoseconds())/1000000),
		)

		// Set span status based on HTTP status code
		if wrappedWriter.statusCode >= 400 {
			span.SetStatus(codes.Error, fmt.Sprintf("HTTP %d", wrappedWriter.statusCode))
		}

		// Inject trace context into response headers
		otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(w.Header()))
	})
}

// extractProjectIDFromBody attempts to extract project-id from the request body
func (m *HTTPMiddleware) extractProjectIDFromBody(r *http.Request) string {
	// Only check for project-id in POST/PUT/PATCH requests with JSON content
	if r.Method != http.MethodPost && r.Method != http.MethodPut && r.Method != http.MethodPatch {
		return ""
	}

	contentType := r.Header.Get("Content-Type")
	if contentType != "application/json" && contentType != "application/json; charset=utf-8" {
		return ""
	}

	// Read the body
	body, err := io.ReadAll(r.Body)
	if err != nil {
		return ""
	}

	// Restore the body for the actual handler to use
	r.Body = io.NopCloser(bytes.NewBuffer(body))

	// Parse JSON to extract project-id
	var jsonData map[string]interface{}
	if err := json.Unmarshal(body, &jsonData); err != nil {
		return ""
	}

	// Extract project-id from JSON
	if projectID, exists := jsonData["project-id"]; exists {
		if projectIDStr, ok := projectID.(string); ok {
			return projectIDStr
		}
	}

	return ""
}

func (m *HTTPMiddleware) HandlerFunc(handler http.HandlerFunc) http.HandlerFunc {
	return m.Handler(handler).ServeHTTP
}

// responseWriter wraps http.ResponseWriter to capture response details
type responseWriter struct {
	http.ResponseWriter
	statusCode   int
	bytesWritten int64
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

func (rw *responseWriter) Write(data []byte) (int, error) {
	n, err := rw.ResponseWriter.Write(data)
	rw.bytesWritten += int64(n)
	return n, err
}

// GetInstrumentedHTTPClient returns an HTTP client that will automatically
// create spans for outgoing requests when used within a traced context
func GetInstrumentedHTTPClient() *http.Client {
	return &http.Client{
		Transport: &InstrumentedTransport{
			base: http.DefaultTransport,
		},
	}
}

// InstrumentedTransport wraps http.RoundTripper to add automatic tracing
type InstrumentedTransport struct {
	base http.RoundTripper
}

// RoundTrip implements http.RoundTripper and automatically creates spans for HTTP requests
func (t *InstrumentedTransport) RoundTrip(req *http.Request) (*http.Response, error) {
	ctx := req.Context()

	// Debug: Print context information
	fmt.Printf("HTTP Client: Request URL: %s\n", req.URL.String())

	// Get the active span from context (if any)
	span := trace.SpanFromContext(ctx)
	fmt.Printf("HTTP Client: Active span found: %t, Recording: %t\n", span != nil, span.IsRecording())

	if !span.IsRecording() {
		// No active span, just pass through
		fmt.Println("HTTP Client: No recording span, passing through")
		return t.base.RoundTrip(req)
	}

	// Get tracer from the global tracer provider
	tracer := otel.Tracer("http-client")

	// Create a new span for the HTTP request
	spanName := fmt.Sprintf("HTTP %s %s", req.Method, req.URL.Host)
	ctx, clientSpan := tracer.Start(ctx, spanName,
		trace.WithSpanKind(trace.SpanKindClient),
		trace.WithAttributes(
			attribute.String("http.method", req.Method),
			attribute.String("http.url", req.URL.String()),
			attribute.String("http.scheme", req.URL.Scheme),
			attribute.String("http.host", req.URL.Host),
			attribute.String("http.target", req.URL.Path),
		),
	)
	defer clientSpan.End()

	fmt.Printf("HTTP Client: Created client span: %s\n", spanName)

	// Inject trace context into request headers for downstream propagation
	otel.GetTextMapPropagator().Inject(ctx, propagation.HeaderCarrier(req.Header))

	// Update request with new context
	req = req.WithContext(ctx)

	// Make the request
	start := time.Now()
	resp, err := t.base.RoundTrip(req)
	duration := time.Since(start)

	// Add response attributes
	clientSpan.SetAttributes(
		attribute.Float64("http.duration_ms", float64(duration.Nanoseconds())/1000000),
	)

	if err != nil {
		clientSpan.RecordError(err)
		clientSpan.SetStatus(codes.Error, err.Error())
		return resp, err
	}

	// Add response status
	clientSpan.SetAttributes(
		attribute.Int("http.status_code", resp.StatusCode),
	)

	// Set span status based on HTTP status code
	if resp.StatusCode >= 400 {
		clientSpan.SetStatus(codes.Error, fmt.Sprintf("HTTP %d", resp.StatusCode))
	} else {
		clientSpan.SetStatus(codes.Ok, "")
	}

	return resp, nil
}
