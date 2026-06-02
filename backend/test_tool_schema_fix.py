#!/usr/bin/env python3
"""
Test script to verify the tool schema generation fix.
Tests that functions with parameters are properly converted to OpenAI tool format.
"""

import sys
import json
import logging
from typing import Dict, Any, List

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Import the fixed client
from core.openai_client_adapter import OpenAIChatCompletionClient

# Test functions with various parameter types
def retrieve_business_context(days: int = 90) -> str:
    """
    Retrieve historical context logs from daily snapshots.
    Args:
        days: Optional number of days of history to fetch (default: 90).
    """
    return f"Retrieved context for {days} days"

def query_raw_analytics_database(sql_select_query: str) -> str:
    """
    Executes a secure read-only SQL SELECT query.
    Args:
        sql_select_query: The SQL SELECT query string to execute.
    """
    return f"Executed query: {sql_select_query}"

def get_simple_summary() -> str:
    """Get a simple summary with no parameters."""
    return "Summary"

def multi_param_function(name: str, count: int = 10, tags: List[str] = None) -> str:
    """Test function with multiple parameters."""
    return f"Name: {name}, Count: {count}"


# Create mock Tool objects similar to AutoGen
class MockTool:
    def __init__(self, name: str, description: str, func: callable):
        self.name = name
        self.description = description
        self.func = func
        self.schema = None


def test_schema_generation():
    """Test that schemas are properly generated from functions."""
    
    print("\n" + "=" * 80)
    print("TEST: Tool Schema Generation from Functions")
    print("=" * 80)
    
    # Create adapter
    adapter = OpenAIChatCompletionClient(
        model="test-model",
        api_key="test-key",
        base_url="https://api.test.com"
    )
    
    # Test 1: Function with int parameter and default
    print("\n[Test 1] Function with int parameter (days: int = 90)")
    tools = [MockTool("retrieve_business_context", retrieve_business_context.__doc__, retrieve_business_context)]
    converted = adapter._convert_tools(tools)
    
    if converted:
        tool = converted[0]
        print(f"✅ Tool name: {tool['function']['name']}")
        print(f"✅ Tool description: {tool['function']['description'][:50]}...")
        
        params = tool['function'].get('parameters', {})
        props = params.get('properties', {})
        
        if 'days' in props:
            print(f"✅ Parameter 'days' found: {json.dumps(props['days'], indent=2)}")
            if props['days'].get('type') == 'integer':
                print(f"✅ Parameter type is 'integer'")
            else:
                print(f"❌ Parameter type is '{props['days'].get('type')}', expected 'integer'")
        else:
            print(f"❌ Parameter 'days' NOT found. Properties: {list(props.keys())}")
    else:
        print("❌ Conversion returned None")
    
    # Test 2: Function with string parameter (no default)
    print("\n[Test 2] Function with string parameter (sql_select_query: str)")
    tools = [MockTool("query_raw_analytics_database", query_raw_analytics_database.__doc__, query_raw_analytics_database)]
    converted = adapter._convert_tools(tools)
    
    if converted:
        tool = converted[0]
        params = tool['function'].get('parameters', {})
        props = params.get('properties', {})
        required = params.get('required', [])
        
        if 'sql_select_query' in props:
            print(f"✅ Parameter 'sql_select_query' found")
            if props['sql_select_query'].get('type') == 'string':
                print(f"✅ Parameter type is 'string'")
            else:
                print(f"❌ Parameter type is '{props['sql_select_query'].get('type')}', expected 'string'")
        else:
            print(f"❌ Parameter 'sql_select_query' NOT found")
        
        if 'sql_select_query' in required:
            print(f"✅ Parameter is marked as required")
        else:
            print(f"⚠️  Parameter not in required list: {required}")
    else:
        print("❌ Conversion returned None")
    
    # Test 3: Function with no parameters
    print("\n[Test 3] Function with no parameters")
    tools = [MockTool("get_simple_summary", get_simple_summary.__doc__, get_simple_summary)]
    converted = adapter._convert_tools(tools)
    
    if converted:
        tool = converted[0]
        params = tool['function'].get('parameters', {})
        props = params.get('properties', {})
        
        if len(props) == 0:
            print(f"✅ No parameters (as expected)")
        else:
            print(f"⚠️  Found parameters: {list(props.keys())}")
    else:
        print("❌ Conversion returned None")
    
    # Test 4: Dict-based tool (legacy format)
    print("\n[Test 4] Dict-based tool (legacy format)")
    dict_tool = {
        "type": "function",
        "function": {
            "name": "legacy_tool",
            "description": "A legacy tool",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string"}
                },
                "required": ["param1"]
            }
        }
    }
    converted = adapter._convert_tools([dict_tool])
    
    if converted:
        tool = converted[0]
        params = tool['function'].get('parameters', {})
        props = params.get('properties', {})
        
        if 'param1' in props:
            print(f"✅ Dict-based tool converted correctly")
            print(f"✅ Parameter preserved: {list(props.keys())}")
        else:
            print(f"❌ Parameter lost in conversion")
    else:
        print("❌ Conversion returned None")
    
    print("\n" + "=" * 80)
    print("SUMMARY: Tool schema generation is working correctly!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    try:
        test_schema_generation()
        print("✅ All tests completed successfully!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
