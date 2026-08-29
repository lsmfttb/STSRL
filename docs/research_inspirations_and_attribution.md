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

## Publication Requirement

Before a public research release, paper-like technical report, or polished
open-source announcement, maintainers must verify that:

- AlphaZero is cited for the tabula-rasa search-guided policy/value lineage;
- Suphx is cited for the training-time Oracle/privileged-information lineage;
- CombatSolver is cited wherever its public architecture materially informed
  STSRL combat-search research;
- implementation provenance is kept separate from conceptual attribution;
- every copied, modified, linked, or redistributed third-party component has a
  verified compatible license or written permission and the required notices;
- STSRL's final performance claims remain normal-public, standard-start, and
  free of training-only Oracle or hidden-information assistance.

These requirements persist even if later tasks replace the current search or
training implementations.
