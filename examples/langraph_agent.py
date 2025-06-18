"""
LangGraph Research Agent Example
A sample agent that can search the web and analyze information using LangGraph framework.
"""

import os
import logging
from typing import TypedDict, Annotated
from dotenv import load_dotenv

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI  # You can replace this with your LLM client
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from pulse_otel import Pulse, pulse_tool, pulse_agent


# Load environment variables from .env file
load_dotenv()  

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# =============================================================================
# Configuration - Replace these with your LLM settings
# =============================================================================

def get_configs():
    """
    Reads and returns configurations from the .env file.
    """
    configs = {
        "perma_auth_token": os.getenv("perma_auth_token"),
        "api_uri": os.getenv("api_uri"),
        "model_name": os.getenv("model_name"),
    }
    return configs


# LLM Configuration - Customize these for your setup
LLM_CONFIG = {
    "api_key": os.getenv("perma_auth_token"),  # Replace with your API key
    "base_url": os.getenv("api_uri"),  # Replace with your LLM URL
    "model": os.getenv("model_name"),  # Replace with your model name
    "temperature": 0.1,
    "max_tokens": 1000
}

# =============================================================================
# Tools Definition
# =============================================================================

@pulse_tool
def web_search(query: str) -> str:
    """Search the web for information about a given query."""
    # This is a mock implementation - replace with actual search API
    # You could use DuckDuckGo, Google Custom Search, or other search APIs
    try:
        # Mock search results for demonstration
        mock_results = {
            "python": "Python is a high-level programming language known for its simplicity and readability.",
            "ai": "Artificial Intelligence (AI) refers to computer systems that can perform tasks typically requiring human intelligence.",
            "climate": "Climate change refers to long-term shifts in global temperatures and weather patterns."
        }
        
        # Simple keyword matching for demo
        for keyword, result in mock_results.items():
            if keyword.lower() in query.lower():
                return f"Search results for '{query}': {result}"
        
        return f"Search results for '{query}': No specific information found, but here are some general insights about the topic."
    
    except Exception as e:
        return f"Error performing search: {str(e)}"

@pulse_tool
def calculator(expression: str) -> str:
    """Evaluate a mathematical expression safely."""
    try:
        # Only allow basic math operations for safety
        allowed_chars = set('0123456789+-*/.() ')
        if not all(c in allowed_chars for c in expression):
            return "Error: Only basic math operations are allowed"
        
        result = eval(expression)
        return f"Result: {result}"
    except Exception as e:
        return f"Error calculating: {str(e)}"

@pulse_tool
def summarize_text(text: str, max_sentences: int = 3) -> str:
    """Summarize a given text to a specified number of sentences."""
    sentences = text.split('.')
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) <= max_sentences:
        return text
    
    # Simple summarization - take first and last sentences, plus one from middle
    summary_sentences = []
    summary_sentences.append(sentences[0])
    
    if max_sentences > 2 and len(sentences) > 2:
        middle_idx = len(sentences) // 2
        summary_sentences.append(sentences[middle_idx])
    
    if max_sentences > 1:
        summary_sentences.append(sentences[-1])
    
    return '. '.join(summary_sentences[:max_sentences]) + '.'

# =============================================================================
# State Definition
# =============================================================================

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    next_action: str
    research_context: str

# =============================================================================
# LLM Setup
# =============================================================================

def create_llm():
    """Create and return the LLM instance with your configuration."""
    # Replace this with your LLM client initialization
    # Example for OpenAI-compatible APIs:
    return ChatOpenAI(
        api_key=LLM_CONFIG["api_key"],
        base_url=LLM_CONFIG["base_url"],
        model=LLM_CONFIG["model"],
        temperature=LLM_CONFIG["temperature"],
        max_tokens=LLM_CONFIG["max_tokens"]
    )

# Initialize LLM and tools
llm = create_llm()
tools = [web_search, calculator, summarize_text]
llm_with_tools = llm.bind_tools(tools)

# =============================================================================
# Agent Nodes
# =============================================================================

def agent_node(state: AgentState):
    """Main agent reasoning node."""
    system_message = SystemMessage(content="""
    You are a helpful research assistant with access to tools. Your job is to help users with their questions by:
    
    1. Understanding what they're asking for
    2. Using appropriate tools when needed (web_search, calculator, summarize_text)
    3. Providing comprehensive and helpful answers
    
    Available tools:
    - web_search: Search for information on the web
    - calculator: Perform mathematical calculations
    - summarize_text: Summarize long text passages
    
    Always think step by step and use tools when they would be helpful.
    """)
    
    messages = [system_message] + state["messages"]
    response = llm_with_tools.invoke(messages)
    
    return {
        "messages": [response],
        "next_action": "tools" if response.tool_calls else "end"
    }

def should_continue(state: AgentState):
    """Determine whether to continue with tools or end."""
    return state["next_action"]

# Create tool node
tool_node = ToolNode(tools)

def tool_handler(state: AgentState):
    """Handle tool execution and continue the conversation."""
    # Execute tools
    result = tool_node.invoke(state)
    
    # After tool execution, go back to agent for reasoning
    result["next_action"] = "agent"
    return result

# =============================================================================
# Graph Construction
# =============================================================================

def create_research_agent():
    """Create and return the LangGraph research agent."""
    
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_handler)
    
    # Add edges
    workflow.add_edge(START, "agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", "end": END}
    )
    workflow.add_edge("tools", "agent")
    
    # Compile the graph
    app = workflow.compile()
    return app

# =============================================================================
# Usage Example
# =============================================================================
@pulse_agent("MyCoolAgent")
def run_agent_example():
    """Example of how to use the agent."""
    
    print("Creating LangGraph Research Agent...")
    agent = create_research_agent()
    
    # Example conversations
    examples = [
        "What is artificial intelligence and how is it being used today?",
        # "Calculate the compound interest for $1000 at 5% annual rate for 3 years",
        # "Search for information about climate change and summarize the key points"
    ]
    
    for i, question in enumerate(examples, 1):
        print(f"\n{'='*50}")
        print(f"Example {i}: {question}")
        print('='*50)
        
        # Run the agent
        initial_state = {
            "messages": [HumanMessage(content=question)],
            "next_action": "agent",
            "research_context": ""
        }
        
        try:
            result = agent.invoke(initial_state)
            
            # Print the conversation
            for message in result["messages"]:
                if isinstance(message, HumanMessage):
                    print(f"Human: {message.content}")
                elif isinstance(message, AIMessage):
                    print(f"Agent: {message.content}")
                    if hasattr(message, 'tool_calls') and message.tool_calls:
                        print(f"Tools used: {[tc['name'] for tc in message.tool_calls]}")
        
        except Exception as e:
            print(f"Error running example: {e}")

# =============================================================================
# Interactive Mode
# =============================================================================

def run_interactive_agent():
    """Run the agent in interactive mode."""
    
    print("🤖 LangGraph Research Agent")
    print("Type 'quit' to exit, 'help' for available commands")
    print("-" * 40)
    
    agent = create_research_agent()
    
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye!")
                break
            
            if user_input.lower() == 'help':
                print("\nAvailable commands:")
                print("- Ask any question and I'll help research it")
                print("- Use 'calculate [expression]' for math")
                print("- Use 'search [query]' for web search")
                print("- Use 'summarize [text]' to summarize text")
                continue
            
            if not user_input:
                continue
            
            # Run the agent
            initial_state = {
                "messages": [HumanMessage(content=user_input)],
                "next_action": "agent",
                "research_context": ""
            }
            
            result = agent.invoke(initial_state)
            
            # Get the last AI message
            ai_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
            if ai_messages:
                print(f"\nAgent: {ai_messages[-1].content}")
        
        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

# =============================================================================
# Main Execution
# =============================================================================

if __name__ == "__main__":
    print("LangGraph Research Agent")
    print("========================")
    print("\n⚠️  SETUP REQUIRED:")
    print("1. Install dependencies: pip install langchain langgraph langchain-openai")
    print("2. Update LLM_CONFIG with your API key, URL, and model name")
    print("3. Replace mock web_search with actual search API if needed")
   
    # Initialize Pulse for OpenTelemetry
    # This will send traces to the OTel collector at the specified endpoint
    _ = Pulse(
        otel_collector_endpoint="http://localhost:4317",
    )

    run_agent_example()
    # choice = input("\nRun in (i)nteractive mode or (e)xamples mode? [i/e]: ").strip().lower()
    
    # if choice == 'e':
    #     run_agent_example()
    # else:
    #     run_interactive_agent()
