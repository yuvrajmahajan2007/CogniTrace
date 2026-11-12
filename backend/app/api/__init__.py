# backend/app/api/__init__.py
# Export the router so that `from .api import files` provides a module with `router` attribute.
from .files import router  # noqa: F401
