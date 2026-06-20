# Devkit devcontainer (Phase-0 spike)

One image, three uses (SPEC `DEC-018`):

1. **CI** runs the plugin e2e lifecycle inside it.
2. **Developers** use it as a dev container.
3. **AI agents** run it (docker or podman) to develop + test locally before pushing.

It boots the Agent Zero container **nested and unprivileged** via **rootless podman** —
no `--privileged`, no host `docker.sock`.

> **Spike finding (base image is load-bearing):** basing on the official Playwright image
> (Ubuntu jammy) + apt `podman` (3.4.4) **fails** to nest rootlessly —
> `cannot setup namespace using newuidmap`. Basing on `quay.io/podman/stable`
> (podman 5.8.2, purpose-built for nesting) **works** (verified locally:
> `NESTED_IN_DEVKIT_OK`). So the image bases on podman/stable; **Playwright** browsers are a
> **Phase-1** Fedora addition (the Phase-0 gate is *nesting*, which needs no browser). See
> SPEC `DEC-039`.

## Why this exists

The whole plugin-quality-standard rests on one risky assumption (`Critical-4` in
`SPEC-REVIEW-001.md`): that rootless podman-in-podman works on GitHub-hosted runners.
This directory is the **Phase-0 gate** that proves it before anything else is built.

The mechanism was confirmed on a real Linux host:

```
podman run --device /dev/fuse --security-opt label=disable --user podman \
  quay.io/podman/stable \
  podman run --rm docker.io/library/alpine echo OK      # → OK, no --privileged
```

## Run it

Locally (needs rootless podman + `/dev/fuse` + subuid/subgid on the host):

```bash
podman build -t plugin-devkit:spike -f devcontainer/Containerfile devcontainer
podman run --rm --device /dev/fuse --security-opt label=disable \
  -v "$PWD":/workspace -w /workspace plugin-devkit:spike \
  -lc 'bash devcontainer/spike/run-acceptance.sh'
```

In CI: the `devcontainer-spike` workflow runs exactly this on `ubuntu-latest`.

## Acceptance (`spike/run-acceptance.sh`)

Passes iff, unprivileged: (1) a nested rootless container runs, (2) the real A0 image
boots nested and `/login` becomes healthy, (3) the harness logs in and gets an
authenticated response. The full `install → verify-installed → uninstall →
verify-uninstalled` cycle layers on top via the existing Playwright harness (Phase 2).

> Status: spike. The image pins `mcr.microsoft.com/playwright:v1.48.0-jammy`; bump in
> lockstep with the harness's Playwright version when this graduates out of spike.
