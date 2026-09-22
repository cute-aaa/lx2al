"""PyInstaller entrypoint (absolute imports; package __main__ uses relative)."""

import sys

from lxmc2alcfg.cli import main

if __name__ == "__main__":
    sys.exit(main())
