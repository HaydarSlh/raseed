# Contract: Auth API (register / login / me)

fastapi-users JWT (bearer). Exact paths/fields finalized in implementation; the
behavior below is fixed.

## Endpoints

| Method | Path | Purpose | Auth |
|--------|------|---------|------|
| POST | `/auth/register` | Create an account (email + password) | none |
| POST | `/auth/jwt/login` | Exchange credentials for a bearer token | none |
| GET  | `/users/me` | Return the current authenticated user | bearer |
| (PATCH) | `/users/me` | Update own profile | bearer |

## Behavioral contract

1. **Register**: valid email + password → account created; duplicate email →
   rejected with a clear, non-revealing error (no "email exists" enumeration leak).
   *(FR-001, edge: duplicate registration)*
2. **Login**: correct credentials → a valid bearer token; wrong credentials →
   rejected, no token, uniform error. *(FR-001, FR-003)*
3. **Protected access**: a request with a valid unexpired token succeeds; missing,
   malformed, or expired token → rejected. *(FR-003, edge: missing/expired session)*
4. **Identity source**: the acting user is derived solely from the verified token;
   any `user_id`/identity field in the request body is ignored. *(FR-002, edge:
   spoofing)*
5. **No stack traces**: all error responses are structured domain errors, never raw
   traces. *(FR-012)*
6. **End-to-end**: register → login works from the frontend shell. *(FR-015,
   SC-001)*
