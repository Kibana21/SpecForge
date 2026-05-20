# PRD: Module 0 — Global System Architecture

> Part of the SpecForge detailed business-requirements PRD set. Sources: `.claude/prd/01-system-overview-and-business-context.md`, `.claude/prd/business-requirements-by-module.md`.

## 1. Introduction / Overview

Module 0 defines SpecForge as a secure, governed, single-page enterprise workbench. It is the foundational layer responsible for the application shell, the navigation model, global route state, the persistent project/document/application context, the centralized design system, cross-document version history access, global auditability, and role-based access control. Every other SpecForge module (Dashboard & Project Hub, SDLC Document Workbench, Template & Prompt Engineer Workspace, Integrations & AI Brains, and Asset Compilation & Export) renders inside the shell this module provides. Without Module 0, the rest of SpecForge would be a set of disconnected screens rather than a coherent SDLC platform.

The business problem is continuity and trust. Enterprise SDLC documentation work is long-running and context-heavy: a Business Analyst moves from portfolio to project to BRD to targeted review to traceability without losing track of which project, document, version, and section they are working in. A reviewer must understand exactly which artefact, version, and review queue they are looking at. A Compliance/Risk Reviewer or auditor must be able to reconstruct how an artefact changed over time and which AI or human actions produced it. These needs cannot be met by independent pages each managing their own state; they require a shared shell with one authoritative source of global context and one governed audit and access foundation.

Module 0 also encodes SpecForge's enterprise visual language. Generated content, human-edited content, app-brain grounding, and document state (approved, edited, AI-generated, stale, warning, danger, info, success) must be visually distinct and consistent everywhere they appear, because reviewers triage on these states. A centralized design-token system guarantees that semantics are applied identically across all surfaces, and that AI output is never mistaken for validated human work.

Finally, because SpecForge is a regulated delivery platform, Module 0 carries the production controls that make the platform trustworthy: user authentication and login, JWT-based session and token management, password/credential security, an API security baseline, an RBAC enforcement service that filters every project, document, source, app brain, setting, and export; an immutable audit log store; and a version-snapshot persistence layer that records every material change. These security requirements (BR-M0-009 through BR-M0-012) are specified to the binding SPEC FORGE security standard captured in `.claude/skills/spec-forge-security/SKILL.md` — JWT HS256, bcrypt, access/refresh token rotation, CORS whitelisting, rate limiting, and strict input validation. This PRD specifies both the user-facing requirements (BR-M0-001 through BR-M0-012) and the backend/production requirements implied by the overview's enterprise controls (section 8) and implied production capabilities (section 9) that are needed to realize Module 0 as a real system.

## 2. Goals

- Provide a single-page workbench shell that coordinates all primary SpecForge views without full page reloads while preserving active context.
- Maintain one authoritative global context for active project, SDLC stage, review document, application brain, and version panel, available to all downstream workflows.
- Keep persistent sidebar and topbar navigation chrome present and accurate across all primary views, including 10-stage SDLC progress visibility.
- Preserve the enterprise desktop layout across supported widths through deterministic canvas scaling that recalculates on resize.
- Govern all visual semantics through a centralized design-token system so status, AI, and app-brain semantics are applied identically everywhere.
- Make version history reachable from a consistent control on every managed document, with immutable snapshots and preview/compare.
- Capture an immutable, queryable audit trail of every material human and AI action affecting content, review, assumptions, traceability, app-brain facts, or exports.
- Enforce role-based access so users see and act on only what they are authorized for, across projects, documents, sources, app brains, settings, and exports.
- Achieve zero unauthorized data exposure through search, citations, exports, or AI answers (measurable target: no authorized-access bypass in security tests).
- Authenticate every user before granting access to any non-public route or API, issuing a short-lived access token and a revocable refresh token on login.
- Manage sessions with signed JWT access tokens and rotation-on-use refresh tokens, validated server-side on every request, per the SPEC FORGE security standard.
- Store and verify credentials securely (bcrypt at cost ≥12, minimum password policy, constant-time verification, no credential leakage in logs or responses).
- Enforce an API security baseline — CORS whitelisting, per-IP/per-user rate limiting, strict input validation, injection prevention, HTTPS-only transport, and security headers — with the backend as the sole security authority.

## 3. Scope

In scope (with priority):

- BR-M0-001 — Single-Page Workbench Shell — Must
- BR-M0-002 — Global Project and Document Context — Must
- BR-M0-003 — Persistent Navigation Chrome — Must
- BR-M0-004 — Responsive Design Scaling — Should
- BR-M0-005 — Design Token Governance — Must
- BR-M0-006 — Global Version History Access — Must
- BR-M0-007 — Global Auditability — Must
- BR-M0-008 — Role-Based Access Control — Must
- BR-M0-009 — User Authentication & Login — Must
- BR-M0-010 — Session & Token Management (JWT) — Must
- BR-M0-011 — Password & Credential Security — Must
- BR-M0-012 — API Security & Backend Integrity — Must

Priorities covered: Must, Should, Could. (The source catalogue's Module 0 business requirements span Must and Should and contain no Could-priority items. BR-M0-009 through BR-M0-012 are security requirements added to this PRD to make authentication, session/token management, credential security, and API security explicit, first-class, production requirements rather than implied backend notes; they are aligned to the binding SPEC FORGE security standard (`.claude/skills/spec-forge-security/SKILL.md`) and are all Must. Could-priority concerns are noted where relevant under Non-Goals and Open Questions.)

## 4. Users & Roles

- **Business Analyst** — Primary daily operator of the shell. Navigates portfolio → project → document → review → traceability; relies on persistent context so they never lose their place; opens version history; their material actions are audited.
- **Product Owner / Business Sponsor** — Enters the shell to review BRD content and approvals; relies on breadcrumbs and review context to know exactly which artefact/version they are validating; their approval actions are audited and RBAC-gated.
- **Solution Architect** — Navigates across FS/NFR/design stages and downstream-impact views; depends on accurate stage-map state and version history to assess readiness; restricted to authorized projects.
- **App Owner** — Enters app-registry and app-brain detail routes; merges app-brain proposals (RBAC-gated to owners/delegated maintainers); app-brain context surfaces in the global context bar.
- **QA Lead** — Navigates to the traceability matrix and test stages; relies on consistent navigation chrome and version access; restricted to authorized projects/documents.
- **Compliance / Risk Reviewer** — Primary consumer of auditability and version history; reconstructs how artefacts changed and which AI/human actions produced them; needs immutable, exportable, complete audit records; RBAC ensures restricted sources are never exposed.
- **Platform Administrator / AI Engineer** — Configures access controls, retention, audit policy, design-token theme governance, and route/permission mappings; the only role that can administer (but not silently rewrite) audit records and RBAC assignments.

## 5. Key Business Objects

- **Active project** — The project currently in focus; its ID scopes project, document, review, trace, and export workflows.
- **Active route/view** — The current navigable view state within the single-page shell (e.g., dashboard, BRD, targeted review).
- **SDLC stage** — The current stage within the 10-stage lifecycle the user is viewing or acting on.
- **Document key** — The identifier of the active managed document (e.g., BRD, FS, NFR) used by version, review, trace, and editing workflows.
- **Review context** — The bundle describing the review session: document key, display label, and return route.
- **Application key** — The identifier of the active application whose AI Brain context is loaded.
- **Version panel context** — The state describing which document's version history is open and which versions are selected for preview/compare.
- **User identity and role** — The authenticated principal and their authorization role(s) that drive RBAC decisions and audit actor attribution.
- **Design/theme tokens** — The centralized set of color, typography, spacing, shadow, status, AI, and app-brain tokens that govern visual semantics.
- **User credential** — The user's secret authenticator (password), persisted only as a bcrypt hash; never stored or returned in plaintext.
- **Session** — An authenticated user session represented by an issued access token plus a revocable, server-side refresh-token record.
- **Access token** — A short-lived (1 hour) HS256-signed JWT authorizing API calls; payload limited to `sub`, `role`, `exp`, `iat`, `jti` (no PII).
- **Refresh token** — A long-lived (7 day), rotation-on-use, server-side-revocable token (stored hashed) used to obtain new access tokens.
- **Auth event** — A login, logout, token-refresh, or failed-login occurrence captured for audit (BR-M0-007) and rate limiting.
- **Rate-limit counter** — Per-IP and per-user counters guarding sensitive endpoints (login, password reset).

## 6. Detailed Business Requirements

### BR-M0-001 — Single-Page Workbench Shell
**Priority:** Must

**Requirement:** SpecForge shall provide a single-page workbench shell that coordinates portfolio, project, document, review, traceability, app registry, and app brain views without requiring a full page reload, while preserving the active project context across route changes and resolving unknown or unauthorized routes to a safe state.

**User Stories:**

#### US-M0-001-1: Navigate primary views without reload
**As a** Business Analyst, **I want** to move between portfolio, project, requirement understanding, BRD, targeted review, stale impact, traceability matrix, generic document stages, app registry, and app brain detail without a full page reload **so that** I keep my flow and never lose in-progress context.

**Acceptance Criteria:**
- [ ] The shell supports distinct route states for: dashboard, project workspace, requirement understanding, BRD, targeted review, stale impact, traceability matrix, generic document stages, app registry, and app brain detail.
- [ ] Switching between any two primary views updates the displayed view without a full browser page reload.
- [ ] Each route state is addressable so a view can be entered directly and reproduced.
- [ ] The active route/view object reflects the currently rendered view at all times.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-001-2: Navigate via multiple entry points
**As a** Business Analyst, **I want** to reach primary views through the sidebar, topbar breadcrumbs, quick links, and in-context buttons **so that** I can navigate the way that fits my current task.

**Acceptance Criteria:**
- [ ] Users can navigate to primary views from the sidebar.
- [ ] Users can navigate to ancestor/parent views from topbar breadcrumbs.
- [ ] Users can navigate via quick links presented in workspace and panel contexts.
- [ ] Users can navigate via in-context buttons embedded in views (e.g., open review, open trace).
- [ ] All navigation paths resolve to the same canonical route state for a given destination.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-001-3: Safe handling of unknown or unauthorized routes
**As a** Platform Administrator, **I want** unknown or unauthorized routes to resolve to a safe fallback or access-denied state **so that** users never reach a broken or data-leaking screen.

**Acceptance Criteria:**
- [ ] Requesting an unknown route resolves to a defined safe fallback view rather than a blank or error-crash screen.
- [ ] Requesting a route the current user is not authorized for resolves to an access-denied state.
- [ ] The access-denied state does not reveal restricted data (no project names, document content, or app facts the user cannot access).
- [ ] Verify in browser using dev-browser skill.

#### US-M0-001-4: Preserve active project across navigation
**As a** Business Analyst, **I want** route changes to preserve my active project context unless I explicitly switch projects **so that** I do not accidentally operate on the wrong project.

**Acceptance Criteria:**
- [ ] Navigating between views within a project preserves the active project context.
- [ ] The active project context changes only when the user explicitly switches projects.
- [ ] Returning from a cross-project view (e.g., app registry) restores the prior active project where applicable.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M0-001-1: The system must maintain a route registry enumerating all supported primary route states (dashboard, project workspace, requirement understanding, BRD, targeted review, stale impact, traceability matrix, generic document stages, app registry, app brain detail).
- FR-M0-001-2: The system must transition between route states without a full page reload while keeping the shell chrome mounted.
- FR-M0-001-3: The system must expose navigation triggers from the sidebar, breadcrumbs, quick links, and in-context buttons that all resolve to canonical route states.
- FR-M0-001-4: The system must resolve unknown routes to a safe fallback view and unauthorized routes to an access-denied view.
- FR-M0-001-5: The system must preserve the active project context across route changes and mutate it only on explicit project switch.

**Backend / Production Requirements:**
- BE-M0-001-1: The system must provide a server-side route/permission resolution capability that, for a requested route plus the authenticated user, returns one of {allowed-render, fallback, access-denied} before any restricted data is loaded.
- BE-M0-001-2: The system must validate deep-linked/bookmarked routes against the user's authorization on entry, not only on in-app navigation.
- BE-M0-001-3: The system must associate each resolvable route with the permission(s) required to view it so route resolution and RBAC enforcement (BR-M0-008) share one authority.

### BR-M0-002 — Global Project and Document Context
**Priority:** Must

**Requirement:** SpecForge shall maintain authoritative global context for the active project, active SDLC stage, active review document, active application brain, and active version panel, and make that context available to all dependent project, document, review, trace, and export workflows.

**User Stories:**

#### US-M0-002-1: Authoritative active project context
**As a** Business Analyst, **I want** the active project ID to be available to every project, document, review, trace, and export workflow **so that** all actions consistently apply to the project I am working in.

**Acceptance Criteria:**
- [ ] The active project ID is readable by project, document, review, trace, and export workflows.
- [ ] All workflows operate against the single authoritative active project ID rather than independently held copies.
- [ ] When no project is active (e.g., on the dashboard), workflows that require a project context are unavailable rather than defaulting silently.

#### US-M0-002-2: Authoritative active document context
**As a** Solution Architect, **I want** the active document key to be available to version history, review, trace, and section-editing workflows **so that** those workflows always act on the document I have open.

**Acceptance Criteria:**
- [ ] The active document key is readable by version history, review, trace, and section-editing workflows.
- [ ] The active SDLC stage context reflects the stage of the active document/view.
- [ ] Changing the active document updates the document key for all dependent workflows consistently.

#### US-M0-002-3: Review context bundle
**As a** Compliance/Risk Reviewer, **I want** the review context to include the document key, a display label, and a return route **so that** I always know what I am reviewing and how to get back.

**Acceptance Criteria:**
- [ ] Review context includes the document key being reviewed.
- [ ] Review context includes a human-readable display label.
- [ ] Review context includes a return route used to exit the review back to its origin.
- [ ] Exiting review navigates to the stored return route.

#### US-M0-002-4: Application and version-panel context
**As an** App Owner, **I want** the application context to include the app key and app-brain details when the app is onboarded, and the version-panel context to track which document's history is open **so that** app and version views are always correctly scoped.

**Acceptance Criteria:**
- [ ] Application context includes the active app key.
- [ ] Application context includes app-brain details where the app is onboarded; for non-onboarded apps it indicates onboarding is required without exposing absent data as present.
- [ ] Version panel context identifies which document's version history is currently open.
- [ ] Version panel context identifies which version(s) are selected for preview/compare.

**Functional Requirements:**
- FR-M0-002-1: The system must maintain a single global context store holding active project ID, active SDLC stage, active document key, review context, application context, and version panel context.
- FR-M0-002-2: The system must expose read access to global context for all dependent workflows from one authoritative source.
- FR-M0-002-3: The system must update global context atomically on navigation and explicit context-switch events so dependent workflows never read inconsistent partial state.
- FR-M0-002-4: The system must represent review context as {document key, display label, return route} and application context as {app key, app-brain details when onboarded}.

**Backend / Production Requirements:**
- BE-M0-002-1: The system must validate, server-side, that the authenticated user is authorized for the active project ID and document key before returning context-scoped data.
- BE-M0-002-2: The system must resolve application context against the application registry/onboarding state of record so onboarded-vs-not is authoritative, not client-assumed.
- BE-M0-002-3: The system must scope all context-derived data reads (documents, reviews, traces, exports) by the active project/document keys so cross-project leakage is impossible.

### BR-M0-003 — Persistent Navigation Chrome
**Priority:** Must

**Requirement:** SpecForge shall display persistent sidebar and topbar navigation across all primary views to orient users within the workspace, the current project, the 10 SDLC stages, and the organisation library, including accurate per-stage status indicators and global topbar entry points.

**User Stories:**

#### US-M0-003-1: Persistent sidebar with workspace, project, stages, library, identity
**As a** Business Analyst, **I want** a persistent sidebar showing workspace links, the current project link, 10-stage document progress, org library links, and my user identity **so that** I always know where I am and can jump anywhere quickly.

**Acceptance Criteria:**
- [ ] The sidebar is present across all primary views.
- [ ] The sidebar displays workspace links.
- [ ] The sidebar displays a link to the current project.
- [ ] The sidebar displays the 10-stage document progress for the current project.
- [ ] The sidebar displays org library links.
- [ ] The sidebar displays the current user's identity.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-003-2: Sidebar stage rows with rich status
**As a** Solution Architect, **I want** each sidebar stage row to show status, sequence number, active indicator, stale/review/current markers, and a progress segment bar **so that** I can assess lifecycle health at a glance.

**Acceptance Criteria:**
- [ ] Each stage row displays its status.
- [ ] Each stage row displays its sequence number.
- [ ] The currently active stage shows an active indicator.
- [ ] Stage rows display stale, review, and current markers where applicable.
- [ ] Each stage row displays a progress segment bar.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-003-3: Topbar breadcrumbs reflecting route
**As a** Product Owner, **I want** topbar breadcrumbs that reflect the active route and let me navigate to the dashboard, project workspace, app registry, and parent documents **so that** I understand my location and can move up the hierarchy.

**Acceptance Criteria:**
- [ ] Breadcrumbs reflect the active route.
- [ ] Breadcrumbs allow navigation to the dashboard.
- [ ] Breadcrumbs allow navigation to the project workspace.
- [ ] Breadcrumbs allow navigation to the app registry where applicable.
- [ ] Breadcrumbs allow navigation to parent documents where applicable.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-003-4: Topbar global entry points
**As a** Business Analyst, **I want** the topbar to expose global search, notifications, settings, and a New project entry point **so that** these high-frequency actions are always one click away.

**Acceptance Criteria:**
- [ ] The topbar exposes a global search entry point.
- [ ] The topbar exposes a notifications entry point.
- [ ] The topbar exposes a settings entry point.
- [ ] The topbar exposes a New project entry point.
- [ ] These entry points are present across all primary views.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M0-003-1: The system must render the sidebar and topbar persistently across all primary route states.
- FR-M0-003-2: The system must populate the sidebar with workspace links, current-project link, 10-stage progress, org library links, and current user identity.
- FR-M0-003-3: The system must render each sidebar stage row with status, sequence number, active indicator, stale/review/current markers, and a progress segment bar.
- FR-M0-003-4: The system must render topbar breadcrumbs that derive from the active route and link to dashboard, project workspace, app registry, and parent documents where applicable.
- FR-M0-003-5: The system must render topbar entry points for global search, notifications, settings, and New project.

**Backend / Production Requirements:**
- BE-M0-003-1: The system must supply per-stage status (status, stale/review/current markers, progress) for the active project from the document/version state of record so chrome reflects real state, not static placeholders.
- BE-M0-003-2: The system must filter sidebar and topbar links so that only destinations the user is authorized to access are shown or actionable (consistent with BR-M0-008).
- BE-M0-003-3: The system must source notification indicators from the notification/inbox service so the topbar reflects the user's actual outstanding items.

### BR-M0-004 — Responsive Design Scaling
**Priority:** Should

**Requirement:** SpecForge shall preserve the enterprise desktop workbench layout by scaling the 1440px design canvas down for narrower browser widths, recalculating on resize, while production accessibility documentation defines minimum supported viewport and browser-zoom expectations.

**User Stories:**

#### US-M0-004-1: Scale canvas to viewport without breakage
**As a** Business Analyst on a smaller laptop, **I want** the 1440px design canvas to scale down to my browser width without horizontal layout breakage **so that** I can use the full workbench on narrower screens.

**Acceptance Criteria:**
- [ ] The application fits within the viewport without horizontal layout breakage at supported desktop widths.
- [ ] The scaled application still fills the viewport height.
- [ ] Layout proportions of the 1440px canvas are preserved when scaled.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-004-2: Recalculate scaling on resize
**As a** Business Analyst, **I want** scaling to recalculate when I resize the browser **so that** the layout stays correct as my window changes.

**Acceptance Criteria:**
- [ ] The scaling behavior recalculates on browser resize.
- [ ] After resize, the application continues to fit within the viewport without horizontal breakage and continues to fill viewport height.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-004-3: Document supported viewport and zoom
**As a** Platform Administrator, **I want** production accessibility documentation that defines the minimum supported viewport and browser-zoom expectations **so that** support boundaries are explicit for enterprise users.

**Acceptance Criteria:**
- [ ] Production accessibility documentation defines the minimum supported viewport width/height.
- [ ] Production accessibility documentation defines supported browser-zoom expectations.
- [ ] The documented minimum viewport is consistent with the implemented scaling behavior.

**Functional Requirements:**
- FR-M0-004-1: The system must scale the fixed 1440px design canvas to the available browser width while preserving layout proportions.
- FR-M0-004-2: The system must ensure the scaled application fills viewport height and does not introduce horizontal layout breakage at supported widths.
- FR-M0-004-3: The system must recompute the scaling factor on browser-resize events.
- FR-M0-004-4: The system must publish accessibility documentation specifying minimum supported viewport and browser-zoom expectations.

**Backend / Production Requirements:** (Primarily a client-side concern; minimal backend involvement.)
- BE-M0-004-1: The system must include the minimum-supported-viewport and zoom expectations in published product/accessibility documentation maintained alongside release artefacts.

### BR-M0-005 — Design Token Governance
**Priority:** Must

**Requirement:** SpecForge shall use a centralized design-token system for colors, typography, spacing, shadows, status semantics, and component states, so that all primary UI surfaces apply shared tokens consistently and so AI output, human edits, and app-brain grounding are visually distinct.

**User Stories:**

#### US-M0-005-1: Shared tokens on all surfaces
**As a** Platform Administrator, **I want** all primary UI surfaces to use shared tokens for background, canvas, surfaces, borders, text, status, AI, and app-brain colors **so that** the product looks consistent and theme changes apply everywhere at once.

**Acceptance Criteria:**
- [ ] All primary UI surfaces use shared tokens for background, canvas, surfaces, borders, and text.
- [ ] All primary UI surfaces use shared tokens for status, AI, and app-brain colors.
- [ ] No primary surface uses hard-coded values that bypass the token system for these properties.
- [ ] The token system also governs typography, spacing, shadows, and component states.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-005-2: Semantic status styling
**As a** Compliance/Risk Reviewer, **I want** status indicators to use semantic styling for approved, edited, AI-generated, stale, warning, danger, info, and success states **so that** I can triage content by state at a glance.

**Acceptance Criteria:**
- [ ] Status indicators use distinct semantic styling for approved, edited, and AI-generated states.
- [ ] Status indicators use distinct semantic styling for stale and warning states.
- [ ] Status indicators use distinct semantic styling for danger, info, and success states.
- [ ] The same status uses the same token-driven styling everywhere it appears.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-005-3: AI output and app-brain grounding visually distinct
**As a** Business Analyst, **I want** AI output to be visually distinct from human-edited content, and app-brain grounding to be visually distinct from document-local content **so that** I never mistake unvalidated AI text for validated work or local content for organisational facts.

**Acceptance Criteria:**
- [ ] Document AI output is visually distinct from human-edited content via tokenized styling.
- [ ] App-brain grounding uses a distinct visual style from document-local content via tokenized styling.
- [ ] The AI and app-brain distinctions are applied consistently across all surfaces where such content appears.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M0-005-1: The system must define a centralized design-token catalogue covering colors (background, canvas, surfaces, borders, text, status, AI, app-brain), typography, spacing, shadows, status semantics, and component states.
- FR-M0-005-2: The system must apply tokens to all primary UI surfaces so theming is centrally controlled.
- FR-M0-005-3: The system must provide semantic status tokens for approved, edited, AI-generated, stale, warning, danger, info, and success.
- FR-M0-005-4: The system must render AI output distinctly from human-edited content and app-brain grounding distinctly from document-local content using dedicated tokens.

**Backend / Production Requirements:**
- BE-M0-005-1: The system must govern theme/token definitions as a versioned, administrator-managed artefact so token changes are controlled and traceable (consistent with prompt/skill version governance in enterprise controls).
- BE-M0-005-2: The system must scope any runtime theme override (e.g., accent color) so it cannot alter semantic status/AI/app-brain distinctions that carry compliance meaning.

### BR-M0-006 — Global Version History Access
**Priority:** Must

**Requirement:** SpecForge shall allow users to open version history for any generated or managed document from a consistent version chip or history button, displaying a complete version timeline with metadata, supporting preview and compare of non-current versions, and treating immutable snapshots as non-restorable.

**User Stories:**

#### US-M0-006-1: Open version history from a consistent control
**As a** Solution Architect, **I want** to open version history for any managed document (BRD, FS, NFR, Requirement Understanding, Traceability Matrix, and any future module) from a consistent version chip or history button **so that** history is reachable the same way everywhere.

**Acceptance Criteria:**
- [ ] Version history can be opened for BRD, FS, NFR, Requirement Understanding, and the Traceability Matrix.
- [ ] Version history can be opened for any future document module via the same consistent control.
- [ ] The version chip or history button appears in a consistent location/manner across document types.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-006-2: Version history shows full metadata
**As a** Compliance/Risk Reviewer, **I want** version history to display the timeline, actor, timestamp, change note, changed sections, change count, generation type, and a current marker **so that** I can understand each version's provenance.

**Acceptance Criteria:**
- [ ] Version history displays a chronological timeline of versions.
- [ ] Each version displays its actor and timestamp.
- [ ] Each version displays its change note and changed sections.
- [ ] Each version displays its change count and generation type (e.g., AI vs human/manual).
- [ ] The current version is marked.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-006-3: Preview and compare non-current versions
**As a** QA Lead, **I want** to preview and compare non-current versions **so that** I can see exactly what changed between versions.

**Acceptance Criteria:**
- [ ] Users can open a read-only preview of a non-current version.
- [ ] Users can compare a non-current version against the current version.
- [ ] Differences between compared versions are visibly indicated.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-006-4: Immutable snapshots cannot be restored
**As a** Compliance/Risk Reviewer, **I want** immutable snapshots to be non-restorable **so that** the audit baseline cannot be overwritten.

**Acceptance Criteria:**
- [ ] Immutable snapshot versions are marked as immutable.
- [ ] No restore action is offered for immutable snapshot versions.
- [ ] Attempting to restore an immutable snapshot is prevented and explained.

**Functional Requirements:**
- FR-M0-006-1: The system must expose a consistent version chip / history button on every managed document type to open version history.
- FR-M0-006-2: The system must display, per version, the timeline position, actor, timestamp, change note, changed sections, change count, generation type, and current marker.
- FR-M0-006-3: The system must support read-only preview of a selected non-current version.
- FR-M0-006-4: The system must support side-by-side comparison of a non-current version against the current version with differences indicated.
- FR-M0-006-5: The system must mark immutable snapshots and prevent any restore operation on them.

**Backend / Production Requirements:**
- BE-M0-006-1: The system must persist version snapshots for all managed document types in a durable store, each recording actor, timestamp, change note, changed sections, change count, and generation type.
- BE-M0-006-2: The system must enforce immutability of snapshot records at the storage layer so they cannot be edited or deleted by non-admin users and cannot be restored.
- BE-M0-006-3: The system must serve version timeline, preview, and compare data scoped to the requesting user's authorization for the document (consistent with BR-M0-008).
- BE-M0-006-4: The system must expose a version-history retrieval interface keyed by document key so any current or future document module can reuse it without bespoke logic.

### BR-M0-007 — Global Auditability
**Priority:** Must

**Requirement:** SpecForge shall audit all material user and AI actions that affect generated content, review status, assumptions, traceability, app-brain facts, or exports, recording full event metadata (including AI-specific metadata), keeping records immutable to non-admin users.

**User Stories:**

#### US-M0-007-1: Audit material actions with full metadata
**As a** Compliance/Risk Reviewer, **I want** every material action to record actor, timestamp, project, document/app, action, source version, target version, and affected sections **so that** I can reconstruct exactly what happened.

**Acceptance Criteria:**
- [ ] Audit events record the actor and timestamp.
- [ ] Audit events record the project and the document or app involved.
- [ ] Audit events record the action performed.
- [ ] Audit events record the source version and target version where applicable.
- [ ] Audit events record affected sections where applicable.

#### US-M0-007-2: AI-specific audit metadata
**As a** Platform Administrator, **I want** AI audit events to additionally record skill version, model, prompt template version, source references, and output decision state **so that** AI-generated content is explainable and governable.

**Acceptance Criteria:**
- [ ] AI audit events record the skill version and model used.
- [ ] AI audit events record the prompt template version.
- [ ] AI audit events record the source references used.
- [ ] AI audit events record the output decision state (e.g., accepted, rejected, pending).

#### US-M0-007-3: Audit material lifecycle actions
**As a** Compliance/Risk Reviewer, **I want** restore, promotion, regeneration, approval, rejection, and export actions to be audit logged **so that** all governance-relevant operations are accountable.

**Acceptance Criteria:**
- [ ] Restore actions are audit logged.
- [ ] Promotion actions are audit logged.
- [ ] Regeneration actions are audit logged.
- [ ] Approval and rejection actions are audit logged.
- [ ] Export actions are audit logged.
- [ ] Logged actions also include those affecting review status, assumptions, traceability, and app-brain facts.

#### US-M0-007-4: Audit records immutable to non-admins
**As a** Platform Administrator, **I want** audit records to be immutable to non-admin users **so that** the audit trail cannot be tampered with.

**Acceptance Criteria:**
- [ ] Non-admin users cannot edit or delete audit records.
- [ ] Audit records are append-only from the perspective of normal application workflows.
- [ ] Any administrative access to audit records is itself constrained and does not allow silent rewriting of historical events.

**Functional Requirements:**
- FR-M0-007-1: The system must emit an audit event for every material action affecting generated content, review status, assumptions, traceability, app-brain facts, or exports.
- FR-M0-007-2: The system must include in each audit event: actor, timestamp, project, document/app, action, source version, target version, and affected sections (where applicable).
- FR-M0-007-3: The system must include in AI audit events: skill version, model, prompt template version, source references, and output decision state.
- FR-M0-007-4: The system must audit restore, promotion, regeneration, approval, rejection, and export actions specifically.
- FR-M0-007-5: The system must prevent edit or deletion of audit records by non-admin users.

**Backend / Production Requirements:**
- BE-M0-007-1: The system must provide an immutable, append-only audit log store as the system of record for all audit events.
- BE-M0-007-2: The system must capture audit events server-side at the point of action so client tampering cannot suppress or fabricate events.
- BE-M0-007-3: The system must support querying/filtering audit records by actor, project, document/app, action, time range, and version for compliance review and export.
- BE-M0-007-4: The system must apply retention and tamper-evidence controls to the audit store consistent with enterprise audit policy.
- BE-M0-007-5: The system must record AI audit metadata by reference to the governed skill/model/prompt-template versions so AI provenance is reconstructable.

### BR-M0-008 — Role-Based Access Control
**Priority:** Must

**Requirement:** SpecForge shall enforce role-based access to projects, documents, sources, app brains, settings, and exports so that users only see and act on what they are authorized for, restricted sources are never exposed through any channel, and only authorized actors can approve or merge.

**User Stories:**

#### US-M0-008-1: Authorized-only visibility of projects and apps
**As a** Business Analyst, **I want** to see only the projects and apps I am authorized to access **so that** I cannot view work outside my remit.

**Acceptance Criteria:**
- [ ] Users only see projects they are authorized to access.
- [ ] Users only see apps they are authorized to access.
- [ ] Counts and listings (portfolio, registry, navigation) reflect only authorized items.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-008-2: Restricted sources never exposed through any channel
**As a** Compliance/Risk Reviewer, **I want** restricted source documents to be unretrievable through search, citations, export, or AI answers for unauthorized users **so that** sensitive data never leaks.

**Acceptance Criteria:**
- [ ] Restricted source documents do not appear in search results for unauthorized users.
- [ ] Restricted source content does not appear in citations shown to unauthorized users.
- [ ] Restricted source content is excluded from exports for unauthorized users.
- [ ] Restricted source content is not used in AI answers returned to unauthorized users.

#### US-M0-008-3: Authorized-only approval of review items and documents
**As a** Product Owner, **I want** only assigned reviewers or authorized approvers to approve review items and documents **so that** approvals carry real authority.

**Acceptance Criteria:**
- [ ] Only assigned reviewers or authorized approvers can approve review items.
- [ ] Only authorized approvers can approve documents.
- [ ] Approval controls are unavailable to users lacking the required role/assignment.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-008-4: Authorized-only app-brain proposal merges
**As an** App Owner, **I want** only app owners or delegated maintainers to merge app-brain proposals **so that** organisational knowledge changes stay governed.

**Acceptance Criteria:**
- [ ] Only app owners or delegated maintainers can merge app-brain proposals.
- [ ] Merge controls are unavailable to users lacking owner/maintainer authority.
- [ ] Settings and export access are likewise gated to authorized roles.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M0-008-1: The system must filter projects and apps shown to a user to only those they are authorized to access.
- FR-M0-008-2: The system must exclude restricted source documents from search, citations, exports, and AI answers for unauthorized users.
- FR-M0-008-3: The system must restrict approval of review items and documents to assigned reviewers or authorized approvers.
- FR-M0-008-4: The system must restrict app-brain proposal merges to app owners or delegated maintainers.
- FR-M0-008-5: The system must gate access to projects, documents, sources, app brains, settings, and exports by role.
- FR-M0-008-6: The system must enforce authorization server-side on every protected endpoint via a require-role/permission check, treating any client-side role checks as UX-only and never as a security control.
- FR-M0-008-7: The system must combine role checks with resource-level access checks (ownership/membership), and return 401 for missing/invalid authentication, 403 for authenticated-but-unauthorized requests, and 404 where revealing existence would leak information to an unauthorized user (status semantics defined in BR-M0-012).

**Backend / Production Requirements:**
- BE-M0-008-1: The system must provide a centralized RBAC enforcement service that authoritatively decides access for projects, documents, sources, app brains, settings, exports, and actions, evaluated server-side.
- BE-M0-008-2: The system must enforce permission-filtered retrieval (RAG/search/citation) so restricted content is filtered before it can reach any client surface or AI prompt.
- BE-M0-008-3: The system must authenticate users and maintain sessions, attaching the resolved identity and role(s) to every request for authorization and audit attribution.
- BE-M0-008-4: The system must model approver assignment and app-owner/delegated-maintainer roles as data so authorization decisions are configurable, not hard-coded.
- BE-M0-008-5: The system must deny by default: any request whose authorization cannot be positively established resolves to access-denied, and the denial is auditable.
- BE-M0-008-6: The system must ensure RBAC decisions are consistent across UI gating, route resolution (BR-M0-001), and data retrieval so UI hiding is never the sole control.
- BE-M0-008-7: The system must combine role checks with resource-level access checks (ownership/membership) for every protected resource and never authorize on role alone (aligns with the SPEC FORGE security standard, `.claude/skills/spec-forge-security/SKILL.md`).

### BR-M0-009 — User Authentication & Login
**Priority:** Must

**Requirement:** SpecForge shall authenticate every user before granting access to any non-public part of the application, issue an access token and a refresh token on successful login, support logout that revokes the session, and resolve all unauthenticated requests to a login/access-denied state without leaking application data. Authentication is implemented to the SPEC FORGE security standard (`.claude/skills/spec-forge-security/SKILL.md`).

**User Stories:**

#### US-M0-009-1: Log in with credentials
**As a** Business Analyst, **I want** to log in with my credentials **so that** I can securely access the workbench.

**Acceptance Criteria:**
- [ ] A `POST /api/auth/login` endpoint accepts credentials and, on success, returns an access token and a refresh token.
- [ ] On successful login, both a short-lived access token and a long-lived refresh token are issued.
- [ ] Invalid credentials are rejected with a generic message that does not reveal whether the account exists or which field was wrong.
- [ ] Repeated failed logins are rate-limited per BR-M0-012.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-009-2: Block unauthenticated access
**As a** Platform Administrator, **I want** all non-public routes and APIs to require authentication **so that** unauthenticated users cannot reach any application data.
**Acceptance Criteria:**
- [ ] Only `/api/auth/login`, `/api/auth/refresh`, and `/api/health` are reachable without a valid access token; every other endpoint requires authentication.
- [ ] An unauthenticated request to a protected API returns 401 and resolves the UI to a login/access-denied state.
- [ ] The login/access-denied state reveals no project names, document content, or app facts.

#### US-M0-009-3: Log out and revoke session
**As a** Business Analyst, **I want** to log out **so that** my refresh token can no longer be used.
**Acceptance Criteria:**
- [ ] Logout invalidates the user's refresh token in the database so it cannot be reused.
- [ ] After logout, the access token expires naturally and cannot be exchanged for a new one.
- [ ] Verify in browser using dev-browser skill.

#### US-M0-009-4: Seeded test/demo identities go through real auth + RBAC
**As a** Platform Administrator, **I want** seeded test/demo users to authenticate through the same login + RBAC path as real users **so that** demos and tests never bypass security.
**Acceptance Criteria:**
- [ ] Test/demo users authenticate through the same login + token flow as production users, with no auth bypass.
- [ ] Test/demo users are subject to the same RBAC enforcement (BR-M0-008).
- [ ] The active environment or test-identity context is visually distinguishable using design tokens (BR-M0-005) so users and auditors always know the system context.
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M0-009-1: The system must provide `POST /api/auth/login` that verifies credentials and, on success, issues an access token and a refresh token.
- FR-M0-009-2: The system must require a valid access token for every endpoint except `/api/auth/login`, `/api/auth/refresh`, and `/api/health`.
- FR-M0-009-3: The system must return generic authentication-failure messages that do not disclose account existence or which credential field was incorrect.
- FR-M0-009-4: The system must provide a logout operation that invalidates the refresh token server-side.
- FR-M0-009-5: The system must route test/demo identities through the same authentication and RBAC path with no bypass, visually distinguished per BR-M0-005.

**Backend / Production Requirements:**
- BE-M0-009-1: The system must persist user identities with their role(s) and never store plaintext passwords (credential storage per BR-M0-011).
- BE-M0-009-2: The system must deny by default on unauthenticated access and emit audit events for login success, login failure, and logout (BR-M0-007).
- BE-M0-009-3: The system must seed test/demo identities as real, RBAC-governed records flagged as non-production identities.

### BR-M0-010 — Session & Token Management (JWT)
**Priority:** Must

**Requirement:** SpecForge shall manage sessions using HS256-signed JWT access tokens and revocable, rotation-on-use refresh tokens, validating tokens on every request and storing tokens securely on the client, per the SPEC FORGE security standard.

**User Stories:**

#### US-M0-010-1: Stateless access-token validation
**As a** Platform Administrator, **I want** every request's access token validated for signature, expiry, and issuer **so that** forged or expired tokens are rejected.
**Acceptance Criteria:**
- [ ] Access tokens are signed with HS256 using a ≥256-bit secret read from the `JWT_SECRET` environment variable (never hardcoded).
- [ ] Token signature, expiry, and issuer are validated on every request.
- [ ] Expired or invalid tokens are rejected with 401 (not 403).
- [ ] The JWT payload contains only `sub` (user_id as string), `role`, `exp`, `iat`, and `jti`; it never contains passwords, emails, or other PII.
- [ ] Access tokens expire 1 hour after issue.

#### US-M0-010-2: Refresh with rotation
**As a** Business Analyst, **I want** my session to refresh without re-login **so that** I am not interrupted, while old refresh tokens stop working.
**Acceptance Criteria:**
- [ ] `POST /api/auth/refresh` accepts a refresh token and returns a new access + refresh token pair.
- [ ] The previous refresh token is invalidated when a new pair is issued (rotation).
- [ ] Refresh tokens expire 7 days after issue.
- [ ] Refresh tokens are stored hashed in the database so they can be revoked.

#### US-M0-010-3: Secure client-side token storage
**As a** Platform Administrator, **I want** tokens stored securely on the client **so that** they cannot be exfiltrated via XSS or persisted insecurely.
**Acceptance Criteria:**
- [ ] The access token is held in memory (application state), never in localStorage.
- [ ] The refresh token is stored in an httpOnly cookie, never in localStorage.
- [ ] Cookies carrying tokens set the `Secure` flag (HTTPS only).
- [ ] Verify in browser using dev-browser skill.

**Functional Requirements:**
- FR-M0-010-1: The system must sign access tokens with HS256 using a ≥256-bit secret sourced from `JWT_SECRET`.
- FR-M0-010-2: The system must validate token signature, expiry, and issuer on every request and reject expired/invalid tokens with 401.
- FR-M0-010-3: The system must restrict the JWT payload to `sub`, `role`, `exp`, `iat`, `jti` and exclude all PII.
- FR-M0-010-4: The system must issue 1-hour access tokens and 7-day refresh tokens on login.
- FR-M0-010-5: The system must implement `POST /api/auth/refresh` with refresh-token rotation that invalidates the prior token.
- FR-M0-010-6: The system must store the access token in client memory and the refresh token in an httpOnly, `Secure` cookie.

**Backend / Production Requirements:**
- BE-M0-010-1: The system must store refresh tokens hashed and revocable in the database while keeping access tokens stateless.
- BE-M0-010-2: The system must invalidate the prior refresh token atomically on rotation and on logout.
- BE-M0-010-3: The system must support `JWT_SECRET` rotation by validating against multiple active secrets during a transition window.
- BE-M0-010-4: The system must attach the resolved identity and role from the validated token to every request for RBAC (BR-M0-008) and audit attribution (BR-M0-007).

### BR-M0-011 — Password & Credential Security
**Priority:** Must

**Requirement:** SpecForge shall store and verify user credentials securely — hashing passwords with bcrypt (cost ≥12), enforcing a minimum password policy, using constant-time verification, and never logging or returning credentials — per the SPEC FORGE security standard.

**User Stories:**

#### US-M0-011-1: Secure password storage
**As a** Platform Administrator, **I want** passwords hashed with bcrypt **so that** a database breach does not expose usable passwords.
**Acceptance Criteria:**
- [ ] Passwords are hashed with bcrypt (passlib) at cost factor ≥12.
- [ ] Plaintext passwords are never stored.
- [ ] Password verification uses constant-time comparison.

#### US-M0-011-2: Password policy enforcement
**As a** Business Analyst, **I want** a minimum password strength enforced **so that** weak passwords are rejected at the API.
**Acceptance Criteria:**
- [ ] The API enforces a minimum password length of 8 characters via request-schema validation.
- [ ] Password-policy violations return a clear validation error without exposing internal detail.

#### US-M0-011-3: No credential leakage
**As a** Compliance/Risk Reviewer, **I want** credentials never exposed in logs or responses **so that** secrets cannot leak.
**Acceptance Criteria:**
- [ ] Passwords are never logged or included in error messages.
- [ ] Password hashes are excluded from all API response schemas.
- [ ] The password-reset flow is rate-limited per BR-M0-012 and does not disclose whether an account exists.

**Functional Requirements:**
- FR-M0-011-1: The system must hash passwords with bcrypt at cost ≥12 using passlib.
- FR-M0-011-2: The system must enforce a minimum password length of 8 at the API via strict request validation.
- FR-M0-011-3: The system must exclude password hashes from all response schemas and never log credentials.
- FR-M0-011-4: The system must verify passwords using constant-time comparison.

**Backend / Production Requirements:**
- BE-M0-011-1: The system must store only salted bcrypt hashes and never reversible credential material.
- BE-M0-011-2: The system must provide a password-reset flow that is rate-limited, audited (BR-M0-007), and non-disclosing of account existence.

### BR-M0-012 — API Security & Backend Integrity
**Priority:** Must

**Requirement:** SpecForge shall enforce baseline API security controls — CORS whitelisting, rate limiting, strict input validation, injection prevention, request-size limits, HTTPS-only transport, security headers, and consistent authorization HTTP-status semantics — so the backend is the sole authority for security decisions, per the SPEC FORGE security standard.

**User Stories:**

#### US-M0-012-1: CORS and HTTPS hardening
**As a** Platform Administrator, **I want** CORS locked to the frontend origin and HTTPS enforced **so that** cross-origin and downgrade attacks are blocked.
**Acceptance Criteria:**
- [ ] CORS allows only the frontend origin from the `FRONTEND_URL` environment variable; wildcard `*` origins are never used in production.
- [ ] All cookies set the `Secure` flag and HTTP is redirected to HTTPS in production.

#### US-M0-012-2: Rate limiting on sensitive endpoints
**As a** Platform Administrator, **I want** auth endpoints rate-limited **so that** brute-force and abuse are mitigated.
**Acceptance Criteria:**
- [ ] Login is limited to 5 attempts/minute, applied per-IP and per-user.
- [ ] Password reset is limited to 3/hour.
- [ ] Exceeding a limit returns a rate-limit response without leaking account state.

#### US-M0-012-3: Input validation and injection prevention
**As a** Platform Administrator, **I want** all input validated and queries parameterized **so that** injection attacks are prevented.
**Acceptance Criteria:**
- [ ] All request bodies are validated via strict-typed request schemas.
- [ ] Raw user input is never passed to SQL, shell commands, or file paths.
- [ ] Database access uses an ORM or parameterized queries; SQL is never built via string interpolation.
- [ ] A maximum request size is enforced (10MB default; explicit higher limits only for file uploads).
- [ ] File uploads validate content type by magic bytes (not extension) and reject path-traversal filenames.

#### US-M0-012-4: Consistent status semantics and security headers
**As a** Compliance/Risk Reviewer, **I want** consistent HTTP status codes, sanitized errors, and security headers **so that** the API neither leaks resource existence nor exposes clients to common attacks.
**Acceptance Criteria:**
- [ ] 401 is returned for missing/invalid tokens, 403 for authenticated-but-unauthorized requests, and 404 where revealing existence would leak information.
- [ ] Production error messages are generic; detailed errors are logged server-side only.
- [ ] Responses set `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `X-XSS-Protection: 1; mode=block`; the frontend sets a `Content-Security-Policy`.

**Functional Requirements:**
- FR-M0-012-1: The system must whitelist CORS to `FRONTEND_URL` and never allow `*` origins in production.
- FR-M0-012-2: The system must enforce per-IP and per-user rate limits (login 5/minute, password reset 3/hour).
- FR-M0-012-3: The system must validate all request bodies with strict typed schemas and reject oversize requests (10MB default).
- FR-M0-012-4: The system must use an ORM or parameterized queries exclusively and never interpolate SQL strings.
- FR-M0-012-5: The system must return 401/403/404 per the defined semantics and sanitize production error messages.
- FR-M0-012-6: The system must set the required security response headers and enforce HTTPS-only transport with `Secure` cookies.
- FR-M0-012-7: The system must validate upload content type by magic bytes and reject path-traversal filenames.

**Backend / Production Requirements:**
- BE-M0-012-1: The system must implement rate limiting via a shared counter store (e.g., Redis-based) so limits hold across instances.
- BE-M0-012-2: The system must keep all secrets (JWT secret, provider/API keys) in environment variables or platform secret stores, never in code or client-side state (coordinated with Module 4 secret management).
- BE-M0-012-3: The system must enforce authorization server-side on every endpoint via a require-role/permission dependency, with frontend role checks treated as UX-only.
- BE-M0-012-4: The system must pin dependencies to exact versions and run a vulnerability audit before each release.

## 7. Non-Goals / Out of Scope

- Module-specific feature behavior beyond the shell and global concerns: the actual dashboard, BRD editor, review queues, traceability logic, app-brain detail, and export job mechanics are owned by Modules 1–5. Module 0 provides the shell, context, chrome, tokens, version-access pattern, audit foundation, and RBAC enforcement they consume.
- Mobile/phone-optimized layouts. Module 0 targets the enterprise desktop workbench with canvas scaling for narrower desktop widths only (BR-M0-004); a separate responsive/mobile experience is not in scope.
- Restricted prototype/demo design tweak controls (accent color, jump-to-screen). These are a Could-priority concern owned by Module 3 (BR-M3-009); Module 0 only ensures any such runtime override cannot break compliance-bearing semantic distinctions (BE-M0-005-2).
- Authoring of version-snapshot content, diff computation semantics for document-specific structures, and export packaging — Module 0 defines the consistent access pattern, immutability, and audit hooks; detailed compare/restore/export behavior is specified in Module 5.
- Real LLM provider integration, model routing, ingestion/OCR/embedding, and notification/inbox internals — Module 0 consumes their outputs (e.g., AI audit metadata, notification indicators) but does not implement them (owned by Module 4 and section-9 production capabilities).
- Defining individual permission grants and approval-assignment UX. Module 0 specifies the RBAC enforcement model and that assignments are data-driven; the administration screens for managing them are part of settings/configuration (Module 4).
- Enterprise SSO / OAuth2 / OIDC federation, SCIM provisioning, and multi-factor authentication. The baseline authentication standard for BR-M0-009/010 is the SPEC FORGE JWT model (`.claude/skills/spec-forge-security/SKILL.md`); federated identity and MFA are flagged as future/Should extensions in Open Questions and would map external identities onto the same internal roles and the same RBAC enforcement (BR-M0-008).

## 8. Technical Considerations

**Data model entities (Module 0):**
- User identity (principal ID, display name, role(s), session).
- Role and permission mapping (role → permitted routes/actions/resource scopes).
- Project access grant (user ↔ project authorization).
- App access grant and app-owner/delegated-maintainer assignment (user ↔ app authorization).
- Global context object (active project ID, active SDLC stage, active document key, review context {document key, label, return route}, application context {app key, app-brain details}, version panel context {document key, selected versions}).
- Route registry entry (route ID → required permission(s) → view).
- Version snapshot (document key, version ID, actor, timestamp, change note, changed sections, change count, generation type, immutability flag).
- Audit event (actor, timestamp, project, document/app, action, source version, target version, affected sections; AI extension: skill version, model, prompt template version, source references, output decision state).
- Design token catalogue (versioned color/typography/spacing/shadow/status/AI/app-brain/component-state tokens).
- User credential (user ID, bcrypt password hash, status); never plaintext (BR-M0-011).
- Refresh-token record (jti, user ID, hashed token, issued/expiry timestamps, revoked flag) for revocation and rotation (BR-M0-010).
- Auth event (login success/failure, logout, refresh) feeding audit (BR-M0-007) and rate limiting.
- Rate-limit counter (key by IP and user, window, count) for sensitive endpoints (BR-M0-012).

**API / service surface:**
- Route/permission resolution service (BR-M0-001, BR-M0-008): given route + user → {allowed-render | fallback | access-denied}.
- Global context provider (BR-M0-002): authoritative read/update of the shared context store.
- Navigation/chrome data service (BR-M0-003): per-stage status, authorized links, notification indicators.
- Version history service (BR-M0-006): timeline, preview, compare; immutability enforcement; keyed by document key for reuse by all modules.
- Audit service (BR-M0-007): append-only event capture and query/filter API; immutable store.
- RBAC enforcement service (BR-M0-008): centralized authorization decisions; permission-filtered retrieval for search/citation/RAG/export.
- Authentication & session service (BR-M0-009, BR-M0-010): `POST /api/auth/login`, `POST /api/auth/refresh` (rotation), logout/revoke; identity establishment, session lifecycle, and identity/role attachment per request. Public endpoints limited to `/api/auth/login`, `/api/auth/refresh`, `/api/health`.
- Credential service (BR-M0-011): bcrypt (cost ≥12) hashing, constant-time verification, minimum-length policy, password reset (rate-limited, audited).
- API security middleware (BR-M0-012): CORS whitelist (`FRONTEND_URL`), per-IP/per-user rate limiting (shared/Redis counter), strict request validation, request-size limits, security headers, HTTPS redirect, and 401/403/404 status semantics.

**Integration points:**
- With Module 1–5 views, which mount inside the shell and read global context.
- With Module 4 configuration for governed skill/model/prompt-template versions referenced in AI audit metadata, and for app onboarding state used in application context.
- With section-9 production capabilities: persistent database (projects, documents, versions, reviews, app brains, trace links), permission-filtered RAG, notification/inbox workflows, export job generation, and approval signatures — Module 0 consumes/feeds these via the services above.

**Performance:**
- View transitions should occur without full page reload (BR-M0-001); navigation should feel immediate for authorized routes.
- Canvas scaling recalculation on resize (BR-M0-004) must not cause visible layout thrash and must keep the app within viewport bounds.
- Audit event capture must be reliable and must not block the user's primary action perceptibly while still guaranteeing durability.

**Security:**
- Deny-by-default authorization, enforced server-side; UI gating is never the sole control (BE-M0-008-6).
- Restricted content filtered before reaching any client surface or AI prompt (BE-M0-008-2).
- Immutable, tamper-evident audit and version stores (BE-M0-007-1, BE-M0-006-2) with retention controls (enterprise controls, section 8).
- Secret management for providers/integrations is handled by Module 4/configuration; Module 0 ensures audit/RBAC consistency around their use.
- Deep-linked routes are re-authorized on entry (BE-M0-001-2), not trusted from prior in-app state.
- Authentication, session/token, credential, and API-security requirements (BR-M0-009 through BR-M0-012) implement the binding SPEC FORGE security standard (`.claude/skills/spec-forge-security/SKILL.md`): JWT HS256 with `JWT_SECRET` from env (rotatable), 1h access / 7d refresh tokens with rotation and DB-stored hashed refresh tokens, bcrypt cost ≥12, access token in memory + refresh token in httpOnly `Secure` cookie (never localStorage), CORS whitelisted to `FRONTEND_URL`, rate limits (login 5/min, reset 3/hour), strict input validation, ORM/parameterized queries only, request-size limits, security headers, and 401/403/404 status discipline.
- These are noted as *the standard to apply*, not a re-implementation: when backend code is written, follow `.claude/skills/spec-forge-security/SKILL.md` directly (it is more prescriptive than this PRD on framework specifics such as passlib, slowapi, FastAPI middleware, and dependency pinning).

**Tech-stack-agnostic note:** specific frameworks, storage engines, and component libraries are intentionally unspecified; requirements describe behavior and guarantees, not implementation.

## 9. Success Metrics

- 100% of supported primary route states are reachable without a full page reload and via at least one navigation entry point each (BR-M0-001).
- 0 occurrences of active-project context loss on intra-project navigation in usability/regression testing (BR-M0-001, BR-M0-002).
- 100% of unknown routes resolve to the safe fallback and 100% of unauthorized routes resolve to access-denied with no restricted data leakage (BR-M0-001, BR-M0-008).
- Sidebar and topbar chrome present and accurate (per-stage status matches state of record) on 100% of primary views (BR-M0-003).
- Application fits within viewport without horizontal breakage across the documented supported desktop width range, recalculating correctly on resize (BR-M0-004).
- 0 primary-surface usages of non-tokenized values for governed properties in design audits; AI vs human and app-brain vs local distinctions present on 100% of applicable surfaces (BR-M0-005).
- Version history openable from a consistent control on 100% of managed document types; immutable snapshots non-restorable in 100% of attempts (BR-M0-006).
- 100% of material/lifecycle actions (restore, promotion, regeneration, approval, rejection, export, plus content/review/assumption/trace/app-fact changes) produce a complete, immutable audit event (BR-M0-007).
- 0 unauthorized-access bypasses in security testing across search, citations, export, AI answers, approvals, and merges (BR-M0-008).
- Auditors can reconstruct an artefact's full change history (actor, time, action, versions, AI provenance) for any audited document on demand (BR-M0-006, BR-M0-007).
- 100% of protected endpoints reject unauthenticated requests with 401 and only `/api/auth/login`, `/api/auth/refresh`, `/api/health` are reachable without a token (BR-M0-009, BR-M0-012).
- 0 access tokens accepted with invalid signature/expiry/issuer; 0 JWTs carrying PII beyond the permitted claims in security testing (BR-M0-010).
- 100% of refresh operations rotate (old token invalidated); revoked/logged-out refresh tokens are rejected in 100% of attempts (BR-M0-010).
- 0 plaintext passwords or password hashes present in logs or API responses; 100% of stored passwords bcrypt-hashed at cost ≥12 (BR-M0-011).
- Login and password-reset rate limits enforced (login 5/min, reset 3/hour) with 0 bypass; 0 wildcard CORS origins and 0 string-interpolated SQL queries in production code review (BR-M0-012).

## 10. Open Questions

- What is the exact documented minimum supported viewport width/height and the supported browser-zoom range for BR-M0-004? (Needs accessibility/product confirmation.)
- What is the canonical safe fallback view for unknown routes — a global dashboard redirect, a dedicated not-found view, or a contextual fallback within the current project? (BR-M0-001.)
- Should the access-denied state offer a request-access workflow, or remain a terminal informational state? (BR-M0-001, BR-M0-008.)
- What administrative actions, if any, may touch the audit store, and what meta-audit captures those administrative accesses to preserve tamper-evidence? (BR-M0-007.)
- What are the precise retention periods and tamper-evidence mechanisms required for the audit and version stores per enterprise/regulatory policy? (BR-M0-006, BR-M0-007.)
- What is the full role taxonomy and permission granularity (e.g., per-project vs per-business-unit roles, delegated-maintainer scope) backing the RBAC service? (BR-M0-008.)
- How are runtime theme overrides (e.g., demo accent color) authorized and scoped so they never alter compliance-bearing semantic tokens, and in which environments are they permitted? (BR-M0-005, relates to BR-M3-009.)
- Should version-panel "generation type" enumerate beyond AI/human (e.g., regeneration, restore, import), and must those map 1:1 to audit action types for cross-referencing? (BR-M0-006, BR-M0-007.)
- Will production require enterprise SSO / OAuth2 / OIDC federation and/or SCIM provisioning, and is MFA mandatory? If so, how do external identities map onto the internal role taxonomy and RBAC (BR-M0-008, BR-M0-009)? (Baseline is the SPEC FORGE JWT model; federation/MFA are candidate Should extensions.)
- What is the `JWT_SECRET` rotation cadence and the transition-window length for accepting multiple active secrets (BR-M0-010, BE-M0-010-3)?
- Are concurrent sessions per user allowed, and is there a max active-refresh-token count or device list per user (BR-M0-010)?
- Should idle/absolute session timeouts be shorter than the 7-day refresh lifetime for sensitive roles (e.g., Compliance, Admin)? (BR-M0-010.)
- What is the account-lockout / backoff policy after repeated failed logins, beyond the 5/min rate limit (BR-M0-009, BR-M0-012)?
- Which seeded test/demo identities and roles are needed for the prototype, and how are they prevented from existing in production tenants (BR-M0-009, US-M0-009-4)?
- What password-reset delivery channel and token lifetime are used, and what audit/notification accompanies a reset (BR-M0-011)?

## 11. Traceability Map

| BR ID | User Stories | Functional Requirements | Backend Reqs |
|---|---|---|---|
| BR-M0-001 — Single-Page Workbench Shell | US-M0-001-1, US-M0-001-2, US-M0-001-3, US-M0-001-4 | FR-M0-001-1, FR-M0-001-2, FR-M0-001-3, FR-M0-001-4, FR-M0-001-5 | BE-M0-001-1, BE-M0-001-2, BE-M0-001-3 |
| BR-M0-002 — Global Project and Document Context | US-M0-002-1, US-M0-002-2, US-M0-002-3, US-M0-002-4 | FR-M0-002-1, FR-M0-002-2, FR-M0-002-3, FR-M0-002-4 | BE-M0-002-1, BE-M0-002-2, BE-M0-002-3 |
| BR-M0-003 — Persistent Navigation Chrome | US-M0-003-1, US-M0-003-2, US-M0-003-3, US-M0-003-4 | FR-M0-003-1, FR-M0-003-2, FR-M0-003-3, FR-M0-003-4, FR-M0-003-5 | BE-M0-003-1, BE-M0-003-2, BE-M0-003-3 |
| BR-M0-004 — Responsive Design Scaling | US-M0-004-1, US-M0-004-2, US-M0-004-3 | FR-M0-004-1, FR-M0-004-2, FR-M0-004-3, FR-M0-004-4 | BE-M0-004-1 |
| BR-M0-005 — Design Token Governance | US-M0-005-1, US-M0-005-2, US-M0-005-3 | FR-M0-005-1, FR-M0-005-2, FR-M0-005-3, FR-M0-005-4 | BE-M0-005-1, BE-M0-005-2 |
| BR-M0-006 — Global Version History Access | US-M0-006-1, US-M0-006-2, US-M0-006-3, US-M0-006-4 | FR-M0-006-1, FR-M0-006-2, FR-M0-006-3, FR-M0-006-4, FR-M0-006-5 | BE-M0-006-1, BE-M0-006-2, BE-M0-006-3, BE-M0-006-4 |
| BR-M0-007 — Global Auditability | US-M0-007-1, US-M0-007-2, US-M0-007-3, US-M0-007-4 | FR-M0-007-1, FR-M0-007-2, FR-M0-007-3, FR-M0-007-4, FR-M0-007-5 | BE-M0-007-1, BE-M0-007-2, BE-M0-007-3, BE-M0-007-4, BE-M0-007-5 |
| BR-M0-008 — Role-Based Access Control | US-M0-008-1, US-M0-008-2, US-M0-008-3, US-M0-008-4 | FR-M0-008-1, FR-M0-008-2, FR-M0-008-3, FR-M0-008-4, FR-M0-008-5, FR-M0-008-6, FR-M0-008-7 | BE-M0-008-1, BE-M0-008-2, BE-M0-008-3, BE-M0-008-4, BE-M0-008-5, BE-M0-008-6, BE-M0-008-7 |
| BR-M0-009 — User Authentication & Login | US-M0-009-1, US-M0-009-2, US-M0-009-3, US-M0-009-4 | FR-M0-009-1, FR-M0-009-2, FR-M0-009-3, FR-M0-009-4, FR-M0-009-5 | BE-M0-009-1, BE-M0-009-2, BE-M0-009-3 |
| BR-M0-010 — Session & Token Management (JWT) | US-M0-010-1, US-M0-010-2, US-M0-010-3 | FR-M0-010-1, FR-M0-010-2, FR-M0-010-3, FR-M0-010-4, FR-M0-010-5, FR-M0-010-6 | BE-M0-010-1, BE-M0-010-2, BE-M0-010-3, BE-M0-010-4 |
| BR-M0-011 — Password & Credential Security | US-M0-011-1, US-M0-011-2, US-M0-011-3 | FR-M0-011-1, FR-M0-011-2, FR-M0-011-3, FR-M0-011-4 | BE-M0-011-1, BE-M0-011-2 |
| BR-M0-012 — API Security & Backend Integrity | US-M0-012-1, US-M0-012-2, US-M0-012-3, US-M0-012-4 | FR-M0-012-1, FR-M0-012-2, FR-M0-012-3, FR-M0-012-4, FR-M0-012-5, FR-M0-012-6, FR-M0-012-7 | BE-M0-012-1, BE-M0-012-2, BE-M0-012-3, BE-M0-012-4 |
