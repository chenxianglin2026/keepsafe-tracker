#!/bin/bash
# Check backend logs and debug the Internal Server Error
cd ~/projects/keepsafe

# Check if backend is running via uvicorn/uvicorn
ps aux | grep -E 'uvicorn|fastapi' | grep -v grep 2>&1

echo "---"
# Try to get details on why location endpoint fails
curl -s -v "http://localhost:8000/api/v1/devices/QA_DEV_002/location" -H "Authorization: Bearer $(curl -s -X POST http://localhost:8000/api/v1/users/login -H 'Content-Type: application/json' -d '{"email":"qa_test2@test.com","password":"test123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin).get("access_token",""))')" 2>&1 | head -50
