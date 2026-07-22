"""OpenAI ChatCompletionClient adapter for AutoGen compatibility."""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from core.config import get_settings

from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    CreateResult,
    FunctionExecutionResultMessage,
    ModelCapabilities,
    ModelInfo,
    RequestUsage,
    SystemMessage,
    UserMessage,
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


from typing import Any, Dict, List, Optional

def clean_and_parse_json(json_str: str) -> Optional[Dict[str, Any]]:
    import re
    json_str = json_str.strip()
    try:
        return json.loads(json_str)
    except Exception:
        pass

    # Try removing trailing commas before closing braces/brackets
    try:
        cleaned = re.sub(r',\s*([\}\]])', r'\1', json_str)
        return json.loads(cleaned)
    except Exception:
        pass

    # Try replacing multiple double quotes with a single double quote
    try:
        cleaned = re.sub(r'"+', '"', json_str)
        return json.loads(cleaned)
    except Exception:
        pass

    # Try replacing "" with " specifically and fixing trailing quotes
    try:
        cleaned = json_str.replace('""', '"')
        cleaned = re.sub(r'"\s*"\s*}', '"}', cleaned)
        return json.loads(cleaned)
    except Exception:
        pass

    # If it is flat, parse with regex
    if json_str.count('{') == 1 and json_str.count('}') == 1:
        try:
            attribs = {}
            matches = re.finditer(r'"([a-zA-Z0-9_]+)"\s*:\s*"+([^"]*)"*', json_str)
            for m in matches:
                key = m.group(1)
                val = m.group(2).strip()
                attribs[key] = val
            if attribs:
                return attribs
        except Exception:
            pass

    return None


class OpenAIChatCompletionClient(ChatCompletionClient):
    """OpenAI ChatCompletionClient for AutoGen."""

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: str,
        model_info: Optional[ModelInfo] = None,
        timeout: float = 30.0,
        disable_fallback: bool = False,
    ):
        """Initialize the client."""
        self.model = model
        self._model_info = model_info
        self.disable_fallback = disable_fallback
        # Store the URL this client was originally pointed at so _find_chain_start can
        # locate the right starting position in the global fallback chain.
        self._initial_base_url = base_url
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout, max_retries=0)
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
                    # Determine role from the AutoGen message's actual TYPE, not from
                    # `.source`/`.role` string-matching — `.source` on an AssistantMessage
                    # is the *agent's name* (e.g. "Clara_Receptionist"), not a role label,
                    # so the old substring check ("assistant" in role_lower) always missed
                    # it and silently mis-classified every assistant tool-call turn as a
                    # "user" message. That corrupted the conversation structure on every
                    # multi-round tool call: the assistant's FunctionCall never became a
                    # proper {"role": "assistant", "tool_calls": [...]}, so the following
                    # tool-result message had no matching call to attach a name to —
                    # which is what produces Gemini's "function_response.name: Name cannot
                    # be empty" 400 error (and, since Groq/HF tolerate the malformed
                    # history more quietly, likely also what left Clara unable to see her
                    # own prior tool results properly within a turn).
                    if isinstance(msg, AssistantMessage):
                        role_str = "assistant"
                    elif isinstance(msg, SystemMessage):
                        role_str = "system"
                    elif isinstance(msg, FunctionExecutionResultMessage):
                        role_str = "tool"
                    elif isinstance(msg, UserMessage):
                        role_str = "user"
                    else:
                        role_str = "user"

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
                    elif role_str == "tool" and isinstance(content, list) and len(content) > 0:
                        for item in content:
                            # FunctionExecutionResult.name is a required field on the type
                            # itself — read it directly instead of trying to reconstruct it
                            # later from a call_id lookup that depended on Case 1 above
                            # having worked (which, before this fix, it never did).
                            result.append({
                                "role": "tool",
                                "tool_call_id": getattr(item, "call_id", ""),
                                "name": getattr(item, "name", None) or "tool_call",
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
        
        # Post-process messages to ensure every 'tool'/'function' message has a valid 'name' field for Gemini compatibility
        tool_id_to_name = {}
        # First pass: collect tool_call_id -> function name mapping from assistant messages
        for msg_dict in result:
            if msg_dict.get("role") == "assistant":
                tcs = msg_dict.get("tool_calls") or []
                for tc in tcs:
                    if isinstance(tc, dict):
                        tc_id = tc.get("id")
                        func_name = tc.get("function", {}).get("name")
                        if tc_id and func_name:
                            tool_id_to_name[tc_id] = func_name
                    else:
                        tc_id = getattr(tc, "id", None)
                        func_name = None
                        if hasattr(tc, "function"):
                            func_name = getattr(tc.function, "name", None)
                        elif hasattr(tc, "name"):
                            func_name = getattr(tc, "name", None)
                        if tc_id and func_name:
                            tool_id_to_name[tc_id] = func_name

        # Second pass: ensure 'name' is populated for 'tool' and 'function' messages
        for msg_dict in result:
            role = msg_dict.get("role")
            if role in ("tool", "function"):
                call_id = msg_dict.get("tool_call_id") or msg_dict.get("id")
                if not msg_dict.get("name"):
                    # Try to look up function name, default to 'tool_call' if not found
                    msg_dict["name"] = tool_id_to_name.get(call_id) or "tool_call"
                    
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

            # Clean tool schema for all models to ensure compatibility with various API providers
            # (especially resolving anyOf/oneOf and null types for Groq/HuggingFace/Gemini)
            def clean_schema(schema_dict, remove_additional_properties=False):
                if not isinstance(schema_dict, dict):
                    return schema_dict
                cleaned = {}
                for k, v in schema_dict.items():
                    if k == "additionalProperties" and remove_additional_properties:
                        continue
                    if k in ("anyOf", "oneOf"):
                        # Simplify anyOf / oneOf
                        options = v
                        non_null_options = [opt for opt in options if isinstance(opt, dict) and opt.get("type") != "null"]
                        if non_null_options:
                            cleaned_opt = clean_schema(non_null_options[0], remove_additional_properties)
                            for ok, ov in cleaned_opt.items():
                                cleaned[ok] = ov
                        else:
                            cleaned["type"] = "string"
                        continue
                    if k == "type" and isinstance(v, list):
                        non_null_types = [t for t in v if t != "null"]
                        if non_null_types:
                            cleaned["type"] = non_null_types[0]
                        else:
                            cleaned["type"] = "string"
                        continue
                    
                    if isinstance(v, dict):
                        cleaned[k] = clean_schema(v, remove_additional_properties)
                    elif isinstance(v, list):
                        cleaned[k] = [clean_schema(item, remove_additional_properties) if isinstance(item, dict) else item for item in v]
                    else:
                        cleaned[k] = v
                return cleaned

            remove_ap = "gemini" in self.model.lower()
            openai_tool["function"]["parameters"] = clean_schema(openai_tool["function"]["parameters"], remove_additional_properties=remove_ap)

            logger.debug(f"  Final tool: type=function, name={name}")
            result.append(openai_tool)

        logger.debug(f"Converted {len(result)} tools")
        return result if result else None

    def _prune_messages(self, openai_messages: List[Dict[str, Any]], max_tokens: int) -> List[Dict[str, Any]]:
        """Prunes messages to stay within a token budget while keeping system prompt and recent history."""
        if not openai_messages:
            return openai_messages

        # Enforce lower target token budget for general queries to actively minimize context window sizes
        max_tokens = min(max_tokens, 2500)

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

        if not conversational_messages:
            return system_messages

        system_tokens = self.count_tokens(system_messages)
        available_tokens = max(0, max_tokens - system_tokens)

        # Build group assignments to keep tool calls/responses together
        # Map tool_call_id -> assistant message index
        tool_to_assistant = {}
        for idx, msg in enumerate(conversational_messages):
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tc in msg.get("tool_calls") or []:
                    tc_id = None
                    if isinstance(tc, dict):
                        tc_id = tc.get("id")
                    else:
                        tc_id = getattr(tc, "id", None)
                    if tc_id:
                        tool_to_assistant[tc_id] = idx

        # Group assignments (index in conversational_messages -> set of indices in group)
        idx_to_group = {idx: {idx} for idx in range(len(conversational_messages))}

        def union(i, j):
            group_i = idx_to_group[i]
            group_j = idx_to_group[j]
            if group_i is not group_j:
                merged = group_i.union(group_j)
                for idx in merged:
                    idx_to_group[idx] = merged

        # Union assistant message with its tool responses
        for idx, msg in enumerate(conversational_messages):
            if msg.get("role") in ("tool", "function"):
                call_id = msg.get("tool_call_id") or msg.get("id")
                if call_id in tool_to_assistant:
                    union(idx, tool_to_assistant[call_id])

        # Extract unique groups
        unique_groups = []
        seen_ids = set()
        for idx in range(len(conversational_messages)):
            group_set = idx_to_group[idx]
            group_id = id(group_set)
            if group_id not in seen_ids:
                seen_ids.add(group_id)
                group_msgs = [conversational_messages[i] for i in sorted(list(group_set))]
                unique_groups.append((min(group_set), group_msgs))

        # Sort groups chronologically
        unique_groups.sort(key=lambda x: x[0])
        sorted_groups = [g[1] for g in unique_groups]

        pruned_groups = []
        accumulated_tokens = 0

        # Greedily include groups from newest to oldest
        for group in reversed(sorted_groups):
            group_tokens = self.count_tokens(group)
            if accumulated_tokens + group_tokens > available_tokens:
                # Always ensure at least the very last group is included
                if not pruned_groups:
                    pruned_groups.append(group)
                break
            pruned_groups.append(group)
            accumulated_tokens += group_tokens

        pruned_groups.reverse()
        pruned_conv = []
        for group in pruned_groups:
            pruned_conv.extend(group)

        pruned_messages = system_messages + pruned_conv
        new_estimated = self.count_tokens(pruned_messages)

        logger.info(
            f"[Token Management] Pruned message context: messages={len(openai_messages)}->{len(pruned_messages)} | "
            f"Est. tokens: {estimated_tokens}->{new_estimated} (Saved ~{estimated_tokens - new_estimated} tokens)"
        )
        return pruned_messages

    # ------------------------------------------------------------------
    # Internal helper: find where in the global chain this client sits
    # ------------------------------------------------------------------
    def _find_chain_start(self, full_chain: list) -> int:
        """
        Locate this client's starting position inside *full_chain* by matching
        the stored initial base_url (and optionally model name).
        Returns 0 if no match is found so the full chain is tried.
        """
        initial_base = self._initial_base_url.rstrip("/")
        # Pass 1: exact model name + base_url
        for i, cfg in enumerate(full_chain):
            if cfg["model"] == self.model and cfg["base_url"].rstrip("/") == initial_base:
                return i
        # Pass 2: base_url only (model may differ due to earlier fallback)
        for i, cfg in enumerate(full_chain):
            if cfg["base_url"].rstrip("/") == initial_base:
                return i
        return 0  # Default: start from Hugging Face

    async def create(
        self,
        messages: List[Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> CreateResult:
        """
        Create a chat completion.
        Fallback order: start at THIS client's provider position in the global
        chain (Ollama → Groq-primary → Groq-fallback → Gemini), then cascade
        downwards on any retryable error.

        Key: the chain is sliced from the CURRENT provider's index so that
        a client initialised for Groq does NOT restart from Ollama.
        """
        max_prompt_tokens = get_settings().max_prompt_tokens

        from core.llm_config import get_llm_config
        manager = get_llm_config()

        if getattr(self, "disable_fallback", False):
            provider_chain = [{
                "provider": "huggingface" if "huggingface" in self._initial_base_url or "router.huggingface.co" in self._initial_base_url else "gemini" if "google" in self._initial_base_url or "generativelanguage" in self._initial_base_url else "groq",
                "model": self.model,
                "api_key": self._client.api_key,
                "base_url": self._initial_base_url,
                "model_info": self._model_info or {
                    "vision": False,
                    "function_calling": True,
                    "json_output": True,
                    "family": "gemini-2.0" if "gemini" in self.model.lower() else "llama-3.3" if "3.3" in self.model.lower() else "qwen" if "qwen" in self.model.lower() else "llama-3.1",
                    "structured_output": False,
                },
            }]
        else:
            full_chain    = manager.get_provider_chain()
            start_idx     = self._find_chain_start(full_chain)
            provider_chain = full_chain[start_idx:]

        if not provider_chain:
            raise RuntimeError("No LLM providers are configured. Check HUGGINGFACE_ENABLED / GROQ_API_KEY / GEMINI_API_KEY.")

        last_error: Optional[Exception] = None

        for chain_idx, provider_cfg in enumerate(provider_chain):
            is_last_provider = chain_idx == len(provider_chain) - 1
            provider_name = provider_cfg["provider"]
            # if provider_name == "huggingface" and tools:
            #     logger.info(f"⏭️ Skipping Hugging Face provider for model '{provider_cfg['model']}' because tool calling is requested and Hugging Face serverless API does not support function calling.")
            #     continue
            model_name    = provider_cfg["model"]
            api_key       = provider_cfg["api_key"]
            base_url      = provider_cfg["base_url"]
            model_info    = provider_cfg["model_info"]

            # Point this client at the chosen provider
            self.model       = model_name
            self._model_info = model_info
            try:
                await self._client.close()
            except Exception:
                pass
            # HuggingFace (Qwen-72B) often needs 60-90s; keep Groq/Gemini at 30s
            _client_timeout = 120.0 if provider_name == "huggingface" else 30.0
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=_client_timeout,
                max_retries=0,
            )

            succeeded = False
            keys_count = (
                len(manager._huggingface_keys) if provider_name == "huggingface"
                else len(manager._groq_keys) if provider_name == "groq"
                else len(manager._gemini_keys) if provider_name == "gemini"
                else 1
            )
            retries = max(2, keys_count)
            backoff = 1.0
            for attempt in range(retries + 1):
                try:
                    logger.info(f"🎯 [{provider_name}] Trying model '{model_name}' (attempt {attempt+1}/{retries+1})...")
                    openai_messages  = self._convert_messages(messages)
                    openai_messages  = self._prune_messages(openai_messages, max_prompt_tokens)
                    logger.info(f"[DEBUG_LLM_MSGS] messages: {json.dumps(openai_messages, default=str)[:3000]}")
                    converted_tools  = self._convert_tools(tools)
                    filtered_kwargs  = self._filter_kwargs(kwargs)

                    if converted_tools:
                        logger.info(f"Sending {len(converted_tools)} tools to {provider_name}:")
                        for tool in converted_tools:
                            func        = tool.get("function", {})
                            params      = func.get("parameters", {})
                            param_names = list(params.get("properties", {}).keys()) if params.get("properties") else []
                            param_str   = f"[{', '.join(param_names)}]" if param_names else "[]"
                            logger.info(f"  - Tool: {func.get('name', 'UNNAMED')} (params: {param_str})")

                    response = await self._client.chat.completions.create(
                        model=model_name,
                        messages=openai_messages,
                        tools=converted_tools,
                        **filtered_kwargs,
                    )
                    logger.info(f"✅ [{provider_name}] '{model_name}' succeeded.")
                    succeeded = True
                    break

                except Exception as e:
                    last_error = e
                    err_str = str(e)
                    status_code = getattr(e, "status_code", None)
                    is_quota    = "429" in err_str or "402" in err_str or "quota" in err_str.lower() or "rate limit" in err_str.lower() or "resource_exhausted" in err_str.lower() or "credits" in err_str.lower() or status_code in [402, 429]
                    is_hard_quota = is_quota and ("limit: 0" in err_str or "quota exceeded" in err_str.lower() or "credits" in err_str.lower()) and "retry" not in err_str.lower() and "delay" not in err_str.lower()
                    is_auth     = "401" in err_str or "invalid api key" in err_str.lower() or "authentication" in err_str.lower() or status_code == 401
                    is_unavail  = "connect" in err_str.lower() or "connection refused" in err_str.lower() or "timed out" in err_str.lower() or "timeout" in err_str.lower() or status_code in [500, 502, 503, 504]
                    is_no_tools = "does not support tools" in err_str.lower() or "tool_use_failed" in err_str.lower() or "failed_generation" in err_str.lower() or status_code == 400
                    is_too_large = "413" in err_str or "too large" in err_str.lower() or "request too large" in err_str.lower() or status_code == 413

                    # Mark provider as daily-exhausted so future fallback decisions skip it instantly
                    if is_hard_quota:
                        manager._exhausted_providers.add(provider_name)
                        logger.warning(f"🚫 [{provider_name}] Daily quota exhausted (limit: 0) — skipping this provider for the rest of the session.")

                    if is_quota and not is_hard_quota and attempt < retries:
                        new_key = manager.rotate_key(provider_name)
                        if new_key and new_key != api_key:
                            api_key = new_key
                            try:
                                await self._client.close()
                            except Exception:
                                pass
                            self._client = AsyncOpenAI(
                                api_key=api_key,
                                base_url=base_url,
                                timeout=_client_timeout,
                                max_retries=0,
                            )
                            logger.info(f"🔄 Switched to rotated {provider_name} API key for attempt {attempt+2}.")
                            continue

                        import re
                        retry_seconds = None
                        # Pattern 1: Match 'try again in 1.45s' or 'Please retry in 20.44s' or 'retry after 5s'
                        match = re.search(r"(?:retry in|try again in|try again after|retry after|retry_after|after|in)\s*[:\s]?\s*([0-9\.]+)\s*s", err_str, re.IGNORECASE)
                        if match:
                            retry_seconds = float(match.group(1))
                        else:
                            # Pattern 2: Match JSON-like: 'retryDelay': '20s'
                            match_json = re.search(r"retryDelay[\'\"]?\s*:\s*[\'\"]?([0-9\.]+)s", err_str, re.IGNORECASE)
                            if match_json:
                                retry_seconds = float(match_json.group(1))

                        if retry_seconds is not None:
                            sleep_time = retry_seconds + 0.5
                        else:
                            sleep_time = backoff * (2 ** attempt)

                        # Waiting out a short rate-limit only helps if there's a real retry
                        # left to make with it. When this is the LAST provider in the chain,
                        # breaking out "to fall back" has nowhere to fall back to — it just
                        # fails the whole request outright, even for waits as short as
                        # 20-30s that easily fit inside the 180s agent timeout budget. So
                        # only skip-ahead-immediately when there's an actual next provider;
                        # on the last provider, wait it out instead (capped at 60s).
                        if sleep_time > 15.0 and not is_last_provider:
                            logger.warning(f"⚠️ [{provider_name}] '{model_name}' requested wait too long ({sleep_time:.2f}s). Falling back immediately to next provider.")
                            break
                        if sleep_time > 60.0:
                            logger.warning(f"⚠️ [{provider_name}] '{model_name}' requested wait too long ({sleep_time:.2f}s) even as last provider — giving up.")
                            break
                        logger.warning(f"⚠️ [{provider_name}] '{model_name}' rate limited. Sleeping for {sleep_time:.2f}s before retry...")

                        # Non-blocking: a plain time.sleep() here would freeze the entire
                        # asyncio event loop — and with it every other concurrent user's
                        # request on this server — for the full sleep duration.
                        await asyncio.sleep(sleep_time)
                        continue

                    # For non-quota errors, hard quota errors, or if we exhausted all retries
                    if is_no_tools and "failed_generation" in err_str:
                        import re
                        fg_match = re.search(r"failed_generation.*?(<function.*?>.*?</function>|<function.*)", err_str, re.DOTALL)
                        if fg_match:
                            raw_fg = fg_match.group(1).replace('\\"', '"').replace('\\n', '\n').rstrip("'\"}")
                            tool_names = []
                            if tools:
                                for tool in tools:
                                    if isinstance(tool, dict):
                                        tname = tool.get("name") or tool.get("function", {}).get("name")
                                    else:
                                        tname = getattr(tool, "name", None)
                                    if tname:
                                        tool_names.append(tname)
                            
                            flexible_pattern = r'[\(<=\s]*function(?:[=>\s\u0022\u0027]+|(?:\s+name=[\"\']?))([a-zA-Z0-9_]+)[=>\s\u0022\u0027\[\],]*({(?:[^{}]|{[^{}]*})*})(?:\s*</?function>)?'
                            recovered_calls = []
                            from autogen_core._types import FunctionCall
                            import uuid
                            for match in re.finditer(flexible_pattern, raw_fg, re.DOTALL):
                                tag_name = match.group(1)
                                args_str = match.group(2) or "{}"
                                if tag_name in tool_names:
                                    parsed_args = clean_and_parse_json(args_str)
                                    args_str = json.dumps(parsed_args) if parsed_args is not None else json.dumps({"query": args_str})
                                    recovered_calls.append(FunctionCall(id=f"call_{uuid.uuid4().hex[:8]}", arguments=args_str, name=tag_name))
                            
                            if recovered_calls:
                                logger.info(f"✅ Successfully recovered {len(recovered_calls)} tool call(s) from Groq failed_generation payload.")
                                return CreateResult(
                                    finish_reason="function_calls",
                                    content=recovered_calls,
                                    usage=RequestUsage(prompt_tokens=0, completion_tokens=0),
                                    cached=False,
                                )

                    if is_auth or is_quota or is_unavail or is_no_tools or is_too_large:
                        cooldown_dur = 0.0
                        if is_auth:
                            cooldown_dur = 300.0
                        elif is_quota:
                            cooldown_dur = 300.0 if is_hard_quota else 30.0
                        elif is_unavail:
                            cooldown_dur = 15.0
                        elif is_too_large:
                            cooldown_dur = 60.0

                        if cooldown_dur > 0:
                            try:
                                manager.set_cooldown(provider_name, model_name, cooldown_dur)
                            except Exception as exc:
                                logger.warning("Failed to set model cooldown: %s", exc)

                        logger.warning(f"⚠️ [{provider_name}] '{model_name}' failed ({err_str}), trying next provider...")
                        break
                    
                    # Unexpected error — propagate immediately
                    logger.error(f"❌ [{provider_name}] Unexpected error: {e}")
                    raise

            if not succeeded:
                continue

            # ---- Successful response: parse and return ----
            if response.usage:
                self._total_input_tokens  += response.usage.prompt_tokens
                self._total_output_tokens += response.usage.completion_tokens
                self._actual_usage = {
                    "prompt_tokens":     response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                }
                logger.info(
                    f"[TOKEN USAGE] Model: {model_name} | "
                    f"Prompt: {response.usage.prompt_tokens} | "
                    f"Completion: {response.usage.completion_tokens} | "
                    f"Total: {response.usage.prompt_tokens + response.usage.completion_tokens}"
                )

            if response.choices:
                choice  = response.choices[0]
                content = choice.message.content or ""

                if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
                    from autogen_core._types import FunctionCall
                    content = []
                    for tc in choice.message.tool_calls:
                        func_name = tc.function.name
                        raw_args  = tc.function.arguments
                        if raw_args is None or (isinstance(raw_args, str) and not raw_args.strip()):
                            raw_args = "{}"
                        try:
                            import inspect as _inspect
                            args_dict = json.loads(raw_args)
                            from ai.agents import receptionist_agent
                            if hasattr(receptionist_agent, "sanitize_tool_arguments"):
                                cleaned_args  = receptionist_agent.sanitize_tool_arguments(func_name, args_dict)
                                sanitized_args = json.dumps(cleaned_args)
                            else:
                                func_obj = getattr(receptionist_agent, func_name, None)
                                if func_obj:
                                    sig         = _inspect.signature(func_obj)
                                    valid_params = sig.parameters.keys()
                                    cleaned_args = {k: v for k, v in args_dict.items() if k in valid_params}
                                    sanitized_args = json.dumps(cleaned_args)
                                else:
                                    sanitized_args = raw_args
                        except Exception as tool_e:
                            logger.error(f"Error sanitizing tool arguments for {func_name}: {tool_e}")
                            sanitized_args = raw_args if (raw_args and isinstance(raw_args, str) and raw_args.strip()) else "{}"

                        content.append(
                            FunctionCall(
                                id=tc.id,
                                arguments=sanitized_args,
                                name=func_name,
                            )
                        )

                elif isinstance(content, str) and content.strip():
                    tool_names = []
                    if tools:
                        for tool in tools:
                            if isinstance(tool, dict):
                                name = tool.get("name") or tool.get("function", {}).get("name")
                            else:
                                name = getattr(tool, "name", None)
                            if name:
                                tool_names.append(name)

                    if tool_names:
                        import re
                        import uuid
                        from autogen_core._types import FunctionCall

                        pattern = r"<([a-zA-Z0-9_]+)(?:=({(?:[^{}]|{[^{}]*})*}|\[.*?\]|[a-zA-Z0-9_]+))?(?:\s+[^>]*)?>(.*?)</\1>|<([a-zA-Z0-9_]+)(?:=({(?:[^{}]|{[^{}]*})*}|\[.*?\]|[a-zA-Z0-9_]+))?(?:\s+[^>]*)?\s*/>|<function=([a-zA-Z0-9_]+)>(.*?)</function>|<function\s+name=[\"\']?([a-zA-Z0-9_]+)[\"\']?\s*>(.*?)</function>|<function/([a-zA-Z0-9_]+)>(.*?)</function>|<([a-zA-Z0-9_]+)\s+({(?:[^{}]|{[^{}]*})*})\s*>?\s*</function>"
                        matches = list(re.finditer(pattern, content, re.DOTALL))

                        function_calls = []
                        for match in matches:
                            tag_name = match.group(1) or match.group(4) or match.group(6) or match.group(8) or match.group(10) or match.group(12)
                            val_after_eq = match.group(2) or match.group(5) or match.group(13)
                            
                            # Check if the value after '=' is a tool name override or direct JSON arguments
                            is_json_arg = False
                            if val_after_eq:
                                val_stripped = val_after_eq.strip()
                                if val_stripped.startswith('{') or val_stripped.startswith('['):
                                    is_json_arg = True
                                else:
                                    tag_name = val_stripped

                            if tag_name in tool_names:
                                if is_json_arg:
                                    args_str = val_stripped
                                else:
                                    # Parse attributes from opening tag
                                    first_gt = match.group(0).find(">")
                                    opening_tag = match.group(0)[:first_gt+1] if first_gt != -1 else match.group(0)
                                    attribs = {}
                                    attr_matches = re.finditer(r'([a-zA-Z0-9_]+)\s*=\s*({(?:[^{}]|{[^{}]*})*}|\[.*?\]|"[^"]*"|\'[^\']*\'|[^\s>]+)', opening_tag)
                                    for am in attr_matches:
                                        key = am.group(1)
                                        val = am.group(2).strip()
                                        if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                                            val = val[1:-1]
                                        parsed_val = clean_and_parse_json(val)
                                        if parsed_val is not None:
                                            val = parsed_val
                                        attribs[key] = val

                                    if attribs:
                                        args_str = json.dumps(attribs)
                                    else:
                                        args_str = match.group(3) or match.group(7) or match.group(9) or match.group(11) or "{}"
                                        args_str = args_str.strip() or "{}"
                                        parsed_args = clean_and_parse_json(args_str)
                                        if parsed_args is not None:
                                            args_str = json.dumps(parsed_args)
                                        else:
                                            args_str = json.dumps({"query": args_str})

                                function_calls.append(
                                    FunctionCall(
                                        id=f"call_{uuid.uuid4().hex[:8]}",
                                        arguments=args_str,
                                        name=tag_name,
                                    )
                                )

                        # Fallback flexible pattern if no matches were found by the strict XML parser
                        if not function_calls:
                            flexible_pattern = r'[\(<=\s]*function(?:[=>\s\u0022\u0027]+|(?:\s+name=[\"\']?))([a-zA-Z0-9_]+)[=>\s\u0022\u0027\[\],]*({(?:[^{}]|{[^{}]*})*})(?:\s*</?function>)?'
                            flex_matches = list(re.finditer(flexible_pattern, content, re.DOTALL))
                            for match in flex_matches:
                                tag_name = match.group(1)
                                args_str = match.group(2) or "{}"
                                
                                if tag_name in tool_names:
                                    args_str = args_str.strip() or "{}"
                                    parsed_args = clean_and_parse_json(args_str)
                                    if parsed_args is not None:
                                        args_str = json.dumps(parsed_args)
                                    else:
                                        args_str = json.dumps({"query": args_str})

                                    function_calls.append(
                                        FunctionCall(
                                            id=f"call_{uuid.uuid4().hex[:8]}",
                                            arguments=args_str,
                                            name=tag_name,
                                        )
                                    )

                        if function_calls:
                            logger.info(f"Parsed {len(function_calls)} XML/flexible tool calls from response.")
                            content = function_calls
                            choice.finish_reason = "tool_calls"

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

        # All providers exhausted
        raise RuntimeError(
            f"All LLM providers (Hugging Face → Groq → Gemini) failed. Last error: {last_error}"
        )

    async def create_stream(
        self,
        messages: List[Any],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ):
        """Streaming version — same chain-start logic as create()."""
        max_prompt_tokens = get_settings().max_prompt_tokens

        from core.llm_config import get_llm_config
        manager = get_llm_config()

        full_chain     = manager.get_provider_chain()
        start_idx      = self._find_chain_start(full_chain)
        provider_chain = full_chain[start_idx:]

        if not provider_chain:
            raise RuntimeError("No LLM providers are configured.")

        last_error: Optional[Exception] = None

        for provider_cfg in provider_chain:
            provider_name = provider_cfg["provider"]
            # if provider_name == "huggingface" and tools:
            #     logger.info(f"⏭️ Skipping Hugging Face provider for model '{provider_cfg['model']}' because tool calling is requested and Hugging Face serverless API does not support function calling.")
            #     continue
            model_name    = provider_cfg["model"]
            api_key       = provider_cfg["api_key"]
            base_url      = provider_cfg["base_url"]
            model_info    = provider_cfg["model_info"]

            self.model       = model_name
            self._model_info = model_info
            try:
                await self._client.close()
            except Exception:
                pass
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=30.0,
                max_retries=0,
            )

            try:
                logger.info(f"🎯 [{provider_name}] Streaming with model '{model_name}'...")
                openai_messages = self._convert_messages(messages)
                openai_messages = self._prune_messages(openai_messages, max_prompt_tokens)
                converted_tools = self._convert_tools(tools)
                filtered_kwargs = self._filter_kwargs(kwargs)

                total_output_chars = 0
                async with await self._client.chat.completions.create(
                    model=model_name,
                    messages=openai_messages,
                    tools=converted_tools,
                    stream=True,
                    **filtered_kwargs,
                ) as response:
                    async for chunk in response:
                        if chunk.choices:
                            delta = chunk.choices[0].delta
                            if delta and delta.content:
                                total_output_chars += len(delta.content)
                                choice_reason = chunk.choices[0].finish_reason
                                mapped_reason = "unknown"
                                if choice_reason in ["stop", "length", "function_calls", "content_filter", "error", "unknown"]:
                                    mapped_reason = choice_reason
                                elif choice_reason == "tool_calls":
                                    mapped_reason = "function_calls"

                                yield CreateResult(
                                    finish_reason=mapped_reason,
                                    content=delta.content,
                                    usage=RequestUsage(prompt_tokens=0, completion_tokens=0),
                                    cached=False,
                                )

                estimated_completion_tokens = max(1, total_output_chars // 4)
                estimated_prompt_tokens     = self.count_tokens(openai_messages)
                self._total_input_tokens  += estimated_prompt_tokens
                self._total_output_tokens += estimated_completion_tokens
                logger.info(
                    f"[TOKEN USAGE (STREAMING)] Model: {model_name} | "
                    f"Est. Prompt: {estimated_prompt_tokens} | "
                    f"Est. Completion: {estimated_completion_tokens}"
                )
                return  # Stream succeeded

            except Exception as e:
                last_error = e
                err_str = str(e)
                status_code = getattr(e, "status_code", None)
                is_auth     = "401" in err_str or "invalid api key" in err_str.lower() or "authentication" in err_str.lower() or status_code == 401
                is_quota    = "429" in err_str or "402" in err_str or "quota" in err_str.lower() or "rate limit" in err_str.lower() or "resource_exhausted" in err_str.lower() or "credits" in err_str.lower() or status_code in [402, 429]
                is_unavail  = "connect" in err_str.lower() or "connection refused" in err_str.lower() or "timed out" in err_str.lower() or "timeout" in err_str.lower() or status_code in [500, 502, 503, 504]
                is_no_tools = "does not support tools" in err_str.lower() or "tool_use_failed" in err_str.lower() or "failed_generation" in err_str.lower() or status_code == 400
                is_too_large = "413" in err_str or "too large" in err_str.lower() or "request too large" in err_str.lower() or status_code == 413
                if is_auth or is_quota or is_unavail or is_no_tools or is_too_large:
                    is_hard_quota = is_quota and ("limit: 0" in err_str or "quota exceeded" in err_str.lower() or "credits" in err_str.lower()) and "retry" not in err_str.lower() and "delay" not in err_str.lower()
                    cooldown_dur = 0.0
                    if is_auth:
                        cooldown_dur = 300.0
                    elif is_quota:
                        cooldown_dur = 300.0 if is_hard_quota else 30.0
                    elif is_unavail:
                        cooldown_dur = 15.0
                    elif is_too_large:
                        cooldown_dur = 60.0

                    if cooldown_dur > 0:
                        try:
                            manager.set_cooldown(provider_name, model_name, cooldown_dur)
                        except Exception as exc:
                            logger.warning("Failed to set model cooldown: %s", exc)

                    logger.warning(f"⚠️ [{provider_name}] '{model_name}' stream failed ({err_str[:120]}), trying next...")
                    continue
                logger.error(f"❌ [{provider_name}] Unexpected stream error: {e}")
                raise

        raise RuntimeError(
            f"All LLM providers (Hugging Face → Groq → Gemini) failed for streaming. Last error: {last_error}"
        )

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
            await self._client.close()
        except Exception:
            pass

