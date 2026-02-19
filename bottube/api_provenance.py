"""
BoTTube Provenance API Endpoints

FastAPI routes for remix lineage and provenance tree.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, List, Optional, Any

from .provenance import (
    LineageService,
    LineageValidator,
    LineageTree,
    CircularReferenceError,
    SelfReferentialError,
    VideoNotFoundError,
    build_lineage_response,
    build_error_response,
)


router = APIRouter(prefix="/api/v1/provenance", tags=["Provenance"])


# Mock data store - in production, this would be a database
def get_video_store() -> Dict[str, Dict]:
    """Get video data store."""
    # This would be replaced with actual database queries
    return {}


def get_lineage_store() -> Dict[str, Optional[str]]:
    """Get lineage/parent relationships."""
    # This would be replaced with actual database queries
    return {}


def get_lineage_service(
    video_store: Dict = Depends(get_video_store),
    lineage_store: Dict = Depends(get_lineage_store),
) -> LineageService:
    """Dependency to get lineage service."""
    return LineageService(video_store, lineage_store)


@router.get("/lineage/{video_id}")
async def get_lineage(
    video_id: str,
    include_siblings: bool = Query(True, description="Include sibling remixes"),
    max_depth: int = Query(3, ge=1, le=10, description="Maximum lineage depth"),
    service: LineageService = Depends(get_lineage_service),
) -> Dict[str, Any]:
    """
    Get complete lineage tree for a video.
    
    Returns ancestors (parent chain), descendants (remixes), and optionally siblings.
    """
    try:
        tree = service.get_lineage_tree(video_id)
        
        if not include_siblings:
            tree.siblings = []
        
        return build_lineage_response(tree)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lineage/{video_id}/ancestors")
async def get_ancestors(
    video_id: str,
    max_depth: int = Query(10, ge=1, le=20),
    service: LineageService = Depends(get_lineage_service),
) -> Dict[str, Any]:
    """Get ancestor chain (parent videos) for a video."""
    try:
        ancestors = service.get_ancestors(video_id, max_depth=max_depth)
        return {
            "success": True,
            "data": {
                "video_id": video_id,
                "ancestors": [a.to_dict() for a in ancestors],
                "count": len(ancestors),
            },
            "meta": {"api_version": "1.0"},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lineage/{video_id}/descendants")
async def get_descendants(
    video_id: str,
    max_depth: int = Query(3, ge=1, le=5),
    service: LineageService = Depends(get_lineage_service),
) -> Dict[str, Any]:
    """Get descendant videos (remixes) of a video."""
    try:
        descendants = service.get_descendants(video_id, max_depth=max_depth)
        return {
            "success": True,
            "data": {
                "video_id": video_id,
                "descendants": [d.to_dict() for d in descendants],
                "count": len(descendants),
            },
            "meta": {"api_version": "1.0"},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/lineage/{video_id}/chain")
async def get_remix_chain(
    video_id: str,
    service: LineageService = Depends(get_lineage_service),
) -> Dict[str, Any]:
    """
    Get linear remix chain from original to current video.
    
    This is a simplified view showing just the direct lineage path.
    """
    try:
        chain = service.get_remix_chain(video_id)
        return {
            "success": True,
            "data": {
                "video_id": video_id,
                "chain": chain,
                "length": len(chain),
                "is_remix": len(chain) > 1,
            },
            "meta": {"api_version": "1.0"},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate")
async def validate_lineage(
    video_id: str,
    revision_of: Optional[str] = None,
    video_store: Dict = Depends(get_video_store),
    lineage_store: Dict = Depends(get_lineage_store),
) -> Dict[str, Any]:
    """
    Validate a proposed lineage relationship.
    
    Checks for circular references, self-references, and missing parents.
    """
    try:
        is_valid = LineageValidator.validate_lineage(
            video_id=video_id,
            revision_of=revision_of,
            video_store=video_store,
            lineage_store=lineage_store,
        )
        
        return {
            "success": True,
            "data": {
                "valid": is_valid,
                "video_id": video_id,
                "revision_of": revision_of,
            },
            "meta": {"api_version": "1.0"},
        }
    
    except SelfReferentialError as e:
        return build_error_response(str(e), "SELF_REFERENCE")
    
    except CircularReferenceError as e:
        return build_error_response(str(e), "CIRCULAR_REFERENCE")
    
    except VideoNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/{video_id}")
async def get_provenance_stats(
    video_id: str,
    service: LineageService = Depends(get_lineage_service),
) -> Dict[str, Any]:
    """
    Get provenance statistics for a video.
    
    Returns counts and metadata about the video's lineage.
    """
    try:
        tree = service.get_lineage_tree(video_id)
        
        return {
            "success": True,
            "data": {
                "video_id": video_id,
                "is_original": len(tree.ancestors) == 0,
                "is_remixed": len(tree.descendants) > 0,
                "remix_count": len(tree.descendants),
                "ancestor_count": len(tree.ancestors),
                "sibling_count": len(tree.siblings),
                "lineage_depth": len(tree.ancestors),
            },
            "meta": {"api_version": "1.0"},
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
