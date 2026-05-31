"""OpenAI ChatCompletionClient adapter for AutoGen compatibility."""

import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

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
    ):
        """Initialize the client."""
        self.model = model
        self._model_info = model_info
        self._client = OpenAI(api_key=api_key, base_url=base_url)
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
        """Convert AutoGen message format to OpenAI format."""
        result = []
        for msg in messages:
            if isinstance(msg, dict):
                result.append(msg)
            else:
                # Convert message object to dict
                msg_dict = {
                    "role": getattr(msg, "role", "user"),
                    "content": getattr(msg, "content", str(msg)),
                }
                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    msg_dict["tool_calls"] = msg.tool_calls
                result.append(msg_dict)
        return result

    def _filter_kwargs(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out unsupported parameters before passing to OpenAI API."""
        return {k: v for k, v in kwargs.items() if k not in UNSUPPORTED_PARAMS}

    def _convert_tools(
        self, tools: Optional[List[Dict[str, Any]]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Convert AutoGen tool format to OpenAI format."""
        if not tools:
            return None

        result = []
        for i, tool in enumerate(tools):
            logger.debug(f"Processing tool {i}: {type(tool).__name__}")
            if isinstance(tool, dict):
                logger.debug(f"  Dict tool keys: {tool.keys()}")
                # Ensure it has the 'type' field
                if "type" not in tool:
                    tool = {**tool, "type": "function"}
                
                # Ensure function has required fields
                if "function" in tool and isinstance(tool["function"], dict):
                    func = tool["function"]
                    logger.debug(f"    Function keys: {func.keys()}")
                    if "name" not in func or not func["name"]:
                        # Try to get name from outer dict
                        func["name"] = tool.get("name", "unknown_function")
                    if "description" not in func:
                        func["description"] = tool.get("description", "")
                elif "function" not in tool:
                    # Create function object if missing
                    tool["function"] = {
                        "name": tool.get("name", "unknown_function"),
                        "description": tool.get("description", ""),
                    }
                logger.debug(f"  Final tool: type={tool.get('type')}, name={tool.get('function', {}).get('name')}")
                result.append(tool)
            else:
                # Handle function objects - convert to OpenAI format
                func_name = getattr(tool, "__name__", "unknown_function")
                if not func_name:
                    func_name = "unknown_function"
                logger.debug(f"  Function object: {func_name}")
                result.append(
                    {
                        "type": "function",
                        "function": {
                            "name": func_name,
                            "description": getattr(tool, "__doc__", ""),
                        },
                    }
                )
        logger.debug(f"Converted {len(result)} tools")
        return result if result else None

    async def create(
        self,
        messages: List[Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> CreateResult:
        """Create a chat completion."""
        openai_messages = self._convert_messages(messages)
        converted_tools = self._convert_tools(tools)
        filtered_kwargs = self._filter_kwargs(kwargs)

        # Log the exact tools being sent
        if converted_tools:
            logger.info(f"Sending {len(converted_tools)} tools to OpenAI:")
            for tool in converted_tools:
                func = tool.get("function", {})
                logger.info(f"  - Tool: {func.get('name', 'UNNAMED')} (type: {tool.get('type')})")

        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=converted_tools,
                **filtered_kwargs,
            )

            # Track token usage
            if response.usage:
                self._total_input_tokens += response.usage.prompt_tokens
                self._total_output_tokens += response.usage.completion_tokens
                self._actual_usage = {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }

            # Extract response content
            if response.choices:
                choice = response.choices[0]
                content = choice.message.content or ""

                # Handle tool calls if present
                if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                    # AutoGen expects tool calls in the content or as a separate field
                    content = json.dumps(
                        [
                            {
                                "id": tc.id,
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            for tc in choice.message.tool_calls
                        ]
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
        converted_tools = self._convert_tools(tools)
        filtered_kwargs = self._filter_kwargs(kwargs)

        try:
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
