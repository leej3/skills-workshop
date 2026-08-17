"""Shared compatibility rules for materialization lock metadata."""

from __future__ import annotations

from collections.abc import Mapping

CURRENT_LOCK_SCHEMA_VERSION = 3
SUPPORTED_LOCK_SCHEMA_VERSIONS = frozenset({1, 2, 3})
SEPARATE_BASELINE_SCHEMA_VERSIONS = frozenset({2, 3})


def lock_schema_version(data: Mapping[str, object], *, context: str) -> int:
    """Return a supported lock version, treating an omitted version as v1."""

    version = data.get("schema_version", 1)
    if type(version) is not int or version not in SUPPORTED_LOCK_SCHEMA_VERSIONS:
        raise ValueError(f"unsupported {context} schema version: {version!r}")
    return version


def lock_bundle(data: Mapping[str, object], *, context: str) -> str:
    """Return the bundle name across the v1/v2 ``cluster`` rename."""

    version = lock_schema_version(data, context=context)
    bundle = data.get("bundle")
    cluster = data.get("cluster")
    if version == CURRENT_LOCK_SCHEMA_VERSION:
        if cluster is not None:
            raise ValueError(f"{context} schema-v3 uses 'bundle', not 'cluster'")
        value = bundle
    else:
        if bundle is not None and cluster is not None and bundle != cluster:
            raise ValueError(f"{context} has conflicting bundle and cluster names")
        # ``bundle`` also accepts locks briefly written as schema v2 after the
        # terminology changed but before that change received a new version.
        value = cluster if cluster is not None else bundle
    if not isinstance(value, str) or not value:
        field = "bundle" if version == CURRENT_LOCK_SCHEMA_VERSION else "cluster"
        raise ValueError(f"{context} has no {field}")
    return value
