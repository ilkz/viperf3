#!/usr/bin/env bash
# Build a standalone viperf3 binary (no Python/venv needed on the target).
#
# Requirements on the build machine:
#   - pyinstaller, either in the project venv or on PATH
#   - libpython3.10 (apt install libpython3.10) — PyInstaller needs the shared lib
#
# The result is dist/viperf3 (~18 MB).  Target machine requirements:
#   - same or newer glibc than the build machine (build on the oldest distro
#     you need to support; Ubuntu 22.04 → glibc 2.35)
#   - iperf3 >= 3.17 on PATH (not bundled on purpose)
set -euo pipefail
cd "$(dirname "$0")/.."

# Use the project venv when it exists, otherwise whatever is on PATH (CI).
if [ -x .venv/bin/pyinstaller ]; then
    PYINSTALLER=.venv/bin/pyinstaller
else
    PYINSTALLER=pyinstaller
fi

"$PYINSTALLER" --onefile --name viperf3 \
    --paths . \
    --collect-submodules viperf3 \
    --add-data "viperf3/app.tcss:viperf3" \
    --clean --noconfirm build_scripts/entry.py

ls -lah dist/viperf3
echo "OK: dist/viperf3"
