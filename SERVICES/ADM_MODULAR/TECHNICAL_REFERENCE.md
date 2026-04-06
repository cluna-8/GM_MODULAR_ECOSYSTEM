# Technical Reference Guide: ADM_MODULAR

## 1. System Architecture
`ADM_MODULAR` acts as the **Central Gateway (Portero)** and Administrative Hub for the GoMedisys ecosystem. It is built as an asynchronous reverse proxy that manages authentication, authorization, and unified accounting (consumption tracking) for all underlying clinical microservices.

## 2. Security Tier & Protocols

### 2.1. Authentication (AuthN)
- **Mechanism**: Bearer Token Authentication.
- **API Keys**: Custom tokens with the `hcg_` prefix.
- **Entropy**: Generated using `secrets.token_urlsafe(32)`, providing 256 bits of entropy.
- **Hashing**: Passwords (used for the Admin Panel) are hashed using `bcrypt` (Passlib context) with a standard work factor, ensuring protection against rainbow tables and brute force.

### 2.2. Authorization (AuthZ)
- **Role-Based Access Control (RBAC)**: Supports `admin`, `user`, and `monitor` roles.
- **Validation Logic**: Implemented as a FastAPI `Depends` dependency (`validate_api_key`) that performs a real-time database look-up on Every incoming request.

### 2.3. Identity & Session Management
- **Protocol**: JSON Web Tokens (JWT).
- **Algorithm**: `HS256` (HMAC with SHA-256).
- **Lifecycle**: Admin sessions expire after 24 hours (`ACCESS_TOKEN_EXPIRE_MINUTES = 1440`).

## 3. Database Schema (SQLite/SQLAlchemy)

The system manages three primary entities in `modular_gateway.db`:

- **User Table**: Stores administrative identities and roles.
- **Token Table**: Maps API Keys to users. Includes `total_tokens_consumed` as a cumulative counter for LLM billing/monitoring.
- **APILog Table**: Forensic registry of every interaction.
  - Fields: `token_id`, `endpoint`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `timestamp`.

## 4. Software Stack
- **Framework**: FastAPI (Asynchronous execution).
- **ORM**: SQLAlchemy 2.0.
- **Networking**: `httpx` (Async HTTP Client for proxying).
- **Security**: `python-jose` (JWT), `passlib[bcrypt]` (Hashing).

## 5. Module Registry
The gateway maintains a static registry (expandable via Environment Variables) of clinical modules:
- `chat1`: General Clinical Specialist (`gm-general-chat`)
- `chat2`: Clinical Summary (`gm-ch-summary`)
- `chat3`: Voice-to-JSON (`gm-voice`)
- `chat4`: Diagnosis Agent (`gm-diagnosis`)
