from dotenv import load_dotenv
import os
import datetime
import json

from openai import OpenAI

from opentelemetry.sdk._logs import LoggingHandler

from pulse_otel import Pulse, pulse_agent, pulse_tool

import logging
from tenacity import retry, stop_after_attempt, wait_fixed

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
    funny_timestamp =  f"{funny_phrase}! The time is {current_time}"
    return get_funny_timestamp_phrase(funny_timestamp)

def get_funny_timestamp_phrase(funny_timestamp):
    logger.info("TEST LOGS get_funny_timestamp_phrase")
    logger.debug("DEBUG LOGS get_funny_timestamp_phrase")
    logger.critical("CRITICAL LOGS get_funny_timestamp_phrase")
    return f"Here is a funny timestamp: {funny_timestamp}"
    
# Simple agent function to process user input and decide on tool use
@retry(stop=stop_after_attempt(3), wait=wait_fixed(2))
@pulse_agent(name="MyAgentName")
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
                result = get_current_time()
            elif tool_call.function.name == "get_current_date":
                result = get_current_date()
            elif tool_call.function.name == "get_funny_current_time":
                arguments = json.loads(tool_call.function.arguments)
                funny_phrase = arguments.get("funny_phrase", "Just kidding")
                result = get_funny_current_time(funny_phrase)
            
            return result

    else:
        return response.choices[0].message.content


def main():
   
   #create a Pulse instance
    # _ = Pulse(
    #     write_to_file=True,
    # )

    # write to otel collector 
    _ = Pulse(
        otel_collector_endpoint="http://localhost:4317",
    )


    user_prompt = "What time is it?"
    result = agent_run(user_prompt)
    print(result)

    print("==========================")
    user_prompt = "What date is it?"
    result = agent_run(user_prompt)
    print(result)
    print("==========================")
    user_prompt = "What time is it? Make it funny!"
    result = agent_run(user_prompt)
    print(result)
    print("==========================")

if __name__ == "__main__":
    main()
