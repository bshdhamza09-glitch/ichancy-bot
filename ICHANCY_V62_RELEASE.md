# EL SHEIKH V62 — documented 201 session expiry fix

## Root cause status
- Confirmed client bug: the API documentation shows HTTP 201 / result `"ex"` for invalid access tokens; V61 mistakenly treated this as successful application data. Now it triggers token renewal for **read-only** operations, never automatic replay of financial actions or player registration.
- HTTP 403 HTML at `signin` remains a confirmed upstream refusal, not an expired token. Refresh cannot repair a refusal before initial authentication. `CF-Ray` identifies the request but by itself does not conclusively prove whether the origin or Cloudflare generated 403.
- Additional diagnostics distinguish explicit Cloudflare challenge markers from unknown-source 403, without reading or logging secrets.
- No manual account creation and no requests forwarded to admins.

## Run
- Railway variables: ICHANCY_API_BASE_URL=https://agents.ichancy.com, ICHANCY_CASHIER_USERNAME, ICHANCY_CASHIER_PASSWORD, ICHANCY_AGENT_ID=2836401.
- Persist ICHANCY_TOKEN_PATH and DATABASE_PATH on a Railway volume, run **one worker replica** because only one valid token pair exists per agent.
- After deploying, use `/ichancy_check` from admin account to run an API *read-only* check; do not send sensitive credentials in chat.
- Server-side 403 needs an officially authorized API route or allowance from Ichancy. Neither copying cookies nor forging browser fingerprints is a durable/approved fix.

## Verification
- `python -m unittest discover -s tests -v` includes mocked 201, 403, and no-duplicate-mutation regressions.
- No valid Ichancy login/token or Railway environment is accessible in this test environment; actual API success not verified.

## Optional browser-only endpoint diagnostic (no real secrets)
On the already authenticated `https://agents.ichancy.com` page, open DevTools Console and run:

```javascript
fetch('/global/api/UserApi/refreshToken', {
  method: 'POST',
  headers: {'Content-Type':'application/json', 'Accept':'application/json'},
  body: JSON.stringify({refreshToken:'INVALID_TEST_TOKEN_ONLY'})
}).then(async r => console.log('HTTP', r.status, 'TYPE', r.headers.get('content-type')))
  .catch(e => console.log('Network error', e.name));
```

- Documented invalid refresh tokens should return a structured JSON rejection (often HTTP 201), not create a session or invalidate an existing valid token.
- JSON proves the documented UserApi route is reachable from your **browser**, but it does not prove Railway is allowed.
- HTML 403 on this harmless fake-token probe points to a route-level policy or protection issue even in the browser.
- **Do not share browser cookies, Authorization, access or refresh tokens, or HAR files.**
