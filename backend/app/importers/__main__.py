"""``python -m app.importers <bundle.zip> ...`` does the same as ``python -m app.importers.pitchdriven``."""
from .pitchdriven import main

if __name__ == "__main__":
    raise SystemExit(main())
