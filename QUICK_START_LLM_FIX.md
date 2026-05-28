# ⚡ QUICK START - Fixed Model Configuration

## 🎯 What Was Fixed

Your API was crashing because agents were trying to use:
- ❌ `llama-3.1-405b` (decommissioned by Groq)
- ❌ `llama-3.3-70b-specdec` (decommissioned by Groq)

Now they use:
- ✅ `llama-3.3-70b-versatile` (stable, supported)

---

## 🚀 Get Running in 2 Minutes

### Step 1: Set Your Groq API Key

```bash
# In your .env file:
GROQ_API_KEY=gsk_your_actual_key_from_groq_console
```

Get your free key: https://console.groq.com

### Step 2: Restart Your Server

```bash
# Kill current server (Ctrl+C)
# Then restart:
cd backend
uvicorn main:app --reload
```

You should see:
```
==============================================================================
🔧 LLM CONFIGURATION STARTUP DIAGNOSTICS
==============================================================================
✅ Primary Model: llama-3.3-70b-versatile
✅ Fallback Model: llama-3.1-8b-instant
==============================================================================
```

### Step 3: Test the Chat Endpoint

```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "I want to book a haircut tomorrow",
    "session_id": "test-123",
    "chat_history": []
  }'
```

---

## 📋 What Changed

### New File
- `backend/core/llm_config.py` - Centralized LLM configuration

### Updated Files (5 agents)
- `backend/agents/receptionist_agent.py`
- `backend/agents/bi_agent.py`
- `backend/agents/lead_followup_agent.py`
- `backend/agents/reputation_agent.py`
- `backend/agents/orchestrator.py`

### Updated Files (API & startup)
- `backend/main.py` - Added LLM validation at startup
- `backend/api/routes/agent_routes.py` - Better error handling

### New Files
- `.env.example` - Template with all settings
- `docx/LLM_CONFIGURATION_GUIDE.md` - Complete documentation

---

## 🔑 Key Improvements

| Before | After |
|--------|-------|
| ❌ Hardcoded invalid models | ✅ Centralized valid models |
| ❌ No fallback logic | ✅ Automatic fallback to llama-3.1-8b |
| ❌ API crashes on errors | ✅ Graceful error responses |
| ❌ No startup validation | ✅ Diagnostics at startup |
| ❌ Duplicate config in 5 files | ✅ Single source of truth |

---

## ✅ Checklist

- [ ] Add `GROQ_API_KEY` to your `.env`
- [ ] Restart the server
- [ ] See "✅ LLM CONFIGURATION STARTUP DIAGNOSTICS" in logs
- [ ] Test `/api/v1/agent/chat` endpoint
- [ ] Verify response is JSON (no 500 errors)

---

## 🆘 Troubleshooting

**Q: Still getting "model not found" error?**
A: Make sure your GROQ_API_KEY is correct. Get it from https://console.groq.com

**Q: API still crashes?**
A: Check startup logs for "LLM CONFIGURATION STARTUP DIAGNOSTICS". If it shows ❌, the model is invalid.

**Q: Slow responses?**
A: Try the fallback: Add `GROQ_MODEL=llama-3.1-8b-instant` to `.env`

**Q: More detailed help?**
A: Read `docx/LLM_CONFIGURATION_GUIDE.md`

---

## 📊 Model Comparison

| Model | Speed | Quality | Use Case |
|-------|-------|---------|----------|
| **llama-3.3-70b-versatile** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Default (everything) |
| **llama-3.1-8b-instant** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Fallback (fast) |
| **mixtral-8x7b-32768** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | Complex tasks |

---

**Status:** ✅ Production Ready  
**Last Updated:** May 28, 2026
