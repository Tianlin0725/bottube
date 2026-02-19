"""
BoTTube Provenance API - Remix lineage and provenance tree.

This module provides API endpoints and utilities for tracking video remix
lineage, enabling attribution and discovery of derivative works.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Any
from enum import Enum


class LineageError(Exception):
    """Base exception for lineage operations."""
    pass


class CircularReferenceError(LineageError):
    """Raised when a circular lineage is detected."""
    pass


class SelfReferentialError(LineageError):
    """Raised when a video references itself."""
    pass


class VideoNotFoundError(LineageError):
    """Raised when a referenced video doesn't exist."""
    pass


@dataclass
class ProvenanceNode:
    """A node in the provenance tree representing a video."""
    video_id: str
    title: str
    author: str
    created_at: str
    revision_of: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "author": self.author,
            "created_at": self.created_at,
            "revision_of": self.revision_of,
        }


@dataclass  
class LineageTree:
    """Complete lineage tree for a video."""
    video_id: str
    ancestors: List[ProvenanceNode]  # Parent chain (oldest first)
    descendants: List[ProvenanceNode]  # Children/remixes
    siblings: List[ProvenanceNode]  # Other remixes of same parent
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "video_id": self.video_id,
            "ancestors": [n.to_dict() for n in self.ancestors],
            "descendants": [n.to_dict() for n in self.descendants],
            "siblings": [n.to_dict() for n in self.siblings],
            "depth": len(self.ancestors),
            "remix_count": len(self.descendants),
        }


class LineageValidator:
    """Validates lineage relationships to prevent spam/abuse."""
    
    MAX_LINEAGE_DEPTH = 10  # Prevent infinite recursion
    
    @classmethod
    def check_circular_reference(
        cls,
        video_id: str,
        parent_id: str,
        lineage_store: Dict[str, Optional[str]]
    ) -> None:
        """
        Check if adding parent_id as parent of video_id would create a cycle.
        
        Args:
            video_id: The video being created/modified
            parent_id: The proposed parent video
            lineage_store: Mapping of video_id -> parent_id
            
        Raises:
            SelfReferentialError: If video references itself
            CircularReferenceError: If a cycle would be created
        """
        if video_id == parent_id:
            raise SelfReferentialError(
                f"Video {video_id} cannot reference itself as parent"
            )
        
        # Walk up the parent chain
        current = parent_id
        visited: Set[str] = {video_id}
        depth = 0
        
        while current is not None:
            if current in visited:
                raise CircularReferenceError(
                    f"Circular reference detected: {video_id} -> {parent_id} ... -> {current}"
                )
            
            visited.add(current)
            depth += 1
            
            if depth > cls.MAX_LINEAGE_DEPTH:
                raise CircularReferenceError(
                    f"Lineage depth exceeds maximum ({cls.MAX_LINEAGE_DEPTH})"
                )
            
            current = lineage_store.get(current)
    
    @classmethod
    def validate_lineage(
        cls,
        video_id: str,
        revision_of: Optional[str],
        video_store: Dict[str, Dict],
        lineage_store: Dict[str, Optional[str]]
    ) -> bool:
        """
        Full validation of a lineage relationship.
        
        Args:
            video_id: The video being validated
            revision_of: Parent video ID (can be None)
            video_store: Full video metadata store
            lineage_store: Parent relationships
            
        Returns:
            True if valid
            
        Raises:
            VideoNotFoundError: If parent doesn't exist
            LineageError: For any validation failure
        """
        if revision_of is None:
            return True
        
        # Check parent exists
        if revision_of not in video_store:
            raise VideoNotFoundError(
                f"Parent video {revision_of} not found"
            )
        
        # Check for circular reference
        cls.check_circular_reference(video_id, revision_of, lineage_store)
        
        return True


class LineageService:
    """Service for building and querying lineage trees."""
    
    def __init__(
        self,
        video_store: Dict[str, Dict],
        lineage_store: Dict[str, Optional[str]]
    ):
        """
        Initialize with data stores.
        
        Args:
            video_store: Mapping of video_id to video metadata
            lineage_store: Mapping of video_id to parent_id (revision_of)
        """
        self.video_store = video_store
        self.lineage_store = lineage_store
    
    def get_ancestors(
        self,
        video_id: str,
        max_depth: int = 10
    ) -> List[ProvenanceNode]:
        """
        Get ancestor chain for a video (oldest first).
        
        Args:
            video_id: Starting video
            max_depth: Maximum ancestry depth
            
        Returns:
            List of ancestor nodes
        """
        ancestors = []
        current = self.lineage_store.get(video_id)
        depth = 0
        
        while current is not None and depth < max_depth:
            video = self.video_store.get(current)
            if video is None:
                break
            
            ancestors.append(ProvenanceNode(
                video_id=current,
                title=video.get("title", "Unknown"),
                author=video.get("author", "Unknown"),
                created_at=video.get("created_at", ""),
                revision_of=video.get("revision_of"),
            ))
            
            current = self.lineage_store.get(current)
            depth += 1
        
        # Reverse to get oldest first
        ancestors.reverse()
        return ancestors
    
    def get_descendants(
        self,
        video_id: str,
        max_depth: int = 3
    ) -> List[ProvenanceNode]:
        """
        Get all descendant videos (remixes/children).
        
        Args:
            video_id: Starting video
            max_depth: Maximum depth to traverse
            
        Returns:
            List of descendant nodes
        """
        descendants = []
        to_process = [(video_id, 0)]
        processed: Set[str] = set()
        
        while to_process:
            current_id, depth = to_process.pop(0)
            
            if current_id in processed or depth >= max_depth:
                continue
            
            processed.add(current_id)
            
            # Find all videos that have current_id as parent
            for vid, parent_id in self.lineage_store.items():
                if parent_id == current_id and vid != video_id:
                    video = self.video_store.get(vid)
                    if video:
                        descendants.append(ProvenanceNode(
                            video_id=vid,
                            title=video.get("title", "Unknown"),
                            author=video.get("author", "Unknown"),
                            created_at=video.get("created_at", ""),
                            revision_of=vid,
                        ))
                        to_process.append((vid, depth + 1))
        
        return descendants
    
    def get_siblings(self, video_id: str) -> List[ProvenanceNode]:
        """
        Get sibling videos (other remixes of the same parent).
        
        Args:
            video_id: Target video
            
        Returns:
            List of sibling nodes
        """
        parent_id = self.lineage_store.get(video_id)
        if parent_id is None:
            return []
        
        siblings = []
        for vid, parent in self.lineage_store.items():
            if parent == parent_id and vid != video_id:
                video = self.video_store.get(vid)
                if video:
                    siblings.append(ProvenanceNode(
                        video_id=vid,
                        title=video.get("title", "Unknown"),
                        author=video.get("author", "Unknown"),
                        created_at=video.get("created_at", ""),
                        revision_of=vid,
                    ))
        
        return siblings
    
    def get_lineage_tree(self, video_id: str) -> LineageTree:
        """
        Get complete lineage tree for a video.
        
        Args:
            video_id: Target video
            
        Returns:
            Complete lineage tree
        """
        return LineageTree(
            video_id=video_id,
            ancestors=self.get_ancestors(video_id),
            descendants=self.get_descendants(video_id),
            siblings=self.get_siblings(video_id),
        )
    
    def get_remix_chain(self, video_id: str) -> List[Dict]:
        """
        Get linear remix chain from original to current.
        
        Args:
            video_id: Target video
            
        Returns:
            List of videos in chain order
        """
        ancestors = self.get_ancestors(video_id)
        current = self.video_store.get(video_id)
        
        chain = []
        for ancestor in ancestors:
            chain.append({
                "video_id": ancestor.video_id,
                "title": ancestor.title,
                "author": ancestor.author,
                "created_at": ancestor.created_at,
            })
        
        if current:
            chain.append({
                "video_id": video_id,
                "title": current.get("title", "Unknown"),
                "author": current.get("author", "Unknown"),
                "created_at": current.get("created_at", ""),
            })
        
        return chain


# API Response Helpers

def build_lineage_response(tree: LineageTree) -> Dict[str, Any]:
    """Build standardized API response for lineage tree."""
    return {
        "success": True,
        "data": tree.to_dict(),
        "meta": {
            "api_version": "1.0",
            "timestamp": datetime.utcnow().isoformat(),
        },
    }


def build_error_response(error: str, code: str = "LINEAGE_ERROR") -> Dict[str, Any]:
    """Build standardized error response."""
    return {
        "success": False,
        "error": {
            "code": code,
            "message": error,
        },
        "meta": {
            "api_version": "1.0",
            "timestamp": datetime.utcnow().isoformat(),
        },
    }
