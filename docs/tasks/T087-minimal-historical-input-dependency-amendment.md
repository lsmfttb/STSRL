# T087 Minimal Historical Input Dependency Amendment

This file is a **normative part of the T087 specification bundle** and supersedes every T087 clause that makes the historical T085 paired aggregate a required execution, report-finalization, retention, or acceptance input.

It follows the Maintainer dependency audit on PR #100 at implementation head `5014da2e8c511ad8cdb7bad7c5ecf896fcd8e31b`. That audit established that the exact T085 paired aggregate is used only for redundant admission/report bookkeeping and that none of its 2,977 historical outcome rows are consumed by T087 record selection, simulator execution, dense diagnostics, HP rescue, or blind-audit selection.

The previously published `T087-legacy-t085-paired-report-compatibility-amendment.md` is withdrawn in full. It was based on a false factual premise about row-level task/native provenance in the retained aggregate and must not be implemented, used as evidence, or treated as an acceptance requirement.

No canary or formal simulator execution is authorized until Maintainer approves an exact PR head containing this amendment and independently accepts the corresponding implementation repair.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

Inputs: the exact T085 selection artifact SHA-256 `d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752`; exact T085 restore-evidence artifact SHA-256 `0adbdc4e055bd8d53680757a395e3e7973b7242b06db1c5053281ef883b679ef`; the exact A/B/C canonical source artifacts and per-record bindings authenticated by that restore evidence; accepted T085 scientific/evaluator source head `5edaa255959d34d4d31bbfae7e6b6bed9758024d`; historical T085 native identity `lsmfttb/sts_lightspeed refs/heads/stsrl/main @ d62ff35579b54d70a7428afdf84743c94df3fe0c`; current accepted T087 native identity `lsmfttb/sts_lightspeed refs/heads/stsrl/main @ 96052d24b9c2c16ff25b6f7241edd972613be997`; and all T087 newly generated raw evidence/report/retention artifacts.

Reuse mode: `scientific_quality_claim` only inside T087's diagnostic-validity boundary. Historical T085 outcomes/classification are not reused as T087 scientific observations.

Claim boundary: this amendment establishes only the minimum historical dependency set needed to authenticate and re-execute the frozen A/B/C battle starts under T087. It does not create a new T085 result, alter historical T085 artifacts, relax record/source/native verification, or change the T087 controller, dense metrics, HP-rescue semantics, or human-audit role.

Required predicates: exact selection-artifact hash/schema and A/B/C occurrence-safe identity/order; exact restore-evidence hash/schema and complete outcome-blind restore/public/legal/source parity; exact canonical source record binding for every selected A/B/C record; accepted T085 evaluator contract bound to source head `5edaa255959d34d4d31bbfae7e6b6bed9758024d`; historical T085 native identity authenticated by the accepted selection/restore/source provenance; current T087 native identity `96052d24...` verified as an accepted descendant under native-lineage/source-verifier rules; 413/413 current-native revalidation before formal execution; and all existing T087 raw-evidence/diagnostic/retention gates.

Unavailable-fact behavior: any required selection, restore, canonical-source, evaluator-contract, historical-native, current-native, lineage, public/legal parity, artifact hash, or per-record binding fact that is missing, malformed, conflicting, filename-inferred, path-inferred, or otherwise unavailable fails closed to `INCOMPLETE`. The historical paired aggregate may not be used to fill such a gap.

## 1. Historical paired aggregate is not a required T087 input

The historical paired report with SHA-256:

`f756c9f4ac885c61c2a73ff9b2d0e05a15b317df2cce9c9bf5dbd374f7afcec3`

is **not** a required input to any T087 execution gate, report finalizer, retention readiness gate, or terminal classification.

T087 must not require:

- loading that report before natural execution;
- validating its top-level or row-level task/native provenance;
- comparing its `selection_binding` as a second mandatory copy of the T085 selection order;
- retaining its path/SHA as a required T087 input-artifact reference;
- a `--t085-paired` CLI argument for any required T087 command;
- a `paired_report_sha256` predicate for `DENSE_COMBAT_DIAGNOSTICS_READY`.

The report may be mentioned in documentation only as historical T085 evidence. Its availability or schema shape cannot cause T087 to pass or fail.

## 2. Required historical identity and selection binding

T087 must bind the natural cohort directly to the exact accepted T085 selection artifact:

- SHA-256 `d5c335cd6e1f96e72ae3b302eebca17a5f6531fa0aac97ee2febec2c41c2e752`;
- schema `t085-native-selection-artifact-v1`;
- exact selected identity/order for A=93, B=192, C=128;
- B@400 may remain validated as historical selection-manifest content but is not part of the 413-row T087 natural execution set.

No paired-report copy of the selection order is required.

## 3. Required restore and canonical-source binding

T087 must bind every selected A/B/C identity to the exact accepted T085 restore evidence:

- SHA-256 `0adbdc4e055bd8d53680757a395e3e7973b7242b06db1c5053281ef883b679ef`;
- schema `t085-native-selection-restore-evidence-v1`;
- `complete=true`;
- `partial=false`;
- `restore_parity_passed=true`;
- `outcome_blind_selection=true`;
- `search_invoked=false`;
- exact source/artifact identity for every retained record.

The canonical A/B/C source artifacts referenced by the accepted restore evidence must themselves be opened and hash/size/schema verified before execution. T087 must not accept caller-constructed record maps whose artifact references have not been independently verified.

The authoritative source identities include the already accepted T085/T052 artifacts, including T052 cohort SHA-256 `b7f8e9b85b53bbf8e37adfe6cc90d0579937661309b26bce2a8f2921604a8608`, Cohort-B source manifest SHA-256 `11b7a55cc1bca52481699c6ebe10f16af2ad1cdf1765b565fdfdbfe5aad93e06`, and Cohort-C source manifest SHA-256 `2a9986972764197d0c9b4927617c15a71221358364823d3f0f9687433face376`, where applicable through the retained restore/source chain.

## 4. Accepted T085 evaluator/randomness contract

The historical evaluator contract is frozen by the accepted T085 scientific source head:

`5edaa255959d34d4d31bbfae7e6b6bed9758024d`

T087 re-execution must preserve the already published contract:

- native Search v2 / `BattleScumSearcher2`;
- 100 simulations;
- root selection `highest_mean`;
- no policy-prior callback;
- no learned leaf-value callback;
- action space `ActionSpaceConfig.initial_no_potions()`;
- restore the exact canonical record and do not reset/reseed afterward;
- `execute_controlled_run(..., seed=None, max_steps=200, ...)`;
- no extra Python/controller/per-record Search seed.

The source-head identity is a historical contract anchor. T087 must also verify the corresponding executable controller/evaluator configuration at its own exact implementation head; merely recording the `5edaa255...` string without checking the current T087 evaluator configuration is insufficient.

## 5. Native identity split

Historical T085 provenance remains authenticated against:

`d62ff35579b54d70a7428afdf84743c94df3fe0c`.

All new T087 simulator execution uses:

`96052d24b9c2c16ff25b6f7241edd972613be997`.

The T087 native identity must remain an accepted descendant of the historical identity under the repository native-lineage policy, and the clean pinned-source verifier must pass. Every one of the exact 413 A/B/C records must re-pass the current-native restore/public/legal/source-parity gate before any formal natural evaluation. No record may be recollected, substituted, or dropped.

## 6. Execution-gate implementation requirements

The authoritative T087 input gate must be constructible only after all required artifacts above have been independently opened and verified. A caller-supplied dataclass or mapping with superficially matching values is not sufficient.

Natural evaluation and HP rescue must receive/use the same verified gate. At each execution boundary, the implementation must fail closed if the verified token/reference set is missing, substituted, stale, or inconsistent with the exact record being restored.

Focused tests must prove at least:

1. the real pinned selection + restore + canonical-source chain is accepted without loading the paired aggregate;
2. paired-report absence does not affect admission;
3. a substituted selection artifact fails;
4. a substituted restore artifact fails;
5. a substituted canonical source artifact or record binding fails;
6. a forged/superficially matching gate fails;
7. HP rescue cannot execute without the same verified gate;
8. B@400 being present in the selection artifact does not contaminate the 413-row A/B/C execution set;
9. current T087 evaluator configuration drifting from the frozen Search-v2@100/seed-none/max-200 contract fails;
10. current-native lineage/source verification failure prevents execution.

## 7. Report and retention requirements

T087 final report/retention must retain and verify at minimum:

- exact T085 selection-artifact reference;
- exact T085 restore-evidence reference;
- exact canonical A/B/C source-artifact references consumed by the 413 records;
- accepted T085 scientific/evaluator source head `5edaa255...`;
- historical native identity `d62ff355...`;
- current T087 native identity `96052d24...`;
- lineage/source-verifier result;
- exact T087 implementation/run head;
- every existing T087 natural, dense, HP-rescue, blind-audit, report, and retention artifact required by the primary contract.

The T085 paired aggregate reference must not be a required retention role. If retained as optional historical citation, it must be clearly marked non-authoritative for T087 and omitted from every readiness predicate.

Any regeneration command retained by T087 must be complete and executable with explicit required paths/arguments or a repository-owned wrapper. It must not require a paired-report path.

## 8. Withdrawal of the rejected compatibility route

`T087-legacy-t085-paired-report-compatibility-amendment.md` is withdrawn and superseded by this amendment.

The implementation commits that attempted to validate/infer compatibility for the historical paired aggregate must be removed or rendered unreachable from all required T087 execution/finalization paths. Synthetic tests for a legacy paired shape cannot substitute for the real minimum-dependency gates above.

Do not rewrite or regenerate the T085 paired aggregate merely for T087.

## 9. Re-approval and execution boundary

This is a material reproducibility-contract change.

Maintainer must approve an exact PR head containing this amendment before implementation changes proceed under it. After implementation, Maintainer must independently review the exact implementation head and explicitly authorize exactly one bounded canary. The 413-record formal execution remains separately gated after canary evidence.

The terminal classes remain unchanged: `DENSE_COMBAT_DIAGNOSTICS_READY` only when all primary T087 requirements plus this amendment pass; otherwise `INCOMPLETE`.