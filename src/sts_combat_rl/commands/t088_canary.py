"""Authorized path-bound T088 canary routing.

This command is deliberately a small admission boundary.  It reads the
accepted T087/T085 artifacts, projects only the 413 retained identities, and
does not construct a simulator adapter until every identity, authorization,
and output-path check has succeeded.  It never writes a replacement cohort or
copies the large T087 evidence table.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from sts_combat_rl.commands.t085_native_execution import (
    T085NativeExecutionError,
    resolve_t085_canonical_records,
)
from sts_combat_rl.commands.t088_classical_combat_tournament import (
    t088_controller_definitions,
)
from sts_combat_rl.sim.t087_dense_combat_diagnostics import (
    T085_RESTORE_SCHEMA_ID,
    T085_RESTORE_SHA256,
    T085_SELECTION_SCHEMA_ID,
    T085_SELECTION_SHA256,
    T087_COHORT_COUNTS,
    T087_NATURAL_RECORD_COUNT,
    T087IncompleteError,
    load_t087_t085_input_gate,
)
from sts_combat_rl.sim.t088_canary_execution import (
    T088NativeCanaryRecordRunner,
    execute_t088_canary,
    write_t088_canary_evidence,
)
from sts_combat_rl.sim.t088_tournament_workflow import (
    T088_T087_FINAL_REPORT_SHA256,
    T088_T087_FORMAL_NATURAL_EVIDENCE_SHA256,
    T088_T087_RETENTION_MANIFEST_SHA256,
    _binding_identity,
    select_t088_canary_records,
    validate_t088_t087_cohort_binding,
)

T088_CANARY_PATH_AUTHORIZATION_SCHEMA_ID = "t088-maintainer-canary-authorization-v2"


class T088CanaryPathError(ValueError):
    """A required retained input or exact authorization is unavailable."""


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def _read_exact_json(
    path: Path, *, expected_sha256: str | None, schema_id: str, label: str
) -> tuple[dict[str, object], dict[str, object]]:
    resolved = path.resolve(strict=True)
    actual = _sha256_file(resolved)
    if expected_sha256 is not None and actual != expected_sha256:
        raise T088CanaryPathError(f"{label} SHA-256 differs from its accepted identity")
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T088CanaryPathError(f"{label} is not readable JSON") from exc
    if not isinstance(document, Mapping) or document.get("schema_id") != schema_id:
        raise T088CanaryPathError(f"{label} schema is not current")
    return dict(document), {
        "path": str(resolved),
        "sha256": actual,
        "schema_id": schema_id,
        "byte_count": resolved.stat().st_size,
    }


def _validate_t087_common_document(document: Mapping[str, object], label: str) -> None:
    if (
        document.get("task_id") != "T087"
        or not isinstance(document.get("approved_spec"), str)
        or not document["approved_spec"]
        or not isinstance(document.get("implementation_run_head"), str)
        or len(document["implementation_run_head"]) != 40
    ):
        raise T088CanaryPathError(f"{label} current retained structure is invalid")


def _validate_t087_formal_document(document: Mapping[str, object]) -> None:
    _validate_t087_common_document(document, "T087 formal natural evidence")
    rows = document.get("rows")
    if (
        document.get("record_count") != T087_NATURAL_RECORD_COUNT
        or document.get("cohort_counts") != T087_COHORT_COUNTS
        or document.get("formal_authorized") is not True
        or not isinstance(rows, Sequence)
        or isinstance(rows, (str, bytes))
        or len(rows) != T087_NATURAL_RECORD_COUNT
        or any(not isinstance(row, Mapping) for row in rows)
    ):
        raise T088CanaryPathError(
            "T087 formal natural evidence current retained structure is invalid"
        )


def _validate_t087_report_document(document: Mapping[str, object]) -> None:
    _validate_t087_common_document(document, "T087 final report")
    if (
        document.get("terminal_classification") != "DENSE_COMBAT_DIAGNOSTICS_READY"
        or not isinstance(document.get("artifact_references"), Mapping)
        or not isinstance(document.get("natural_execution"), Mapping)
        or not isinstance(document.get("t085_binding"), Mapping)
    ):
        raise T088CanaryPathError(
            "T087 final report current retained structure is invalid"
        )


def _validate_t087_retention_document(document: Mapping[str, object]) -> None:
    _validate_t087_common_document(document, "T087 retention manifest")
    if (
        document.get("terminal_classification") != "DENSE_COMBAT_DIAGNOSTICS_READY"
        or not isinstance(document.get("artifact_references"), Mapping)
        or not isinstance(document.get("stable_root"), str)
        or not document["stable_root"]
        or not isinstance(document.get("regeneration_command"), str)
        or not document["regeneration_command"]
    ):
        raise T088CanaryPathError(
            "T087 retention manifest current retained structure is invalid"
        )


def _read_t087_accepted_json(
    path: Path,
    *,
    expected_sha256: str,
    reference_schema_id: str,
    label: str,
    validator: Callable[[Mapping[str, object]], None],
) -> tuple[dict[str, object], dict[str, object]]:
    """Read a fixed T087 artifact without inventing a root-schema requirement.

    These three retained artifacts are admitted by their published immutable
    SHA-256 plus their actual current document shape.  ``reference_schema_id``
    is the downstream T088 artifact-reference contract, not a claim about the
    JSON root's ``schema_id`` field.
    """

    resolved = path.resolve(strict=True)
    if _sha256_file(resolved) != expected_sha256:
        raise T088CanaryPathError(f"{label} SHA-256 differs from its accepted identity")
    try:
        document = json.loads(resolved.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise T088CanaryPathError(f"{label} is not readable JSON") from exc
    if not isinstance(document, Mapping):
        raise T088CanaryPathError(f"{label} current retained structure is invalid")
    try:
        validator(document)
    except (TypeError, ValueError) as exc:
        raise T088CanaryPathError(
            f"{label} current retained structure is invalid"
        ) from exc
    return dict(document), {
        "path": str(resolved),
        "sha256": expected_sha256,
        "schema_id": reference_schema_id,
        "byte_count": resolved.stat().st_size,
    }


def _artifact_reference(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise T088CanaryPathError(f"{label} reference is missing")
    path = value.get("path")
    sha = value.get("sha256")
    schema = value.get("schema_id")
    if (
        not isinstance(path, str)
        or not isinstance(sha, str)
        or not isinstance(schema, str)
    ):
        raise T088CanaryPathError(f"{label} reference is malformed")
    return dict(value)


def _verify_supplied_path(
    path: Path, reference: Mapping[str, object], label: str
) -> Path:
    resolved = path.resolve(strict=True)
    expected = reference.get("sha256")
    if not isinstance(expected, str) or _sha256_file(resolved) != expected:
        raise T088CanaryPathError(f"{label} bytes differ from the T085-bound identity")
    return resolved


def _source_references(restore_document: Mapping[str, object]) -> Mapping[str, object]:
    sources = restore_document.get("source_bindings")
    if not isinstance(sources, Mapping) or set(sources) != {"A", "B", "C"}:
        raise T088CanaryPathError(
            "T085 restore evidence source bindings are incomplete"
        )
    return sources


def _load_canonical_maps(
    *,
    restore_document: Mapping[str, object],
    selection_document: Mapping[str, object],
    a_pool_path: Path,
    b_pool_path: Path,
    c_pool_path: Path,
    b_source_manifest_path: Path,
    c_source_manifest_path: Path,
) -> tuple[dict[str, Mapping[str, object]], dict[str, dict[str, object]]]:
    """Resolve full pools with the existing T085 verifier, never a local parser."""

    sources = _source_references(restore_document)
    refs: dict[str, dict[str, object]] = {}
    pools = {"A": a_pool_path, "B": b_pool_path, "C": c_pool_path}
    for cohort, path in pools.items():
        source = sources[cohort]
        if not isinstance(source, Mapping):
            raise T088CanaryPathError(f"T085 {cohort} source binding is malformed")
        refs[cohort] = _artifact_reference(source.get("map"), f"T085 {cohort} pool")
        _verify_supplied_path(path, refs[cohort], f"T085 {cohort} pool")
    selected = selection_document.get("cohorts")
    if not isinstance(selected, Mapping):
        raise T088CanaryPathError("T085 selection artifact has no selected cohorts")
    selected_b = selected.get("B")
    if not isinstance(selected_b, Sequence) or isinstance(selected_b, (str, bytes)):
        raise T088CanaryPathError("T085 B selection is malformed")
    selected_b_ids = [
        item.get("source_artifact_record_identity", item.get("source_checkpoint_id"))
        for item in selected_b
        if isinstance(item, Mapping)
    ]
    if len(selected_b_ids) != len(selected_b) or any(
        not isinstance(value, str) or not value for value in selected_b_ids
    ):
        raise T088CanaryPathError("T085 B selection identities are malformed")
    manifests: dict[str, dict[str, object]] = {}
    for cohort, supplied in (
        ("B", b_source_manifest_path),
        ("C", c_source_manifest_path),
    ):
        source = sources[cohort]
        assert isinstance(source, Mapping)
        reference = _artifact_reference(
            source.get("source_manifest"), f"T085 {cohort} source manifest"
        )
        _verify_supplied_path(supplied, reference, f"T085 {cohort} source manifest")
        manifests[cohort] = reference
    try:
        maps = {
            "A": resolve_t085_canonical_records(
                a_pool_path,
                expected_sha256=str(refs["A"]["sha256"]),
                artifact_kind="fixed_cohort",
            ),
            "B": resolve_t085_canonical_records(
                b_pool_path,
                expected_sha256=str(refs["B"]["sha256"]),
                artifact_kind="assisted_pool",
                expected_source_manifest_path=b_source_manifest_path,
                expected_source_manifest_sha256=str(manifests["B"]["sha256"]),
                selected_source_checkpoint_ids=selected_b_ids,
            ),
            "C": resolve_t085_canonical_records(
                c_pool_path,
                expected_sha256=str(refs["C"]["sha256"]),
                artifact_kind="natural_pool",
                expected_source_manifest_path=c_source_manifest_path,
                expected_source_manifest_sha256=str(manifests["C"]["sha256"]),
            ),
        }
    except (OSError, T085NativeExecutionError, ValueError) as exc:
        raise T088CanaryPathError("T085 canonical pool verification failed") from exc
    return maps, refs


def _project_t087_cohort(
    formal_document: Mapping[str, object],
    source_identity: Mapping[str, object],
    canonical_records_by_cohort: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    rows = formal_document.get("rows")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        raise T088CanaryPathError("T087 formal natural evidence rows are unavailable")
    result: list[dict[str, object]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise T088CanaryPathError("T087 formal natural evidence row is malformed")
        identity, cohort = row.get("selection_identity"), row.get("cohort")
        if not isinstance(identity, str) or not isinstance(cohort, str):
            raise T088CanaryPathError("T087 formal row lacks identity/cohort")
        canonical = canonical_records_by_cohort.get(cohort, {}).get(identity)
        if canonical is None:
            raise T088CanaryPathError("T087 formal row has no canonical T085 record")
        entry = row.get("entry")
        terminal = row.get("terminal")
        if not isinstance(entry, Mapping) or not isinstance(terminal, Mapping):
            raise T088CanaryPathError("T087 formal row lacks raw diagnostic evidence")
        entry_raw = entry.get("raw_snapshot")
        terminal_raw = terminal.get("raw_snapshot")
        if not isinstance(entry_raw, Mapping) or not isinstance(terminal_raw, Mapping):
            raise T088CanaryPathError("T087 formal raw snapshot is unavailable")
        enemies = terminal_raw.get("completed_battle_monsters")
        if not isinstance(enemies, Sequence) or isinstance(enemies, (str, bytes)):
            raise T088CanaryPathError("T087 terminal enemy occurrences are unavailable")
        parsed_enemies = [enemy for enemy in enemies if isinstance(enemy, Mapping)]
        if len(parsed_enemies) != len(enemies):
            raise T088CanaryPathError("T087 terminal enemy occurrence is malformed")
        for enemy in parsed_enemies:
            if (
                not isinstance(enemy.get("id_label"), str)
                or isinstance(enemy.get("current_hp"), bool)
                or not isinstance(enemy.get("current_hp"), (int, float))
                or not isinstance(enemy.get("targetable"), bool)
            ):
                raise T088CanaryPathError("T087 terminal enemy facts are incomplete")
        raw_actions = canonical.public_run_context.get("candidate_actions")
        if (
            not isinstance(raw_actions, Mapping)
            or raw_actions.get("availability") != "available"
        ):
            raise T088CanaryPathError("canonical root legal actions are unavailable")
        legal_actions = raw_actions.get("items")
        if not isinstance(legal_actions, Sequence) or isinstance(
            legal_actions, (str, bytes)
        ):
            raise T088CanaryPathError("canonical root legal action list is malformed")
        structural = getattr(canonical, "structural_metadata", None)
        if not isinstance(structural, Mapping):
            raise T088CanaryPathError(
                "T085 canonical record structural facts are unavailable"
            )
        act = structural.get("act")
        room_type = structural.get("room_type")
        if (
            isinstance(act, bool)
            or not isinstance(act, int)
            or act <= 0
            or not isinstance(room_type, str)
            or not room_type
        ):
            raise T088CanaryPathError(
                "T085 canonical record structural facts are invalid"
            )
        positive_hp = [enemy for enemy in parsed_enemies if enemy["current_hp"] > 0]
        escaped_mugger = any(
            enemy["id_label"].upper() == "MUGGER"
            and enemy["current_hp"] > 0
            and enemy["targetable"] is False
            for enemy in parsed_enemies
        )
        result.append(
            {
                "selection_identity": identity,
                "cohort": cohort,
                "source_selection_manifest_identity": dict(source_identity),
                "provenance": {
                    "native_commit": "96052d24b9c2c16ff25b6f7241edd972613be997"
                },
                "is_escaping_mugger_case": escaped_mugger,
                "is_ordinary_victory": (
                    row.get("outcome") == "PLAYER_VICTORY" and not positive_hp
                ),
                "is_ordinary_loss": row.get("outcome") == "PLAYER_LOSS",
                "is_later_act_or_boss": act > 1 or room_type.upper() == "BOSS",
                "legal_root_action_count": len(legal_actions),
            }
        )
    return result


def _build_t087_cohort_binding(
    cohort: Sequence[Mapping[str, object]],
    *,
    source_identity: Mapping[str, object],
    formal_reference: Mapping[str, object],
    report_reference: Mapping[str, object],
    retention_reference: Mapping[str, object],
) -> dict[str, object]:
    """Create the exact lightweight binding expected by the reviewed T088 seam."""

    entries = [
        {"selection_identity": row["selection_identity"], "cohort": row["cohort"]}
        for row in cohort
    ]
    ordered_sha = hashlib.sha256(
        json.dumps(
            entries, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()

    def artifact(reference: Mapping[str, object]) -> dict[str, object]:
        return {
            "path": reference["path"],
            "sha256": reference["sha256"],
            "schema_id": reference["schema_id"],
            "size_bytes": reference["byte_count"],
        }

    binding = {
        "schema_id": "t088-t087-cohort-binding-v1",
        "task_id": "T088",
        "t087_task_id": "T087",
        "t087_native_identity": {
            "repository": "lsmfttb/sts_lightspeed",
            "ref": "refs/heads/stsrl/main",
            "commit": "96052d24b9c2c16ff25b6f7241edd972613be997",
        },
        "source_selection_manifest_identity": dict(source_identity),
        "t087_artifacts": {
            "formal_natural_evidence": artifact(formal_reference),
            "final_report": artifact(report_reference),
            "retention_manifest": artifact(retention_reference),
        },
        "ordered_cohort_entries": entries,
        "ordered_cohort_entries_sha256": ordered_sha,
    }
    try:
        validate_t088_t087_cohort_binding(binding, cohort)
    except ValueError as exc:
        raise T088CanaryPathError("T088 exact T087 cohort binding failed") from exc
    return binding


def _validate_path_authorization(
    authorization: Mapping[str, object],
    *,
    implementation_head: str,
    inputs: Mapping[str, object],
) -> dict[str, object]:
    if not _is_sha(implementation_head):
        raise T088CanaryPathError("T088 implementation head must be a full SHA-1")
    required = {
        "schema_id",
        "task_id",
        "authorization_kind",
        "authorized",
        "authorization_id",
        "implementation_head",
        "input_identities_sha256",
        "maintainer_attestation",
    }
    if set(authorization) != required or (
        authorization.get("schema_id") != T088_CANARY_PATH_AUTHORIZATION_SCHEMA_ID
        or authorization.get("task_id") != "T088"
        or authorization.get("authorization_kind") != "bounded_canary"
        or authorization.get("authorized") is not True
        or not isinstance(authorization.get("authorization_id"), str)
        or not authorization["authorization_id"]
        or authorization.get("implementation_head") != implementation_head
        or authorization.get("input_identities_sha256") != _canonical_sha256(inputs)
    ):
        raise T088CanaryPathError(
            "T088 path authorization is not an exact input binding"
        )
    attestation = authorization.get("maintainer_attestation")
    if not isinstance(attestation, Mapping) or dict(attestation) != {
        "role": "maintainer",
        "decision": "CANARY_AUTHORIZED",
        "exact_head": implementation_head,
    }:
        raise T088CanaryPathError("T088 path authorization attestation is invalid")
    return {
        "schema_id": "t088-maintainer-canary-authorization-v1",
        "task_id": "T088",
        "authorization_kind": "bounded_canary",
        "authorized": True,
        "authorization_id": authorization["authorization_id"],
        "implementation_head": implementation_head,
        # Filled after deterministic selection/binding, while the v2 attestation
        # above cryptographically commits to every input identity.
    }


def _is_sha(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _default_adapter_factory() -> object:
    from sts_combat_rl.sim.lightspeed import LightSpeedAdapter

    return LightSpeedAdapter(seed=1, ascension=20, player_class="IRONCLAD")


def run_t088_authorized_canary_from_paths(
    *,
    authorization_path: Path,
    implementation_head: str,
    t087_formal_path: Path,
    t087_report_path: Path,
    t087_retention_path: Path,
    t085_selection_path: Path,
    t085_restore_path: Path,
    a_pool_path: Path,
    b_pool_path: Path,
    c_pool_path: Path,
    b_source_manifest_path: Path,
    c_source_manifest_path: Path,
    output_path: Path,
    artifact_root: Path,
    adapter_factory: Callable[[], object] | None = None,
    runner_factory: Callable[..., object] = T088NativeCanaryRecordRunner,
) -> dict[str, object]:
    """Run one approved bounded canary only after complete path admission."""

    formal, formal_ref = _read_t087_accepted_json(
        t087_formal_path,
        expected_sha256=T088_T087_FORMAL_NATURAL_EVIDENCE_SHA256,
        reference_schema_id="t087-natural-evidence-v1",
        label="T087 formal natural evidence",
        validator=_validate_t087_formal_document,
    )
    _report, report_ref = _read_t087_accepted_json(
        t087_report_path,
        expected_sha256=T088_T087_FINAL_REPORT_SHA256,
        reference_schema_id="t087-dense-combat-diagnostics-report-v1",
        label="T087 final report",
        validator=_validate_t087_report_document,
    )
    _retention, retention_ref = _read_t087_accepted_json(
        t087_retention_path,
        expected_sha256=T088_T087_RETENTION_MANIFEST_SHA256,
        reference_schema_id="t087-retention-manifest-v1",
        label="T087 retention manifest",
        validator=_validate_t087_retention_document,
    )
    selection, selection_ref = _read_exact_json(
        t085_selection_path,
        expected_sha256=T085_SELECTION_SHA256,
        schema_id=T085_SELECTION_SCHEMA_ID,
        label="T085 selection",
    )
    restore, restore_ref = _read_exact_json(
        t085_restore_path,
        expected_sha256=T085_RESTORE_SHA256,
        schema_id=T085_RESTORE_SCHEMA_ID,
        label="T085 restore",
    )
    maps, canonical_refs = _load_canonical_maps(
        restore_document=restore,
        selection_document=selection,
        a_pool_path=a_pool_path,
        b_pool_path=b_pool_path,
        c_pool_path=c_pool_path,
        b_source_manifest_path=b_source_manifest_path,
        c_source_manifest_path=c_source_manifest_path,
    )
    try:
        gate = load_t087_t085_input_gate(
            selection_artifact_path=t085_selection_path,
            restore_evidence_path=t085_restore_path,
            canonical_records_by_cohort=maps,
            canonical_artifact_references=canonical_refs,
        )
    except (OSError, T087IncompleteError, ValueError) as exc:
        raise T088CanaryPathError("T087/T085 input gate failed") from exc
    inputs = {
        "t087_formal": formal_ref,
        "t087_report": report_ref,
        "t087_retention": retention_ref,
        "t085_selection": selection_ref,
        "t085_restore": restore_ref,
        "t085_canonical": canonical_refs,
    }
    authorization_document, _ = _read_exact_json(
        authorization_path,
        expected_sha256=None,
        schema_id=T088_CANARY_PATH_AUTHORIZATION_SCHEMA_ID,
        label="T088 canary authorization",
    )
    execution_authorization = _validate_path_authorization(
        authorization_document, implementation_head=implementation_head, inputs=inputs
    )
    cohort = _project_t087_cohort(formal, gate.source_selection_manifest_identity, maps)
    binding = _build_t087_cohort_binding(
        cohort,
        source_identity=gate.source_selection_manifest_identity,
        formal_reference=formal_ref,
        report_reference=report_ref,
        retention_reference=retention_ref,
    )
    selection_manifest = select_t088_canary_records(cohort, cohort_binding=binding)
    execution_authorization.update(
        {
            "canary_selection_sha256": _canonical_sha256(selection_manifest),
            "t087_cohort_binding": _binding_identity(binding),
            "controller_definitions_sha256": _canonical_sha256(
                t088_controller_definitions()
            ),
            "maintainer_attestation": {
                "role": "maintainer",
                "decision": "CANARY_AUTHORIZED",
                "exact_head": implementation_head,
            },
        }
    )
    artifact_root = artifact_root.resolve()
    output_path = output_path.resolve()
    try:
        output_path.relative_to(artifact_root)
    except ValueError as exc:
        raise T088CanaryPathError(
            "T088 canary output must remain under its retention root"
        ) from exc
    if output_path.exists():
        raise T088CanaryPathError("refusing to overwrite retained canary evidence")
    if adapter_factory is None:
        adapter_factory = _default_adapter_factory
    selected_records = {
        record.selection_identity: record
        for cohort in ("A", "B", "C")
        for record in gate.cohorts[cohort]
    }
    runner = runner_factory(
        adapter_factory=adapter_factory,
        selected_records=selected_records,
        canonical_records_by_cohort=maps,
        worker_count=1,
    )
    evidence = execute_t088_canary(
        authorization=execution_authorization,
        implementation_head=implementation_head,
        cohort_rows=cohort,
        cohort_binding=binding,
        selection=selection_manifest,
        runner=runner,
    )
    reference = write_t088_canary_evidence(output_path, evidence)
    return {
        "evidence": evidence,
        "artifact": reference,
        "inputs": inputs,
        "worker_count": 1,
        "single_worker_reason": "bounded canary has at most 20 executions",
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the explicit-only authorized-canary command line."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, required=True)
    parser.add_argument("--implementation-head", required=True)
    parser.add_argument("--t087-formal", type=Path, required=True)
    parser.add_argument("--t087-report", type=Path, required=True)
    parser.add_argument("--t087-retention", type=Path, required=True)
    parser.add_argument("--t085-selection", type=Path, required=True)
    parser.add_argument("--t085-restore", type=Path, required=True)
    parser.add_argument("--a-pool", type=Path, required=True)
    parser.add_argument("--b-pool", type=Path, required=True)
    parser.add_argument("--c-pool", type=Path, required=True)
    parser.add_argument("--b-source-manifest", type=Path, required=True)
    parser.add_argument("--c-source-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--artifact-root", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Route only fully explicit authorized paths; stdout is success JSON only."""

    args = build_parser().parse_args(argv)
    try:
        result = run_t088_authorized_canary_from_paths(
            authorization_path=args.authorization,
            implementation_head=args.implementation_head,
            t087_formal_path=args.t087_formal,
            t087_report_path=args.t087_report,
            t087_retention_path=args.t087_retention,
            t085_selection_path=args.t085_selection,
            t085_restore_path=args.t085_restore,
            a_pool_path=args.a_pool,
            b_pool_path=args.b_pool,
            c_pool_path=args.c_pool,
            b_source_manifest_path=args.b_source_manifest,
            c_source_manifest_path=args.c_source_manifest,
            output_path=args.output,
            artifact_root=args.artifact_root,
        )
    except (OSError, TypeError, ValueError) as exc:
        print(f"T088 canary command failed: {exc}", file=sys.stderr)
        return 2
    artifact = result.get("artifact")
    if not isinstance(artifact, Mapping):
        print(
            "T088 canary command failed: retained artifact reference is missing",
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "schema_id": "t088-canary-command-result-v1",
                "task_id": "T088",
                "artifact": dict(artifact),
                "worker_count": result.get("worker_count"),
                "single_worker_reason": result.get("single_worker_reason"),
            },
            sort_keys=True,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "T088CanaryPathError",
    "build_parser",
    "main",
    "run_t088_authorized_canary_from_paths",
]
