from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts import backup_store, import_skills, manage_skills

DAY_SECONDS = 24 * 60 * 60
DIGEST = "a" * 64


def make_backup(root: Path, relative: Path, modified: float) -> Path:
    parent = root / relative
    backup = parent / "pending"
    backup.mkdir(parents=True)
    (backup / "SKILL.md").write_text(
        f"---\nname: {relative.name}\ndescription: Test backup.\n---\n\n"
        "Recovery copy.\n",
        encoding="utf-8",
    )
    digest = manage_skills.digest_tree(backup)
    destination = parent / digest
    backup.rename(destination)
    backup = destination
    os.utime(backup, (modified, modified), follow_symlinks=False)
    return backup


def test_cleanup_is_dry_run_by_default_and_expires_at_age_boundary(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".backups"
    now = 1_800_000_000.0
    cutoff = now - 30 * DAY_SECONDS
    expired = make_backup(
        root,
        Path("project--bundle") / "project" / "old",
        cutoff,
    )
    retained = make_backup(
        root,
        Path("project-import") / "recent",
        cutoff + 1,
    )

    preview = manage_skills.cleanup_backups(root, now=now)

    assert preview == {
        "expired": (expired.relative_to(root).as_posix(),),
        "retained": (retained.relative_to(root).as_posix(),),
        "unsafe": (),
        "removed": (),
    }
    assert expired.is_dir()
    assert retained.is_dir()

    applied = manage_skills.cleanup_backups(root, now=now, apply=True)

    assert applied["removed"] == preview["expired"]
    assert not expired.exists()
    assert retained.is_dir()


def test_cleanup_refuses_symlinked_backup_paths_without_following_them(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".backups"
    parent = root / "project-import" / "linked"
    parent.mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("keep\n", encoding="utf-8")
    linked_backup = parent / DIGEST
    linked_backup.symlink_to(outside, target_is_directory=True)

    nested = make_backup(
        root,
        Path("project--bundle") / "project" / "nested-link",
        1.0,
    )
    (nested / "outside").symlink_to(outside, target_is_directory=True)

    result = manage_skills.cleanup_backups(root, now=1_800_000_000.0, apply=True)

    assert result["removed"] == ()
    assert set(result["unsafe"]) == {
        nested.relative_to(root).as_posix(),
        f"project-import/linked/{DIGEST}",
    }
    assert linked_backup.is_symlink()
    assert nested.is_dir()
    assert marker.read_text(encoding="utf-8") == "keep\n"


def test_cleanup_rejects_symlinked_backup_root(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / ".backups"
    root.symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="backup root is not a real directory"):
        manage_skills.cleanup_backups(root, apply=True)

    assert outside.is_dir()


def test_cleanup_requires_positive_retention(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least one day"):
        manage_skills.cleanup_backups(tmp_path / ".backups", retention_days=0)


def test_reused_content_addressed_backups_refresh_their_retention_age(
    workshop: Path,
    make_skill,
) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    materialized = manage_skills.backup_tree(
        source,
        "project",
        "bundle",
        "project",
        "alpha",
    )
    assert materialized is not None
    os.utime(materialized, (1, 1), follow_symlinks=False)

    reused = manage_skills.backup_tree(
        source,
        "project",
        "bundle",
        "project",
        "alpha",
    )

    assert reused == materialized
    assert reused.stat().st_mtime > 1

    import_skills.backup_source(source, "alpha")
    imported = (
        workshop
        / ".backups"
        / "project-import"
        / "alpha"
        / import_skills.digest_tree(source)
    )
    os.utime(imported, (1, 1), follow_symlinks=False)

    import_skills.backup_source(source, "alpha")

    assert imported.stat().st_mtime > 1


def test_cleanup_preserves_unrecognized_layouts_and_corrupt_backups(
    tmp_path: Path,
) -> None:
    root = tmp_path / ".backups"
    old = 1.0
    valid = make_backup(
        root,
        Path("project--bundle") / "project" / "valid",
        old,
    )
    unrelated = make_backup(root, Path("notes") / "other" / "keep", old)
    corrupt = make_backup(
        root,
        Path("project--bundle") / "workshop" / "corrupt",
        old,
    )
    corrupt_digest = corrupt.with_name("b" * 64)
    corrupt.rename(corrupt_digest)
    unknown_side = make_backup(
        root,
        Path("project--bundle") / "other" / "unknown-side",
        old,
    )
    unsafe_name = make_backup(
        root,
        Path("project--bundle") / "project" / "NotSafe",
        old,
    )

    result = manage_skills.cleanup_backups(
        root,
        now=1_800_000_000.0,
        apply=True,
    )

    assert result["removed"] == (valid.relative_to(root).as_posix(),)
    assert set(result["unsafe"]) == {
        "notes",
        "project--bundle/other",
        "project--bundle/project/NotSafe",
        corrupt_digest.relative_to(root).as_posix(),
    }
    assert unrelated.is_dir()
    assert corrupt_digest.is_dir()
    assert unknown_side.is_dir()
    assert unsafe_name.is_dir()


def test_cleanup_rejects_root_swap_during_discovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / ".backups"
    backup = make_backup(
        root,
        Path("project-import") / "alpha",
        1.0,
    )
    replacement = tmp_path / "replacement"
    replacement.mkdir()
    marker = replacement / "keep.txt"
    marker.write_text("replacement\n", encoding="utf-8")
    displaced = tmp_path / "displaced"
    discover = manage_skills._backup_candidates

    def discover_then_swap(root_descriptor: int):
        result = discover(root_descriptor)
        root.rename(displaced)
        replacement.rename(root)
        return result

    monkeypatch.setattr(manage_skills, "_backup_candidates", discover_then_swap)

    with pytest.raises(RuntimeError, match="backup root changed"):
        manage_skills.cleanup_backups(
            root,
            now=1_800_000_000.0,
            apply=True,
        )

    assert (displaced / backup.relative_to(root)).is_dir()
    assert (root / marker.name).read_text(encoding="utf-8") == "replacement\n"


def test_cleanup_deletion_stays_anchored_to_open_root_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / ".backups"
    backup = make_backup(
        root,
        Path("project-import") / "alpha",
        1.0,
    )
    relative = backup.relative_to(root)
    replacement = tmp_path / "replacement"
    replacement_backup = make_backup(
        replacement,
        Path("project-import") / "alpha",
        1.0,
    )
    assert replacement_backup.relative_to(replacement) == relative
    marker = replacement / "keep.txt"
    marker.write_text("replacement\n", encoding="utf-8")
    displaced = tmp_path / "displaced"
    remove = manage_skills._remove_backup_tree

    def swap_then_remove(
        root_descriptor: int,
        candidate: Path,
        snapshot: tuple[int, int, int],
    ) -> None:
        root.rename(displaced)
        replacement.rename(root)
        remove(root_descriptor, candidate, snapshot)

    monkeypatch.setattr(manage_skills, "_remove_backup_tree", swap_then_remove)

    with pytest.raises(RuntimeError, match="backup root changed"):
        manage_skills.cleanup_backups(
            root,
            now=1_800_000_000.0,
            apply=True,
        )

    assert not (displaced / relative).exists()
    assert (root / relative).is_dir()
    assert (root / marker.name).read_text(encoding="utf-8") == "replacement\n"


def test_materialization_backup_rejects_corrupt_reused_digest_directory(
    workshop: Path,
    make_skill,
) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    destination = manage_skills.backup_tree(
        source,
        "project",
        "bundle",
        "project",
        "alpha",
    )
    assert destination is not None
    (destination / "SKILL.md").write_text(
        "---\nname: alpha\ndescription: Forged.\n---\n\nCorrupt.\n",
        encoding="utf-8",
    )
    os.utime(destination, (1, 1), follow_symlinks=False)

    with pytest.raises(ValueError, match="backup content digest mismatch"):
        manage_skills.backup_tree(
            source,
            "project",
            "bundle",
            "project",
            "alpha",
        )

    assert destination.stat().st_mtime == 1


def test_import_backup_rejects_forged_reused_skill_tree(
    workshop: Path,
    make_skill,
) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    import_skills.backup_source(source, "alpha")
    destination = (
        workshop
        / ".backups"
        / "project-import"
        / "alpha"
        / import_skills.digest_tree(source)
    )
    (destination / "SKILL.md").write_text(
        "---\nname: forged\ndescription: Forged.\n---\n\nCorrupt.\n",
        encoding="utf-8",
    )
    os.utime(destination, (1, 1), follow_symlinks=False)

    with pytest.raises(ValueError, match="declares 'forged', expected 'alpha'"):
        import_skills.backup_source(source, "alpha")

    assert destination.stat().st_mtime == 1


@pytest.mark.parametrize("producer", ["materialization", "import"])
def test_new_backup_is_not_published_when_source_changes_during_copy(
    workshop: Path,
    make_skill,
    monkeypatch: pytest.MonkeyPatch,
    producer: str,
) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    original_copy_tree = backup_store._copy_tree

    def copy_then_change_source(source_descriptor: int, destination: int) -> None:
        original_copy_tree(source_descriptor, destination)
        make_skill(source, "alpha", "Changed during backup.\n")

    monkeypatch.setattr(backup_store, "_copy_tree", copy_then_change_source)

    if producer == "materialization":
        parent = workshop / ".backups" / "project--bundle" / "project" / "alpha"
    else:
        parent = workshop / ".backups" / "project-import" / "alpha"

    with pytest.raises(RuntimeError, match="skill changed while creating backup"):
        if producer == "materialization":
            manage_skills.backup_tree(
                source,
                "project",
                "bundle",
                "project",
                "alpha",
            )
        else:
            import_skills.backup_source(source, "alpha")

    assert parent.is_dir()
    assert list(parent.iterdir()) == []


def test_new_backup_staging_tree_must_match_content_digest(
    workshop: Path,
    make_skill,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    original_copy_tree = backup_store._copy_tree

    def copy_then_corrupt_stage(source_descriptor: int, destination: int) -> None:
        original_copy_tree(source_descriptor, destination)
        skill_file = os.open(
            "SKILL.md",
            os.O_WRONLY | os.O_TRUNC,
            dir_fd=destination,
        )
        try:
            os.write(
                skill_file,
                b"---\nname: alpha\ndescription: Test.\n---\n\nCorrupt stage.\n",
            )
        finally:
            os.close(skill_file)

    monkeypatch.setattr(backup_store, "_copy_tree", copy_then_corrupt_stage)

    with pytest.raises(ValueError, match="backup content digest mismatch"):
        import_skills.backup_source(source, "alpha")

    parent = workshop / ".backups" / "project-import" / "alpha"
    assert parent.is_dir()
    assert list(parent.iterdir()) == []


@pytest.mark.parametrize("producer", ["materialization", "import"])
def test_backup_producer_rejects_symlinked_backup_root(
    workshop: Path,
    make_skill,
    producer: str,
) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    outside = workshop.parent / f"outside-{producer}"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("outside\n", encoding="utf-8")
    (workshop / ".backups").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="backup root is not a real directory"):
        if producer == "materialization":
            manage_skills.backup_tree(
                source,
                "project",
                "bundle",
                "project",
                "alpha",
            )
        else:
            import_skills.backup_source(source, "alpha")

    assert list(outside.iterdir()) == [marker]


@pytest.mark.parametrize(
    ("producer", "linked_component"),
    [
        ("materialization", "project--bundle"),
        ("import", "project-import"),
    ],
)
def test_backup_producer_rejects_symlinked_layout_component(
    workshop: Path,
    make_skill,
    producer: str,
    linked_component: str,
) -> None:
    source = make_skill(workshop / "skills" / "alpha", "alpha")
    root = workshop / ".backups"
    root.mkdir()
    outside = workshop.parent / f"outside-component-{producer}"
    outside.mkdir()
    marker = outside / "keep.txt"
    marker.write_text("outside\n", encoding="utf-8")
    (root / linked_component).symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="not a real directory"):
        if producer == "materialization":
            manage_skills.backup_tree(
                source,
                "project",
                "bundle",
                "project",
                "alpha",
            )
        else:
            import_skills.backup_source(source, "alpha")

    assert list(outside.iterdir()) == [marker]
