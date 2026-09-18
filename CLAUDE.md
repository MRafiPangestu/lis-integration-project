# CLAUDE.md

Project instructions for Claude Code in this repository. These rules are permanent and apply to every session, in the CLI and in the GUI. A task may add constraints; it does not remove these unless it says so explicitly.

## Project orientation

Laboratory Information System (LIS). Backend: FastAPI + SQLAlchemy + Alembic on PostgreSQL (`backend/`). Frontend: React + Vite (`frontend/`). Documentation and instrument evidence: `docs/`.

Development happens on **`refactor/orm-architecture`**. `main` tracks the same commit and is not a development branch. `poc/mindray` preserves the original proof-of-concept.

Instrument tracks are at different stages and must not be conflated: Mindray BC-5150 (implemented, clinical path), Sysmex XN-550 (implemented through the frontend, development baseline frozen), Boditech ichroma II (survey evidence only — nothing implemented).

## Git Commit and Push Rules

### 1. Pre-commit inspection

Before every commit:

- run `git status`;
- inspect `git diff`;
- inspect `git diff --cached` whenever anything is staged;
- confirm that every change about to be committed belongs to the current task.

Never commit without looking at what is being committed. `git commit -a` and a blind `git add -A` are not substitutes for this.

### 2. Commit message

When the task supplies an exact message — for example:

> Commit the current changes with this exact message:
> `<message>`

use **exactly** that message, byte for byte. Do not rewrite it, improve its wording, fix its capitalisation, add a prefix or scope, append an explanation or extra paragraph, or add any trailer.

When the task supplies no message, write one that describes the change, following the convention already in this repository's history: `type(scope): summary`, e.g. `feat(xn550): …`, `docs(ichroma2): …`, `fix(…)`, `test(…)`, `chore: …`. This is a rule about behaviour: the message comes from the task when the task gives one, and from the change itself when it does not.

### 3. No `Co-Authored-By`

Never add a `Co-Authored-By:` trailer to any commit. Never add generated attribution, tool advertising, or similar metadata to a commit message.

This applies to new commits. Commits already in the published history are history — do not rewrite them to remove a trailer.

### 4. Commit scope

Commit only what the current task changed.

Never include, silently or otherwise:

- unrelated working-tree changes, including work left over from another task;
- temporary files, scratch scripts, debug output or generated junk;
- secrets, credentials, tokens or connection strings;
- PHI, real patient identifiers, patient names, specimen or sample numbers;
- raw clinical data or raw instrument captures containing identifiers;
- private instrument survey evidence that has not been sanitised and approved.

If the working tree already holds unrelated changes, leave them alone. Keep them out of the commit — do not stash them away, revert them or delete them to get a clean tree. Stage specific paths rather than everything.

### 5. Push

After a successful commit, push the current branch to its corresponding `origin` branch, unless the task says not to push.

- Push the branch that is checked out, never another one.
- If the branch has no upstream, determine the correct `origin` branch first (normally the same name) and set it with `git push -u origin <branch>`. Do not guess, and do not push to a differently named branch.
- **Never force-push without explicit authorisation.** When force is explicitly authorised, use `--force-with-lease`, never bare `--force`.
- Do not rewrite or otherwise alter published history as a side effect of pushing.

### 6. Post-commit verification

After committing and pushing, verify and report:

- the exact commit SHA;
- the current branch;
- the push result, including the ref update line;
- `git status`, and whether the working tree is clean;
- whether the branch is in sync with its upstream.

Report what actually happened. If the push failed or was rejected, say so and stop rather than working around it.

### 7. Destructive Git operations

Never run these without explicit user authorisation for that specific action:

- `git reset --hard`
- `git clean -fd`
- force push in any form
- rewriting published history (`rebase`, `commit --amend` on a pushed commit, `filter-branch`)
- deleting branches or tags
- reverting work that belongs to another task

Do not reach for a destructive command merely to make the working tree look clean. A dirty tree containing someone else's work is not a problem to be cleaned up.

## Repository safety

- **Databases.** `lis_marina_permata` is the stable PoC database: never modify it. Development uses `lis_marina_permata_dev`, tests use `lis_marina_permata_test`, and migration-chain tests create their own disposable `zz_m90_test_*` databases. `lis_marina_permata_migration_test` is retained deliberately pending an owner decision — do not delete it. Do not run migrations against any database unless the task asks for it, and name the target explicitly when you do.
- **Production.** Do not modify production systems, deployment configuration or shipped example configuration unless the task asks. Local developer settings live in the gitignored `backend/instruments.json`; `backend/instruments.example.json` is the shipped file.
- **Evidence versus implementation.** Instrument survey evidence, field-validation records and implementation contracts are different classes of document and must stay distinguishable. Never edit a historical validation record to match current code.
- **Claims must match evidence.** Do not claim a physical instrument was connected, tested or validated without evidence that it was. Do not present an assumption about protocol behaviour — framing, identity fields, ACK handling, timing — as an observed fact. Say UNKNOWN when it is unknown, and state which evidence class a finding rests on.
- **PHI.** Never commit PHI or real patient identifiers. Raw instrument captures containing identifiers stay outside the repository unless explicitly approved and properly sanitised. Scan added lines before committing anything derived from instrument evidence.
- **No collateral changes.** Do not modify an existing instrument integration, its parser, schema, API or frontend as a side effect of work on something else. If a change there looks necessary, raise it instead of making it.
