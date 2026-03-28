#!/usr/bin/env bash
#
# Configures Keycloak fine-grained permissions to allow the mcp-server client
# to perform RFC 8693 token exchange targeting the project-api client.
#
# Run this AFTER Keycloak is healthy (docker compose up -d && wait for health).
#
set -euo pipefail

KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8080}"
REALM="workshop"
ADMIN_USER="admin"
ADMIN_PASS="admin"

echo "=== Keycloak Token Exchange Setup ==="
echo "Keycloak: $KEYCLOAK_URL"
echo "Realm:    $REALM"
echo ""

# 1. Get admin token
echo "1. Getting admin access token..."
ADMIN_TOKEN=$(curl -s -X POST "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=$ADMIN_USER" \
  -d "password=$ADMIN_PASS" \
  -d "grant_type=password" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "   Done."

# 2. Get project-api client UUID
echo "2. Looking up project-api client UUID..."
PROJECT_API_ID=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$KEYCLOAK_URL/admin/realms/$REALM/clients?clientId=project-api" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
echo "   project-api UUID: $PROJECT_API_ID"

# 3. Get mcp-server client UUID
echo "3. Looking up mcp-server client UUID..."
MCP_SERVER_ID=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$KEYCLOAK_URL/admin/realms/$REALM/clients?clientId=mcp-server" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
echo "   mcp-server UUID: $MCP_SERVER_ID"

# 4. Enable fine-grained permissions on project-api
echo "4. Enabling fine-grained permissions on project-api..."
curl -s -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  "$KEYCLOAK_URL/admin/realms/$REALM/clients/$PROJECT_API_ID/management/permissions" \
  -d '{"enabled": true}' > /dev/null
echo "   Done."

# 5. Get the auto-created token-exchange permission
echo "5. Looking up token-exchange permission..."
# When permissions are enabled, Keycloak creates a "token-exchange" scope permission
# on the realm-management client's authorization. We need to find it.
MGMT_PERMISSIONS=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$KEYCLOAK_URL/admin/realms/$REALM/clients/$PROJECT_API_ID/management/permissions")
TOKEN_EXCHANGE_SCOPE_ID=$(echo "$MGMT_PERMISSIONS" | python3 -c "
import sys, json
perms = json.load(sys.stdin)
scope_perms = perms.get('scopePermissions', {})
print(scope_perms.get('token-exchange', ''))
")

if [ -z "$TOKEN_EXCHANGE_SCOPE_ID" ]; then
  echo "   ERROR: No token-exchange scope permission found. Keycloak may not have token-exchange feature enabled."
  echo "   Make sure docker-compose.yml includes: --features=token-exchange"
  exit 1
fi
echo "   token-exchange permission ID: $TOKEN_EXCHANGE_SCOPE_ID"

# 6. Get the realm-management client (where the permission policies live)
echo "6. Looking up realm-management client..."
REALM_MGMT_ID=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$KEYCLOAK_URL/admin/realms/$REALM/clients?clientId=realm-management" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
echo "   realm-management UUID: $REALM_MGMT_ID"

# 7. Create a client policy that references mcp-server
echo "7. Creating client policy for mcp-server..."
POLICY_RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  "$KEYCLOAK_URL/admin/realms/$REALM/clients/$REALM_MGMT_ID/authz/resource-server/policy/client" \
  -d "{
    \"name\": \"mcp-server-token-exchange-policy\",
    \"description\": \"Allow mcp-server to perform token exchange\",
    \"logic\": \"POSITIVE\",
    \"clients\": [\"$MCP_SERVER_ID\"]
  }" -w "\n%{http_code}")

HTTP_CODE=$(echo "$POLICY_RESPONSE" | tail -1)
POLICY_BODY=$(echo "$POLICY_RESPONSE" | head -1)

if [ "$HTTP_CODE" = "409" ]; then
  echo "   Policy already exists, looking it up..."
  POLICY_ID=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
    "$KEYCLOAK_URL/admin/realms/$REALM/clients/$REALM_MGMT_ID/authz/resource-server/policy?name=mcp-server-token-exchange-policy" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")
else
  POLICY_ID=$(echo "$POLICY_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
fi
echo "   Policy ID: $POLICY_ID"

# 8. Associate the policy with the token-exchange permission
echo "8. Associating policy with token-exchange permission..."
# Get current permission details
PERM_DETAILS=$(curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "$KEYCLOAK_URL/admin/realms/$REALM/clients/$REALM_MGMT_ID/authz/resource-server/permission/scope/$TOKEN_EXCHANGE_SCOPE_ID")

# Update it to include our policy
curl -s -X PUT -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  "$KEYCLOAK_URL/admin/realms/$REALM/clients/$REALM_MGMT_ID/authz/resource-server/permission/scope/$TOKEN_EXCHANGE_SCOPE_ID" \
  -d "$(echo "$PERM_DETAILS" | python3 -c "
import sys, json
perm = json.load(sys.stdin)
perm['policies'] = ['$POLICY_ID']
perm['decisionStrategy'] = 'AFFIRMATIVE'
print(json.dumps(perm))
")" > /dev/null
echo "   Done."

echo ""
echo "=== Token Exchange Setup Complete ==="
echo "The mcp-server client can now exchange user tokens for project-api-scoped tokens."
echo ""
echo "To test manually:"
echo "  1. Get a user token:  curl -s -X POST '$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token' \\"
echo "       -d 'client_id=mcp-client&grant_type=password&username=bob&password=bob&scope=openid tasks:read tasks:admin'"
echo "  2. Exchange it:       curl -s -X POST '$KEYCLOAK_URL/realms/$REALM/protocol/openid-connect/token' \\"
echo "       -d 'grant_type=urn:ietf:params:oauth:grant-type:token-exchange' \\"
echo "       -d 'client_id=mcp-server&client_secret=mcp-server-secret' \\"
echo "       -d 'subject_token=<TOKEN>&subject_token_type=urn:ietf:params:oauth:token-type:access_token' \\"
echo "       -d 'audience=project-api'"
