"""Dataset registration, validation, and deterministic manifests."""

from .core import FileRecord, Manifest, Source, build_manifest, inspect_file, validate_record
from .persistence import Store
from .lineage import EvidenceGraph, Lineage, deterministic_node_id, redact
from .release import QualityContract, QualityResult, Release, ReleaseCandidate, evaluate_contract
from .credentials import (Credential, CredentialProfile, CredentialProvider,
                          MockCredentialProvider, ProviderUnavailable,
                          RotationPlan, WindowsCredentialManagerProvider,
                          build_rotation_plan, redacted_metadata,
                          verify_profile)
from .connectors import (ArchiveConnector, ConnectorMetadata, DownloadBoundary,
                         FilesystemConnector, HTTPSConnector, SourceConnector,
                         connector_for, inspect_target)

__all__ = ["FileRecord", "Manifest", "Source", "Store", "QualityContract", "QualityResult",
           "Release", "ReleaseCandidate", "Lineage", "EvidenceGraph", "deterministic_node_id",
           "redact", "build_manifest", "evaluate_contract", "inspect_file",
           "validate_record", "Credential", "CredentialProfile", "CredentialProvider",
           "MockCredentialProvider", "ProviderUnavailable", "WindowsCredentialManagerProvider",
           "RotationPlan", "build_rotation_plan", "redacted_metadata", "verify_profile"]
__all__ += ["ArchiveConnector", "ConnectorMetadata", "DownloadBoundary",
            "FilesystemConnector", "HTTPSConnector", "SourceConnector",
            "connector_for", "inspect_target"]
from .analyzer import InventoryDatabase, ScanResult, export_report, scan_filesystem
from .datasets import discover_dataset, validate_coco, validate_yolo
from .integrations import OptionalDependencyError, capability
__all__ += ["InventoryDatabase", "ScanResult", "scan_filesystem", "export_report",
            "discover_dataset", "validate_coco", "validate_yolo",
            "OptionalDependencyError", "capability"]
__version__ = "0.1.0"
