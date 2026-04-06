# System Logic & Architecture Documentation: ADM_MODULAR

## 1. The "Portero" (Gateway) Pattern
The core logic revolves around the **Portero Lifecycle**. Unlike a simple proxy, `ADM_MODULAR` intercepts the request-response cycle to perform business and security validations.

### Request Execution Flow:
1. **Dependency Injection (Security)**: `FastAPI` intercepts the `Authorization: Bearer` header.
2. **Key Validation**: The system queries the `tokens` table in SQLite. If the token is missing or a user is inactive, a `401 Unauthorized` is returned immediately.
3. **Module Routing**: The `module_id` in the URL (e.g., `/v1/chat1/...`) is validated against the internal `CHAT_MODULES` registry.
4. **Asynchronous Forwarding**: Using `httpx.AsyncClient`, the original JSON payload is forwarded to the internal service. The connection is held open (timeout 60s) to support complex medical reasoning tasks.

## 2. Integrated Accounting & Forensics
The system implements "Post-Response Accounting." This means that after the clinical service responds, the Gateway parses the response body before returning it to the user.

### Token Consumption Cycle:
- **Extraction**: The logic specifically looks for the `usage` object in the downstream response.
- **Persistence**: It asynchronously writes a new entry to the `APILog` table.
- **Aggregation**: It updates the `total_tokens_consumed` field in the `Token` record for real-time monitoring of service costs.
- **Atomicity**: The DB transaction ensures that usage is only logged if the call was successful.

## 3. Legacy Compatibility Layer
To ensure zero-downtime integration for existing clients, the system includes a **Transparent Tunnel**:
- Endpoint: `POST /medical/chat`
- Logic: This route is hardcoded to redirect all traffic to the `chat1` (General Chat) module using the standard proxying logic, allowing clients to migrate at their own pace without changing their base URL.

## 4. Administrative Intelligence
The ADM module provides the logic for:
- **Token Minting**: Programmatic generation of keys with high entropy.
- **Resource Monitoring**: The `/health` endpoint checks not only the gateway's status but also reveals the active internal modules, acting as a heartbeat for the entire network.
