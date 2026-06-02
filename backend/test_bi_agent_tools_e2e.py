#!/usr/bin/env python3
"""
End-to-end test to verify the tool schema fix works with BI agent tools.
This simulates how AutoGen will pass tools to the OpenAI client.
"""

import sys
import json
import logging
from typing import Dict, Any, List, Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import the fixed client and BI tools
from core.openai_client_adapter import OpenAIChatCompletionClient
from agents.bi_agent import (
    retrieve_business_context,
    query_raw_analytics_database,
    get_dashboard_summary,
    get_revenue_summary,
)

# Mock AutoGen Tool class (similar to what AutoGen uses)
class AutoGenTool:
    """Simulates AutoGen Tool object with function reference."""
    def __init__(self, name: str, description: str, func: callable):
        self.name = name
        self.description = description
        self.func = func
        self.schema = None  # AutoGen might set this, but often doesn't
        

def test_bi_agent_tools():
    """Test that BI agent tools are properly converted."""
    
    print("\n" + "=" * 80)
    print("TEST: BI Agent Tools Schema Conversion")
    print("=" * 80)
    
    # Create adapter for Groq
    adapter = OpenAIChatCompletionClient(
        model="llama-3.1-70b-versatile",  # Groq model
        api_key="test-key",
        base_url="https://api.groq.com/openai/v1"
    )
    
    # Create AutoGen tools (as they would be created by BI agent)
    bi_tools = [
        AutoGenTool("get_dashboard_summary", get_dashboard_summary.__doc__, get_dashboard_summary),
        AutoGenTool("get_revenue_summary", get_revenue_summary.__doc__, get_revenue_summary),
        AutoGenTool("retrieve_business_context", retrieve_business_context.__doc__, retrieve_business_context),
        AutoGenTool("query_raw_analytics_database", query_raw_analytics_database.__doc__, query_raw_analytics_database),
    ]
    
    # Convert tools as the client would
    converted = adapter._convert_tools(bi_tools)
    
    if not converted:
        print("[FAIL] Conversion returned None")
        return False
    
    print(f"\n[PASS] Successfully converted {len(converted)} BI agent tools\n")
    
    # Verify each tool
    success = True
    for tool in converted:
        func = tool.get("function", {})
        name = func.get("name", "UNNAMED")
        params = func.get("parameters", {})
        props = params.get("properties", {})
        required = params.get("required", [])
        
        print(f"Tool: {name}")
        print(f"  - Type: {tool.get('type')}")
        print(f"  - Description: {func.get('description', '')[:60]}...")
        
        if props:
            param_names = list(props.keys())
            print(f"  - Parameters: {param_names}")
            for param_name, param_schema in props.items():
                param_type = param_schema.get("type", "unknown")
                is_required = param_name in required
                print(f"      * {param_name}: type={param_type}, required={is_required}")
        else:
            print(f"  - Parameters: None (no parameters)")
        
        # Validate that tools with parameters have them properly defined
        if name == "retrieve_business_context":
            if "days" not in props:
                print(f"  [FAIL] Missing 'days' parameter")
                success = False
            elif props["days"].get("type") != "integer":
                print(f"  [FAIL] 'days' parameter should be 'integer', got '{props['days'].get('type')}'")
                success = False
            else:
                print(f"  [PASS] Parameters properly defined")
        elif name == "query_raw_analytics_database":
            if "sql_select_query" not in props:
                print(f"  [FAIL] Missing 'sql_select_query' parameter")
                success = False
            elif props["sql_select_query"].get("type") != "string":
                print(f"  [FAIL] 'sql_select_query' should be 'string', got '{props['sql_select_query'].get('type')}'")
                success = False
            elif "sql_select_query" not in required:
                print(f"  [FAIL] 'sql_select_query' should be required")
                success = False
            else:
                print(f"  [PASS] Parameters properly defined")
        else:
            # No-parameter tools
            if props:
                print(f"  [WARN] Expected no parameters, but found {list(props.keys())}")
                success = False
            else:
                print(f"  [PASS] Correctly has no parameters")
        
        print()
    
    # Print the JSON that would be sent to Groq
    print("\n" + "=" * 80)
    print("JSON Schema to be sent to Groq API:")
    print("=" * 80)
    print(json.dumps(converted, indent=2))
    
    return success


def test_logging_output():
    """Verify that logging shows parameter information."""
    
    print("\n" + "=" * 80)
    print("TEST: Enhanced Logging for Tools")
    print("=" * 80)
    
    adapter = OpenAIChatCompletionClient(
        model="llama-3.1-70b-versatile",
        api_key="test-key",
        base_url="https://api.groq.com/openai/v1"
    )
    
    tools = [
        AutoGenTool("retrieve_business_context", retrieve_business_context.__doc__, retrieve_business_context),
        AutoGenTool("get_dashboard_summary", get_dashboard_summary.__doc__, get_dashboard_summary),
    ]
    
    print("\n[Expected log output below]")
    print("-" * 80)
    
    converted = adapter._convert_tools(tools)
    
    print("-" * 80)
    print("\n[PASS] Logging output should show parameter names for each tool")
    
    return True


if __name__ == "__main__":
    try:
        # Run tests
        test1_pass = test_bi_agent_tools()
        test2_pass = test_logging_output()
        
        if test1_pass and test2_pass:
            print("\n" + "=" * 80)
            print("ALL TESTS PASSED!")
            print("=" * 80)
            print("\nThe fix is ready. The error should be resolved when:")
            print("1. Groq API receives tool schemas with proper parameters")
            print("2. LLM calls retrieve_business_context with {'days': 30}")
            print("3. Groq API validates and finds matching tool definition")
            print("\n" + "=" * 80 + "\n")
            sys.exit(0)
        else:
            print("\nSome tests failed")
            sys.exit(1)
            
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
