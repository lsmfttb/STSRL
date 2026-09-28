# T105 source-acceptance execution

This record accompanies the [T105 contract](../../T105-native-stage-observability-source-acceptance.md)
on STSRL PR #121. The publication base is
`a2d23573043e1e89fb0b19857b343988b38845ba`, the approved specification
is `11f3050f9225578f8924519acf723cbe4f0a3002`, and the implementation
producer is `6f362d7176024bf6d35e1233ad6825b1abc7b145`. The PR's final
acceptance comments bind the landing head after this factual record is added.

## Native source and capability

The canonical manifest advances only the integration commit on the existing
`https://github.com/lsmfttb/sts_lightspeed.git` / `refs/heads/stsrl/main`
line to `5afae22def0c69657b0139bfa21306aebac831af`. Independent Git
ancestry checks show that both the previous accepted pin
`97f59b620efe5ee1571f8da298c99d1e21c1149b` and the independently
reviewed STSRL-007 PR #22 head `38ab89618495dfc8b8e996fbcca44a93e5c18cfe`
are ancestors of that merge; the merge has those two commits as parents. The
active native ref resolved exactly to the new pin at review time.

The added manifest inventory entry requires the STSRL-007 diagnostic API and
test-only audit alongside the unchanged STSRL-006 capability. Its six stages
have closed statuses, with native Search setup and execution preceding root
occurrence mapping in the real control flow. The verifier checks a successful
two-particle trace with exact safe fields, all seven native audit predicates,
and the imported module's location inside the fresh build. The independent
native review covers the failure trace's safe field surface. No exception text
is parsed for stage classification. T077/T085 runtime allowlists admit the new
pin without rewriting historical producer identities; T088's historical
exact-identity opt-in remains unchanged.

## Verification and limits

`scripts/verify_lightspeed_source.sh` fetched the exact active ref, created a
fresh detached `/tmp/stsrl-lightspeed-source.*` worktree at the pinned commit,
built `slaythespire` with eight build jobs, imported only that build, and
passed native T096 visibility/sampler, STSRL-006 bridge, Search-v2 geometry and
state-utilization, and STSRL-007 deterministic stage checks. The disposable
worktree was removed. Implementer focused WSL tests passed 50/50; independent
Maintainer focused tests passed 26/26. Changed-file Ruff format, diff checks,
compile, and the two CLI mock commands passed.

The final-head WSL full suite completed with 1594 passed, 2 skipped, and 10
failed. Each of those ten failing test identities was independently reproduced
on the unmodified merged `main` (10/10), including historical T088 pinning,
fixed-path expectations, and T092 fixture assertions. Thus the full suite is
not reported green, while no T105-specific regression was found. Repository
wide lint/format limitations remain inherited; changed-file checks pass.

Small ignored logs are retained outside the disposable review worktree under
`artifacts/t105-native-stage-observability-6f362d7/` in the main workspace:

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `canonical-source-verifier.log` | 7,128 | `4e54ea300f7f37c1d25c1bf9cf0864eb45be8b0208c64c7c3836534e83fc2603` |
| `pytest-wsl-final.log` | 32,939 | `827ab8b2446b085d2e15f63a1bbeced699b037f21b4ac6bd8c346a50af8813` |

Maintainer owns these logs through T105 landing and any immediate source
provenance audit. They can be regenerated from the pinned native commit,
STSRL implementation producer, canonical verifier, and the WSL Python test
command above; they may be removed once no active successor needs raw logs.

T105 performed no T104 70/343 population replay, native source modification,
mechanics repair, particle convergence, training, or controller promotion.
The terminal is `NATIVE_PARTICLE_SEARCH_STAGE_OBSERVABILITY_ACCEPTED` only as
a source/capability acceptance. A bounded diagnostic re-entry requires a
separately published Planner contract.
