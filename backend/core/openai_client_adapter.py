"""OpenAI ChatCompletionClient adapter for AutoGen compatibility."""

import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI
from core.config import get_settings

from autogen_core.models import (
    ChatCompletionClient,
    CreateResult,
    ModelCapabilities,
    ModelInfo,
    RequestUsage,
)

logger = logging.getLogger(__name__)

UNSUPPORTED_PARAMS = {
    "model_info",
    "cancellation_token",
    "json_output",
    "extra_body",
    "headers",
    "query_params",
    "timeout",
}


class OpenAIChatCompletionClient(ChatCompletionClient):
    """OpenAI ChatCompletionClient for AutoGen."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        model_info: Optional[ModelInfo] = None,
        timeout: float = 30.0,
    ):
        """Initialize the client."""
        self.model = model
        self._model_info = model_info
        self._client = OpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._actual_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    @property
    def model_info(self) -> ModelInfo:
        """Get model info."""
        if self._model_info:
            info = dict(self._model_info)
            if "vision" not in info:
                info["vision"] = False
            if "function_calling" not in info:
                info["function_calling"] = True
            if "json_output" not in info:
                info["json_output"] = True
            if "family" not in info:
                model_lower = str(info.get("model_id", self.model)).lower()
                if "gemini-2.0" in model_lower:
                    info["family"] = "gemini-2.0-flash"
                elif "gemini-1.5-flash" in model_lower:
                    info["family"] = "gemini-1.5-flash"
                elif "gemini-1.5-pro" in model_lower:
                    info["family"] = "gemini-1.5-pro"
                elif "llama-3.3" in model_lower:
                    info["family"] = "llama-3.3-70b"
                elif "qwen" in model_lower:
                    info["family"] = "qwen"
                else:
                    info["family"] = "unknown"
            if "structured_output" not in info:
                info["structured_output"] = False
            return info  # type: ignore

        family_str = "unknown"
        model_lower = self.model.lower()
        if "gemini-2.0" in model_lower:
            family_str = "gemini-2.0-flash"
        elif "gemini-1.5-flash" in model_lower:
            family_str = "gemini-1.5-flash"
        elif "gemini-1.5-pro" in model_lower:
            family_str = "gemini-1.5-pro"
        elif "llama-3.3" in model_lower or "llama3.3" in model_lower:
            family_str = "llama-3.3-70b"
        elif "llama-3.1-8b" in model_lower:
            family_str = "llama-3.3-8b"
        elif "llama-3.1-70b" in model_lower:
            family_str = "llama-3.3-70b"
        elif "qwen" in model_lower:
            family_str = "qwen"

        return ModelInfo(
            vision=False,
            function_calling=True,
            json_output=True,
            family=family_str,
            structured_output=False,
        )

    @property
    def capabilities(self) -> ModelCapabilities:
        """Get model capabilities."""
        return ModelCapabilities(
            vision=False,
            function_calling=True,
            vision_detail="low",
        )

    def _convert_messages(self, messages: List[Any]) -> List[Dict[str, Any]]:
        """Convert AutoGen message format to OpenAI format using official to_oai_type when possible."""
        import uuid
        result = []
        for msg in messages:
            if isinstance(msg, dict):
                result.append(msg)
            else:
                try:
                    from autogen_ext.models.openai._openai_client import to_oai_type
                    converted = to_oai_type(
                        msg,
                        prepend_name=False,
                        model=self.model,
                        model_family=self.model_info.get("family", "unknown"),
                    )
                    # Convert to list of dicts
                    for item in converted:
                        if isinstance(item, dict):
                            result.append(item)
                        elif hasattr(item, "model_dump"):
                            result.append(item.model_dump())
                        else:
                            result.append(dict(item))
                except (ImportError, Exception) as e:
                    logger.warning(f"Failed to use official to_oai_type: {e}. Falling back.")
                    # Normalise role name from AutoGen message
                    role = getattr(msg, "role", getattr(msg, "source", "user"))
                    role_str = "user"
                    role_lower = str(role).lower()
                    if "assistant" in role_lower:
                        role_str = "assistant"
                    elif "system" in role_lower:
                        role_str = "system"
                    elif "tool" in role_lower or "function" in role_lower:
                        role_str = "tool"
                    
                    content = getattr(msg, "content", None)
                    
                    # Case 1: Assistant message requesting tool calls
                    if role_str == "assistant" and isinstance(content, list):
                        tool_calls = []
                        for item in content:
                            if hasattr(item, "name") and hasattr(item, "arguments"):
                                tool_calls.append({
                                    "id": getattr(item, "id", None) or f"call_{uuid.uuid4().hex[:8]}",
                                    "type": "function",
                                    "function": {
                                        "name": item.name,
                                        "arguments": item.arguments
                                    }
                                })
                        
                        msg_dict = {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": tool_calls
                        }
                        result.append(msg_dict)
                        
                    # Case 2: Tool execution result message
                    elif isinstance(content, list) and len(content) > 0 and hasattr(content[0], "call_id"):
                        for item in content:
                            result.append({
                                "role": "tool",
                                "tool_call_id": getattr(item, "call_id", ""),
                                "content": getattr(item, "content", "")
                            })
                            
                    # Case 3: Standard User / System / Assistant text message
                    else:
                        msg_dict = {
                            "role": role_str,
                            "content": str(content) if content is not None else None
                        }
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                            msg_dict["tool_calls"] = msg.tool_calls
                        result.append(msg_dict)
        return result

    def _filter_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out unsupported parameters before passing to OpenAI API."""
        return {k: v for k, v in kwargs.items() if k not in UNSUPPORTED_PARAMS}

    def _generate_schema_from_function(self, func: Any) -> Dict[str, Any]:
        """Generate JSON schema from a Python function's signature."""
        import inspect
        try:
            sig = inspect.signature(func)
            parameters = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue
                
                param_schema = {"type": "string"}  # Default type
                
                # Infer type from annotation
                if param.annotation != inspect.Parameter.empty:
                    annotation = param.annotation
                    if annotation == int:
                        param_schema["type"] = "integer"
                    elif annotation == float:
                        param_schema["type"] = "number"
                    elif annotation == bool:
                        param_schema["type"] = "boolean"
                    elif annotation in (list, List):
                        param_schema["type"] = "array"
                    elif annotation in (dict, Dict):
                        param_schema["type"] = "object"
                    else:
                        param_schema["type"] = "string"
                
                # Add parameter description if available
                if param.annotation != inspect.Parameter.empty:
                    param_schema["description"] = f"Parameter of type {param.annotation.__name__ if hasattr(param.annotation, '__name__') else str(param.annotation)}"
                
                # Check if parameter has a default
                if param.default == inspect.Parameter.empty:
                    required.append(param_name)
                else:
                    param_schema["description"] = f"Optional parameter (default: {param.default})"
                
                parameters[param_name] = param_schema
            
            schema = {
                "type": "object",
                "properties": parameters,
                "required": required
            }
            return schema
        except Exception as e:
            logger.debug(f"Failed to generate schema from function: {e}")
            return {"type": "object", "properties": {}}

    def _convert_tools(
        self, tools: Optional[List[Any]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Convert AutoGen tool format to OpenAI format with Gemini-specific schema conversions."""
        if not tools:
            return None

        result = []
        for i, tool in enumerate(tools):
            logger.debug(f"Processing tool {i}: {type(tool).__name__}")
            if isinstance(tool, dict):
                name = tool.get("name") or tool.get("function", {}).get("name") or "unknown_function"
                desc = tool.get("description") or tool.get("function", {}).get("description") or ""
                params = tool.get("parameters") or tool.get("function", {}).get("parameters") or {"type": "object", "properties": {}}
                strict = tool.get("strict") if tool.get("strict") is not None else tool.get("function", {}).get("strict")
            else:
                name = getattr(tool, "name", "unknown_function")
                desc = getattr(tool, "description", "")
                schema = getattr(tool, "schema", None)
                
                # Try to extract parameters from schema first
                if isinstance(schema, dict):
                    params = schema.get("parameters", None)
                    strict = schema.get("strict")
                else:
                    params = None
                    strict = None
                
                # If no parameters found, try to generate from callable function
                if params is None or (isinstance(params, dict) and not params.get("properties")):
                    func = getattr(tool, "func", None) or getattr(tool, "function", None) or getattr(tool, "callable", None)
                    if callable(func):
                        logger.debug(f"Generating schema from callable for tool '{name}'")
                        params = self._generate_schema_from_function(func)
                    else:
                        params = {"type": "object", "properties": {}}

            openai_tool = {
                "type": "function",
                "function": {
                    "name": name,
                    "description": desc,
                    "parameters": params
                }
            }
            if strict is not None:
                openai_tool["function"]["strict"] = strict

            # Clean tool schema specifically for Gemini compatibility
            if "gemini" in self.model.lower():
                logger.info(f"Converting tool schema '{name}' for Gemini compatibility")
                def clean_schema_for_gemini(schema_dict):
                    if not isinstance(schema_dict, dict):
                        return schema_dict
                    cleaned = {}
                    for k, v in schema_dict.items():
                        if k == "additionalProperties":
                            continue
                        if isinstance(v, dict):
                            cleaned[k] = clean_schema_for_gemini(v)
                        elif isinstance(v, list):
                            cleaned[k] = [clean_schema_for_gemini(item) if isinstance(item, dict) else item for item in v]
                        else:
                            cleaned[k] = v
                    return cleaned

                openai_tool["function"]["parameters"] = clean_schema_for_gemini(openai_tool["function"]["parameters"])

            logger.debug(f"  Final tool: type=function, name={name}")
            result.append(openai_tool)

        logger.debug(f"Converted {len(result)} tools")
        return result if result else None

    def _prune_messages(self, openai_messages: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
        """Prunes messages to stay within a token budget while keeping system prompt and recent history."""
        if not openai_messages:
            return openai_messages

        estimated_tokens = self.count_tokens(openai_messages)
        if estimated_tokens <= max_tokens:
            return openai_messages

        logger.info(f"[Token Management] Prompt size ({estimated_tokens} tokens) exceeds budget ({max_tokens} tokens). Pruning context...")

        system_messages = []
        conversational_messages = []

        for msg in openai_messages:
            if msg.get("role") == "system":
                system_messages.append(msg)
            else:
                conversational_messages.append(msg)

        system_tokens = self.count_tokens(system_messages)
        available_tokens = max(0, max_tokens - system_tokens)

        pruned_conv = []
        accumulated_tokens = 0

        # Greedily include messages from the newest to oldest
        for msg in reversed(conversational_messages):
            msg_tokens = self.count_tokens([msg])
            if accumulated_tokens + msg_tokens > available_tokens:
                # Always ensure at least the very last message is included
                if not pruned_conv:
                    pruned_conv.append(msg)
                break
            pruned_conv.append(msg)
            accumulated_tokens += msg_tokens

        pruned_conv.reverse()
        pruned_messages = system_messages + pruned_conv
        new_estimated = self.count_tokens(pruned_messages)

        logger.info(
            f"[Token Management] Pruned message context: messages={len(openai_messages)}->{len(pruned_messages)} | "
            f"Est. tokens: {estimated_tokens}->{new_estimated} (Saved ~{estimated_tokens - new_estimated} tokens)"
        )
        return pruned_messages

    async def create(
        self,
        messages: List[Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> CreateResult:
        """Create a chat completion."""
        openai_messages = self._convert_messages(messages)
        max_prompt_tokens = get_settings().max_prompt_tokens
        openai_messages = self._prune_messages(openai_messages, max_prompt_tokens)
        converted_tools = self._convert_tools(tools)
        filtered_kwargs = self._filter_kwargs(kwargs)

        # Log the exact tools being sent
        if converted_tools:
            logger.info(f"Sending {len(converted_tools)} tools to OpenAI:")
            for tool in converted_tools:
                func = tool.get("function", {})
                params = func.get("parameters", {})
                param_names = list(params.get("properties", {}).keys()) if params.get("properties") else []
                param_str = f"[{', '.join(param_names)}]" if param_names else "[]"
                logger.info(f"  - Tool: {func.get('name', 'UNNAMED')} (type: {tool.get('type')}, params: {param_str})")

        try:
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=openai_messages,
                    tools=converted_tools,
                    **filtered_kwargs,
                )
            except Exception as e:
                from core.llm_config import get_llm_config
                manager = get_llm_config()
                if manager.detect_rate_limit_error(e) and manager.gemini_available:
                    logger.warning("Rate limit detected in OpenAIChatCompletionClient. Falling back to Gemini...")
                    success, gemini_config = manager.switch_to_gemini_fallback()
                    if success:
                        self.model = gemini_config["model"]
                        self._model_info = gemini_config["model_info"]
                        from openai import OpenAI
                        try:
                            self._client.close()
                        except Exception:
                            pass
                        self._client = OpenAI(
                            api_key=gemini_config["api_key"],
                            base_url=gemini_config["base_url"],
                            timeout=30.0,
                        )
                        logger.info(f"Retrying request with Gemini model: {self.model}")
                        openai_messages = self._convert_messages(messages)
                        openai_messages = self._prune_messages(openai_messages, max_prompt_tokens)
                        converted_tools = self._convert_tools(tools)
                        try:
                            response = self._client.chat.completions.create(
                                model=self.model,
                                messages=openai_messages,
                                tools=converted_tools,
                                **filtered_kwargs,
                            )
                        except Exception as gemini_err:
                            logger.error(f"Gemini fallback also failed: {gemini_err}")
                            # Both providers failed - raise a clean rate limit error
                            raise RuntimeError(
                                "429 Rate limit: Both primary (Groq) and fallback (Gemini) AI providers are "
                                "temporarily at capacity. Please wait a minute and try again."
                            ) from gemini_err
                    else:
                        raise
                else:
                    raise

            # Track token usage
            if response.usage:
                self._total_input_tokens += response.usage.prompt_tokens
                self._total_output_tokens += response.usage.completion_tokens
                self._actual_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }
                logger.info(
                    f"[TOKEN USAGE] Model: {self.model} | "
                    f"Prompt (Input) Tokens: {response.usage.prompt_tokens} | "
                    f"Completion (Output) Tokens: {response.usage.completion_tokens} | "
                    f"Total Tokens: {response.usage.prompt_tokens + response.usage.completion_tokens}"
                )

            # Extract response content
            if response.choices:
                choice = response.choices[0]
                content = choice.message.content or ""

                # Handle tool calls if present
                if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                    from autogen_core._types import FunctionCall
                    content = []
                    for tc in choice.message.tool_calls:
                        func_name = tc.function.name
                        raw_args = tc.function.arguments
                        
                        try:
                            import json
                            import inspect
                            args_dict = json.loads(raw_args)
                            
                            # Safely import the wrapper functions to inspect signature
                            from agents import receptionist_agent
                            if hasattr(receptionist_agent, "sanitize_tool_arguments"):
                                cleaned_args = receptionist_agent.sanitize_tool_arguments(func_name, args_dict)
                                sanitized_args = json.dumps(cleaned_args)
                            else:
                                func_obj = getattr(receptionist_agent, func_name, None)
                                if func_obj:
                                    sig = inspect.signature(func_obj)
                                    valid_params = sig.parameters.keys()
                                    cleaned_args = {k: v for k, v in args_dict.items() if k in valid_params}
                                    sanitized_args = json.dumps(cleaned_args)
                                else:
                                    sanitized_args = raw_args
                        except Exception as e:
                            logger.error(f"Error sanitizing tool arguments for {func_name}: {e}")
                            sanitized_args = raw_args
                            
                        content.append(
                            FunctionCall(
                                id=tc.id,
                                arguments=sanitized_args,
                                name=func_name,
                            )
                        )

                # Safely map finish reason to FinishReasons literal values
                choice_reason = choice.finish_reason
                mapped_reason = "unknown"
                if choice_reason in ["stop", "length", "function_calls", "content_filter", "error", "unknown"]:
                    mapped_reason = choice_reason
                elif choice_reason == "tool_calls":
                    mapped_reason = "function_calls"

                return CreateResult(
                    finish_reason=mapped_reason,
                    content=content,
                    usage=RequestUsage(
                        prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                        completion_tokens=response.usage.completion_tokens if response.usage else 0,
                    ),
                    cached=False,
                )

            return CreateResult(
                finish_reason="error",
                content="No response from model",
                usage=RequestUsage(prompt_tokens=0, completion_tokens=0),
                cached=False,
            )

        except Exception as e:
            logger.error(f"OpenAI API error in create(): {e}")
            raise

    async def create_stream(
        self,
        messages: List[Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ):
        """Create a streaming chat completion."""
        openai_messages = self._convert_messages(messages)
        max_prompt_tokens = get_settings().max_prompt_tokens
        openai_messages = self._prune_messages(openai_messages, max_prompt_tokens)
        converted_tools = self._convert_tools(tools)
        filtered_kwargs = self._filter_kwargs(kwargs)

        try:
            try:
                total_output_chars = 0
                with self._client.chat.completions.create(
                    model=self.model,
                    messages=openai_messages,
                    tools=converted_tools,
                    stream=True,
                    **filtered_kwargs,
                ) as response:
                    for chunk in response:
                        if chunk.choices:
                            delta = chunk.choices[0].delta
                            if delta and delta.content:
                                total_output_chars += len(delta.content)
                                choice_reason = chunk.choices[0].finish_reason
                                mapped_reason = "unknown"
                                if choice_reason in ["stop", "length", "function_calls", "content_filter", "error", "unknown"]:
                                    mapped_reason = choice_reason

                                yield CreateResult(
                                    finish_reason=mapped_reason,
                                    content=delta.content,
                                    usage=RequestUsage(prompt_tokens=0, completion_tokens=0),
                                    cached=False,
                                )
                
                # Estimate streaming token usage
                estimated_completion_tokens = max(1, total_output_chars // 4)
                estimated_prompt_tokens = self.count_tokens(openai_messages)
                self._total_input_tokens += estimated_prompt_tokens
                self._total_output_tokens += estimated_completion_tokens
                logger.info(
                    f"[TOKEN USAGE (STREAMING)] Model: {self.model} | "
                    f"Est. Prompt Tokens: {estimated_prompt_tokens} | "
                    f"Est. Completion Tokens: {estimated_completion_tokens} | "
                    f"Est. Total Tokens: {estimated_prompt_tokens + estimated_completion_tokens}"
                )
            except Exception as e:
                from core.llm_config import get_llm_config
                manager = get_llm_config()
                if manager.detect_rate_limit_error(e) and manager.gemini_available:
                    logger.warning("Rate limit detected in OpenAIChatCompletionClient.create_stream(). Falling back to Gemini...")
                    success, gemini_config = manager.switch_to_gemini_fallback()
                    if success:
                        self.model = gemini_config["model"]
                        self._model_info = gemini_config["model_info"]
                        from openai import OpenAI
                        try:
                            self._client.close()
                        except Exception:
                            pass
                        self._client = OpenAI(
                            api_key=gemini_config["api_key"],
                            base_url=gemini_config["base_url"],
                            timeout=30.0,
                        )
                        logger.info(f"Retrying stream request with Gemini model: {self.model}")
                        openai_messages = self._convert_messages(messages)
                        openai_messages = self._prune_messages(openai_messages, max_prompt_tokens)
                        converted_tools = self._convert_tools(tools)
                        try:
                            async for chunk in self.create_stream(messages, tools, **kwargs):
                                yield chunk
                            return
                        except Exception as gemini_err:
                            logger.error(f"Gemini stream fallback also failed: {gemini_err}")
                            raise RuntimeError(
                                "429 Rate limit: Both primary and fallback AI providers are temporarily at capacity."
                            ) from gemini_err
                    else:
                        raise
                else:
                    raise
        except Exception as e:
            logger.error(f"OpenAI API error in create_stream(): {e}")
            raise

    def actual_usage(self) -> RequestUsage:
        """Get actual usage."""
        return RequestUsage(
            prompt_tokens=self._actual_usage.get("prompt_tokens", 0),
            completion_tokens=self._actual_usage.get("completion_tokens", 0),
        )

    def total_usage(self) -> RequestUsage:
        """Get total usage."""
        return RequestUsage(
            prompt_tokens=self._total_input_tokens,
            completion_tokens=self._total_output_tokens,
        )

    def count_tokens(self, messages: Any, *, tools: Any = []) -> int:
        """Count tokens in messages (rough estimate)."""
        total_chars = sum(len(str(msg)) for msg in messages)
        return max(1, total_chars // 4)

    def remaining_tokens(self, messages: Any, *, tools: Any = []) -> int:
        """Remaining tokens (not supported)."""
        return 0

    async def close(self) -> None:
        """Close the client."""
        try:
            self._client.close()
        except Exception:
            pass
