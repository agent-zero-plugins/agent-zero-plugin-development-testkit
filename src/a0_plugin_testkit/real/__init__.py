"""Real (non-fake) helpers: spin up actual A0 pieces in-process.

Deliberately separated from `a0_plugin_testkit.fakes` because these helpers
have real dependencies (fasta2a, httpx, uvicorn, a running A0 submodule, etc.)
that most unit tests don't want to pull in.

Current contents:

    from a0_plugin_testkit.real.fasta2a     import scripted_a2a_server, ScriptedWorker
    from a0_plugin_testkit.real.validator   import static_validate, assert_validator_clean
    from a0_plugin_testkit.real.deps        import audit_dependencies, assert_dependencies_declared
    from a0_plugin_testkit.real.public_urls import assert_no_naked_container_urls_in_public_response
    from a0_plugin_testkit.real.ports       import assert_plugin_declares_required_ports

Planned:

    from a0_plugin_testkit.real.llm       import fake_openai_server   # roadmap
    from a0_plugin_testkit.real.compose   import a0_container         # roadmap
"""

from __future__ import annotations
