"""
Utility helper functions for API field name conversion and other utilities.
"""

from typing import Dict, Any


def snake_to_camel(name: str) -> str:
    """Convert snake_case to camelCase."""
    components = name.split('_')
    return components[0] + ''.join(x.capitalize() for x in components[1:])


def convert_config_to_camel(config: Dict[str, Any]) -> Dict[str, Any]:
    """Convert config dictionary keys from snake_case to camelCase."""
    camel_config = {}
    for key, value in config.items():
        camel_key = snake_to_camel(key)
        camel_config[camel_key] = value
    return camel_config
