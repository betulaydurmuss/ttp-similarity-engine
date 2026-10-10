"""Stage 4 -- the station: a JSON API over the engine plus the built interface.

* ``service`` -- gathers engine artefacts into what the interface draws
* ``app``     -- FastAPI routes, validation, security headers, static hosting
"""

from __future__ import annotations

__all__ = ["app", "service"]
