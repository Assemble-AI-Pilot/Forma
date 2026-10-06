"""Core for the Assemble Forma (ACC Cost Management) integration."""
import sys

# Keep in step with .claude-plugin/plugin.json - diagnostics reports THIS as
# `plugin_version`, and it sat at 0.7.0 through every 0.8 and 0.9 release.
__version__ = "0.10.1-beta"

# Checked here because this package is imported by every entry point, so the
# message lands whichever way the plugin was started. A version error that says
# "SyntaxError: invalid syntax" tells a non-developer nothing.
_MINIMUM = (3, 10)
if sys.version_info < _MINIMUM:
    raise SystemExit(
        "\nForma MCP needs Python {}.{} or newer. You are running {}.{}.{}\n\n"
        "  Windows: install from https://www.python.org/downloads/windows/\n"
        "           TICK 'Add python.exe to PATH' on the first screen.\n"
        "  macOS:   brew install python@3.12  (or download from python.org)\n\n"
        "Then run:  python login.py setup\n".format(
            _MINIMUM[0], _MINIMUM[1], *sys.version_info[:3]
        )
    )
