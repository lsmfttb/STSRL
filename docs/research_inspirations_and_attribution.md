# Research Inspirations And Attribution

This document records the external research and public implementations that
materially inspired STSRL. It is a provenance and publication requirement, not
an implementation dependency list.

The project must keep two questions separate:

1. what ideas influenced the research design; and
2. what external code, if any, is copied, modified, linked, or redistributed.

A citation satisfies the first question. It does not by itself grant permission
for the second.

## AlphaZero

STSRL's primary learning objective is inspired by AlphaZero's tabula-rasa,
search-guided policy/value improvement: the final agent should receive game
rules and legal observations, but not human strategy labels, card rankings,
deck archetype knowledge, or hand-written expert policy targets.

Primary reference:

- David Silver, Thomas Hubert, Julian Schrittwieser, Ioannis Antonoglou,
  Matthew Lai, Arthur Guez, Marc Lanctot, Laurent Sifre, Dharshan Kumaran,
  Thore Graepel, Timothy Lillicrap, Karen Simonyan, Demis Hassabis.
  "Mastering Chess and Shogi by Self-Play with a General Reinforcement Learning
  Algorithm." arXiv:1712.01815, 2017.
  https://arxiv.org/abs/1712.01815

STSRL adapts this idea to a single-agent stochastic game. The project therefore
uses search-guided self-generated policy improvement rather than literal
adversarial self-play.

## Suphx

STSRL's training-time use of privileged simulator information is inspired by
Suphx's Oracle-guiding approach for imperfect-information learning. Privileged
information may assist training, diagnostics, curriculum generation, search
improvement, and public-policy transfer, but it is not deployment evidence and
must not enter the final normal-public controller contract.

Primary reference:

- Junjie Li et al. "Suphx: Mastering Mahjong with Deep Reinforcement Learning."
  arXiv:2003.13590, 2020.
  https://arxiv.org/abs/2003.13590

STSRL specifically borrows the Oracle-assistance principle. It does not adopt
Suphx's human-game supervised-pretraining stage as a final-policy requirement;
STSRL's human-knowledge boundary remains defined by
[`training_paradigm.md`](training_paradigm.md).

## CombatSolver

The public CombatSolver project by Torch1230/Torch is a direct implementation
reference for our investigation of Slay the Spire 2 combat-search architecture,
including state identity/transposition, beam-search organization, route
retention, cross-turn search, route reuse, and simulator engineering.

Project references:

- GitHub: https://github.com/Torch1230/CombatSolver
- Steam Workshop: https://steamcommunity.com/sharedfiles/filedetails/?id=3790899961
- Bilibili introduction/demo: https://www.bilibili.com/video/BV1Dh8d6WEDx

Any future public technical report, README research-history section, or paper-like
project write-up that discusses search ideas materially informed by CombatSolver
must acknowledge it explicitly rather than presenting those ideas as uniquely
originating in STSRL.

### Source-use and licensing boundary

As reviewed on 2026-08-28, CombatSolver's README states that its source is public
but that a unified software license is still pending clarification of the Random
Foreseer licensing relationship. Its `THIRD_PARTY_NOTICES.md` also records that
parts of its built-in combat simulation core use and modify Random Foreseer code
under permission granted to CombatSolver.

Therefore, until a compatible public license or separate permission covering the
intended STSRL use has been reviewed and recorded:

- STSRL may read CombatSolver source, study its architecture, compare algorithms,
  and independently implement general ideas;
- STSRL must not copy, port, translate, or mechanically adapt CombatSolver source
  code into this repository;
- citation or attribution must not be treated as a substitute for software
  license compliance;
- if future STSRL code does reuse external implementation text or source, the PR
  must identify the exact upstream revision, license/permission basis, copied or
  derived files, and all required LICENSE/NOTICE obligations before merge.

Relevant upstream notices:

- https://github.com/Torch1230/CombatSolver/blob/main/README.md
- https://github.com/Torch1230/CombatSolver/blob/main/THIRD_PARTY_NOTICES.md

## Jialeiv/sts-rl-agent

The public `Jialeiv/sts-rl-agent` project is an external empirical baseline for
STSRL's split between learned non-combat judgment and online combat planning. It
was reviewed at upstream commit
`54d74021f905b78f32923ccd49fbdacb8fc43553` (2026-08-31).

Project reference:

- GitHub: https://github.com/Jialeiv/sts-rl-agent

The project trains a small shared candidate scorer for all non-combat decisions
(map pathing, card rewards, shops, campfires, and events) while leaving combat to
the same `sts_lightspeed` MCTS in both learned and baseline conditions. The
published scorer consumes the simulator's 412-dimensional run observation plus a
candidate-action descriptor, uses a two-layer `[128, 128]` MLP of roughly 100k
parameters, and is trained from self-generated complete runs with episodic
REINFORCE. The training return is final floor divided by 50 with a moving-average
baseline; no internet guide or human gameplay trace is used as the policy target.

### Reported controlled result

On A0 Ironclad, the repository reports the following comparison on the same fixed
50 evaluation seeds with the combat-search budget held equal:

| Non-combat controller | Combat | Mean floor | Win rate |
| --- | --- | ---: | ---: |
| stock/built-in non-combat (`map = random`) | MCTS @2000 | 22.8 | 2% |
| learned non-combat scorer | MCTS @2000 | 38.5 | 4% |
| stock/built-in non-combat (`map = random`) | MCTS @50000 | 31.2 | 6% |
| learned non-combat scorer | MCTS @50000 | 42.5 | 14% |

The repository also provides a real-Steam integration case in which, for one
high-contrast seed with the same combat search on both sides, the random
non-combat controller died on floor 7 and the learned non-combat controller
cleared floor 51. That single run is integration evidence only; the repository
itself treats the 50-seed simulator table as its comparative performance
boundary.

### Evaluation and information-regime limitations

This result is relevant evidence, but it is not directly comparable to STSRL's
A20 Heart objective or final normal-public information regime:

- the headline controlled result is A0 Ironclad;
- the same 50 seeds were repeatedly evaluated during training and used for best
  checkpoint selection, so the upstream project correctly describes them as a
  validation/evaluation set rather than an untouched final test set;
- the reported table is a single trained run with no confidence intervals or
  multiple training initializations;
- the repository reports its MCTS@2000 difficulty ladder falling to mean floor
  25.7 and 0% wins at A20;
- the real-Steam bridge exports exact RNG state to reconstruct simulator battle
  state for MCTS, so that integration mechanism is not normal-public deployment
  evidence under STSRL's stricter final controller boundary.

The large mean-floor improvement at A0 is nevertheless a material external signal
that learned non-combat control can substantially improve complete-run occupancy
while combat remains fixed.

### Combat-learning negative result

The repository separately documents six attempts to replace or guide combat MCTS
with learned models. Its reported behavior cloning, DAgger, combat REINFORCE,
attention models, value/lookahead, and policy/value-guided PUCT did not match the
blind search baseline; in particular, learned PUCT guidance lost to blind MCTS at
an equal search budget. The authors attribute an important part of the difficulty
to the native search teacher's access to true future RNG/draw information.

This negative result is independently relevant to STSRL because it supports two
working hypotheses already present in our architecture:

1. non-combat decisions can be treated as a distinct long-horizon learned policy
   rather than forcing one learner to solve both decision regimes; and
2. learned combat guidance should not be judged from a weak or semantically
   mismatched network plugged into search. STSRL's T082--T084 line therefore
   continues to repair the learned-leaf target/search contract rather than
   interpreting early harmful value guidance as evidence that search-guided
   combat learning is intrinsically invalid.

For future planning, this project should be treated as motivation for a minimal
self-generated non-combat REINFORCE baseline after the currently authorized
battle-value target work reaches its review boundary. Such a baseline should be
implemented and evaluated under STSRL's own public-state, A20, seed-split, and
artifact-eligibility contracts rather than importing the upstream headline
numbers as STSRL evidence.

### Source-use and licensing boundary

At the reviewed upstream commit, `Jialeiv/sts-rl-agent` is published under the
MIT License and explicitly includes attribution for its `sts_lightspeed`-derived
patch material. The current STSRL use is reference-only: no upstream source or
weights have been copied into this repository.

If future work reuses implementation text, code, patches, or weights rather than
independently reproducing the experimental idea, the consuming PR must pin the
exact upstream revision and preserve the applicable MIT copyright/license notice
and any transitive third-party attribution requirements.

## Publication Requirement

Before a public research release, paper-like technical report, or polished
open-source announcement, maintainers must verify that:

- AlphaZero is cited for the tabula-rasa search-guided policy/value lineage;
- Suphx is cited for the training-time Oracle/privileged-information lineage;
- CombatSolver is cited wherever its public architecture materially informed
  STSRL combat-search research;
- `Jialeiv/sts-rl-agent` is cited wherever its public non-combat learning result or
  combat-learning negative evidence materially informs STSRL experimental design;
- implementation provenance is kept separate from conceptual attribution;
- every copied, modified, linked, or redistributed third-party component has a
  verified compatible license or written permission and the required notices;
- STSRL's final performance claims remain normal-public, standard-start, and
  free of training-only Oracle or hidden-information assistance.

These requirements persist even if later tasks replace the current search or
training implementations.
