# T087 Legacy T085 Paired-Report Compatibility Amendment — WITHDRAWN

This document is retained only as historical record of a rejected T087 compatibility route. It is **not normative** for current T087 execution, report finalization, retention, or acceptance.

The route was withdrawn after direct inspection of the exact pinned T085 paired aggregate showed that its 2,977 outcome rows do not contain the row-level `task_id`, `native_execution_provenance`, or `native_identity` facts assumed by the original amendment. The previous migration therefore cannot establish historical native provenance from that aggregate and must not be implemented or used as evidence.

The controlling replacement is:

`docs/tasks/T087-minimal-historical-input-dependency-amendment.md`

That replacement removes the historical paired aggregate from T087's required input/finalization/retention dependency set and binds T087 directly to the accepted T085 selection, restore, canonical-source, evaluator-contract, and native-lineage evidence actually needed for re-execution.

## Artifact Eligibility Contract

Artifact Eligibility Required: true.

Inputs: this withdrawn historical document and the controlling `T087-minimal-historical-input-dependency-amendment.md` only for provenance of the specification history.

Reuse mode: `historical_reproduction` documentation only. This withdrawn route is unavailable for `scientific_quality_claim` reuse.

Claim boundary: this document establishes only that a proposed paired-report compatibility path was rejected after its factual premise failed direct artifact inspection. It establishes no T087 input eligibility, native provenance, diagnostic validity, or controller result.

Required predicates: current T087 implementations must not depend on this document's former migration rules, must not infer d62 provenance from the paired aggregate, and must follow the controlling minimum-dependency amendment.

Unavailable-fact behavior: any attempt to use the withdrawn migration as scientific evidence or as a required T087 admission/finalization path is invalid and must fail closed.