from dotenv import load_dotenv
import os
import datetime
import json
from fastapi import FastAPI, HTTPException
from fastapi import Request
import uvicorn
from pydantic import BaseModel

from openai import OpenAI
import requests
from fastapi.responses import JSONResponse
from opentelemetry.sdk._logs import LoggingHandler

from pulse_otel import Pulse, pulse_agent, pulse_tool

import logging
from tenacity import retry, stop_after_attempt, wait_fixed

app = FastAPI(title="My time agent", description="A FastAPI app that uses Pulse OTel for tracing and logging", version="1.0.0")

# Define a Pydantic model for the request body
class AgentRunRequest(BaseModel):
    prompt: str
    session_id: str = None  # Optional session ID

class Item(BaseModel):
    id: int
    name: str
    price: float

logger = logging.getLogger("myapp")
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

# Define available tools
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time in HH:MM:SS format",
            "parameters": {}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_date",
            "description": "Get the current date in YYYY-MM-DD format",
            "parameters": {}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_funny_current_time",
            "description": "Get the current time in HH:MM:SS format with a funny phrase",
            "parameters": {
                "type": "object",
                "properties": {
                    "funny_phrase": {
                        "type": "string",
                        "description": "A humorous phrase to include with the time"
                    }
                },
                "required": ["funny_phrase"]
            }
        }
    }
]

# Define a simple tool: a function to get the current time
@pulse_tool()
def get_current_time():
    logger.info("TEST LOGS get_current_time")
    logger.debug("DEBUG LOGS get_current_time")
    logger.critical("CRITICAL LOGS get_current_time")
    return datetime.datetime.now().strftime("%H:%M:%S")

# Define a new tool: a function to get the current date
@pulse_tool(name="ToolA")
def get_current_date():
    logger.critical("CRITICAL LOGS of get_current_date")
    logger.debug("DEBUG LOGS of get_current_date")
    logger.info("INFO LOGS of get_current_date")
    return datetime.datetime.now().strftime("%Y-%m-%d")

# Define a new tool: a function to get the current time with a funny phrase
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
@pulse_tool("toolB")
def get_funny_current_time(funny_phrase):
    logger.critical("CRITICAL LOGS of get_funny_current_time")
    logger.debug("DEBUG LOGS of get_funny_current_time")
    logger.info("INFO LOGS of get_funny_current_time")

    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    funny_timestamp = f"{funny_phrase}! The time is {current_time}"
    return get_funny_timestamp_phrase(funny_timestamp)

def get_funny_timestamp_phrase(funny_timestamp):
    logger.info("TEST LOGS get_funny_timestamp_phrase")
    logger.debug("DEBUG LOGS get_funny_timestamp_phrase")
    logger.critical("CRITICAL LOGS get_funny_timestamp_phrase")
    return f"Here is a funny timestamp: {funny_timestamp}"

# Simple agent function to process user input and decide on tool use
@app.post("/agent/run")
@pulse_agent("MyDockerTimeAgent")
def agent_run(request: Request, body: AgentRunRequest):  # Changed back to sync function
    try:
        prompt = body.prompt
        messages = [{"role": "user", "content": prompt}]
        
        configs = get_configs()
        
        # Validate required configs
        if not configs["perma_auth_token"] or not configs["api_uri"] or not configs["model_name"]:
            raise HTTPException(status_code=500, detail="Missing required configuration")
        
        client = OpenAI(
            api_key=configs["perma_auth_token"],
            base_url=configs["api_uri"],
        )
        
        # Make a chat completion request with tools
        response = client.chat.completions.create(
            model=configs["model_name"],
            messages=messages,
            tools=tools,
            tool_choice="auto",
            extra_headers={"X-Session-ID": "session_id"},
        )
        
        # Check if the response involves a tool call
        if response.choices[0].message.tool_calls:
            results = []
            for tool_call in response.choices[0].message.tool_calls:
                if tool_call.function.name == "get_current_time":
                    result = get_current_time()
                    results.append(result)
                elif tool_call.function.name == "get_current_date":
                    result = get_current_date()
                    results.append(result)
                elif tool_call.function.name == "get_funny_current_time":
                    arguments = json.loads(tool_call.function.arguments)
                    funny_phrase = arguments.get("funny_phrase", "Just kidding")
                    result = get_funny_current_time(funny_phrase)
                    results.append(result)
            
            # Return the first result (or combine multiple results if needed)
            return {"response": results[0] if len(results) == 1 else results}
        else:
            return {"response": response.choices[0].message.content}
            
    except Exception as e:
        logger.error(f"Error in agent_run: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def http_req(body: Item):
    """
    Makes an HTTP request to the myapp_2 service at the /cftocf endpoint.
    """
    url = "http://myapp_2:8000/getdata"
    
    data = {
        "name": body.name,
        "price": body.price,
        "id": body.id
    }
    
    # Set headers
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Make the POST request with timeout
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        # Check if the request was successful
        response.raise_for_status()
        
        # Log successful response
        logger.info(f"HTTP request to myapp_2 successful. Status Code: {response.status_code}")
        
        return {
            "status": "success",
            "status_code": response.status_code,
            "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        }
        
    except requests.exceptions.Timeout:
        logger.error("HTTP request to myapp_2 timed out")
        raise HTTPException(status_code=504, detail="Request to myapp_2 service timed out")
    
    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to myapp_2 service")
        raise HTTPException(status_code=502, detail="Failed to connect to myapp_2 service")
    
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred when calling myapp_2: {e}")
        raise HTTPException(status_code=response.status_code, detail=f"myapp_2 service error: {response.text}")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error occurred when calling myapp_2: {e}")
        raise HTTPException(status_code=500, detail="Failed to make request to myapp_2 service")

# Define a health check endpoint
@app.get("/health")
def health_check():
    return {"status": "ok"}

# Define the root endpoint for FastAPI
@app.get("/")
def root():
    return {"message": "Welcome to the Pulse OTel FastAPI agent!"}

# @pulse_agent("MyCloudFunctionToCloudFunctionAgent")
@app.post("/cloud_function_to_cloud_function")
@pulse_agent("MyCloudFunctionToCloudFunctionAgent")
def agent_run_2(request: Request, body: Item): 
    try:
        return http_req(body)
    except Exception as e:
        logger.error(f"Error in cloud_function_to_cloud_function: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def http_req_go_service(body: Item):
    """
    Makes an HTTP request to the Go webapp service at the /api/process endpoint.
    """
    url = "http://go-webapp:8000/api/process"
    
    data = {
        "id": body.id,
        "name": body.name,
        "price": body.price
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    try:
        # Make the POST request with timeout
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        # Check if the request was successful
        response.raise_for_status()
        
        # Log successful response
        logger.info(f"HTTP request to go-webapp successful. Status Code: {response.status_code}")
        
        return {
            "status": "success",
            "status_code": response.status_code,
            "response": response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
        }
        
    except requests.exceptions.Timeout:
        logger.error("HTTP request to go-webapp timed out")
        raise HTTPException(status_code=504, detail="Request to go-webapp service timed out")
    
    except requests.exceptions.ConnectionError:
        logger.error("Failed to connect to go-webapp service")
        raise HTTPException(status_code=502, detail="Failed to connect to go-webapp service")
    
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred when calling go-webapp: {e}")
        raise HTTPException(status_code=response.status_code, detail=f"go-webapp service error: {response.text}")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error occurred when calling go-webapp: {e}")
        raise HTTPException(status_code=500, detail="Failed to make request to go-webapp service")

@pulse_agent("MyGoServiceAgent")
@app.post("/call-go-service")
def call_go_service(request: Request, body: Item):
    """
    Endpoint that calls the Go webapp service
    """
    try:
        return http_req_go_service(body)
    except Exception as e:
        logger.error(f"Error in call-go-service: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.post("/go_py_py")
def cftocf_endpoint(request: Request, body: Item):
    """
    This is the target endpoint that myapp will call.
    It processes the item and returns a response.
    """
    try:
        # Process the item (you can add your business logic here)
        processed_data = {
            "id": body.id,
            "name": body.name,
            "price": body.price
        }
        
        logger.info(f"Successfully processed item {body.id}")
        
        # Call the http_req function to make an HTTP request to another service
        return {
            "status": "success",
            "data": processed_data,
            "message": "Item processed successfully"
        }
        
    except Exception as e:
        logger.error(f"Error in cftocf endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

def main():
    # write to otel collector 
    _ = Pulse(
        otel_collector_endpoint="http://otel-collector:4317",
    )

    # Create a FastAPI app
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == "__main__":
    main()
