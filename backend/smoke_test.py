"""Quick smoke test for all new backend endpoints."""
import requests, json, sys

base = "http://localhost:8000"
results = {}

# 1. Docs
try:
    r = requests.get(f"{base}/docs", timeout=5)
    results["GET /docs"] = f"{r.status_code}"
except Exception as e:
    results["GET /docs"] = str(e)

# 2. Register
try:
    r = requests.post(f"{base}/auth/register", json={"email": "test@smoke.com", "password": "Pass1234!", "name": "SmokeUser"}, timeout=5)
    results["POST /auth/register"] = f"{r.status_code} {r.text[:120]}"
    # 409 = already exists from previous run, still a pass
    if r.status_code == 409:
        results["POST /auth/register"] = "409 (already exists — OK)"
except Exception as e:
    results["POST /auth/register"] = str(e)

# 3. Login
token = None
try:
    r = requests.post(f"{base}/auth/login", json={"email": "test@smoke.com", "password": "Pass1234!"}, timeout=5)
    results["POST /auth/login"] = f"{r.status_code}"
    if r.status_code == 200:
        token = r.json().get("access_token")
        results["POST /auth/login"] += " (token obtained)"
except Exception as e:
    results["POST /auth/login"] = str(e)

headers = {"Authorization": f"Bearer {token}"} if token else {}

# 4. Create workspace
ws_id = None
try:
    r = requests.post(f"{base}/workspaces/", json={"name": "SmokeWS", "description": "test"}, headers=headers, timeout=5)
    results["POST /workspaces/"] = f"{r.status_code} {r.text[:120]}"
    if r.status_code in (200, 201):
        ws_id = r.json().get("id")
except Exception as e:
    results["POST /workspaces/"] = str(e)

# 5. List workspaces
try:
    r = requests.get(f"{base}/workspaces/", headers=headers, timeout=5)
    results["GET /workspaces/"] = f"{r.status_code} count={len(r.json())}"
except Exception as e:
    results["GET /workspaces/"] = str(e)

# 6. Create channel
ch_id = None
if ws_id:
    try:
        r = requests.post(f"{base}/workspaces/{ws_id}/channels", json={"name": "general"}, headers=headers, timeout=5)
        results["POST /ws/{id}/channels"] = f"{r.status_code} {r.text[:120]}"
        if r.status_code in (200, 201):
            ch_id = r.json().get("id")
    except Exception as e:
        results["POST /ws/{id}/channels"] = str(e)

# 7. Send message
if ch_id:
    try:
        r = requests.post(f"{base}/messages/", json={"channel_id": ch_id, "content": "Hello from smoke test"}, headers=headers, timeout=15)
        results["POST /messages/"] = f"{r.status_code} {r.text[:200]}"
    except Exception as e:
        results["POST /messages/"] = str(e)

# 8. Get tasks
try:
    r = requests.get(f"{base}/tasks/", headers=headers, timeout=5)
    results["GET /tasks/"] = f"{r.status_code}"
except Exception as e:
    results["GET /tasks/"] = str(e)

# 9. Dashboard
if ws_id:
    try:
        r = requests.get(f"{base}/dashboard?workspace_id={ws_id}", headers=headers, timeout=5)
        results["GET /dashboard"] = f"{r.status_code}"
    except Exception as e:
        results["GET /dashboard"] = str(e)

# 10. Risk
if ws_id:
    try:
        r = requests.get(f"{base}/risk/workspace/{ws_id}", headers=headers, timeout=10)
        results["GET /risk/workspace/{id}"] = f"{r.status_code}"
    except Exception as e:
        results["GET /risk/workspace/{id}"] = str(e)

print()
print("=" * 60)
print("  SMOKE TEST RESULTS")
print("=" * 60)
all_pass = True
for k, v in results.items():
    ok = v.startswith("200") or v.startswith("201") or "OK" in v
    status = "PASS" if ok else "FAIL"
    if not ok:
        all_pass = False
    print(f"  [{status:4s}] {k:30s} -> {v}")
print("=" * 60)
sys.exit(0 if all_pass else 1)
