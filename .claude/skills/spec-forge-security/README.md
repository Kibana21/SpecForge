# spec-forge-security

A Claude Code skill that encodes SPEC FORGE's security standards for FastAPI (backend) and Next.js (frontend).

## What it covers

- **JWT and sessions**: issuance, validation, algorithm pinning, refresh rotation with reuse detection, kill-switch via JTI blocklist.
- **Auth flows**: login, logout, password reset, email verification, account lockout, brute-force defense, enumeration prevention.
- **FastAPI patterns**: auth/RBAC dependencies, resource-level authorization, CORS, rate limiting, Pydantic validation, SQL safety, security headers, file uploads, audit logging.
- **Next.js patterns**: token storage model, fetch wrapper with auto-refresh, server-side session validation, route middleware, CSRF defense, CSP, cookie flags, client/server boundary.
- **Anti-patterns**: 20 concrete patterns to refuse or rewrite, each with wrong/right code and rationale.

## Structure

```
spec-forge-security/
├── SKILL.md                  # Always-in-context: triggers, principles, checklist, anti-pattern summary
└── references/
    ├── jwt-auth.md           # JWT, sessions, auth flows
    ├── fastapi-patterns.md   # Backend hardening
    ├── nextjs-patterns.md    # Frontend hardening
    └── anti-patterns.md      # Detailed wrong/right examples
```

## How to install

### Claude Code (project-level)

Place this folder at `.claude/skills/spec-forge-security/` in your repo. Claude Code auto-discovers it.

```bash
mkdir -p .claude/skills
cp -r spec-forge-security .claude/skills/
```

### Claude Code (user-level)

Place at `~/.claude/skills/spec-forge-security/` for it to apply across all your projects.

```bash
mkdir -p ~/.claude/skills
cp -r spec-forge-security ~/.claude/skills/
```

## How to verify it's working

Open Claude Code in your project and ask something like:

> Add a login endpoint to the FastAPI backend.

Before generating, Claude should consult the skill — you'll typically see it `view` the SKILL.md and then `jwt-auth.md`. The generated code should:
- Use `Depends(require_user)` or similar
- Pin the JWT algorithm
- Return generic "Invalid credentials" rather than separate "no user"/"wrong password"
- Set `httponly=True, secure=True, samesite="lax"` on the refresh cookie
- Apply a `slowapi` rate limit

If those things are missing, the skill isn't triggering — open an issue with the prompt that should have triggered it.

## Tuning

The skill is opinionated. If your stack diverges (e.g., you use `pyjwt` instead of `python-jose`, or Pages Router instead of App Router), update the relevant reference file. The principles in `SKILL.md` should generally stay.

Token lifetimes (15-min access, 7-day refresh) are conservative defaults. If your compliance regime requires shorter, tighten them — never lengthen without a documented reason.
