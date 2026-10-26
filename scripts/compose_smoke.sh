#!/usr/bin/env bash
# Smoke test for the Docker Compose stack. Run after `docker compose up -d --build --wait`.
# Checks through the web server (port 3000, like a browser): health, front end, login, Ask TARA, and a CSV upload processed by the Celery worker.
set -euo pipefail
WEB="${WEB:-http://localhost:3000}"
API="${API:-http://localhost:8000}"
J=$(mktemp)
H=(-H "X-Requested-With: IntelliMetrics" -H "Content-Type: application/json")
ok() { echo "PASS $*"; }
fail() { echo "FAIL $*"; exit 1; }

curl -fsS "$API/health" | grep -q '"ok"' && ok "API health" || fail "API health"
curl -fsS "$WEB/" | grep -qi "<div id=\"root\"" && ok "front end served by Nginx" || fail "front end"

curl -fsS -c "$J" "${H[@]}" -d '{"email":"business@intellimetrics.demo","password":"Business@12345"}' "$WEB/api/auth/login" | grep -q '"business_user"' && ok "login through Nginx (demo data was seeded)" || fail "login"

ANS=$(curl -fsS -b "$J" "${H[@]}" -d '{"question":"Which 5 states had the highest sales this year?"}' "$WEB/api/chat/ask")
echo "$ANS" | grep -q '"kind":"answer"' && echo "$ANS" | grep -q '₹' && ok "Ask TARA returns a rupee answer from the data" || fail "Ask TARA: $ANS"

# upload a small CSV as the analyst and wait for the Celery worker to finish it
curl -fsS -c "$J" "${H[@]}" -d '{"email":"analyst@intellimetrics.demo","password":"Analyst@12345"}' "$WEB/api/auth/login" >/dev/null
printf 'city,amount\nMumbai,100\nDelhi,250\nChennai,75\n' > /tmp/smoke.csv
UP=$(curl -fsS -b "$J" -H "X-Requested-With: IntelliMetrics" -F "file=@/tmp/smoke.csv;type=text/csv" "$WEB/api/datasets/upload")
ID=$(echo "$UP" | python3 -c 'import json,sys; print(json.load(sys.stdin)["dataset"]["id"])')
for i in $(seq 1 40); do
  ST=$(curl -fsS -b "$J" "$WEB/api/datasets/$ID" | python3 -c 'import json,sys; d=json.load(sys.stdin); d=d.get("dataset",d); print(d["status"])')
  [ "$ST" = "ready" ] && break
  [ "$ST" = "failed" ] && fail "upload processing failed"
  sleep 3
done
[ "$ST" = "ready" ] && ok "CSV upload processed by the Celery worker (status ready)" || fail "upload stuck at $ST"
echo "All Compose smoke checks passed."
