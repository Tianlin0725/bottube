"""Tests for BoTTube Provenance module."""

import pytest
from datetime import datetime

from bottube.provenance import (
    ProvenanceNode,
    LineageTree,
    LineageValidator,
    LineageService,
    LineageError,
    CircularReferenceError,
    SelfReferentialError,
    VideoNotFoundError,
)


class TestProvenanceNode:
    """Test ProvenanceNode dataclass."""

    def test_node_creation(self):
        """Basic node creation."""
        node = ProvenanceNode(
            video_id="vid123",
            title="Test Video",
            author="@testuser",
            created_at="2024-01-01T00:00:00Z",
        )
        assert node.video_id == "vid123"
        assert node.revision_of is None

    def test_node_with_parent(self):
        """Node with parent reference."""
        node = ProvenanceNode(
            video_id="vid456",
            title="Remix",
            author="@remixer",
            created_at="2024-01-02T00:00:00Z",
            revision_of="vid123",
        )
        assert node.revision_of == "vid123"

    def test_to_dict(self):
        """Serialization to dict."""
        node = ProvenanceNode(
            video_id="vid123",
            title="Test",
            author="@user",
            created_at="2024-01-01",
            revision_of="parent",
        )
        d = node.to_dict()
        assert d["video_id"] == "vid123"
        assert d["revision_of"] == "parent"


class TestLineageValidator:
    """Test lineage validation."""

    def test_self_reference_detection(self):
        """Should detect self-referential videos."""
        with pytest.raises(SelfReferentialError):
            LineageValidator.check_circular_reference(
                "vid123", "vid123", {}
            )

    def test_circular_reference_detection(self):
        """Should detect circular references."""
        lineage = {
            "vid2": "vid3",
            "vid3": "vid1",
        }
        with pytest.raises(CircularReferenceError):
            LineageValidator.check_circular_reference(
                "vid1", "vid2", lineage
            )

    def test_valid_lineage(self):
        """Should accept valid lineage."""
        lineage = {
            "vid2": "vid1",
        }
        # Should not raise
        LineageValidator.check_circular_reference("vid3", "vid2", lineage)

    def test_deep_lineage_limit(self):
        """Should enforce max depth."""
        lineage = {f"vid{i}": f"vid{i-1}" for i in range(2, 15)}
        with pytest.raises(CircularReferenceError):
            LineageValidator.check_circular_reference("vid15", "vid14", lineage)

    def test_validate_missing_parent(self):
        """Should raise for missing parent video."""
        with pytest.raises(VideoNotFoundError):
            LineageValidator.validate_lineage(
                "vid1", "missing", {}, {}
            )


class TestLineageService:
    """Test LineageService."""

    @pytest.fixture
    def sample_data(self):
        """Create sample video and lineage data."""
        videos = {
            "vid1": {"title": "Original", "author": "@creator", "created_at": "2024-01-01"},
            "vid2": {"title": "Remix 1", "author": "@remixer1", "created_at": "2024-01-02"},
            "vid3": {"title": "Remix 2", "author": "@remixer2", "created_at": "2024-01-03"},
            "vid4": {"title": "Remix of Remix", "author": "@remixer3", "created_at": "2024-01-04"},
        }
        lineage = {
            "vid2": "vid1",
            "vid3": "vid1",
            "vid4": "vid2",
        }
        return videos, lineage

    def test_get_ancestors(self, sample_data):
        """Should get ancestor chain."""
        videos, lineage = sample_data
        service = LineageService(videos, lineage)
        
        ancestors = service.get_ancestors("vid4")
        assert len(ancestors) == 2
        assert ancestors[0].video_id == "vid1"  # Oldest first
        assert ancestors[1].video_id == "vid2"

    def test_get_descendants(self, sample_data):
        """Should get descendant videos."""
        videos, lineage = sample_data
        service = LineageService(videos, lineage)
        
        descendants = service.get_descendants("vid1")
        assert len(descendants) == 3  # vid2, vid3, vid4

    def test_get_siblings(self, sample_data):
        """Should get sibling videos."""
        videos, lineage = sample_data
        service = LineageService(videos, lineage)
        
        siblings = service.get_siblings("vid2")
        assert len(siblings) == 1
        assert siblings[0].video_id == "vid3"

    def test_get_lineage_tree(self, sample_data):
        """Should build complete lineage tree."""
        videos, lineage = sample_data
        service = LineageService(videos, lineage)
        
        tree = service.get_lineage_tree("vid4")
        assert tree.video_id == "vid4"
        assert len(tree.ancestors) == 2
        assert len(tree.descendants) == 0  # vid4 has no children

    def test_get_remix_chain(self, sample_data):
        """Should build linear remix chain."""
        videos, lineage = sample_data
        service = LineageService(videos, lineage)
        
        chain = service.get_remix_chain("vid4")
        assert len(chain) == 3
        assert chain[0]["video_id"] == "vid1"
        assert chain[2]["video_id"] == "vid4"

    def test_original_video_no_ancestors(self, sample_data):
        """Original video should have no ancestors."""
        videos, lineage = sample_data
        service = LineageService(videos, lineage)
        
        ancestors = service.get_ancestors("vid1")
        assert len(ancestors) == 0

    def test_no_siblings_for_original(self, sample_data):
        """Original video should have no siblings."""
        videos, lineage = sample_data
        service = LineageService(videos, lineage)
        
        siblings = service.get_siblings("vid1")
        assert len(siblings) == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_stores(self):
        """Should handle empty data stores."""
        service = LineageService({}, {})
        tree = service.get_lineage_tree("vid1")
        assert len(tree.ancestors) == 0
        assert len(tree.descendants) == 0

    def test_missing_video_in_store(self):
        """Should handle missing video metadata."""
        lineage = {"vid2": "vid1"}
        service = LineageService({}, lineage)
        
        # Should not crash, just return empty
        ancestors = service.get_ancestors("vid2")
        assert len(ancestors) == 0

    def test_broken_lineage_chain(self):
        """Should handle broken lineage chains."""
        videos = {"vid1": {}, "vid3": {}}
        lineage = {"vid3": "vid2", "vid2": "vid1"}  # vid2 missing from videos
        service = LineageService(videos, lineage)
        
        ancestors = service.get_ancestors("vid3")
        # Should only get vid1 (vid2 is missing)
        assert len(ancestors) == 1
        assert ancestors[0].video_id == "vid1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
