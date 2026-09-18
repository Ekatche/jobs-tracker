# Phase 7 — Usage Tracking, Quotas & Monétisation UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Phase 7 of the Master Plan by providing a full subscription & quota tracking interface on `/settings/usage`, allowing users to monitor their monthly LLM allowances and switch tiers.

**Architecture:** Extend FastAPI `usage.py` with `PUT /usage/me/tier` to persist tier upgrades. Add frontend `usageApi` client, TypeScript types, and an interactive Next.js dashboard `/settings/usage` displaying visual quota gauges, pricing cards, and an LLM call audit log.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, Motor (MongoDB), Next.js 14, React, TailwindCSS, TypeScript.

---

## Global Constraints
- Python type hints required for all backend code.
- Preservation of existing models and code annotations.
- Code and comments in English; user chat in French.
- Conventional commits in English imperative style.

---

### Task 1: Backend `PUT /usage/me/tier` Endpoint & Tests

**Files:**
- Modify: `backend/app/routers/usage.py`
- Create: `backend/tests/test_usage_tier_api.py`

- [ ] **Step 1: Write failing unit test**
Create `backend/tests/test_usage_tier_api.py`:
```python
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_database
from app.models import UserModel, UserTier
from main import app

client = TestClient(app)

mock_user_id = str(ObjectId())
mock_user = UserModel(
    id=mock_user_id,
    username="tieruser",
    email="tier@test.com",
    hashed_password="fakehashpassword",
)


@pytest.fixture
def override_auth():
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_update_user_tier(override_auth):
    db = await get_database()
    await db.users.update_one(
        {"_id": ObjectId(mock_user_id)},
        {"$set": {"_id": ObjectId(mock_user_id), "username": "tieruser", "email": "tier@test.com", "tier": "free"}},
        upsert=True,
    )

    res = client.put("/usage/me/tier", json={"tier": "advanced"})
    assert res.status_code == 200
    data = res.json()
    assert data["tier"] == "advanced"

    # Verify in DB
    user_in_db = await db.users.find_one({"_id": ObjectId(mock_user_id)})
    assert user_in_db["tier"] == "advanced"
```

- [ ] **Step 2: Run test to verify it fails**
```bash
docker exec jobtracker-backend pytest tests/test_usage_tier_api.py -v
```
Expected: FAIL (404 or 405 Method Not Allowed)

- [ ] **Step 3: Implement `PUT /usage/me/tier` in `backend/app/routers/usage.py`**
Add `UpdateUserTierRequest` model and `update_my_tier` handler.

- [ ] **Step 4: Run test to verify it passes**
```bash
docker exec jobtracker-backend pytest tests/test_usage_tier_api.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add backend/app/routers/usage.py backend/tests/test_usage_tier_api.py
git commit -m "feat(usage): add PUT /usage/me/tier endpoint for tier updates"
```

---

### Task 2: Frontend Types & API Client

**Files:**
- Create: `frontend/src/types/usage.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Create `frontend/src/types/usage.ts`**
Define `UserTier`, `ActionQuotaUsage`, `UserQuotaSummary`, `ApiUsageRecord`, `TierPricingInfo`.

- [ ] **Step 2: Add `usageApi` in `frontend/src/lib/api.ts`**
Implement `getSummary()`, `getRecords(skip, limit, action)`, `getTiers()`, `updateTier(tier)`.

- [ ] **Step 3: Commit**
```bash
git add frontend/src/types/usage.ts frontend/src/lib/api.ts
git commit -m "feat(usage): add TypeScript types and usageApi client"
```

---

### Task 3: Frontend `/settings/usage` Dashboard & Navigation

**Files:**
- Create: `frontend/src/app/settings/usage/page.tsx`
- Create: `frontend/src/app/settings/page.tsx` (redirect to `/settings/usage`)
- Modify: `frontend/src/components/layout/Header.tsx`

- [ ] **Step 1: Create `/settings/usage/page.tsx`**
Implement user tier header, visual quota progress bars, interactive pricing cards with instant upgrade, and recent LLM activity table.

- [ ] **Step 2: Create `/settings/page.tsx`**
Redirect to `/settings/usage`.

- [ ] **Step 3: Add link to Header user dropdown**
Add "Quotas & Abonnement" in `Header.tsx`.

- [ ] **Step 4: Verify Next.js build**
```bash
cd frontend && npm run build
```
Expected: PASS with 0 errors.

- [ ] **Step 5: Commit**
```bash
git add frontend/src/app/settings/ frontend/src/components/layout/Header.tsx
git commit -m "feat(usage): implement subscription and quota settings dashboard"
```

---

### Task 4: End-to-End Verification & Master Plan Completion

**Files:**
- Modify: `docs/CAREER_OPS_INTEGRATION_PLAN.md`

- [ ] **Step 1: Run all backend tests**
```bash
docker exec jobtracker-backend pytest tests/test_usage_*.py tests/test_interview_prep_*.py -v
```

- [ ] **Step 2: Update Master Plan**
Mark Phase 7 as 100% completed.

- [ ] **Step 3: Commit**
```bash
git add docs/CAREER_OPS_INTEGRATION_PLAN.md
git commit -m "docs: mark Phase 7 and full Master Plan as completed"
```
