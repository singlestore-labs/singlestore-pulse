package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"time"

	pulse_otel "github.com/aanshu-ss/s2-otel-instrumentation-go"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/trace"
)

type User struct {
	ID    string `json:"id"`
	Name  string `json:"name"`
	Email string `json:"email"`
}

type Response struct {
	Success bool        `json:"success"`
	Data    interface{} `json:"data,omitempty"`
	Error   string      `json:"error,omitempty"`
}

var (
	middleware *pulse_otel.HTTPMiddleware // Only keep the middleware as global
)

func main() {
	// Initialize OpenTelemetry base configuration
	config := pulse_otel.DefaultConfig()
	config.ServiceName = "user-api"
	config.ServiceVersion = "1.0.0"
	config.Environment = "development"
	config.AddResourceAttribute("api.type", "rest")
	config.AddResourceAttribute("team", "backend")

	// Create HTTP middleware with project support (this creates project manager internally)
	middleware = pulse_otel.NewHTTPMiddleware("user-api", config)

	defer func() {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		middleware.Shutdown(ctx) // Shutdown through middleware
	}()

	// Setup routes with instrumentation
	http.Handle("/users", middleware.Handler(http.HandlerFunc(getUsersHandler)))
	http.Handle("/users/create", middleware.Handler(http.HandlerFunc(createUserHandler)))
	http.Handle("/health", middleware.Handler(http.HandlerFunc(healthHandler)))
	http.Handle("/my-post", middleware.Handler(http.HandlerFunc(myPostHandler)))

	log.Println("Starting server on :8093")
	log.Fatal(http.ListenAndServe(":8093", nil))
}

func getUsersHandler(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// Get project-specific tracer
	projectID := r.Header.Get("x-project-id")
	if projectID == "" {
		projectID = "default"
	}

	tracer, err := middleware.GetPulseTraceManager().GetTracer(projectID, "user-api")
	if err != nil {
		log.Printf("Error getting tracer for project %s: %v", projectID, err)
		writeErrorResponse(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	// Add custom span attributes
	tracer.AddSpanAttributes(ctx,
		attribute.String("handler.name", "getUsers"),
		attribute.String("operation.type", "read"),
		attribute.String("project.id", projectID),
	)

	// Simulate database call with child span
	users, err := fetchUsersFromDB(ctx, tracer)
	if err != nil {
		tracer.RecordError(ctx, err)
		writeErrorResponse(w, "Failed to fetch users", http.StatusInternalServerError)
		return
	}

	tracer.AddSpanAttribute(ctx, "users.count", strconv.Itoa(len(users)))
	writeSuccessResponse(w, users)
}

func createUserHandler(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Get project-specific tracer
	projectID := r.Header.Get("x-project-id")
	if projectID == "" {
		projectID = "default"
	}

	tracer, err := middleware.GetPulseTraceManager().GetTracer(projectID, "user-api")
	if err != nil {
		log.Printf("Error getting tracer for project %s: %v", projectID, err)
		writeErrorResponse(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	var user User
	if err := json.NewDecoder(r.Body).Decode(&user); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Add request attributes
	tracer.AddSpanAttributes(ctx,
		attribute.String("user.name", user.Name),
		attribute.String("user.email", user.Email),
		attribute.String("project.id", projectID),
	)

	// Create user in database
	createdUser, err := createUserInDB(ctx, user, tracer)
	if err != nil {
		tracer.RecordError(ctx, err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	// Add response attributes
	tracer.AddSpanAttributes(ctx,
		attribute.String("created.user_id", createdUser.ID),
		attribute.String("response.status", "created"),
	)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(createdUser)
}

// Update database functions to accept tracer parameter
func fetchUsersFromDB(ctx context.Context, tracer *pulse_otel.Tracer) ([]User, error) {
	return pulse_otel.WithSpanReturnTyped(tracer, ctx, "db.fetch_users", func(ctx context.Context) ([]User, error) {
		tracer.AddSpanAttributes(ctx,
			attribute.String("db.operation", "SELECT"),
			attribute.String("db.table", "users"),
		)

		// Simulate database latency
		time.Sleep(50 * time.Millisecond)

		users := []User{
			{ID: "1", Name: "John Doe", Email: "john@example.com"},
			{ID: "2", Name: "Jane Smith", Email: "jane@example.com"},
		}

		tracer.AddSpanAttribute(ctx, "db.rows_affected", strconv.Itoa(len(users)))
		return users, nil
	})
}

func createUserInDB(ctx context.Context, user User, tracer *pulse_otel.Tracer) (User, error) {
	return pulse_otel.WithSpanReturnTyped(tracer, ctx, "db.create_user", func(ctx context.Context) (User, error) {
		tracer.AddSpanAttributes(ctx,
			attribute.String("db.operation", "INSERT"),
			attribute.String("db.table", "users"),
			attribute.String("user.email", user.Email),
		)

		// Simulate database write latency
		time.Sleep(100 * time.Millisecond)

		user.ID = fmt.Sprintf("user_%d", time.Now().Unix())
		tracer.AddSpanAttribute(ctx, "user.id", user.ID)
		return user, nil
	})
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// Get project-specific tracer
	projectID := r.Header.Get("x-project-id")
	if projectID == "" {
		projectID = "default"
	}

	tracer, err := middleware.GetPulseTraceManager().GetTracer(projectID, "user-api")
	if err != nil {
		log.Printf("Error getting tracer for project %s: %v", projectID, err)
		writeErrorResponse(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	tracer.AddSpanAttribute(ctx, "handler.name", "health")

	response := map[string]interface{}{
		"status":    "healthy",
		"timestamp": time.Now().UTC(),
		"service":   "user-api",
	}

	writeSuccessResponse(w, response)
}

func writeSuccessResponse(w http.ResponseWriter, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(Response{
		Success: true,
		Data:    data,
	})
}

func writeErrorResponse(w http.ResponseWriter, message string, statusCode int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	json.NewEncoder(w).Encode(Response{
		Success: false,
		Error:   message,
	})
}

func myPostHandler(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	// Debug: Check if we have an active span
	span := trace.SpanFromContext(ctx)
	fmt.Printf("Handler: Active span found: %t, Recording: %t\n", span != nil, span.IsRecording())

	// Get project-specific tracer
	projectID := r.Header.Get("x-project-id")
	if projectID == "" {
		projectID = "default"
	}

	tracer, err := middleware.GetPulseTraceManager().GetTracer(projectID, "user-api")
	if err != nil {
		log.Printf("Error getting tracer for project %s: %v", projectID, err)
		writeErrorResponse(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	tracer.AddSpanAttribute(ctx, "handler.name", "createHandlerFunc")

	url := "http://myapp_2:8000/go_py_py"

	var reqBody struct {
		Name  string `json:"name"`
		Price string `json:"price"`
		ID    string `json:"id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&reqBody); err != nil {
		writeErrorResponse(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	newBody, err := json.Marshal(map[string]string{
		"name":  reqBody.Name,
		"price": reqBody.Price,
		"id":    reqBody.ID,
	})
	if err != nil {
		tracer.RecordError(ctx, err)
		writeErrorResponse(w, "Failed to marshal request body", http.StatusInternalServerError)
		return
	}

	// Simulate a POST request to the given URL using instrumented HTTP client

	// Create request with context to ensure trace propagation
	req, err := http.NewRequestWithContext(ctx, "POST", url, bytes.NewBuffer(newBody))
	if err != nil {
		tracer.RecordError(ctx, err)
		writeErrorResponse(w, "Failed to create request", http.StatusInternalServerError)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	fmt.Printf("Handler: Making HTTP request to %s\n", url)
	// Use instrumented HTTP client for automatic span creation and propagation
	resp, err := pulse_otel.GetInstrumentedHTTPClient().Do(req)
	fmt.Printf("Handler: HTTP request completed, status: %v, error: %v\n",
		func() string {
			if resp != nil {
				return fmt.Sprintf("%d", resp.StatusCode)
			} else {
				return "nil"
			}
		}(), err)
	if err != nil {
		tracer.RecordError(ctx, err)
		writeErrorResponse(w, "Failed to make request", http.StatusInternalServerError)
		return
	}
	defer resp.Body.Close()

	w.WriteHeader(resp.StatusCode)
	json.NewEncoder(w).Encode(Response{
		Success: true,
		Data:    fmt.Sprintf("Request made to %s with status %d", url, resp.StatusCode),
	})
}
