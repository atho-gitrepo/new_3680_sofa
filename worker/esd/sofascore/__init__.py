"""
Sofascore client module.
"""

# Import the main client class
from .client import SofascoreClient 

# Import and expose the specific type needed from the nested module
# 🛠️ THE FIX: Changed 'Entity' to 'entity' to match the file name 'entity.py'
from .types.entity import EntityType 

# Import the entire types submodule as well (for users who want to access other types)
from . import types

# Update __all__ to include the new symbols you want to expose at the package level
__all__ = ["SofascoreClient", "EntityType", "types"]
