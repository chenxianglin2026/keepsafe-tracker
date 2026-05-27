#!/bin/bash
# KeepSafe Backend QA Test Script
BASE="http://localhost:8000"

echo "=== 1. GET /health ==="
curl -s "$BASE/health"
echo -e "\n"

echo "=== 2. POST /api/v1/users/register ==="
curl -s -X POST "$BASE/api/v1/users/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"qa_test2@test.com","password":"test123","nickname":"QA_Tester2"}'
echo -e "\n"

echo "=== 3. POST /api/v1/users/login ==="
LOGIN=$(curl -s -X POST "$BASE/api/v1/users/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"qa_test2@test.com","password":"test123"}')
echo "$LOGIN"
TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
echo "TOKEN_EXTRACTED: ${TOKEN:0:30}..."
echo -e "\n"

if [ -z "$TOKEN" ]; then
  echo "LOGIN FAILED, trying original user..."
  LOGIN=$(curl -s -X POST "$BASE/api/v1/users/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"qa_test@test.com","password":"test123"}')
  echo "$LOGIN"
  TOKEN=$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('access_token',''))" 2>/dev/null)
  echo "TOKEN_EXTRACTED: ${TOKEN:0:30}..."
fi
echo -e "\n"

AUTH="Authorization: Bearer $TOKEN"

echo "=== 4. GET /api/v1/users/profile ==="
curl -s "$BASE/api/v1/users/profile" -H "$AUTH"
echo -e "\n"

echo "=== 5. PUT /api/v1/users/profile ==="
curl -s -X PUT "$BASE/api/v1/users/profile" -H "$AUTH" -H "Content-Type: application/json" -d '{"nickname":"QA_Updated"}'
echo -e "\n"

echo "=== 6. GET /api/v1/users/me/devices ==="
curl -s "$BASE/api/v1/users/me/devices" -H "$AUTH"
echo -e "\n"

echo "=== 7. POST /api/v1/users/me/push-token ==="
curl -s -X POST "$BASE/api/v1/users/me/push-token" -H "$AUTH" -H "Content-Type: application/json" -d '{"platform":"ios","token":"qa-push-001"}'
echo -e "\n"

echo "=== 8. POST /api/v1/devices/bind ==="
curl -s -X POST "$BASE/api/v1/devices/bind" -H "$AUTH" -H "Content-Type: application/json" -d '{"device_id":"QA_DEV_002","token":"dev-token","user_id":"'$(echo "$LOGIN" | python3 -c "import sys,json; print(json.load(sys.stdin).get('user_id',''))" 2>/dev/null)'","nickname":"QA Test"}'
echo -e "\n"

echo "=== 9. GET /api/v1/devices/QA_DEV_002/location ==="
curl -s "$BASE/api/v1/devices/QA_DEV_002/location" -H "$AUTH"
echo -e "\n"

echo "=== 10. GET /api/v1/devices/QA_DEV_002/status ==="
curl -s "$BASE/api/v1/devices/QA_DEV_002/status" -H "$AUTH"
echo -e "\n"

echo "=== 11. GET /api/v1/devices/QA_DEV_002/history ==="
curl -s "$BASE/api/v1/devices/QA_DEV_002/history?from=2026-01-01&to=2026-12-31" -H "$AUTH"
echo -e "\n"

echo "=== 12. GET /api/v1/devices/QA_DEV_002/sos/events ==="
curl -s "$BASE/api/v1/devices/QA_DEV_002/sos/events" -H "$AUTH"
echo -e "\n"

echo "=== 13. GET /api/v1/alerts/ ==="
curl -s "$BASE/api/v1/alerts/?page=1&page_size=10" -H "$AUTH"
echo -e "\n"

echo "=== 14. PUT /api/v1/alerts/read-all ==="
curl -s -X PUT "$BASE/api/v1/alerts/read-all" -H "$AUTH" -H "Content-Type: application/json"
echo -e "\n"

echo "=== 15. GET /api/v1/devices/QA_DEV_002/fences ==="
curl -s "$BASE/api/v1/devices/QA_DEV_002/fences" -H "$AUTH"
echo -e "\\n"

echo "=== 16. POST /api/v1/devices/QA_DEV_002/fences ==="
curl -s -X POST "$BASE/api/v1/devices/QA_DEV_002/fences" -H "$AUTH" -H "Content-Type: application/json" -d '{"name":"QA_Fence","lat":22.5431,"lng":114.0579,"radius":100,"type":"circle","enabled":true}'
echo -e "\n"

echo "=== ALL API TESTS COMPLETE ==="
