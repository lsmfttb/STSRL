"""Live CommunicationMod runtime adapter.

Converts a real CommunicationMod combat observation into the same decision/action
interface used by simulator-side controllers, invokes a configured
``OnlineController``, and maps the selected action back to a CommunicationMod
protocol command.

The adapter is normal-public only. It must not receive hidden RNG, hidden draw
order, unrevealed future encounters, or hidden Boss information.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from sts_combat_rl.comm.protocol import (
    Command,
    constrain_to_available_commands,
    format_command,
)
from sts_combat_rl.sim.controller_contract import (
    ControllerDecision,
)
from sts_combat_rl.sim.contract import SimulatorAction, SimulatorSnapshot
from sts_combat_rl.sim.features import (
    TACTICAL_FEATURE_SCHEMA_ID,
    build_public_tactical_actions,
    build_public_tactical_state,
    encode_communicationmod_battle_snapshot,
    normalize_communicationmod_battle_snapshot,
    public_tactical_missing_fields,
    tactical_field_parity_rows,
)
from sts_combat_rl.sim.policy import DecisionContext

if TYPE_CHECKING:
    from sts_combat_rl.sim.controller_contract import OnlineController

logger = logging.getLogger("sts_combat_rl.live_adapter")

LIVE_SOURCE_FORMAT = "communicationmod_live_v1"
LIVE_INFORMATION_REGIME = "normal_public_policy"

# Prefix for live-only action ids to avoid collision with simulator replay ids.
_LIVE_ACTION_ID_PREFIX = "live"

# Legal action kinds for the live battle adapter.
_LIVE_ACTION_KINDS = frozenset({"card", "end_turn", "potion", "potion_discard"})


@dataclass(frozen=True)
class LiveDecisionResult:
    """Result of one live controller invocation.

    Fields:
        command: the CommunicationMod command to emit (or ``None`` if the
            state is unsupported and no fallback was produced).
        formatted_command: the protocol string to write to stdout.
        provenance: controller provenance serialized as a dict.
        decision: the ``ControllerDecision`` from the controller, or ``None``
            if no controller was invoked.
        tactical_state: the structured ``public-tactical-v2`` state.
        tactical_actions: the structured public action representations.
        selected_action_index: index of the selected legal action.
        action_identity: the public identity of the selected action.
        missing_fields: fields represented through an explicit missing path.
        parity_report: the simulator/live tactical-field parity rows.
        is_combat: whether the snapshot was a combat state.
        unsupported_reason: why the state was unsupported (``None`` if combat).
        source_format: the source format label for provenance.
        step_index: the step counter passed by the caller.
        raw_snapshot: the raw CommunicationMod snapshot (for audit).
    """

    command: Command | None
    formatted_command: str
    provenance: dict[str, Any] | None
    decision: ControllerDecision | None
    tactical_state: dict[str, Any]
    tactical_actions: list[dict[str, Any]]
    selected_action_index: int | None
    action_identity: dict[str, Any]
    missing_fields: list[str]
    parity_report: list[dict[str, str]]
    is_combat: bool
    unsupported_reason: str | None = None
    source_format: str = LIVE_SOURCE_FORMAT
    step_index: int = 0
    raw_snapshot: dict[str, Any] = field(default_factory=dict)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    return (
        value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes))
        else ()
    )


def _has_sequence_field(data: Mapping[str, Any], key: str) -> bool:
    return isinstance(data.get(key), Sequence) and not isinstance(
        data.get(key), (str, bytes)
    )


def _nullable_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _number(value: Any) -> float:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def _is_combat_snapshot(raw: Mapping[str, Any]) -> bool:
    """Determine whether a CommunicationMod snapshot represents a combat state."""

    if raw.get("battle_active") is True:
        return True

    game = _mapping(raw.get("game_state")) or _mapping(raw.get("gameState")) or raw
    screen_type = str(game.get("screen_type", game.get("screenType", ""))).strip()

    if screen_type.upper() in {"COMBAT", "BATTLE"}:
        return True

    combat = _mapping(game.get("combat_state")) or _mapping(game.get("combatState"))
    if combat:
        return True

    room_phase = str(game.get("room_phase", game.get("roomPhase", ""))).strip()
    if room_phase.upper() in {"COMBAT", "BATTLE"}:
        return True

    return False


def _parse_available_commands(raw: Mapping[str, Any]) -> frozenset[str]:
    """Extract available commands from a CommunicationMod snapshot."""

    commands = raw.get("available_commands", raw.get("availableCommands"))
    if not isinstance(commands, list):
        return frozenset()
    return frozenset(
        item for item in commands if isinstance(item, str) and item.strip()
    )


def _monster_alive(monster: Mapping[str, Any]) -> bool:
    if monster.get("is_gone") is True:
        return False
    hp = monster.get("current_hp", monster.get("currentHp"))
    if isinstance(hp, (int, float)) and not isinstance(hp, bool):
        return hp > 0
    return True


def build_live_legal_actions(
    raw_snapshot: Mapping[str, Any],
) -> list[SimulatorAction]:
    """Build legal actions from CommunicationMod-visible state.

    Each action carries enough metadata in its ``raw`` field to be mapped back to
    a CommunicationMod protocol command after the controller selects one.

    Actions with identical visible identity (e.g. two Strikes without targets)
    are distinguished by occurrence in ``_attach_live_action_identities``, called
    by ``build_live_decision_context``.
    """

    available = _parse_available_commands(raw_snapshot)
    normalized = normalize_communicationmod_battle_snapshot(raw_snapshot)

    hand = _sequence(normalized.get("battle_hand"))
    monsters = _sequence(normalized.get("battle_monsters"))
    potions = _sequence(normalized.get("battle_potions"))
    actions: list[SimulatorAction] = []
    action_counter = 0

    # Card play actions — one action per (card_index, target_index) pair when
    # a target is required; one action without a target otherwise.
    if "play" in available:
        for card_index, raw_card in enumerate(hand):
            card = _mapping(raw_card)
            playable = _nullable_bool(card.get("is_playable", card.get("playable")))
            requires_target = _nullable_bool(
                card.get("has_target", card.get("requires_target"))
            )
            if playable is not True:
                continue
            if requires_target is True:
                for monster_index, raw_monster in enumerate(monsters):
                    monster = _mapping(raw_monster)
                    if not _monster_alive(monster):
                        continue
                    action_counter += 1
                    actions.append(
                        SimulatorAction(
                            action_id=f"{_LIVE_ACTION_ID_PREFIX}_{action_counter}",
                            label=(
                                f"play {card.get('name', card.get('id', '?'))} "
                                f"(hand {card_index}) -> "
                                f"{monster.get('name', monster.get('id', '?'))} "
                                f"(monster {monster_index})"
                            ),
                            kind="card",
                            raw={
                                "scope": "battle",
                                "kind": "card",
                                "card_index": card_index,
                                "target_index": monster_index,
                                "card": dict(raw_card),
                                "target": dict(raw_monster),
                                "requires_target": True,
                                "_live_command_type": "play_card",
                                "_live_card_index": card_index,
                                "_live_target_index": monster_index,
                            },
                        )
                    )
            else:
                action_counter += 1
                actions.append(
                    SimulatorAction(
                        action_id=f"{_LIVE_ACTION_ID_PREFIX}_{action_counter}",
                        label=(
                            f"play {card.get('name', card.get('id', '?'))} "
                            f"(hand {card_index})"
                        ),
                        kind="card",
                        raw={
                            "scope": "battle",
                            "kind": "card",
                            "card_index": card_index,
                            "card": dict(raw_card),
                            "requires_target": False,
                            "_live_command_type": "play_card",
                            "_live_card_index": card_index,
                        },
                    )
                )

    # End turn.
    if "end" in available:
        action_counter += 1
        actions.append(
            SimulatorAction(
                action_id=f"{_LIVE_ACTION_ID_PREFIX}_{action_counter}",
                label="end turn",
                kind="end_turn",
                raw={
                    "scope": "battle",
                    "kind": "end_turn",
                    "_live_command_type": "end_turn",
                },
            )
        )

    # Potion use actions.
    if "potion" in available:
        for slot, raw_potion in enumerate(potions):
            potion = _mapping(raw_potion)
            potion_id = str(
                potion.get("id", potion.get("name", potion.get("potion_id", "")))
            ).strip()
            if potion_id in {"", "Potion Slot", "EMPTY_POTION_SLOT"}:
                continue
            can_use = _nullable_bool(potion.get("can_use", potion.get("is_usable")))
            if can_use is False:
                continue
            requires_target = _nullable_bool(
                potion.get("requires_target", potion.get("has_target"))
            )
            if requires_target is True:
                for monster_index, raw_monster in enumerate(monsters):
                    monster = _mapping(raw_monster)
                    if not _monster_alive(monster):
                        continue
                    action_counter += 1
                    actions.append(
                        SimulatorAction(
                            action_id=f"{_LIVE_ACTION_ID_PREFIX}_{action_counter}",
                            label=(
                                f"potion use {potion_id} (slot {slot}) -> "
                                f"{monster.get('name', monster.get('id', '?'))} "
                                f"(monster {monster_index})"
                            ),
                            kind="potion",
                            raw={
                                "scope": "battle",
                                "kind": "potion",
                                "card_index": None,
                                "target_index": monster_index,
                                "target": dict(raw_monster),
                                "requires_target": True,
                                "_live_command_type": "potion",
                                "_live_potion_action": "use",
                                "_live_potion_slot": slot,
                                "_live_target_index": monster_index,
                            },
                        )
                    )
            else:
                action_counter += 1
                actions.append(
                    SimulatorAction(
                        action_id=f"{_LIVE_ACTION_ID_PREFIX}_{action_counter}",
                        label=f"potion use {potion_id} (slot {slot})",
                        kind="potion",
                        raw={
                            "scope": "battle",
                            "kind": "potion",
                            "card_index": None,
                            "requires_target": False,
                            "_live_command_type": "potion",
                            "_live_potion_action": "use",
                            "_live_potion_slot": slot,
                        },
                    )
                )

        # Potion discard actions.
        for slot, raw_potion in enumerate(potions):
            potion = _mapping(raw_potion)
            potion_id = str(
                potion.get("id", potion.get("name", potion.get("potion_id", "")))
            ).strip()
            if potion_id in {"", "Potion Slot", "EMPTY_POTION_SLOT"}:
                continue
            action_counter += 1
            actions.append(
                SimulatorAction(
                    action_id=f"{_LIVE_ACTION_ID_PREFIX}_{action_counter}",
                    label=f"potion discard {potion_id} (slot {slot})",
                    kind="potion_discard",
                    raw={
                        "scope": "battle",
                        "kind": "potion_discard",
                        "card_index": None,
                        "requires_target": False,
                        "_live_command_type": "potion",
                        "_live_potion_action": "discard",
                        "_live_potion_slot": slot,
                    },
                )
            )

    return actions


def build_live_decision_context(
    raw_snapshot: Mapping[str, Any],
    actions: list[SimulatorAction],
) -> DecisionContext:
    """Build a ``DecisionContext`` from a CommunicationMod snapshot and live actions.

    The context uses the same ``public-tactical-v2`` state and action contracts
    as the simulator path, but the features are encoded from the CommunicationMod
    normalization path and the eligible action indices include all constructed
    live actions.
    """

    normalized = normalize_communicationmod_battle_snapshot(raw_snapshot)
    snapshot_features = encode_communicationmod_battle_snapshot(raw_snapshot)
    tactical_state = build_public_tactical_state(normalized)
    tactical_legal_actions = build_public_tactical_actions(actions, normalized)

    return DecisionContext(
        screen_state="BATTLE",
        snapshot_features=snapshot_features,
        legal_action_features=encode_live_action_features(tactical_legal_actions),
        legal_action_kinds=[action.kind for action in actions],
        eligible_action_indices=list(range(len(actions))),
        snapshot_metadata={},
        legal_action_metadata=[_live_action_metadata(action) for action in actions],
        tactical_state=tactical_state,
        tactical_legal_actions=tactical_legal_actions,
        tactical_feature_schema_id=TACTICAL_FEATURE_SCHEMA_ID,
    )


def encode_live_action_features(
    tactical_actions: list[dict[str, Any]],
) -> list[list[float]]:
    """Encode tactical public actions into compatibility numeric vectors."""

    from sts_combat_rl.sim.features import _encode_public_action

    return [_encode_public_action(action) for action in tactical_actions]


def _live_action_metadata(action: SimulatorAction) -> dict[str, int]:
    """Expose visible live-action parameters for audit."""

    meta: dict[str, int] = {}
    card_index = action.raw.get("card_index")
    if isinstance(card_index, int) and not isinstance(card_index, bool):
        meta["card_index"] = card_index
    target_index = action.raw.get("target_index")
    if isinstance(target_index, int) and not isinstance(target_index, bool):
        meta["target_index"] = target_index
    return meta


def live_action_to_command(action: SimulatorAction) -> Command:
    """Map one live ``SimulatorAction`` back to a CommunicationMod ``Command``."""

    raw = action.raw
    live_type = raw.get("_live_command_type", "end_turn")

    if live_type == "play_card":
        return Command.play_card(
            card_index=raw.get("_live_card_index", 0),
            target_index=raw.get("_live_target_index"),
            reason=f"live:{action.label}",
        )

    if live_type == "end_turn":
        return Command.end_turn(f"live:{action.label}")

    if live_type == "potion":
        return Command.potion(
            action=raw.get("_live_potion_action", "use"),
            potion_slot=raw.get("_live_potion_slot", 0),
            target_index=raw.get("_live_target_index"),
            reason=f"live:{action.label}",
        )

    return Command.end_turn("live: unmapped action")


def build_live_parity_report() -> list[dict[str, str]]:
    """Return the simulator/live tactical-field parity rows."""

    return tactical_field_parity_rows()


def invoke_live_controller(
    raw: dict[str, Any],
    controller: OnlineController,
    *,
    step_index: int = 0,
    non_combat_fallback: Command | None = None,
) -> LiveDecisionResult:
    """Invoke a configured battle controller on a CommunicationMod snapshot.

    Parameters:
        raw: the parsed CommunicationMod JSON snapshot.
        controller: the battle controller to invoke. Must implement
            ``OnlineController``.
        step_index: the logical step counter for provenance.
        non_combat_fallback: a fallback ``Command`` to emit when the snapshot
            is not a combat state. If ``None``, the result will have
            ``command=None`` and ``unsupported_reason`` set.

    Returns:
        A ``LiveDecisionResult`` with the selected command, provenance, tactical
        state, parity report, and any missing-field diagnostics.
    """

    normalized = normalize_communicationmod_battle_snapshot(raw)
    is_combat = _is_combat_snapshot(raw)
    available = _parse_available_commands(raw)
    provenance_dict: dict[str, Any] | None = None
    decision: ControllerDecision | None = None
    selected_index: int | None = None
    action_identity: dict[str, Any] = {}
    tactical_state: dict[str, Any] = {}
    tactical_actions: list[dict[str, Any]] = []
    missing_fields: list[str] = []
    parity_report = build_live_parity_report()
    command: Command | None = None
    unsupported_reason: str | None = None

    if not is_combat:
        unsupported_reason = "not a combat state"
        if non_combat_fallback is not None:
            command = non_combat_fallback
        return LiveDecisionResult(
            command=command,
            formatted_command=format_command(command) if command else "state",
            provenance=provenance_dict,
            decision=decision,
            tactical_state=tactical_state,
            tactical_actions=tactical_actions,
            selected_action_index=selected_index,
            action_identity=action_identity,
            missing_fields=missing_fields,
            parity_report=parity_report,
            is_combat=False,
            unsupported_reason=unsupported_reason,
            source_format=LIVE_SOURCE_FORMAT,
            step_index=step_index,
            raw_snapshot=dict(raw),
        )

    # Build the structured state and actions.
    tactical_state = build_public_tactical_state(normalized)
    missing_fields = public_tactical_missing_fields(tactical_state)
    live_actions = build_live_legal_actions(raw)

    if not live_actions:
        unsupported_reason = "no legal live actions constructed"
        command = Command.end_turn("no legal live actions")
        return LiveDecisionResult(
            command=command,
            formatted_command=format_command(command),
            provenance=provenance_dict,
            decision=decision,
            tactical_state=tactical_state,
            tactical_actions=tactical_actions,
            selected_action_index=selected_index,
            action_identity=action_identity,
            missing_fields=missing_fields,
            parity_report=parity_report,
            is_combat=True,
            unsupported_reason=unsupported_reason,
            source_format=LIVE_SOURCE_FORMAT,
            step_index=step_index,
            raw_snapshot=dict(raw),
        )

    tactical_actions = build_public_tactical_actions(live_actions, normalized)
    context = build_live_decision_context(raw, live_actions)

    # Build synthetic simulator interface objects.  Public controllers ignore
    # the adapter and snapshot, so these carry only the visible data.
    snapshot_features = encode_communicationmod_battle_snapshot(raw)
    synthetic_snapshot = SimulatorSnapshot(
        observation=list(snapshot_features),
        raw=dict(raw),
    )

    # Dummy adapter — a public controller must never call it.

    synthetic_adapter = _DummyLiveAdapter()

    try:
        decision = controller.select_action(
            synthetic_adapter,
            synthetic_snapshot,
            list(live_actions),
            context,
            step_index,
        )
    except (RuntimeError, ValueError) as exc:
        unsupported_reason = f"controller raised {type(exc).__name__}: {exc}"
        command = Command.end_turn("controller error")
        return LiveDecisionResult(
            command=command,
            formatted_command=format_command(command),
            provenance=provenance_dict,
            decision=decision,
            tactical_state=tactical_state,
            tactical_actions=tactical_actions,
            selected_action_index=selected_index,
            action_identity=action_identity,
            missing_fields=missing_fields,
            parity_report=parity_report,
            is_combat=True,
            unsupported_reason=unsupported_reason,
            source_format=LIVE_SOURCE_FORMAT,
            step_index=step_index,
            raw_snapshot=dict(raw),
        )

    selected_index = decision.selected_index
    provenance_dict = decision.provenance.to_dict()

    # Build the raw command, then constrain to actually available commands.
    if 0 <= selected_index < len(live_actions):
        selected_action = live_actions[selected_index]
        command = live_action_to_command(selected_action)
        if selected_index < len(tactical_actions):
            action_identity = dict(tactical_actions[selected_index].get("identity", {}))
    else:
        unsupported_reason = (
            f"selected index {selected_index} outside {len(live_actions)} "
            "live legal actions"
        )
        command = Command.end_turn("out of bounds selection")

    # Constrain to actually available CommunicationMod commands.
    if command is not None and available:
        available_list = sorted(available)
        command = constrain_to_available_commands(command, available_list)

    return LiveDecisionResult(
        command=command,
        formatted_command=format_command(command) if command else "state",
        provenance=provenance_dict,
        decision=decision,
        tactical_state=tactical_state,
        tactical_actions=tactical_actions,
        selected_action_index=selected_index,
        action_identity=action_identity,
        missing_fields=missing_fields,
        parity_report=parity_report,
        is_combat=True,
        unsupported_reason=unsupported_reason,
        source_format=LIVE_SOURCE_FORMAT,
        step_index=step_index,
        raw_snapshot=dict(raw),
    )


class _DummyLiveAdapter:
    """A stand-in for the simulator adapter when no simulator is present.

    Public controllers must never call the simulator adapter, but the
    ``OnlineController`` protocol requires one.  Any call raises an error.
    """

    def reset(self, seed: int | None = None) -> SimulatorSnapshot:
        raise RuntimeError("live adapter cannot reset a simulator")

    def legal_actions(self, snapshot: SimulatorSnapshot) -> list[SimulatorAction]:
        raise RuntimeError("live adapter does not supply simulator legal actions")

    def step(self, action: SimulatorAction) -> Any:
        raise RuntimeError("live adapter cannot step a simulator")


def log_live_decision_result(result: LiveDecisionResult) -> dict[str, Any]:
    """Return a JSON-safe log record for a live decision result."""

    return {
        "is_combat": result.is_combat,
        "source_format": result.source_format,
        "information_regime": LIVE_INFORMATION_REGIME,
        "step_index": result.step_index,
        "selected_action_index": result.selected_action_index,
        "formatted_command": result.formatted_command,
        "missing_fields": sorted(result.missing_fields),
        "unknown_identity_counts": result.tactical_state.get(
            "unknown_identity_counts", {}
        ),
        "unsupported_reason": result.unsupported_reason,
        "provenance": result.provenance,
        "action_identity": result.action_identity,
    }
