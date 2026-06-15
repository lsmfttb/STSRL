# Simulator Candidate Scan

> Historical document. `sts_lightspeed` is now the authoritative simulator
> target; see `docs/sts_lightspeed_wsl_spike.md` for the current setup.

Scanned on 2026-06-03. External repositories were cloned only under
`~/stsrl-spikes` in WSL, not into this repository.

## Ranking

1. `sts_lightspeed`
   - Repository: https://github.com/gamerpuppy/sts_lightspeed
   - Commit inspected: `7476a81`
   - License: MIT
   - Verdict: primary candidate.
   - Reason: real C++17 standalone simulator with pybind11 bindings, substantial
     implementation, tree search, save/combat loading support, and claimed high
     rollout speed.
   - WSL result: C++ `small-test` and Python `slaythespire` module build/import
     successfully after external-checkout-only compatibility fixes.
   - Current gap: Python binding exposes observations and built-in playouts, but
     not direct legal actions or one-step execution. Needs a small pybind shim
     before adapter work can continue.

2. `decapitate-the-spire`
   - Repository: https://github.com/jahabrewer/decapitate-the-spire
   - Commit inspected: `7a7b7ff`
   - License: GPLv3
   - Verdict: secondary adapter candidate.
   - Reason: Python source imports and `Game.step(...)` works with legal actions.
   - Risk: pre-alpha, Silent-focused, incomplete Exordium content, approximate
     correctness.

3. `STS-AI-Master`
   - Repository: https://github.com/XlousMao/STS-AI-Master
   - Commit inspected: `d689156`
   - License: no LICENSE file found in checkout.
   - Verdict: architecture reference, not a standalone simulator.
   - Reason: includes `gym_sts`, Protobuf, custom Java bridge mod, and headless
     launch scripts. It still depends on launching Slay the Spire + ModTheSpire
     and sending socket commands to a custom bridge.
   - Risk: would require adopting/reconciling another mod/protocol stack.

4. `MiniSTS`
   - Repository: https://github.com/iambb5445/MiniSTS
   - Commit inspected: `10ad4df`
   - License: GPLv3
   - Verdict: useful toy/research environment, not fidelity training backend.
   - Reason: simplified, headless battle-only implementation designed for
     experimentation with cards and agents.
   - Risk: README explicitly says it omits map and level progression.

5. `Slay-AI`
   - Repository: https://github.com/matthewReff/Slay-AI
   - Commit inspected: `0d51987`
   - License: no LICENSE file found in checkout.
   - Verdict: not a simulator candidate for this repo.
   - Reason: mod stack around ModTheSpire/BaseMod/CommunicationMod/SuperFastMode
     and a modified spirecomm. Requires copying the real game folder into the
     repo layout and has heavy ML/CUDA dependencies.
   - Risk: conflicts with this repo's boundary of not adding game files, jars,
     mods, or large external stacks.

## gym-sts

No independent `gym-sts` project was found from primary-source search. The
observable `gym_sts` package is inside `STS-AI-Master`, where it wraps the
custom Java bridge over sockets. Treat it as part of `STS-AI-Master`, not as a
separate simulator.

## slai-the-spire

No primary repository named `slai-the-spire` was found. If this refers to
`Slay-AI`, see the `Slay-AI` entry above.
