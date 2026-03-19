# ADEP PR and Push Instructions

Use this workflow whenever the user asks to push changes.

## Trigger

Apply these steps when the user says any of the following:
- push this
- make a PR
- open a pull request
- commit and push

## Default Safety Rules

1. Do not push directly to `main` unless the user explicitly asks for direct push.
2. Create or use a feature branch before pushing.
3. Do not include unrelated local changes in the commit.
4. Run relevant checks before push.
5. If checks fail, do not push. Report failures and next fix steps.

## Branch Strategy

1. If current branch is `main`, create a branch:
   - `feat/<short-topic>` for features
   - `fix/<short-topic>` for fixes
   - `chore/<short-topic>` for maintenance
2. If already on a non-main branch, keep using it unless user requests a different one.

## Pre-Push Checklist

1. Review changes and confirm only intended files are included.
2. Run checks that match changed scope:
   - Python/backend changes: run backend tests
   - Frontend changes: run frontend tests or build checks
   - Docs-only changes: tests may be skipped
3. Ensure no secrets are committed.

## Commit and Push

1. Stage only intended files.
2. Use a clear commit message:
   - `feat: ...`
   - `fix: ...`
   - `chore: ...`
   - `docs: ...`
3. Push branch to origin.

## Pull Request

1. Open a PR to `main` after a successful push.
2. PR title should match the main change and commit intent.
3. PR body should include:
   - Summary of changes
   - Test evidence (commands run and results)
   - Risks and rollback notes
4. If PR automation is unavailable, provide exact commands for the user.

## Communication Format

When done, provide:
1. Branch name
2. Commit hash and message
3. Test commands and outcomes
4. PR link (or exact command to create it)

## Exceptions

1. If user explicitly asks for direct push to `main`, proceed but warn about bypassing PR review.
2. If environment prevents pushing (auth, network, permissions), stop and provide the exact next command for the user.
