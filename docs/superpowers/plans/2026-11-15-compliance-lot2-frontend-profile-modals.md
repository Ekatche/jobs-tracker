# Compliance Lot 2: Frontend Profile & Application Drawer Modularization

## Scope
Modularize the 4 large components targeted by Lot 2 of `docs/superpowers/specs/2026-11-15-code-size-compliance-roadmap.md` to strictly stay under 300 lines per file with zero UI or API-contract regression:

1. `frontend/src/components/applications/CoverLetterPanel.tsx` (828 → < 300 lines)
   - `frontend/src/hooks/useCoverLetter.ts`
   - `frontend/src/components/applications/CoverLetterStates.tsx`
   - `frontend/src/components/applications/CoverLetterReviewBanner.tsx`
   - `frontend/src/components/applications/CoverLetterRewriteBox.tsx`
2. `frontend/src/components/applications/ApplicationDetails.tsx` (933 → < 300 lines)
   - `frontend/src/hooks/useApplicationDrawer.ts`
   - `frontend/src/components/applications/ApplicationEvalCard.tsx`
   - `frontend/src/components/applications/ApplicationDrawerBody.tsx`
   - `frontend/src/components/applications/ApplicationNotesCard.tsx`
3. `frontend/src/components/profile/TargetingPreferencesSection.tsx` (999 → < 300 lines)
   - `frontend/src/hooks/useTargetingPreferences.ts`
   - `frontend/src/components/profile/targeting/targetingOptions.ts`
   - `frontend/src/components/profile/targeting/TargetingSectionShell.tsx`
   - `frontend/src/components/profile/targeting/TargetingRolesSection.tsx`
   - `frontend/src/components/profile/targeting/TargetingLocationsSection.tsx`
   - `frontend/src/components/profile/targeting/TargetingContractSalarySection.tsx`
   - `frontend/src/components/profile/targeting/TargetingSectorsBlacklistSection.tsx`
4. `frontend/src/components/profile/CandidateProfileSection.tsx` (1,687 → < 300 lines)
   - `frontend/src/lib/profileFormatters.ts`
   - `frontend/src/hooks/useCandidateProfile.ts`
   - `frontend/src/components/profile/sections/CollapsibleSection.tsx`
   - `frontend/src/components/profile/sections/ProfileSummaryView.tsx`
   - `frontend/src/components/profile/sections/ProfileWorkView.tsx`
   - `frontend/src/components/profile/sections/ProfileProjectsView.tsx`
   - `frontend/src/components/profile/sections/ProfileCredentialsView.tsx`
   - `frontend/src/components/profile/sections/ProfileCoreEditFields.tsx`
   - `frontend/src/components/profile/sections/ProfileExperiencesEditor.tsx`
   - `frontend/src/components/profile/sections/ProfileProjectsEditor.tsx`
   - `frontend/src/components/profile/sections/ProfileCredentialsEditor.tsx`

## Non-goals
- No backend edits.
- No changes to component public props contracts or visual styling.

## Verification
```bash
cd frontend && npm run lint && npm run build
```
