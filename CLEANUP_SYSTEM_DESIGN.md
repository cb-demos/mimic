# Mimic Cleanup System Design

## Overview

This document outlines the design for a comprehensive cleanup system for the Mimic demo resource provisioning tool. The system addresses the problem of accumulating demo resources in GitHub and CloudBees Unify by implementing user-scoped resource tracking with automated and manual cleanup capabilities.

## Problem Statement

- Multiple users access Mimic through both UI (shared environment) and MCP (individual machines)
- Resources are created in GitHub (using shared service account) and CloudBees Unify (using user PATs)
- Currently no cleanup mechanism exists, leading to resource accumulation
- Users should only be able to clean up their own resources
- Challenge: CloudBees cleanup requires the original creator's PAT (no shared service account available)

## Architecture Changes

### 1. MCP Server Migration

**Current State:**
- Local MCP servers running via stdio
- Dual codebase maintenance (`mcp_main.py`, `mcp_server.py`)
- Complex HTTP callback architecture for resource tracking

**New State:**
- Single HTTP MCP endpoint at `/mcp` on hosted server
- Remove local MCP server components
- Unified codebase and resource tracking

**Benefits:**
- Simplified architecture
- Automatic updates for all users
- Consistent resource tracking
- Single authentication point

### 2. Database Schema

**Note on Database Choice:** For the expected internal usage (10-20 users/day), the proposed `sqlite` database is a practical choice that simplifies deployment. To mitigate potential concurrency issues between user actions and the cleanup job, the database should be configured to use **Write-Ahead Logging (WAL) mode**, which allows for greater concurrency between readers and writers.

```sql
-- User table - keyed by email address
CREATE TABLE users (
    email TEXT PRIMARY KEY,  -- Company email address
    name TEXT,  -- Optional display name
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- PAT storage with rotation support and multi-platform
CREATE TABLE user_pats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT REFERENCES users(email),
    encrypted_pat TEXT NOT NULL,
    platform TEXT NOT NULL DEFAULT 'cloudbees',  -- 'cloudbees' or 'github'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Resource sessions tied to user email
CREATE TABLE resource_sessions (
    id TEXT PRIMARY KEY,
    email TEXT REFERENCES users(email),
    scenario_id TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  -- NULL = no expiration
    parameters JSON
);

-- Resources linked to sessions
CREATE TABLE resources (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES resource_sessions(id) ON DELETE CASCADE,
    resource_type TEXT NOT NULL,  -- 'github_repo', 'cloudbees_component', etc.
    resource_id TEXT NOT NULL,    -- GitHub repo full_name, CloudBees UUID, etc.
    resource_name TEXT NOT NULL,
    platform TEXT NOT NULL,      -- 'github' or 'cloudbees'
    status TEXT NOT NULL DEFAULT 'active', -- 'active', 'delete_pending', 'deleted', 'failed'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON                 -- platform-specific data for cleanup
);

-- Indexes
CREATE INDEX idx_user_pats_platform ON user_pats(email, platform, is_active, created_at DESC);
CREATE INDEX idx_resources_session ON resources(session_id);
CREATE INDEX idx_resources_status ON resources(status); -- For finding resources to clean up
CREATE INDEX idx_sessions_user ON resource_sessions(email);
CREATE INDEX idx_sessions_expires ON resource_sessions(expires_at);
```

### 3. Security Implementation

**Encryption Library:** `cryptography` (Fernet) - battle-tested, FIPS 140-2 compliant

```python
# src/security.py
from cryptography.fernet import Fernet
import os
import base64

class SecurePATManager:
    def __init__(self):
        key = os.environ.get('PAT_ENCRYPTION_KEY')
        if not key:
            raise ValueError("PAT_ENCRYPTION_KEY is not set in the environment.")

        # Key should already be base64-encoded in environment variable
        self.cipher = Fernet(key.encode('ascii'))

    def encrypt(self, pat: str) -> str:
        encrypted_bytes = self.cipher.encrypt(pat.encode())
        return base64.urlsafe_b64encode(encrypted_bytes).decode()

    def decrypt(self, encrypted_pat: str) -> str:
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_pat.encode())
        return self.cipher.decrypt(encrypted_bytes).decode()
```

**Environment Variables:**
```bash
# Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
PAT_ENCRYPTION_KEY="base64-encoded-32-byte-fernet-key-here"
DATABASE_URL="sqlite:///./mimic.db?mode=wal"
```

## User Experience Flow

### Initial Authentication (Both UI and MCP)

1. **User Input**
   - User enters their company email address
   - User enters required CloudBees Unify PAT
   - Optional: User can provide custom GitHub PAT for private orgs

2. **Token Validation**
   - Test CloudBees PAT with simple API call (e.g., `get_organization`)
   - Test GitHub PAT if provided
   - No need to fetch user details from API

3. **User Record Creation**
   - Store user record keyed by email address
   - Encrypt and store both PATs linked to email
   - Support multiple PATs per user per platform (for rotation)

4. **Session Creation**
   - Each scenario execution creates a session
   - Optional expiration date (default 7 days)
   - Resources linked to session

### UI Authentication Flow

```javascript
// Check localStorage first
const userData = localStorage.getItem('mimic_user_data');
if (userData) {
    loadMainApp(JSON.parse(userData));
} else {
    showTokenEntryForm();
}

// Token verification
async function verifyTokens() {
    const response = await fetch('/api/auth/verify-tokens', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({
            email: userEmail,
            unify_pat: unifyPat,
            github_pat: githubPat || null
        })
    });

    const result = await response.json();
    if (result.success) {
        localStorage.setItem('mimic_user_data', JSON.stringify(result.user));
        loadMainApp(result.user);
    }
}
```

### MCP Configuration (HTTP-based)

```json
{
  "mcpServers": {
    "mimic": {
      "command": "npx",
      "args": [
        "@modelcontextprotocol/server-fetch",
        "https://mimic.cloudbees.io/mcp"
      ],
      "env": {
        "EMAIL": "your-company-email@company.com",
        "UNIFY_API_KEY": "your-cloudbees-pat",
        "GITHUB_TOKEN": "optional-github-pat"
      }
    }
  }
}
```

**Note**: The MCP client automatically includes these environment variables in requests to the HTTP endpoint. The server extracts EMAIL and UNIFY_API_KEY from each request to authenticate and identify the user, following standard MCP conventions.

## Cleanup Implementation

### Manual Cleanup

**UI Dashboard (`/cleanup` page):**
```html
<div class="cleanup-dashboard">
  <h2>My Demo Resources</h2>
  <div class="sessions-list">
    <div class="session-card">
      <h3>hackers-app-demo</h3>
      <p>Created: 2 days ago</p>
      <p>Expires: 5 days</p>
      <div class="resources">
        <span>3 repos, 2 apps, 1 env</span>
      </div>
      <button class="cleanup-btn">Clean Up</button>
    </div>
  </div>
</div>
```

**MCP Tools:**
```python
@mcp.tool
async def list_my_resources(email: str, unify_pat: str) -> dict:
    """List all your demo sessions with cleanup options"""

@mcp.tool
async def cleanup_session(session_id: str, email: str, unify_pat: str) -> dict:
    """Clean up a specific demo session"""
```

### Automated Cleanup

**Background Job (Two-Stage Process):**
This process is split into two parts to be more robust and idempotent.

```python
async def mark_expired_resources():
    """Stage 1: Mark resources in expired sessions for deletion."""
    await db.execute("""
        UPDATE resources
        SET status = 'delete_pending'
        WHERE session_id IN (
            SELECT id FROM resource_sessions
            WHERE expires_at IS NOT NULL AND expires_at < CURRENT_TIMESTAMP
        ) AND status = 'active'
    """)

async def process_pending_deletions():
    """Stage 2: Process resources marked for deletion idempotently."""
    resources_to_delete = await db.fetchall("""
        SELECT r.id, s.email
        FROM resources r
        JOIN resource_sessions s ON r.session_id = s.id
        WHERE r.status = 'delete_pending'
    """)

    for resource in resources_to_delete:
        try:
            # This service should handle 'Not Found' errors gracefully,
            # treating them as a successful cleanup.
            await cleanup_service.cleanup_single_resource(
                resource['id'],
                resource['email']
            )
            await db.execute(
                "UPDATE resources SET status = 'deleted' WHERE id = ?",
                (resource['id'],)
            )
        except NoValidPATFoundError as e:
            logger.warning(f"Cleanup failed for resource {resource['id']} due to invalid PAT. Marking as 'failed'.")
            await db.execute(
                "UPDATE resources SET status = 'failed' WHERE id = ?",
                (resource['id'],)
            )
        except Exception as e:
            logger.error(f"Failed to cleanup resource {resource['id']}: {e}")
            # Resource remains 'delete_pending' to be retried on the next run.
```

### PAT Rotation Handling

**Fallback Strategy:**
A custom exception should be used to signal when no valid PAT can be found, allowing the cleanup job to handle it gracefully.

```python
# Define a custom exception for clarity
class NoValidPATFoundError(Exception):
    pass

async def _get_working_pat(self, email: str, platform: str) -> str:
    """Get most recent valid PAT, falling back to older ones"""
    pats = await db.fetchall("""
        SELECT id, encrypted_pat, created_at
        FROM user_pats
        WHERE email = ? AND platform = ? AND is_active = true
        ORDER BY created_at DESC
    """, (email, platform))

    for pat_row in pats:
        try:
            decrypted_pat = pat_manager.decrypt(pat_row['encrypted_pat'])

            # Test if PAT still works
            if platform == 'cloudbees':
                with UnifyAPIClient(api_key=decrypted_pat) as client:
                    # Test call - will need to use a known org_id in actual implementation
                    client.get_organization(some_org_id)  # Test call
            elif platform == 'github':
                # Test GitHub API call
                pass

            return decrypted_pat

        except Exception as e:
            logger.warning(f"PAT from {pat_row['created_at']} failed: {e}")
            # Optionally, mark this PAT as inactive so we don't retry it
            # await db.execute("UPDATE user_pats SET is_active = false WHERE id = ?", (pat_row['id'],))
            continue

    raise NoValidPATFoundError(f"No working PAT found for user {email}")
```

## API Endpoints

### New Endpoints

```python
# Authentication
POST /api/auth/verify-tokens
  - Verify Unify + optional GitHub PATs with email
  - Return user details

# Session Management (context-based, no user lookup needed)
POST /api/sessions
  - Create resource session with optional expiration
  - Store encrypted PATs linked to authenticated user

GET /api/my/sessions
  - List current user's sessions with resource counts

DELETE /api/sessions/{session_id}
  - Clean up specific session (validates ownership)

DELETE /api/my/cleanup
  - Clean up current user's old/expired sessions

# Resource Registration
POST /api/sessions/{session_id}/resources
  - Register created resource to session

# MCP Endpoint
POST /mcp
  - HTTP MCP server endpoint
  - Authenticates via EMAIL and UNIFY_API_KEY from request headers/env
```

## Implementation Plan

### ✅ Phase 1: Core Infrastructure (COMPLETED)
1. ✅ Implement database schema and migrations (using WAL mode for SQLite)
2. ✅ Implement secure PAT encryption system
3. ✅ Add user authentication service
4. ✅ Implement cleanup service with robust PAT rotation and error handling
5. ✅ Comprehensive test coverage (49 passing tests)
6. ✅ Full type safety and linting compliance

### ✅ Phase 2: UI Authentication & Token Management (COMPLETED)
1. ✅ Add user token entry UI (email + CloudBees PAT + optional GitHub PAT)
2. ✅ Store tokens in localStorage for UI sessions
3. ✅ Update existing APIs to accept user tokens in request bodies
4. ✅ Initialize database on app startup
5. ✅ Add session creation with user context

### ✅ Phase 3: Resource Tracking Integration (COMPLETED)
1. ✅ Modify `CreationPipeline` to register resources to sessions
2. ✅ Update scenario instantiation to create sessions and track resources
3. ✅ Add user context and GitHub PAT handling to all resource operations
4. ✅ Register ALL resources (GitHub repos, CloudBees components, environments, applications)
5. ✅ Exclude feature flags from cleanup (shared resources)
6. ✅ Add comprehensive test coverage (75 passing tests)
7. ✅ Implement robust error handling for resource registration

### Phase 4: Cleanup UI & Manual Operations
1. Add cleanup dashboard UI (`/cleanup` page) showing user's sessions
2. Add manual cleanup APIs (`DELETE /api/sessions/{id}`)
3. Add cleanup status and history tracking
4. Test manual cleanup flow via UI

### Phase 5: Background Jobs & Automation
1. Implement two-stage automated cleanup background job
2. Add cleanup job scheduling and monitoring
3. Add expired session handling
4. Test automated cleanup with real scenarios

### Phase 6: MCP Integration (FINAL PHASE)
1. Remove local MCP components (`mcp_main.py`, `mcp_server.py`)
2. Add HTTP MCP endpoint to FastAPI app
3. Update MCP client configuration to pass tokens via environment
4. Test MCP authentication and cleanup flows

### Phase 7: Production Readiness
1. Security review and hardening
2. Performance testing and optimization
3. Deployment configuration and monitoring
4. Documentation updates

## Future Enhancements

### Transactional Resource Creation (Post-MVP)
**Problem**: Currently if resource creation fails midway through a scenario, partially created resources remain and need manual cleanup.

**Solution**: Implement atomic scenario creation with rollback capability:
1. **Pre-creation validation**: Validate all parameters and check resource availability before creating anything
2. **Two-phase creation**:
   - Phase 1: Create all resources and mark them as "provisional"
   - Phase 2: Mark all resources as "active" only if the entire scenario succeeds
3. **Automatic rollback**: If any step fails, automatically clean up all provisional resources
4. **Database transactions**: Use database transactions to ensure resource tracking consistency

**Implementation considerations**:
- Would require modifications to both GitHub and CloudBees APIs to support "draft" resources
- Alternative: Create resources normally but maintain a "creation transaction" that can trigger cleanup
- Could be implemented as a wrapper around the existing CreationPipeline

**Priority**: Medium (implement after basic cleanup system is stable and proven)

### Enhanced Error Recovery
- Retry logic for transient API failures
- Partial scenario recovery (continue from last successful step)
- User notification system for failed operations

### Advanced Resource Management
- Resource dependencies and ordered cleanup
- Resource sharing between scenarios
- Resource lifecycle management (expire after N days)

## Security Considerations

- **Encryption**: All PATs encrypted at rest using Fernet (AES 128)
- **Key Management**: Single master key in environment variable. **Must not be logged or exposed.**
- **Email Validation**: Ensure emails are normalized (lowercase) and validated for company domain
- **Access Control**: Users can only clean up their own resources based on email identity
- **PAT Rotation**: System handles expired PATs gracefully by marking resources as failed, preventing job crashes.
- **Audit Trail**: All resource creation and cleanup logged with status changes.

## Benefits

- **User Safety**: Isolated resource management per user
- **Automatic Cleanup**: Prevents resource accumulation
- **Simplified Architecture**: Single hosted service
- **PAT Rotation**: Handles credential changes gracefully
- **Flexible GitHub Access**: Supports both service account and user PATs
- **Unified Experience**: Same functionality via UI and MCP

## Files to Modify/Create

### Remove
- `src/mcp_main.py`
- `src/mcp_server.py`

### Create
- `src/security.py` - PAT encryption/decryption
- `src/auth.py` - User authentication services
- `src/cleanup.py` - Resource cleanup services
- `src/database.py` - Database setup and migrations
- `templates/cleanup.html` - Cleanup dashboard UI

### Modify
- `src/main.py` - Add HTTP MCP endpoint, auth APIs
- `src/creation_pipeline.py` - Add resource registration
- `src/scenario_service.py` - Add session management
- `src/config.py` - Add encryption key settings
- `static/js/main.js` - Add email and token entry flow
- `requirements.txt` - Add cryptography dependency
- `Dockerfile` - Remove MCP mode logic
- `README.md` - Update configuration docs

This design provides a comprehensive solution to the cleanup problem while improving the overall architecture and user experience.
