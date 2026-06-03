# AGENTS.md

This repository is a minimal Python communication probe for a future Slay the Spire combat RL project.

Current boundaries:

- Keep dependencies minimal.
- Do not add game files, jars, mods, save files, or large binaries.
- Do not implement RL, Gymnasium, Stable-Baselines3, or game mechanics in this phase.
- Keep stdout reserved for protocol commands.
- Put debug output in stderr or log files.
- Keep CommunicationMod command formatting centralized in `src/sts_combat_rl/comm/protocol.py`.

Recommended checks:

```bash
pytest
python -m sts_combat_rl.cli --mock tests/fixtures/combat_basic.json
python -m sts_combat_rl.cli --mock tests/fixtures/non_combat.json
```
