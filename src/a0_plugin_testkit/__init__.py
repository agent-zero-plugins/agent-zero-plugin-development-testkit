"""Agent Zero plugin testkit — shared test scaffolding.

Designed for extraction into a standalone repo consumed via git submodule.
All imports work the same whether testkit is vendored in-tree or submoduled.

Stable entry points:

    from a0_plugin_testkit.discovery import KNOWN_HTML_SURFACES, KNOWN_JS_HOOKS
    from a0_plugin_testkit.assertions import (
        assert_extension_at_surface,
        assert_valid_surface,
        assert_valid_js_hook,
    )
    from a0_plugin_testkit.fakes import FakeSettings

Optional (extra dependencies):

    from a0_plugin_testkit.real.fasta2a import scripted_a2a_server  # needs fasta2a+uvicorn
    from a0_plugin_testkit.real.validator import run_plugin_validator  # needs A0 on PYTHONPATH
"""

from __future__ import annotations

__version__ = "0.0.1"
