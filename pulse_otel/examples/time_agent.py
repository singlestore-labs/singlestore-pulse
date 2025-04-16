from dotenv import load_dotenv
import os
import datetime

from openai import OpenAI

from traceloop.sdk import Traceloop
from traceloop.sdk.decorators import agent, tool
from opentelemetry.sdk._logs import LoggingHandler

from pulse_otel import Pulse

import logging

handler = LoggingHandler()

# Use the handler with Python’s standard logging
logger = logging.getLogger("myapp")
logger.setLevel(logging.INFO)
logger.addHandler(handler)

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
	}
]


# Define a simple tool: a function to get the current time
@tool("toolB")
def get_current_time():
    print("**************")
    print("Fetching the current time...")
    print("**************")
    # Simulate some work
    logger.info("TEST LOGS")
    logger.debug("DEBUG LOGS")
    logger.critical("CRITICAL LOGS")
    return datetime.datetime.now().strftime("%H:%M:%S")

# Define a new tool: a function to get the current date
@tool("toolA")
def get_current_date():
    return datetime.datetime.now().strftime("%Y-%m-%d")


# Simple agent function to process user input and decide on tool use
@agent("Myagent")
def agent_run(prompt):
    messages = [{"role": "user", "content": prompt}]
    
    configs = get_configs()
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
        extra_headers={"X-Session-ID" : "session_id"},
    )
    
    # Check if the response involves a tool call
    if response.choices[0].message.tool_calls:
        for tool_call in response.choices[0].message.tool_calls:
            if tool_call.function.name == "get_current_time":
                time_result = get_current_time()
                return f"Current time: {time_result}"
    else:
        return response.choices[0].message.content

#Define a simple tool: a function to get the current time with a funny argument
@tool("FFFF")
def get_funny_current_time(funny_phrase):
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    return f"{funny_phrase}! The time is {current_time}"

# Define available tools with a parameter for the funny phrase
specialTool = [
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


def main():
   
   #create a Pulse instance
    _ = Pulse(
        write_to_file=True,
    )

    user_prompt = "What time is it?"
    result = agent_run(user_prompt)
    print(result)

if __name__ == "__main__":
    main()
