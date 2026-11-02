# CLAUDE.md

## OpenSpec workflow (required)

All user-facing changes to this repository MUST go through the OpenSpec framework. A change is user-facing if it alters behavior that users or downstream consumers can observe (new features, bug fixes, changed outputs or configuration they rely on).

Do not edit user-facing code directly without an associated OpenSpec change. Use the following workflow:

1. **Explore** (optional): `/opsx:explore` to think through ideas or clarify requirements.
2. **Propose**: `/opsx:propose` to create a change with its proposal, design, specs, and tasks.
3. **Update** (if the plan changes): `/opsx:update` to revise the change's artifacts and keep them coherent.
4. **Apply**: `/opsx:apply` to implement the tasks from the change.
5. **Sync / Archive**: `/opsx:sync` to sync delta specs to main specs, then `/opsx:archive` to finalize the completed change.

If a requested user-facing change has no OpenSpec change yet, create one with `/opsx:propose` before writing any implementation code.

### Exclusions

The following are exempt from the OpenSpec workflow and may be edited directly:

- Documentation-only changes (e.g., `README.md`, other `.md` docs, code comments).
- Non-user-facing changes, such as CI/CD workflows, build and tooling configuration, test-only changes, and internal refactors with no observable behavior change.
