# Anti-Patterns to Refuse or Rewrite

This file lists code patterns that look reasonable but are wrong. Read it before generating any auth, validation, or security-sensitive code. When a user request leads you toward one of these, push back with the alternative shown.

The skill's main `SKILL.md` has a short summary table. This file is the detailed version with full examples and rationale.

---

## 1. JWT decode without algorithm pinning

```python
# WRONG
payload = jwt.decode(token, secret)
# WRONG (singular `algorithm` is ignored on decode in some libraries)
payload = jwt.decode(token, secret, algorithm="HS256")
```

```python
# RIGHT
payload = jwt.decode(token, secret, algorithms=["HS256"])
```

**Why**: Without `algorithms`, the library may honor whatever's in the token header — including `"none"` (no signature) or `"HS256"` when the server expects `"RS256"` (signing key confusion). Both lead to forged tokens being accepted.

## 2. CORS with wildcard + credentials

```python
# WRONG
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
)
```

```python
# RIGHT
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
)
```

**Why**: Browsers reject `Access-Control-Allow-Origin: *` with credentials, but this combo signals a misunderstanding. If a developer "fixes" it by reflecting `Origin` back, you've built a CSRF amplifier.

## 3. Storing tokens in localStorage

```typescript
// WRONG
localStorage.setItem("token", accessToken);
const token = localStorage.getItem("token");
```

```typescript
// RIGHT — access token in React state, refresh in httpOnly cookie set by backend
const { accessToken } = useAuth();
```

**Why**: Any XSS payload — your own code, a malicious npm package, an injected ad script — reads localStorage. HttpOnly cookies are invisible to JS.

If a user says "I need to persist login across page reloads," the answer is the refresh cookie restoring the access token on mount, not localStorage.

## 4. SQL via string formatting

```python
# WRONG
await db.execute(text(f"SELECT * FROM users WHERE email = '{email}'"))
await db.execute(text("SELECT * FROM users WHERE email = '{}'".format(email)))
await db.execute(text("SELECT * FROM users WHERE email = '" + email + "'"))
```

```python
# RIGHT
stmt = select(User).where(User.email == email)
# or
stmt = text("SELECT * FROM users WHERE email = :email").bindparams(email=email)
```

**Why**: SQL injection. There is no acceptable reason to interpolate user input into a SQL string.

## 5. Returning raw exception details

```python
# WRONG
try:
    user = process_payment(...)
except Exception as e:
    return {"error": str(e)}
```

```python
# RIGHT
try:
    user = process_payment(...)
except PaymentDeclined as e:
    return JSONResponse(status_code=402, content={"detail": "Payment declined"})
except Exception as e:
    correlation_id = uuid.uuid4().hex
    logger.exception("Payment processing failed", extra={"correlation_id": correlation_id})
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal error", "correlation_id": correlation_id},
    )
```

**Why**: `str(e)` leaks paths, lib versions, sometimes credentials. Stack traces give attackers structural information about the app.

## 6. Enumeration-enabling responses

```python
# WRONG — different responses reveal whether email exists
@router.post("/login")
async def login(body: LoginRequest):
    user = await get_user(body.email)
    if not user:
        raise HTTPException(404, "No account with this email")
    if not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Wrong password")
    ...

# WRONG — password reset confirms email existence
@router.post("/password-reset")
async def reset(body: ResetRequest):
    user = await get_user(body.email)
    if not user:
        raise HTTPException(404, "Email not registered")
    ...
```

```python
# RIGHT — identical response shape
@router.post("/login")
async def login(body: LoginRequest):
    user = await get_user(body.email)
    if not user or not verify_password(body.password, user.password_hash):
        # Run a dummy verify if user is None to keep timing similar
        if not user:
            await bcrypt_dummy_verify()
        raise HTTPException(401, "Invalid credentials")
    ...

@router.post("/password-reset", status_code=204)
async def reset(body: ResetRequest):
    user = await get_user(body.email)
    if user:
        await send_reset_email(user)
    else:
        await enqueue_noop()  # equalize timing
    return  # 204 either way
```

**Why**: Account enumeration is the prerequisite for credential stuffing campaigns. Don't help.

## 7. Role checks inline in handlers

```python
# WRONG
@router.delete("/projects/{id}")
async def delete_project(id: str, user=Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(403)
    ...
```

```python
# RIGHT
@router.delete("/projects/{id}")
async def delete_project(id: str, _: User = Depends(require_role("admin"))):
    ...
```

**Why**: Centralizing through `require_role` makes auth checks (a) consistent, (b) audit-loggable in one place, (c) immune to copy-paste drift, and (d) visible in the route signature so reviewers can see "this is admin-only" at a glance.

## 8. Logging request bodies

```python
# WRONG
logger.info(f"Login attempt: {request_body}")
logger.debug(f"User data: {user.__dict__}")
```

```python
# RIGHT
logger.info("Login attempt", extra={"email_hash": sha256(email), "ip": ip})
logger.debug("User context", extra={"user_id": user.id, "role": user.role})
```

**Why**: Request bodies and full model dumps contain passwords, tokens, PII. Logs end up in many places (files, log aggregators, screenshots). Log specific safe fields only.

## 9. Shell with user input

```python
# WRONG
os.system(f"convert {filename} -resize 800x output.jpg")
subprocess.run(f"ffmpeg -i {user_file} out.mp4", shell=True)
```

```python
# RIGHT
subprocess.run(
    ["ffmpeg", "-i", validated_path, "out.mp4"],
    shell=False,
    check=True,
)
# or use a library
from PIL import Image
Image.open(validated_path).resize((800, 600)).save("output.jpg")
```

**Why**: `shell=True` plus interpolation gives an attacker who controls any of those values arbitrary command execution. `;`, `&&`, `$()`, backticks all work.

## 10. Path construction from user input

```python
# WRONG
open(f"/uploads/{user_filename}")
open(f"/data/{user_id}/../other_user/file.txt")  # path traversal works
```

```python
# RIGHT
storage_key = f"uploads/{user.id}/{uuid.uuid4().hex}{validated_extension}"
# Never let user-supplied name appear in a filesystem path
```

**Why**: `..` traversal lets attackers read or write outside the intended directory. Even with sanitization, the safest pattern is to discard the user-supplied name entirely.

## 11. Disabling TLS verification

```python
# WRONG
requests.get(url, verify=False)
httpx.get(url, verify=False)
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
```

```python
# RIGHT
# Fix the cert. If a corporate CA, install it. If self-signed, pin the cert:
requests.get(url, verify="/path/to/ca-bundle.pem")
```

**Why**: Disables MITM defense entirely. A `verify=False` line in production is a silent open door.

## 12. Hardcoded secrets

```python
# WRONG
JWT_SECRET = "change-me-in-production"
OPENAI_API_KEY = "sk-..."
```

```python
# RIGHT
from app.core.config import settings
secret = settings.jwt_secret  # raises at startup if missing
```

**Why**: Source control history is forever. Even after removal, the secret is in the git log, in CI logs, in backup snapshots. If you find one, rotate immediately.

## 13. Catch-all exception swallowing

```python
# WRONG
try:
    user = authenticate(token)
except Exception:
    user = None  # silently treat as anonymous
```

```python
# RIGHT
try:
    user = authenticate(token)
except (InvalidTokenError, ExpiredTokenError):
    user = None
# Let unexpected errors propagate to the global handler
```

**Why**: Broad except hides bugs and can mask security failures — e.g., a DB connection error during auth becomes "user is anonymous, proceed."

## 14. Frontend-only authorization

```typescript
// WRONG — relying on this for security
{user.role === "admin" && <DeleteButton onClick={deleteProject} />}
```

```typescript
// RIGHT — frontend hides the button (UX), backend enforces (security)
{user.role === "admin" && <DeleteButton onClick={deleteProject} />}
// AND the backend has Depends(require_role("admin")) on DELETE /projects/{id}
```

**Why**: A non-admin can open dev tools and fire the API call directly. Frontend role checks are presentation logic; they have zero security value. The backend dependency is the source of truth.

## 15. Trusting `Content-Type` on uploads

```python
# WRONG
@router.post("/upload")
async def upload(file: UploadFile):
    if file.content_type != "image/png":
        raise HTTPException(400)
    # Save the file...
```

```python
# RIGHT
import magic
head = await file.read(2048)
detected = magic.from_buffer(head, mime=True)
if detected not in ALLOWED_MIME:
    raise HTTPException(400)
```

**Why**: The client sets `Content-Type`. An attacker uploads a `.php` or `.exe` with `Content-Type: image/png`. Detect MIME from the file's magic bytes, not the client's header.

## 16. Unbounded request handling

```python
# WRONG — no size limit, can be DoSed
@router.post("/upload")
async def upload(request: Request):
    body = await request.body()  # reads entire body into memory
    ...
```

```python
# RIGHT — limit via middleware (see fastapi-patterns.md) and stream large files
@router.post("/upload")
async def upload(file: UploadFile):
    # Read in chunks, enforce size cap
    total = 0
    while chunk := await file.read(1 << 20):  # 1MB at a time
        total += len(chunk)
        if total > MAX_BYTES:
            raise HTTPException(413)
        # process chunk
```

**Why**: A single attacker request with `Content-Length: 10GB` can exhaust server memory.

## 17. Mutating Pydantic models in place

```python
# WRONG — bypasses validation, leaks sensitive fields back
@router.patch("/users/{id}")
async def update_user(id: str, body: dict):  # untyped dict input
    user = await db.get(User, id)
    for k, v in body.items():
        setattr(user, k, v)  # attacker sets `is_admin=True`
    await db.commit()
    return user  # returns raw model with password_hash
```

```python
# RIGHT
class UserUpdate(BaseModel):
    display_name: str | None = None
    # NOT including: role, is_admin, email_verified, password_hash

@router.patch("/users/{id}", response_model=UserResponse)
async def update_user(
    id: str,
    body: UserUpdate,
    current: User = Depends(require_resource_owner_or_admin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    await db.commit()
    return UserResponse.model_validate(user)
```

**Why**: Mass assignment is the #1 source of privilege escalation in API apps. Define an explicit update schema with only safe fields.

## 18. `eval` / `exec` on anything that touches user input

```python
# WRONG — any user influence on `expression` is RCE
result = eval(expression)
exec(user_code)
```

```python
# RIGHT
import ast
tree = ast.parse(expression, mode="eval")
# Walk the AST, allow only specific node types
# Or better: don't accept code from users. Use a domain-specific parser.
```

**Why**: `eval` and `exec` are arbitrary code execution. There's almost no legitimate reason to use them on input that has any path from a user. If you're sure you need it, use a sandboxed parser (e.g., `simpleeval` for math expressions) — not raw `eval`.

## 19. Returning success on auth failure to "be nice"

```python
# WRONG — silently treating bad token as anonymous
@router.get("/dashboard")
async def dashboard(creds=Depends(bearer_scheme)):
    try:
        user = decode_access_token(creds.credentials)
    except JWTError:
        return {"message": "Welcome, guest"}  # bypass via bad token
```

```python
# RIGHT — 401 on bad token, redirect at the UI layer
async def dashboard(user: User = Depends(get_current_user)):
    return {"user": user.id}
```

**Why**: Silent failure modes are how authorization bypasses happen. Be explicit. The frontend can decide what to do with a 401.

## 20. Skipping rate limits "for dev"

```python
# WRONG
if settings.environment != "production":
    return  # skip rate limit in dev
```

```python
# RIGHT
# Apply the rate limiter in all envs; just use higher limits in dev:
RATE_LIMIT_LOGIN = "5/minute" if settings.environment == "production" else "100/minute"
```

**Why**: Code paths that exist only in prod aren't tested. Run the rate limiter everywhere; tune the limits.
