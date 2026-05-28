# SalonAI LLM Configuration & Error Resolution Guide

## 🎯 Overview

This document explains the LLM configuration system for SalonAI, how to fix model errors, and how to deploy safely to production.

---

## ❌ Error: Model Not Found / Model Decommissioned

### Symptoms
```
openai.NotFoundError: Error code: 404 - {
  'error': {
    'message': 'The model `llama-3.1-405b` does not exist or you do not have access to it.',
    'type': 'invalid_request_error',
    'code': 'model_not_found'
  }
}
```

### Root Cause
- **llama-3.1-405b** was decommissioned by Groq
- **llama-3.3-70b-specdec** was decommissioned by Groq  
- Old configuration had hardcoded invalid model names

### ✅ Solution (Applied)

All agent files have been updated to use **`llama-3.3-70b-versatile`** - a stable, currently supported Groq model.

---

## 🏗️ New Architecture: Centralized LLM Configuration

### Before (Problematic)
Each agent file had hardcoded model names:
```python
# ❌ Bad: Hardcoded, duplicated in 5 files
self.model_client = OpenAIChatCompletionClient(
    model="llama-3.1-405b",  # INVALID MODEL!
    api_key=groq_key,
    base_url="https://api.groq.com/openai/v1"
)
```

**Problems:**
- Updating model required changes in 5 files
- No validation of model support
- No fallback logic
- No startup diagnostics

### After (Fixed)
New centralized configuration system: `core/llm_config.py`

```python
# ✅ Good: Single source of truth
llm_config = get_llm_config()
config = llm_config.get_config()
self.model_client = OpenAIChatCompletionClient(**config)
```

**Benefits:**
- ✅ Update model in one place
- ✅ Automatic validation
- ✅ Fallback models when primary fails
- ✅ Startup diagnostics
- ✅ Environment variable support
- ✅ Production-grade error handling

---

## 📋 New Module: `core/llm_config.py`

### Key Features

#### 1. Model Enum (Validation)
```python
class GroqModel(str, Enum):
    LLAMA_3_3_70B_VERSATILE = "llama-3.3-70b-versatile"  # PRIMARY
    LLAMA_3_1_8B_INSTANT = "llama-3.1-8b-instant"        # FALLBACK
    MIXTRAL_8X7B = "mixtral-8x7b-32768"                  # ALTERNATIVE
```

**What it does:**
- Only allows validated models
- Easy to add new models
- Self-documenting code

#### 2. LLMConfigManager (Orchestration)
```python
manager = get_llm_config()

# Get configuration
config = manager.get_config()  # Uses primary model
config = manager.get_config(use_fallback=True)  # Uses fallback

# Validation
is_valid = manager.validate_at_startup()

# Diagnostics
manager.print_diagnostics()
```

**What it does:**
- Loads API key from settings or environment
- Validates models exist
- Provides fallback logic
- Logs startup diagnostics

#### 3. Startup Validation
Automatically runs when the API starts:
```
✅ LLM CONFIGURATION STARTUP DIAGNOSTICS
Environment: development
Provider: Groq (https://groq.com)
Base URL: https://api.groq.com/openai/v1
Primary Model: llama-3.3-70b-versatile ✅
Fallback Model: llama-3.1-8b-instant ✅
Supported Models: llama-3.3-70b-versatile, llama-3.1-8b-instant, mixtral-8x7b-32768
```

---

## 🔧 Configuration Methods

### Method 1: Environment Variable (Recommended)
```bash
# .env file
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### Method 2: Settings Configuration
Edit `core/config.py`:
```python
groq_api_key: Optional[str] = Field(default=None, alias="GROQ_API_KEY")
```

### Method 3: Programmatic Override
```python
from core.llm_config import get_llm_config

config_manager = get_llm_config()
config = config_manager.get_config(use_fallback=True)  # Switch to fallback
```

---

## 📊 Model Selection Guide

### Primary Model: `llama-3.3-70b-versatile`
**Use for:** Everything by default
- ✅ Excellent reasoning
- ✅ Good code generation
- ✅ Fast inference
- ✅ Supports function calling
- ✅ Supports JSON output
- ✅ Best Groq model for agents

### Fallback Model: `llama-3.1-8b-instant`
**Use when:** Primary model is unavailable or rates are exceeded
- ✅ Lightweight, super fast
- ✅ Supports function calling
- ✅ Supports JSON output
- ❌ Smaller context window
- ❌ Less capable reasoning

### Alternative: `mixtral-8x7b-32768`
**Use for:** Complex reasoning tasks requiring larger context
- ✅ Very large context (32K tokens)
- ✅ Mixture of Experts architecture
- ✅ Good reasoning capability
- ⚠️ Can be slower

---

## 🚀 Updated Agent Files

All 5 agents have been refactored to use the new centralized config:

### 1. `backend/agents/receptionist_agent.py`
```python
# OLD: Hardcoded model
self.model_client = OpenAIChatCompletionClient(model="llama-3.1-405b", ...)

# NEW: Centralized config
llm_config = get_llm_config()
config = llm_config.get_config()
self.model_client = OpenAIChatCompletionClient(**config)
```

### 2. `backend/agents/bi_agent.py`
✅ Updated to use centralized config

### 3. `backend/agents/lead_followup_agent.py`
✅ Updated to use centralized config

### 4. `backend/agents/reputation_agent.py`
✅ Updated to use centralized config

### 5. `backend/agents/orchestrator.py`
✅ Updated to use centralized config via `_create_model_client()` factory

---

## 🛡️ Error Handling Improvements

### Before (Crashes API)
```python
# ❌ Old: HTTPException crashes the whole endpoint
try:
    response = agent.process()
    if not response.get("success"):
        raise HTTPException(status_code=500, detail=error)
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

### After (Graceful Degradation)
```python
# ✅ New: Returns structured JSON, never crashes API
try:
    response = agent.process()
    if not response.get("success"):
        return ChatResponse(
            success=False,
            response="Error message for user",
            agent_name="Clara"
        )
except Exception as e:
    logger.error(..., exc_info=True)
    return ChatResponse(
        success=False,
        response="An unexpected error occurred. Please try again.",
        agent_name="Clara"
    )
```

**Result:** API server stays up, returns proper JSON errors

---

## 🔌 API Startup Flow

### What Happens on Startup
```
1. main.py loads
   ↓
2. lifespan() context manager enters (startup phase)
   ↓
3. validate_llm_startup() runs
   ↓
4. LLMConfigManager initialized
   ↓
5. Validates primary & fallback models
   ↓
6. Prints diagnostics to logs
   ↓
7. API ready to accept requests
```

### View Startup Logs
```bash
# When you start the server
uvicorn main:app --reload

# You'll see:
==============================================================================
🔧 LLM CONFIGURATION STARTUP DIAGNOSTICS
==============================================================================
Environment: development
Provider: Groq (https://groq.com)
Primary Model: llama-3.3-70b-versatile ✅
Fallback Model: llama-3.1-8b-instant ✅
==============================================================================
```

---

## 📝 Environment Variable Template

Copy this to your `.env`:
```bash
# REQUIRED
GROQ_API_KEY=your-actual-groq-api-key

# OPTIONAL - Override default model
GROQ_MODEL=llama-3.3-70b-versatile

# DATABASE
DATABASE_URL=postgresql://user:pass@localhost:5432/salonai

# SERVER
DEBUG=true
ENVIRONMENT=development
LOG_LEVEL=INFO
```

**Get Your GROQ_API_KEY:**
1. Visit https://console.groq.com
2. Sign up (free, no credit card required)
3. Go to API Keys
4. Create new key
5. Copy and paste into `.env`

---

## 🧪 Testing the Configuration

### Test 1: Check Model Validation
```python
from core.llm_config import GroqModel, get_llm_config

# List all supported models
print(GroqModel.list_supported())
# Output: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant', 'mixtral-8x7b-32768']

# Validate a model
print(GroqModel.validate("llama-3.3-70b-versatile"))  # True
print(GroqModel.validate("invalid-model"))             # False
```

### Test 2: Check Configuration Manager
```python
from core.llm_config import get_llm_config

manager = get_llm_config()
print(manager.primary_model)    # llama-3.3-70b-versatile
print(manager.fallback_model)   # llama-3.1-8b-instant
print(manager.is_mock_mode)     # False (if API key is set)
```

### Test 3: Get Config
```python
config = manager.get_config()
print(config["model"])          # llama-3.3-70b-versatile
print(config["base_url"])       # https://api.groq.com/openai/v1
print(config["api_key"])        # Your key
print(config["model_info"])     # Model capabilities dict
```

### Test 4: Chat Endpoint
```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "I want to book a haircut",
    "session_id": "test-session",
    "chat_history": []
  }'
```

Expected response:
```json
{
  "success": true,
  "session_id": "test-session",
  "response": "...",
  "agent_name": "Clara"
}
```

---

## 🚨 Troubleshooting

### Issue: Model Not Found Error
**Symptoms:**
- Error code: 404 or 400
- Message contains "does not exist"

**Solution:**
1. Check `.env` has `GROQ_API_KEY` set
2. Check `GROQ_MODEL` is in supported list
3. Check you're not using deprecated models:
   - ❌ llama-3.1-405b (decommissioned)
   - ❌ llama-3.3-70b-specdec (decommissioned)
4. Update to: `llama-3.3-70b-versatile`

### Issue: No API Key Found
**Symptoms:**
- Logs show "⚠️  MOCK MODE ENABLED"
- Agent responses are empty

**Solution:**
1. Create `.env` file in project root
2. Add: `GROQ_API_KEY=your-actual-key`
3. Restart server: `Ctrl+C` then `uvicorn main:app --reload`

### Issue: API Crashes on Chat Request
**Symptoms:**
- 500 Internal Server Error
- Agent exception in logs

**Solution:**
1. Check startup logs for LLM diagnostics
2. Verify GROQ_API_KEY is valid
3. Check primary and fallback models are supported
4. Review agent error logs with full traceback

### Issue: Slow Responses
**Symptoms:**
- Chat requests take 10+ seconds

**Solution:**
1. Check network connectivity to Groq API
2. Try fallback model: `GROQ_MODEL=llama-3.1-8b-instant`
3. Check Groq status page: https://status.groq.com

---

## 📚 File Structure

```
backend/
├── core/
│   ├── config.py              # Settings & config
│   ├── llm_config.py          # ✨ NEW: LLM configuration system
│   ├── logging.py             # Logging setup
│   └── security.py            # Auth utilities
├── agents/
│   ├── receptionist_agent.py  # ✅ Updated: Uses centralized config
│   ├── bi_agent.py            # ✅ Updated: Uses centralized config
│   ├── lead_followup_agent.py # ✅ Updated: Uses centralized config
│   ├── reputation_agent.py    # ✅ Updated: Uses centralized config
│   ├── orchestrator.py        # ✅ Updated: Uses centralized config
│   └── __init__.py
├── api/
│   └── routes/
│       └── agent_routes.py    # ✅ Updated: Better error handling
├── main.py                     # ✅ Updated: Startup diagnostics
└── ...

.env.example                    # ✨ NEW: Template with GROQ settings
```

---

## 🎓 Key Concepts

### 1. Centralization
**Why:** Instead of hardcoding config in each agent file, we have one source of truth that all agents use.

### 2. Validation
**Why:** Instead of using random model names, we validate that models are currently supported by Groq.

### 3. Fallback Logic
**Why:** If the primary model fails, we automatically try the fallback model instead of crashing.

### 4. Startup Diagnostics
**Why:** At app startup, we validate the LLM configuration and print status so you can see any issues immediately.

### 5. Graceful Degradation
**Why:** When an agent fails, we return a structured JSON error response instead of crashing the entire API server.

---

## 🔒 Security Notes

### API Key Handling
- ✅ Never commit `.env` files
- ✅ Use `.env.example` as template
- ✅ Keep `GROQ_API_KEY` in environment only
- ✅ Rotate keys periodically in production

### Production Checklist
- [ ] Set `ENVIRONMENT=production`
- [ ] Set `DEBUG=false`
- [ ] Use strong `SECRET_KEY` (generate with `openssl rand -hex 32`)
- [ ] Set proper `CORS_ORIGINS`
- [ ] Use HTTPS only
- [ ] Keep `GROQ_API_KEY` in secret manager (not version control)
- [ ] Use appropriate `LOG_LEVEL` (WARNING or ERROR)
- [ ] Test fallback model works before deployment

---

## 📞 Getting Help

### Groq Support
- API Status: https://status.groq.com
- Documentation: https://console.groq.com/docs/models
- API Reference: https://console.groq.com/docs/api-reference
- Community: https://discord.gg/groq

### Project Issues
- Check logs: `tail -f logs/app.log`
- Enable debug: `DEBUG=true` in `.env`
- Check startup diagnostics: Look for "LLM CONFIGURATION STARTUP DIAGNOSTICS"
- Review error handling: `/api/v1/agent/chat` returns structured JSON

---

## ✅ Summary of Changes

### Files Modified
1. ✅ `core/llm_config.py` - NEW: Centralized configuration system
2. ✅ `core/config.py` - Already had GROQ_API_KEY
3. ✅ `backend/main.py` - Added startup validation
4. ✅ `backend/agents/receptionist_agent.py` - Use centralized config
5. ✅ `backend/agents/bi_agent.py` - Use centralized config
6. ✅ `backend/agents/lead_followup_agent.py` - Use centralized config
7. ✅ `backend/agents/reputation_agent.py` - Use centralized config
8. ✅ `backend/agents/orchestrator.py` - Use centralized config
9. ✅ `backend/api/routes/agent_routes.py` - Better error handling
10. ✅ `.env.example` - NEW: Template with all Groq settings

### Models Updated
- ❌ Removed: `llama-3.1-405b` (decommissioned)
- ❌ Removed: `llama-3.3-70b-specdec` (decommissioned)
- ✅ Added: `llama-3.3-70b-versatile` (PRIMARY)
- ✅ Added: `llama-3.1-8b-instant` (FALLBACK)
- ✅ Added: `mixtral-8x7b-32768` (ALTERNATIVE)

### Error Handling
- ✅ API no longer crashes on agent failures
- ✅ Graceful degradation with fallback models
- ✅ Structured JSON error responses
- ✅ Full error logging with tracebacks
- ✅ Startup validation with diagnostics

---

**Last Updated:** May 28, 2026  
**Status:** ✅ Production Ready
