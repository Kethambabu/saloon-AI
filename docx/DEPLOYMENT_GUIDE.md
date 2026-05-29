# 🚀 Deployment & Implementation Guide

## Quick Deployment (5 Minutes)

### Step 1: Update Environment
```bash
# In project root, create/update .env:
GROQ_API_KEY=gsk_YOUR_ACTUAL_KEY_FROM_GROQ_CONSOLE
GROQ_MODEL=llama-3.3-70b-versatile
ENVIRONMENT=production
DEBUG=false
```

**Get GROQ_API_KEY:**
1. Go to https://console.groq.com
2. Sign up (free, no credit card)
3. Create API Key
4. Copy and paste

### Step 2: Restart Backend
```bash
# Terminal 1: Backend
cd backend
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Step 3: Verify Startup
Look for:
```
✅ LLM CONFIGURATION STARTUP DIAGNOSTICS
Primary Model: llama-3.3-70b-versatile ✅
Fallback Model: llama-3.1-8b-instant ✅
```

### Step 4: Test API
```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "message": "I want to book a haircut tomorrow at 2 PM",
    "session_id": "test-session-123",
    "chat_history": []
  }'
```

Expected: HTTP 200 with JSON response (not 500 error)

---

## Docker Deployment

### Step 1: Update Docker Compose
```yaml
# docker-compose.yml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    environment:
      GROQ_API_KEY: ${GROQ_API_KEY}
      GROQ_MODEL: llama-3.3-70b-versatile
      ENVIRONMENT: production
      DEBUG: "false"
```

### Step 2: Create .env for Docker
```bash
# Create .env in project root
GROQ_API_KEY=gsk_your_actual_key
DATABASE_URL=postgresql://user:pass@db:5432/salonai
```

### Step 3: Deploy
```bash
docker-compose up -d
docker-compose logs backend  # Watch logs
```

---

## Kubernetes Deployment

### Step 1: Create Secret
```bash
kubectl create secret generic groq-credentials \
  --from-literal=api-key=gsk_your_actual_key
```

### Step 2: Update Deployment
```yaml
# backend-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: salonai-backend
spec:
  template:
    spec:
      containers:
      - name: backend
        env:
        - name: GROQ_API_KEY
          valueFrom:
            secretKeyRef:
              name: groq-credentials
              key: api-key
        - name: GROQ_MODEL
          value: "llama-3.3-70b-versatile"
        - name: ENVIRONMENT
          value: "production"
```

### Step 3: Deploy
```bash
kubectl apply -f backend-deployment.yaml
kubectl logs deployment/salonai-backend
```

---

## Development vs Production

### Development
```bash
# .env
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
GROQ_API_KEY=gsk_your_key
GROQ_MODEL=llama-3.3-70b-versatile
```

**Features:**
- Hot reload
- Detailed logs
- Can use mock mode
- Slower (more debugging)

### Production
```bash
# .env
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=WARNING
GROQ_API_KEY=gsk_your_key
GROQ_MODEL=llama-3.3-70b-versatile
SECRET_KEY=<strong-random-key>
CORS_ORIGINS=["https://yourdomain.com"]
```

**Features:**
- Fast
- Minimal logs
- Strict validation
- Production-grade security

---

## Monitoring & Diagnostics

### Check LLM Configuration
```python
# In Python shell
from core.llm_config import get_llm_config

manager = get_llm_config()
print(f"Primary: {manager.primary_model}")
print(f"Fallback: {manager.fallback_model}")
print(f"Mock mode: {manager.is_mock_mode}")
print(f"API Key set: {bool(manager.api_key)}")
manager.validate_at_startup()
```

### Watch Startup Logs
```bash
# Start server and watch for diagnostics
uvicorn main:app --reload | grep "LLM CONFIGURATION"
```

### Monitor Errors
```bash
# Check for model errors
tail -f logs/app.log | grep -i "model\|groq\|error"
```

---

## Fallback Model Activation

### Automatic (Recommended)
- If `llama-3.3-70b-versatile` fails
- System automatically uses `llama-3.1-8b-instant`
- No manual intervention needed

### Manual (Force Fallback)
```bash
# In .env
GROQ_MODEL=llama-3.1-8b-instant
```

**When to use fallback:**
- Primary model is unavailable
- Rate limits hit
- Slow responses
- Testing

---

## Troubleshooting Deployment

### Issue: "Model not found" 404 error
```bash
# 1. Check API key is valid
GROQ_API_KEY=gsk_...  # Should start with gsk_

# 2. Verify model is supported
GROQ_MODEL=llama-3.3-70b-versatile  # Correct ✅

# 3. Restart server
kill the uvicorn process and restart
```

### Issue: Mock mode enabled
```bash
# In startup logs:
# ⚠️  MOCK MODE ENABLED - Using test API key

# Solution: Set GROQ_API_KEY
export GROQ_API_KEY=gsk_your_actual_key
# Restart server
```

### Issue: Slow responses
```bash
# Try faster fallback model
GROQ_MODEL=llama-3.1-8b-instant

# Or check Groq status
# https://status.groq.com
```

### Issue: 500 errors on /api/v1/agent/chat
```bash
# 1. Check startup logs for LLM validation
docker logs <container> | grep "LLM CONFIGURATION"

# 2. Verify both models are valid
# Primary: llama-3.3-70b-versatile ✅
# Fallback: llama-3.1-8b-instant ✅

# 3. Check application logs
docker logs <container> | grep -i error
```

---

## Health Checks

### Endpoint: `/health`
```bash
curl http://localhost:8000/health
```

Response:
```json
{
  "status": "healthy",
  "environment": "production",
  "version": "0.1.0"
}
```

### Endpoint: `/api/v1/agent/chat` (Full Test)
```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TOKEN" \
  -d '{
    "message": "Test message",
    "session_id": "health-check",
    "chat_history": []
  }'
```

Success: HTTP 200 with valid JSON  
Failure: Check logs for error details

---

## Performance Tuning

### Primary Model Performance
- **Speed:** ⭐⭐⭐⭐ (Fast)
- **Quality:** ⭐⭐⭐⭐⭐ (Excellent)
- **Use for:** Everything (default)

### Fallback Model Performance
- **Speed:** ⭐⭐⭐⭐⭐ (Fastest)
- **Quality:** ⭐⭐⭐ (Good)
- **Use for:** When speed is critical

### If Experiencing Slow Responses
1. Check Groq API status: https://status.groq.com
2. Try fallback: `GROQ_MODEL=llama-3.1-8b-instant`
3. Check network connectivity
4. Review Groq documentation for rate limits

---

## Security Checklist

- [ ] GROQ_API_KEY not in version control
- [ ] .env file in .gitignore
- [ ] Use .env.example as template
- [ ] Rotate API key periodically
- [ ] Use HTTPS in production
- [ ] Set strong SECRET_KEY
- [ ] Restrict CORS_ORIGINS
- [ ] Keep dependencies updated

---

## Rollback Plan

If something goes wrong:

### Step 1: Identify Issue
```bash
# Check logs
docker logs <container> | tail -50

# Look for:
# - "Model not found" → Invalid model name
# - "MOCK MODE" → Missing API key
# - 500 errors → Agent initialization failed
```

### Step 2: Revert Changes
```bash
# Option 1: Use previous .env
cp .env.backup .env
docker-compose restart backend

# Option 2: Use fallback model
GROQ_MODEL=llama-3.1-8b-instant
docker-compose restart backend

# Option 3: Disable agents (if critical)
ENABLE_AGENTS=false
docker-compose restart backend
```

### Step 3: Verify
```bash
curl http://localhost:8000/health  # Should be healthy
docker logs <container> | grep "LLM CONFIGURATION"  # Should show diagnostics
```

---

## Post-Deployment Verification

### 1. Startup Checks ✅
```bash
# Should see:
# 🔧 LLM CONFIGURATION STARTUP DIAGNOSTICS
# Primary Model: llama-3.3-70b-versatile ✅
# Fallback Model: llama-3.1-8b-instant ✅
```

### 2. Health Endpoint ✅
```bash
curl http://localhost:8000/health
# Response: {"status": "healthy", ...}
```

### 3. Chat Endpoint ✅
```bash
curl -X POST http://localhost:8000/api/v1/agent/chat \
  -H "Authorization: Bearer TOKEN" \
  -d '{"message": "test", "session_id": "1", "chat_history": []}'
# Response: {"success": true, "response": "...", ...}
```

### 4. Error Handling ✅
```bash
# Send invalid request
curl http://localhost:8000/api/v1/agent/chat  # Missing auth
# Response: HTTP 401 (not 500)

# API should stay running after error
curl http://localhost:8000/health
# Response: {"status": "healthy", ...}
```

### 5. Logs Verified ✅
```bash
# Check for errors
docker logs <container> | grep -i error
# Should be minimal, no model-related errors
```

---

## Success Indicators

When deployment is successful:

✅ Server starts without "Model not found" errors  
✅ Startup logs show both models valid  
✅ Health endpoint returns 200  
✅ Chat endpoint returns JSON (not 500)  
✅ Agent responds to queries  
✅ API stays running after agent errors  
✅ Logs show clear diagnostics  

---

## Next Steps

1. **Monitor:** Watch logs for first 24 hours
2. **Load Test:** Test with realistic query volume
3. **Document:** Add your specific deployment details
4. **Automate:** Set up CI/CD for future deployments
5. **Scale:** Use Docker Swarm or Kubernetes as needed

---

**Deployment Date:** May 28, 2026  
**Status:** ✅ Ready for Production
