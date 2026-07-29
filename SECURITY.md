# Security Policy

## Supported versions

Only the latest tagged release (`vX.Y.Z`) and `main` receive security fixes. Consumer plugin repos
should keep their vendored `tests/_testkit` submodule pinned to a recent tag.

| Version | Supported |
|---|---|
| Latest release + `main` | ✅ |
| Older tags | ❌ — bump your submodule pin |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Use GitHub's private vulnerability reporting:
[Report a vulnerability](https://github.com/agent-zero-plugins/agent-zero-plugin-development-testkit/security/advisories/new).

Include: affected file/module, reproduction steps, and impact assessment. You will get an
acknowledgement within 7 days and a fix or mitigation plan within 30 days for confirmed issues.

## Scope notes

- The devkit runs **inside CI and dev containers** — it deliberately boots nested, rootless A0
  instances and executes plugin code under test. Reports about the devkit executing the plugin code
  it was asked to test are out of scope.
- Reports about secrets handling in the reusable workflows (`plugin-e2e.yml`, `devkit-sync.yml`),
  the static validator's secret-pattern checks, or sandbox escapes from the devcontainer are
  very much in scope.
- Vulnerabilities in Agent Zero itself should be reported to the upstream
  [agent-zero](https://github.com/agent0ai/agent-zero) project.
