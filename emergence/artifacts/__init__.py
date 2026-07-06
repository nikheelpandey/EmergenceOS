"""Physical artifact management for EmergenceOS."""

from emergence.artifacts.service import (
    ArtifactRecord,
    ArtifactService,
    ArtifactStatus,
    create_artifact_service,
)

__all__ = [
    "ArtifactRecord",
    "ArtifactService",
    "ArtifactStatus",
    "create_artifact_service",
]
