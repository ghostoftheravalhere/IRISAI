# IRIS AI V4 — Permanent Agent Rules for Antigravity

1. **Read Current State**: Always read `.ai/current_state.md` before starting work.
2. **Read Task Queue**: Always read `.ai/task_queue.md` before selecting or proposing work.
3. **Read Decisions Log**: Always read `.ai/decisions.md` before proposing or implementing architecture changes.
4. **No Silent Sprints**: Never silently begin a new sprint or feature without explicit user request and approval.
5. **Scoped Modifications**: Never modify unrelated modules outside the scope of the current task.
6. **Fact-Based Testing**: Never claim tests passed unless they were actually executed in the current session.
7. **Empirical Verification**: Never claim runtime integration from unit tests alone; perform real integration tests.
8. **Update Current State**: Update `.ai/current_state.md` after completing every task.
9. **Update Verification Status**: Update `.ai/verification.md` immediately after executing test suites.
10. **Update Handoff Log**: Update `.ai/handoff.md` after every completed task.
11. **Update Task Queue**: Update `.ai/task_queue.md` whenever a task's status changes (e.g., pending -> in_progress -> complete).
12. **Record Architecture Decisions**: Record all significant architecture decisions in `.ai/decisions.md` (date, decision, reason, impact).
13. **Preserve Backward Compatibility**: Preserve existing APIs and backward compatibility unless breaking changes are explicitly requested and approved.
14. **Clean Code Isolation**: Keep production source code clean and separate from temporary scratch scripts or diagnostic files.
15. **No Unapproved Staging**: Never stage or push unapproved files to Git.
16. **No Force-Push**: Never use `git push --force` or `git push -f`.
17. **No Bulk Staging**: Never use `git add .` or `git add -A` for sprint commits.
18. **Explicit Staging Output**: Before committing, list and display the exact staged files to the user.
19. **Single Task Execution**: Never auto-start a new task after completing a task unless explicitly instructed by the user.
