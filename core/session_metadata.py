"""
Session Metadata Management
Supports custom attributes and metadata storage per session.
"""

from typing import Dict, Any, Optional
from datetime import datetime


class SessionMetadataManager:
    """Manages custom metadata and attributes for sessions."""
    
    def __init__(self):
        pass
    
    def set_metadata(self, session: Dict[str, Any], key: str, value: Any) -> Dict[str, Any]:
        """
        Set a custom metadata attribute in the session.
        
        Args:
            session: Session dictionary
            key: Metadata key
            value: Metadata value (must be JSON-serializable)
        
        Returns:
            Updated session dictionary
        """
        if "metadata" not in session:
            session["metadata"] = {}
        
        session["metadata"][key] = value
        session["metadata"]["_last_updated"] = datetime.utcnow().isoformat()
        
        return session
    
    def get_metadata(self, session: Dict[str, Any], key: str, default: Any = None) -> Any:
        """
        Get a custom metadata attribute from the session.
        
        Args:
            session: Session dictionary
            key: Metadata key
            default: Default value if key not found
        
        Returns:
            Metadata value or default
        """
        if "metadata" not in session:
            return default
        
        return session["metadata"].get(key, default)
    
    def get_all_metadata(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get all metadata from the session.
        
        Args:
            session: Session dictionary
        
        Returns:
            Dictionary of all metadata
        """
        return session.get("metadata", {})
    
    def remove_metadata(self, session: Dict[str, Any], key: str) -> Dict[str, Any]:
        """
        Remove a metadata attribute from the session.
        
        Args:
            session: Session dictionary
            key: Metadata key to remove
        
        Returns:
            Updated session dictionary
        """
        if "metadata" in session and key in session["metadata"]:
            del session["metadata"][key]
            session["metadata"]["_last_updated"] = datetime.utcnow().isoformat()
        
        return session
    
    def set_custom_attribute(self, session: Dict[str, Any], attribute: str, value: Any) -> Dict[str, Any]:
        """
        Set a custom attribute (alias for set_metadata for clarity).
        
        Args:
            session: Session dictionary
            attribute: Attribute name
            value: Attribute value
        
        Returns:
            Updated session dictionary
        """
        return self.set_metadata(session, attribute, value)
    
    def get_custom_attribute(self, session: Dict[str, Any], attribute: str, default: Any = None) -> Any:
        """
        Get a custom attribute (alias for get_metadata for clarity).
        
        Args:
            session: Session dictionary
            attribute: Attribute name
            default: Default value if attribute not found
        
        Returns:
            Attribute value or default
        """
        return self.get_metadata(session, attribute, default)


# Global instance
metadata_manager = SessionMetadataManager()
