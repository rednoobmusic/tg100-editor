import sys

from .gui.main import main

if sys.version_info < (3, 9):
    raise SystemExit("this needs Python 3.9 or newer")

raise SystemExit(main())
