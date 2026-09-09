# Skill Maintenance and Release

Use this workflow only when the user asks to update, compare, commit, push, install, or derive reusable Ptah skill guidance. Do not add Git or installation work to an ordinary data-flow task.

## Source contract

- The version-controlled `skills/ptah-data-flow` directory is the release source of truth.
- The Codex `ptah-data-flow` skill directory is a deployed runtime mirror, not a Git checkout and not the canonical editing surface.
- The public release is `https://github.com/data-flowers/codex-skills/tree/main/skills/ptah-data-flow` unless the user names another remote.
- A parity claim covers the entire skill tree, including `SKILL.md`, `agents`, `references`, `scripts`, and assets. Ignore only transient files such as `__pycache__`, `*.pyc`, and `.DS_Store`.

## Fast maintenance loop

1. Locate the repository checkout and installed skill. Inspect the repository status and keep unrelated changes out of the skill update.
2. Fetch the repository remote before editing. If the branch is behind or diverged, integrate the remote first; do not build a release on a stale base.
3. Run `scripts/audit_skill_sync.py --source <repo-skill> --installed <installed-skill>`. Review every source-only, installed-only, and changed path. An installed-only change is a candidate lesson to port, not permission to overwrite a newer repository file wholesale.
4. Make the semantic change in the repository copy. Merge overlapping guidance deliberately and preserve newer remote capabilities.
5. Validate the complete repository skill with the skill validator, compile all bundled Python scripts, syntax-check changed JavaScript modules, and run the repository whitespace check.
6. Stage only the intended Ptah paths and create one logical commit after the full-tree audit. If pushing is authorized, fetch again when the task has been long-running or the remote may have changed, rebase before push, and never force-push merely to publish the skill.
7. Refresh the installed skill from the final committed repository tree using the environment's supported installer or an exact local deployment. Do this after conflict resolution so the runtime receives the released result, not the pre-rebase draft.
8. Run the parity audit again. Completion requires `identical: true`, a clean repository, the final commit id, and—when a push was requested—confirmation that the local branch and upstream match.

## Conflict rules

- Preserve both independently useful capabilities when parallel changes overlap.
- Prefer the newer repository workflow for operational mechanics, then add the learned invariant at the narrowest relevant point.
- Drop duplicate wording rather than carrying both variants through a rebase.
- If source and installed copies changed independently and intent is ambiguous, report the exact paths and ask before replacing either side.

## Reporting

State separately:

- repository source updated or unchanged
- commit created and pushed, or not authorized
- installed runtime refreshed or still stale
- parity result and any ignored transient paths

Do not say “the skill is current” when only the repository or only the installed copy was updated.
