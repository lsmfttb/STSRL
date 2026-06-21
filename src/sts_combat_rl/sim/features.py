"""Versioned, normal-public tactical battle feature contract.

The structured contract in this module is the authoritative representation for
model inputs.  The fixed-size numeric vectors remain a compatibility view for
the pre-trainer plumbing, but are deliberately derived from the same public
structure.  No caller may pass a simulator object or an arbitrary raw snapshot
through this boundary: every accepted field is selected below.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
from typing import Any

from sts_combat_rl.sim.contract import SimulatorAction


TACTICAL_FEATURE_SCHEMA_ID = "public-tactical-v2"
TACTICAL_FEATURE_SCHEMA_VERSION = 2
IDENTITY_VOCABULARY_VERSION = "public-identity-v1"
LEGACY_FEATURE_SCHEMA_ID = "legacy-unversioned"

MAX_HAND_CARDS = 10
MAX_MONSTERS = 5
MAX_POTIONS = 5

CARD_TYPES = ("ATTACK", "SKILL", "POWER", "CURSE", "STATUS")
CARD_RARITIES = ("BASIC", "COMMON", "UNCOMMON", "RARE", "SPECIAL", "CURSE")
MONSTER_INTENTS = (
    "NONE",
    "ATTACK",
    "ATTACK_BUFF",
    "ATTACK_DEBUFF",
    "ATTACK_DEFEND",
    "BUFF",
    "DEBUFF",
    "STRONG_DEBUFF",
    "DEFEND",
    "DEFEND_DEBUFF",
    "DEFEND_BUFF",
    "ESCAPE",
    "MAGIC",
    "SLEEP",
    "STUN",
    "UNKNOWN",
)
ACTION_SCOPES = ("battle", "game")
ACTION_KINDS = (
    "card",
    "end_turn",
    "potion",
    "potion_discard",
    "single_card_select",
    "multi_card_select",
    "event",
    "reward_card",
    "reward_gold",
    "reward_key",
    "reward_potion",
    "reward_relic",
    "card_remove",
    "skip",
    "boss_relic",
    "card_select",
    "map",
    "treasure_open",
    "treasure_leave",
    "rest",
    "shop_reward_card",
    "shop_reward_gold",
    "shop_reward_key",
    "shop_reward_potion",
    "shop_reward_relic",
    "shop_card_remove",
    "shop_skip",
    "game_potion_use",
    "game_potion_discard",
    "game_unknown",
    "battle_unknown",
)

# These registries intentionally cover only identities whose spelling is part of
# the first public vocabulary.  An unlisted but visible identity is retained as
# its canonical string with ``status == "unknown"``; it is never converted to
# zero or a hash bucket without being reported.
_IDENTITY_VOCABULARIES: Mapping[str, frozenset[str]] = {
    "card": frozenset(
        {
            "Strike_R",
            "Defend_R",
            "Strike",
            "Defend",
            "Bash",
            "Anger",
            "Armaments",
            "Body Slam",
            "Cleave",
            "Flex",
            "Inflame",
            "Pommel Strike",
            "Shrug It Off",
            "True Grit",
            "Uppercut",
            "Whirlwind",
        }
    ),
    "monster": frozenset(
        {
            "Cultist",
            "JawWorm",
            "LouseNormal",
            "LouseDefensive",
            "SlaverBlue",
            "SlaverRed",
            "GremlinNob",
            "Lagavulin",
            "Sentry",
        }
    ),
    "potion": frozenset(
        {
            "Potion Slot",
            "EMPTY_POTION_SLOT",
            "Fire Potion",
            "Block Potion",
            "Strength Potion",
            "Dexterity Potion",
            "Energy Potion",
        }
    ),
    "relic": frozenset(
        {
            "Burning Blood",
            "Vajra",
            "Anchor",
            "Lantern",
            "Bag of Preparation",
            "Potion Belt",
        }
    ),
    "power": frozenset(
        {
            "Strength",
            "Dexterity",
            "Artifact",
            "Focus",
            "Vulnerable",
            "Weak",
            "Weakened",
            "Frail",
            "Poison",
            "Metallicize",
            "Plated Armor",
            "Regeneration",
        }
    ),
}

_PLAYER_SCALAR_FIELDS = (
    "current_hp",
    "max_hp",
    "energy",
    "energy_per_turn",
    "block",
    "strength",
    "dexterity",
    "artifact",
    "focus",
    "vulnerable",
    "weak",
    "frail",
    "cards_played_this_turn",
    "attacks_played_this_turn",
    "skills_played_this_turn",
    "cards_discarded_this_turn",
    "times_damaged_this_combat",
)
_CARD_SCALAR_FIELDS = (
    "cost",
    "cost_for_turn",
    "damage",
    "block",
    "magic_number",
    "upgrade_count",
    "misc",
)
_CARD_BOOL_FIELDS = (
    "playable",
    "requires_target",
    "upgraded",
    "exhausts",
    "ethereal",
    "retain",
    "innate",
    "exhaust_on_use_once",
)
_MONSTER_SCALAR_FIELDS = (
    "current_hp",
    "max_hp",
    "block",
    "move_base_damage",
    "move_hits",
)
_MONSTER_BOOL_FIELDS = ("alive", "targetable", "half_dead")
_POWER_SCALAR_FIELDS = (
    "strength",
    "dexterity",
    "artifact",
    "focus",
    "vulnerable",
    "weak",
    "frail",
    "poison",
    "metallicize",
    "plated_armor",
    "regen",
)


@dataclass(frozen=True)
class TacticalFieldParity:
    """Availability classification for one contract field family.

    ``live_missing`` fields still have a defined ``None``/missing path in the
    contract.  ``simulator_only`` values are audit-only and never enter a model
    feature.  ``explicitly_unsupported`` values are rejected by design because
    they are hidden or not stable public game data.
    """

    field: str
    classification: str
    missing_value_behavior: str
    detail: str


TACTICAL_FIELD_PARITY: tuple[TacticalFieldParity, ...] = (
    TacticalFieldParity("run.ascension", "shared", "null", "Visible ascension."),
    TacticalFieldParity("run.hp_gold", "shared", "null", "Visible run resources."),
    TacticalFieldParity(
        "battle.turn_and_pile_sizes", "shared", "null", "Visible combat counters."
    ),
    TacticalFieldParity(
        "hand.cards", "shared", "empty_list", "Visible hand card instances."
    ),
    TacticalFieldParity(
        "monsters.identity_intent_status",
        "shared",
        "empty_list",
        "Visible enemy state.",
    ),
    TacticalFieldParity(
        "potions.identity", "shared", "empty_list", "Visible potion slots."
    ),
    TacticalFieldParity(
        "player.powers", "shared", "empty_list", "Visible player powers when supplied."
    ),
    TacticalFieldParity(
        "relics.identity", "shared", "empty_list", "Visible relic list."
    ),
    TacticalFieldParity(
        "card.rarity_and_instance_flags",
        "live_missing",
        "null",
        "Not guaranteed by captured CommunicationMod snapshots.",
    ),
    TacticalFieldParity(
        "player.energy_per_turn_and_turn_counters",
        "live_missing",
        "null",
        "Current live snapshot format omits these fields.",
    ),
    TacticalFieldParity(
        "monster.move_history",
        "live_missing",
        "null",
        "Current live format exposes intent, not all state-machine history.",
    ),
    TacticalFieldParity(
        "relic.visible_counters",
        "live_missing",
        "null",
        "Counters require a live-format audit before deployment.",
    ),
    TacticalFieldParity(
        "action.identity_kind_target_parameters",
        "live_missing",
        "unsupported_state",
        "Captured live snapshots do not enumerate the complete legal action list.",
    ),
    TacticalFieldParity(
        "action.live_command_payload",
        "explicitly_unsupported",
        "excluded",
        "T013 owns CommunicationMod command mapping; v2 has no live payload guess.",
    ),
    TacticalFieldParity(
        "action.native_bits",
        "simulator_only",
        "excluded",
        "Native simulator payload; never a model feature.",
    ),
    TacticalFieldParity(
        "draw_pile_order", "explicitly_unsupported", "excluded", "Hidden draw order."
    ),
    TacticalFieldParity(
        "hidden_rng_and_future_moves",
        "explicitly_unsupported",
        "excluded",
        "Forbidden normal-information data.",
    ),
)

COMMUNICATIONMOD_POWER_ALIASES: Mapping[str, tuple[str, ...]] = {
    "strength": ("Strength",),
    "dexterity": ("Dexterity",),
    "artifact": ("Artifact",),
    "focus": ("Focus",),
    "vulnerable": ("Vulnerable",),
    "weak": ("Weak", "Weakened"),
    "frail": ("Frail",),
}


def tactical_field_parity_rows() -> list[dict[str, str]]:
    """Return JSON-safe simulator/live availability classifications."""

    return [
        {
            "field": item.field,
            "classification": item.classification,
            "missing_value_behavior": item.missing_value_behavior,
            "detail": item.detail,
        }
        for item in TACTICAL_FIELD_PARITY
    ]


def build_public_tactical_state(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Build the versioned public tactical state without hidden simulator data."""

    player = _mapping(raw.get("battle_player"))
    hand = _sequence(raw.get("battle_hand"))
    monsters = _sequence(raw.get("battle_monsters"))
    potions = _sequence(raw.get("battle_potions", raw.get("potions")))
    relics = _sequence(raw.get("battle_relics", raw.get("relics")))
    pile_summaries = {
        "hand": _nullable_number(raw.get("battle_hand_size"), fallback=len(hand)),
        "draw": _nullable_number(raw.get("battle_draw_pile_size")),
        "discard": _nullable_number(raw.get("battle_discard_pile_size")),
        "exhaust": _nullable_number(raw.get("battle_exhaust_pile_size")),
    }
    state = {
        "schema_id": TACTICAL_FEATURE_SCHEMA_ID,
        "schema_version": TACTICAL_FEATURE_SCHEMA_VERSION,
        "identity_vocabulary_version": IDENTITY_VOCABULARY_VERSION,
        "scalars": {
            "battle_active": _nullable_bool(raw.get("battle_active")),
            "act": _nullable_number(raw.get("act")),
            "floor_num": _nullable_number(raw.get("floor_num", raw.get("floor"))),
            "ascension": _nullable_number(
                raw.get("ascension", raw.get("ascension_level"))
            ),
            "current_hp": _nullable_number(raw.get("cur_hp")),
            "max_hp": _nullable_number(raw.get("max_hp")),
            "gold": _nullable_number(raw.get("gold")),
            "turn": _nullable_number(raw.get("battle_turn")),
            "monster_count": _nullable_number(
                raw.get("battle_monster_count"), fallback=len(monsters)
            ),
            "monsters_alive": _nullable_number(raw.get("battle_monsters_alive")),
            "potion_count": _nullable_number(raw.get("battle_potion_count")),
            "potion_capacity": _nullable_number(
                raw.get("battle_potion_capacity"), fallback=len(potions)
            ),
        },
        "player": {
            "scalars": {
                field: _nullable_number(player.get(field))
                for field in _PLAYER_SCALAR_FIELDS
            },
            "powers": _public_powers(player),
            "powers_available": _powers_available(player),
        },
        "piles": pile_summaries,
        "availability": {
            "hand": "battle_hand" in raw,
            "monsters": "battle_monsters" in raw,
            "potions": "battle_potions" in raw or "potions" in raw,
            "relics": "battle_relics" in raw or "relics" in raw,
        },
        # Hand, discard, and exhaust membership are public.  Draw order is
        # intentionally never read, even if a simulator debug snapshot happens
        # to contain it.
        "cards": _public_visible_cards(raw),
        "monsters": [
            _public_monster(_mapping(monster), index)
            for index, monster in enumerate(monsters)
        ],
        "potions": [
            _public_potion(_mapping(potion), index)
            for index, potion in enumerate(potions)
        ],
        "relics": [_public_relic(relic, index) for index, relic in enumerate(relics)],
    }
    state["missing_fields"] = public_tactical_missing_fields(state)
    state["unknown_identity_counts"] = public_tactical_unknown_identity_counts(state)
    return state


def build_public_tactical_actions(
    actions: Sequence[SimulatorAction],
    raw_snapshot: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build structured public action inputs aligned to the legal-action list."""

    hand = _sequence(raw_snapshot.get("battle_hand"))
    monsters = _sequence(raw_snapshot.get("battle_monsters"))
    public_actions = [_public_action(action, hand, monsters) for action in actions]
    _attach_public_action_identities(public_actions)
    return public_actions


def encode_lightspeed_battle_snapshot(raw: Mapping[str, Any]) -> list[float]:
    """Return the compatibility numeric view of the public v2 state contract."""

    state = build_public_tactical_state(raw)
    scalars = _mapping(state["scalars"])
    player = _mapping(_mapping(state["player"]).get("scalars"))
    features: list[float] = [
        _number(scalars.get("battle_active")),
        _number(scalars.get("act")),
        _number(scalars.get("floor_num")),
        _number(scalars.get("current_hp")),
        _number(scalars.get("max_hp")),
        _number(scalars.get("gold")),
        _number(scalars.get("ascension")),
    ]
    features.extend(_number(player.get(field)) for field in _PLAYER_SCALAR_FIELDS)
    features.extend(
        [
            _number(scalars.get("turn")),
            _number(_mapping(state["piles"]).get("hand")),
            _number(_mapping(state["piles"]).get("draw")),
            _number(_mapping(state["piles"]).get("discard")),
            _number(_mapping(state["piles"]).get("exhaust")),
            _number(scalars.get("monster_count")),
            _number(scalars.get("monsters_alive")),
            _number(scalars.get("potion_count")),
            _number(scalars.get("potion_capacity")),
            float(len(_sequence(_mapping(state["player"]).get("powers")))),
            float(len(_sequence(state.get("relics")))),
        ]
    )
    cards = [
        card
        for card in _sequence(state.get("cards"))
        if _mapping(card).get("pile") == "hand"
    ]
    for index in range(MAX_HAND_CARDS):
        features.extend(_encode_public_card(_mapping_at(cards, index)))
    monsters = _sequence(state.get("monsters"))
    for index in range(MAX_MONSTERS):
        features.extend(_encode_public_monster(_mapping_at(monsters, index)))
    potions = _sequence(state.get("potions"))
    for index in range(MAX_POTIONS):
        features.extend(_encode_public_potion(_mapping_at(potions, index)))
    return features


def encode_communicationmod_battle_snapshot(raw: Mapping[str, Any]) -> list[float]:
    """Encode a CommunicationMod snapshot through the same public contract."""

    return encode_lightspeed_battle_snapshot(
        normalize_communicationmod_battle_snapshot(raw)
    )


def normalize_communicationmod_battle_snapshot(
    raw: Mapping[str, Any],
) -> dict[str, Any]:
    """Map documented live fields into the simulator-shaped public contract."""

    game = _mapping(raw.get("game_state")) or _mapping(raw.get("gameState")) or raw
    combat = _mapping(game.get("combat_state")) or _mapping(game.get("combatState"))
    player = _mapping(combat.get("player"))
    hand = _sequence(combat.get("hand"))
    monsters = _sequence(combat.get("monsters"))
    potions = _sequence(game.get("potions"))
    return {
        "battle_active": bool(combat),
        "act": game.get("act"),
        "ascension": game.get("ascension_level", game.get("ascension")),
        "floor_num": game.get("floor"),
        "cur_hp": game.get("current_hp"),
        "max_hp": game.get("max_hp"),
        "gold": game.get("gold"),
        "battle_player": _normalize_communicationmod_player(player, combat),
        "battle_turn": combat.get("turn"),
        "battle_hand_size": len(hand),
        "battle_draw_pile_size": len(_sequence(combat.get("draw_pile"))),
        "battle_discard_pile_size": len(_sequence(combat.get("discard_pile"))),
        "battle_exhaust_pile_size": len(_sequence(combat.get("exhaust_pile"))),
        "battle_monster_count": len(monsters),
        "battle_monsters_alive": sum(
            _communicationmod_monster_alive(_mapping(item)) for item in monsters
        ),
        "battle_potion_count": sum(
            _communicationmod_potion_present(_mapping(item)) for item in potions
        ),
        "battle_potion_capacity": len(potions),
        "battle_hand": [
            _normalize_communicationmod_card(_mapping(item)) for item in hand
        ],
        "battle_discard_pile": [
            _normalize_communicationmod_card(_mapping(item))
            for item in _sequence(combat.get("discard_pile"))
        ],
        "battle_exhaust_pile": [
            _normalize_communicationmod_card(_mapping(item))
            for item in _sequence(combat.get("exhaust_pile"))
        ],
        "battle_monsters": [
            _normalize_communicationmod_monster(_mapping(item)) for item in monsters
        ],
        "battle_potions": [
            _normalize_communicationmod_potion(_mapping(item)) for item in potions
        ],
        "relics": [
            _normalize_communicationmod_relic(item)
            for item in _sequence(game.get("relics"))
        ],
    }


def lightspeed_battle_feature_size() -> int:
    """Return the stable v2 compatibility-vector length."""

    return len(encode_lightspeed_battle_snapshot({}))


def communicationmod_battle_feature_size() -> int:
    """Return the stable v2 compatibility-vector length."""

    return len(encode_communicationmod_battle_snapshot({}))


def encode_simulator_action(
    action: SimulatorAction,
    snapshot_raw: Mapping[str, Any] | None = None,
) -> list[float]:
    """Return the numeric compatibility view of one structured public action."""

    raw_snapshot = _mapping(snapshot_raw)
    structure = build_public_tactical_actions([action], raw_snapshot)[0]
    parameters = _mapping(structure["parameters"])
    selected_card = _mapping(structure["selected_card"])
    selected_target = _mapping(structure["selected_target"])
    return (
        _one_hot(str(structure["scope"]), ACTION_SCOPES)
        + _one_hot(str(structure["kind"]), ACTION_KINDS)
        + [
            _identity_code(_mapping(structure["identity"])),
            _identity_status_code(_mapping(structure["identity"])),
        ]
        + [
            _number(parameters.get("card_index")),
            _number(parameters.get("target_index")),
        ]
        + _encode_public_card(selected_card)
        + _encode_public_monster(selected_target)
        + [_number(parameters.get(name)) for name in ("idx1", "idx2", "idx3")]
    )


def encode_simulator_actions(
    actions: Sequence[SimulatorAction],
    snapshot_raw: Mapping[str, Any] | None = None,
) -> list[list[float]]:
    """Encode an aligned legal-action list without creating an action mask."""

    raw_snapshot = _mapping(snapshot_raw)
    structures = build_public_tactical_actions(actions, raw_snapshot)
    return [_encode_public_action(structure) for structure in structures]


def simulator_action_feature_size() -> int:
    """Return the stable v2 compatibility action-vector length."""

    return len(
        encode_simulator_action(SimulatorAction(action_id="empty", label="", raw={}))
    )


def public_tactical_missing_fields(state: Mapping[str, Any]) -> list[str]:
    """List required contract fields represented through an explicit missing path."""

    missing: list[str] = []
    scalars = _mapping(state.get("scalars"))
    for name in (
        "battle_active",
        "act",
        "floor_num",
        "ascension",
        "current_hp",
        "max_hp",
        "gold",
        "turn",
    ):
        if name not in scalars or scalars.get(name) is None:
            missing.append(f"scalars.{name}")
    player = _mapping(state.get("player"))
    player_scalars = _mapping(player.get("scalars"))
    for name in _PLAYER_SCALAR_FIELDS:
        if name not in player_scalars or player_scalars.get(name) is None:
            missing.append(f"player.scalars.{name}")
    if not player.get("powers_available"):
        missing.append("player.powers")
    piles = _mapping(state.get("piles"))
    for name in ("hand", "draw", "discard", "exhaust"):
        if name not in piles or piles.get(name) is None:
            missing.append(f"piles.{name}")
    availability = _mapping(state.get("availability"))
    for name in ("hand", "monsters", "potions", "relics"):
        if not availability.get(name):
            missing.append(f"availability.{name}")
    for card in _sequence(state.get("cards")):
        raw_card = _mapping(card)
        if _mapping(raw_card.get("identity")).get("status") == "missing":
            missing.append("cards.identity")
        if not raw_card.get("type"):
            missing.append("cards.type")
        if not raw_card.get("rarity"):
            missing.append("cards.rarity")
        for name, value in _mapping(raw_card.get("scalars")).items():
            if value is None:
                missing.append(f"cards.scalars.{name}")
        for name, value in _mapping(raw_card.get("flags")).items():
            if value is None:
                missing.append(f"cards.flags.{name}")
    for monster in _sequence(state.get("monsters")):
        raw_monster = _mapping(monster)
        if _mapping(raw_monster.get("identity")).get("status") == "missing":
            missing.append("monsters.identity")
        if not raw_monster.get("intent"):
            missing.append("monsters.intent")
        for name, value in _mapping(raw_monster.get("state_machine")).items():
            if value is None:
                missing.append(f"monsters.state_machine.{name}")
        for name, value in _mapping(raw_monster.get("scalars")).items():
            if value is None:
                missing.append(f"monsters.scalars.{name}")
        if not raw_monster.get("powers_available"):
            missing.append("monsters.powers")
    for potion in _sequence(state.get("potions")):
        raw_potion = _mapping(potion)
        if _mapping(raw_potion.get("identity")).get("status") == "missing":
            missing.append("potions.identity")
    for relic in _sequence(state.get("relics")):
        raw_relic = _mapping(relic)
        if _mapping(raw_relic.get("identity")).get("status") == "missing":
            missing.append("relics.identity")
        if raw_relic.get("counter") is None:
            missing.append("relics.counter")
    return sorted(set(missing))


def public_tactical_unknown_identity_counts(state: Mapping[str, Any]) -> dict[str, int]:
    """Count identities that are absent or outside the versioned vocabulary."""

    counts: dict[str, int] = {}
    for category, items in (
        ("card", _sequence(state.get("cards"))),
        ("monster", _sequence(state.get("monsters"))),
        ("potion", _sequence(state.get("potions"))),
        ("relic", _sequence(state.get("relics"))),
        ("power", _sequence(_mapping(state.get("player")).get("powers"))),
    ):
        counts[category] = sum(
            1
            for item in items
            if _mapping(item).get("identity", {}).get("status") != "known"
        )
    return counts


def tactical_state_problems(state: Mapping[str, Any]) -> list[str]:
    """Validate schema identity, explicit missing values, and public-only shape."""

    problems: list[str] = []
    if state.get("schema_id") != TACTICAL_FEATURE_SCHEMA_ID:
        problems.append("tactical state schema id is unsupported")
    if state.get("schema_version") != TACTICAL_FEATURE_SCHEMA_VERSION:
        problems.append("tactical state schema version is unsupported")
    if state.get("identity_vocabulary_version") != IDENTITY_VOCABULARY_VERSION:
        problems.append("tactical state identity vocabulary version is unsupported")
    required = (
        "scalars",
        "player",
        "piles",
        "availability",
        "cards",
        "monsters",
        "potions",
        "relics",
        "missing_fields",
        "unknown_identity_counts",
    )
    for name in required:
        if name not in state:
            problems.append(f"tactical state silently dropped required field {name}")
    if "missing_fields" in state and state.get(
        "missing_fields"
    ) != public_tactical_missing_fields(state):
        problems.append("tactical state missing_fields does not match explicit values")
    return problems


def tactical_action_problems(actions: Sequence[Mapping[str, Any]]) -> list[str]:
    """Validate aligned structured action inputs before persistence or packing."""

    problems: list[str] = []
    for index, action in enumerate(actions):
        if action.get("schema_id") != TACTICAL_FEATURE_SCHEMA_ID:
            problems.append(f"action {index}: tactical action schema id is unsupported")
        if action.get("schema_version") != TACTICAL_FEATURE_SCHEMA_VERSION:
            problems.append(
                f"action {index}: tactical action schema version is unsupported"
            )
        for name in (
            "identity",
            "scope",
            "kind",
            "parameters",
            "selected_card",
            "selected_target",
            "missing_fields",
        ):
            if name not in action:
                problems.append(
                    f"action {index}: silently dropped required field {name}"
                )
        identity = _mapping(action.get("identity"))
        if "action_id" in identity:
            problems.append(
                f"action {index}: simulator-native replay action_id reached "
                "the public tactical contract"
            )
        parameters = _mapping(action.get("parameters"))
        if "bits" in parameters:
            problems.append(
                f"action {index}: simulator-native action bits reached the public "
                "tactical contract"
            )
    return problems


def _public_card(raw: Mapping[str, Any], pile: str, index: int) -> dict[str, Any]:
    return {
        "identity": _identity(raw, "card", "card_id", "id", "name"),
        "instance_index": index,
        "pile": pile,
        "type": _normalized_option(raw.get("type")),
        "rarity": _normalized_option(raw.get("rarity")),
        "scalars": {
            name: _nullable_number(raw.get(name)) for name in _CARD_SCALAR_FIELDS
        },
        "flags": {name: _nullable_bool(raw.get(name)) for name in _CARD_BOOL_FIELDS},
    }


def _public_visible_cards(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    for source_key, pile in (
        ("battle_hand", "hand"),
        ("battle_discard_pile", "discard"),
        ("battle_exhaust_pile", "exhaust"),
    ):
        for index, card in enumerate(_sequence(raw.get(source_key))):
            cards.append(_public_card(_mapping(card), pile, index))
    return cards


def _public_monster(raw: Mapping[str, Any], index: int) -> dict[str, Any]:
    # The authoritative simulator projects its current MMID label into
    # ``intent``. The model preserves that public label; it does not infer an
    # intent class from hidden monster state or Python mechanics.
    intent = _normalized_option(raw.get("intent"))
    return {
        "identity": _identity(raw, "monster", "id_label", "monster_id", "id", "name"),
        "instance_index": index,
        "intent": intent,
        "intent_identity": _categorical_identity(intent, MONSTER_INTENTS),
        "state_machine": {
            "current_move": intent or None,
            "move_id": _nullable_number(raw.get("move_id")),
            "last_move_id": _nullable_number(raw.get("last_move_id")),
            "second_last_move_id": _nullable_number(raw.get("second_last_move_id")),
        },
        "scalars": {
            name: _nullable_number(raw.get(name)) for name in _MONSTER_SCALAR_FIELDS
        },
        "flags": {
            **{name: _nullable_bool(raw.get(name)) for name in _MONSTER_BOOL_FIELDS},
            "attacking": _nullable_bool(raw.get("attacking"))
            if "attacking" in raw
            else _intent_has_attack(intent),
        },
        "powers": _public_powers(raw),
        "powers_available": _powers_available(raw),
    }


def _public_potion(raw: Mapping[str, Any], index: int) -> dict[str, Any]:
    return {
        "identity": _identity(raw, "potion", "potion_id", "id", "name", "numeric_id"),
        "slot_index": index,
        "is_empty_slot": not _communicationmod_potion_present(raw),
        "can_use": _nullable_bool(raw.get("can_use", raw.get("is_usable"))),
        "requires_target": _nullable_bool(
            raw.get("requires_target", raw.get("has_target"))
        ),
    }


def _public_relic(raw_item: Any, index: int) -> dict[str, Any]:
    raw = _mapping(raw_item)
    if not raw and isinstance(raw_item, str):
        raw = {"id": raw_item}
    return {
        "identity": _identity(raw, "relic", "relic_id", "id", "name"),
        "slot_index": index,
        "counter": _first_nullable_number(
            raw, "counter", "amount", "charges", "counter_value"
        ),
    }


def _public_powers(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    powers = _sequence(raw.get("powers"))
    result = [
        _public_power(_mapping(power), index) for index, power in enumerate(powers)
    ]
    if result:
        return result
    # The current simulator exposes several public powers as scalar fields.
    for name in _POWER_SCALAR_FIELDS:
        value = _nullable_number(raw.get(name))
        if value is not None:
            result.append(_public_power({"id": name, "amount": value}, len(result)))
    return result


def _public_power(raw: Mapping[str, Any], index: int) -> dict[str, Any]:
    return {
        "identity": _identity(raw, "power", "id", "power_id", "name"),
        "instance_index": index,
        "amount": _first_nullable_number(raw, "amount", "counter"),
        "just_applied": _nullable_bool(raw.get("just_applied")),
    }


def _public_action(
    action: SimulatorAction,
    hand: Sequence[Any],
    monsters: Sequence[Any],
) -> dict[str, Any]:
    card_index = _first_int(action.raw, "card_index", "hand_index", "idx1")
    target_index = _first_int(action.raw, "target_index", "monster_index", "idx2")
    selected_card = _mapping(action.raw.get("card")) or _mapping_at_flexible(
        hand, card_index
    )
    selected_target = _mapping(action.raw.get("target")) or _mapping(
        action.raw.get("monster")
    )
    if not selected_target and _action_requires_target(action, selected_card):
        selected_target = _mapping_at_flexible(monsters, target_index)
    parameters = {
        "idx1": _nullable_number(action.raw.get("idx1")),
        "idx2": _nullable_number(action.raw.get("idx2")),
        "idx3": _nullable_number(action.raw.get("idx3")),
        "card_index": card_index,
        "target_index": target_index,
        "requires_target": _action_requires_target(action, selected_card),
    }
    result = {
        "schema_id": TACTICAL_FEATURE_SCHEMA_ID,
        "schema_version": TACTICAL_FEATURE_SCHEMA_VERSION,
        "scope": str(action.raw.get("scope", "")),
        "kind": str(action.kind),
        "label": str(action.label),
        "parameters": parameters,
        "selected_card": _public_card(
            selected_card, "hand", card_index if card_index is not None else -1
        )
        if selected_card
        else {},
        "selected_target": _public_monster(
            selected_target, target_index if target_index is not None else -1
        )
        if selected_target
        else {},
    }
    result["missing_fields"] = ["scope"] if not result["scope"] else []
    return result


def _attach_public_action_identities(actions: list[dict[str, Any]]) -> None:
    """Attach action identities without importing simulator-native replay ids.

    ``SimulatorAction.action_id`` is retained separately by decision records for
    portable replay.  It is intentionally absent here: a normal-public model
    may use only legal-action facts that a live runtime can also construct.
    """

    occurrences: dict[str, int] = {}
    for action in actions:
        payload = _public_action_identity_payload(action)
        key = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        occurrence = occurrences.get(key, 0)
        occurrences[key] = occurrence + 1
        stable_id = json.dumps(
            {"occurrence": occurrence, "public_action": payload},
            sort_keys=True,
            separators=(",", ":"),
        )
        action["identity"] = {
            "scope": payload["scope"],
            "kind": payload["kind"],
            "parameters": payload["parameters"],
            "selected_card_identity": payload["selected_card_identity"],
            "selected_target_identity": payload["selected_target_identity"],
            "occurrence": occurrence,
            "stable_id": stable_id,
            "vocabulary_version": IDENTITY_VOCABULARY_VERSION,
            "status": "known",
        }


def _public_action_identity_payload(action: Mapping[str, Any]) -> dict[str, Any]:
    """Return the complete public basis for one model action identity."""

    return {
        "scope": str(action.get("scope", "")),
        "kind": str(action.get("kind", "")),
        "parameters": dict(_mapping(action.get("parameters"))),
        "selected_card_identity": dict(
            _mapping(_mapping(action.get("selected_card")).get("identity"))
        ),
        "selected_target_identity": dict(
            _mapping(_mapping(action.get("selected_target")).get("identity"))
        ),
    }


def _encode_public_card(card: Mapping[str, Any]) -> list[float]:
    if not card:
        return [0.0] * (
            1
            + 2
            + 1
            + len(CARD_TYPES)
            + len(CARD_RARITIES)
            + len(_CARD_SCALAR_FIELDS)
            + len(_CARD_BOOL_FIELDS)
        )
    identity = _mapping(card.get("identity"))
    scalars = _mapping(card.get("scalars"))
    flags = _mapping(card.get("flags"))
    return [
        1.0,
        _identity_code(identity),
        _identity_status_code(identity),
        1.0 if card.get("pile") == "hand" else 0.0,
        *_one_hot(str(card.get("type", "")), CARD_TYPES),
        *_one_hot(str(card.get("rarity", "")), CARD_RARITIES),
        *(_number(scalars.get(name)) for name in _CARD_SCALAR_FIELDS),
        *(_number(flags.get(name)) for name in _CARD_BOOL_FIELDS),
    ]


def _encode_public_monster(monster: Mapping[str, Any]) -> list[float]:
    if not monster:
        return [0.0] * (
            1
            + 2
            + len(MONSTER_INTENTS)
            + 2
            + 3
            + len(_MONSTER_SCALAR_FIELDS)
            + len(_MONSTER_BOOL_FIELDS)
            + 1
        )
    identity = _mapping(monster.get("identity"))
    state_machine = _mapping(monster.get("state_machine"))
    scalars = _mapping(monster.get("scalars"))
    flags = _mapping(monster.get("flags"))
    return [
        1.0,
        _identity_code(identity),
        _identity_status_code(identity),
        *_one_hot(str(monster.get("intent", "")), MONSTER_INTENTS),
        _identity_code(_mapping(monster.get("intent_identity"))),
        _identity_status_code(_mapping(monster.get("intent_identity"))),
        *(
            _number(state_machine.get(name))
            for name in ("move_id", "last_move_id", "second_last_move_id")
        ),
        *(_number(scalars.get(name)) for name in _MONSTER_SCALAR_FIELDS),
        *(_number(flags.get(name)) for name in _MONSTER_BOOL_FIELDS),
        _number(flags.get("attacking")),
    ]


def _encode_public_potion(potion: Mapping[str, Any]) -> list[float]:
    if not potion:
        return [0.0] * 5
    identity = _mapping(potion.get("identity"))
    return [
        1.0,
        _identity_code(identity),
        _identity_status_code(identity),
        _bool(potion.get("is_empty_slot")),
        _number(potion.get("requires_target")),
    ]


def _encode_public_action(action: Mapping[str, Any]) -> list[float]:
    parameters = _mapping(action.get("parameters"))
    return (
        _one_hot(str(action.get("scope", "")), ACTION_SCOPES)
        + _one_hot(str(action.get("kind", "")), ACTION_KINDS)
        + [
            _identity_code(_mapping(action.get("identity"))),
            _identity_status_code(_mapping(action.get("identity"))),
        ]
        + [
            _number(parameters.get("card_index")),
            _number(parameters.get("target_index")),
        ]
        + _encode_public_card(_mapping(action.get("selected_card")))
        + _encode_public_monster(_mapping(action.get("selected_target")))
        + [_number(parameters.get(name)) for name in ("idx1", "idx2", "idx3")]
    )


def _normalize_communicationmod_player(
    player: Mapping[str, Any], combat: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "current_hp": player.get("current_hp"),
        "max_hp": player.get("max_hp"),
        "energy": player.get("energy"),
        "block": player.get("block"),
        "powers": list(_sequence(player.get("powers"))),
        "strength": _communicationmod_power_amount(
            player, COMMUNICATIONMOD_POWER_ALIASES["strength"]
        ),
        "dexterity": _communicationmod_power_amount(
            player, COMMUNICATIONMOD_POWER_ALIASES["dexterity"]
        ),
        "artifact": _communicationmod_power_amount(
            player, COMMUNICATIONMOD_POWER_ALIASES["artifact"]
        ),
        "focus": _communicationmod_power_amount(
            player, COMMUNICATIONMOD_POWER_ALIASES["focus"]
        ),
        "vulnerable": _communicationmod_power_amount(
            player, COMMUNICATIONMOD_POWER_ALIASES["vulnerable"]
        ),
        "weak": _communicationmod_power_amount(
            player, COMMUNICATIONMOD_POWER_ALIASES["weak"]
        ),
        "frail": _communicationmod_power_amount(
            player, COMMUNICATIONMOD_POWER_ALIASES["frail"]
        ),
        "cards_discarded_this_turn": combat.get("cards_discarded_this_turn"),
        "times_damaged_this_combat": combat.get("times_damaged"),
    }


def _normalize_communicationmod_card(card: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": card.get("id", card.get("card_id")),
        "name": card.get("name"),
        "type": card.get("type"),
        "rarity": card.get("rarity"),
        "cost": card.get("cost"),
        "cost_for_turn": card.get("cost_for_turn", card.get("cost")),
        "damage": card.get("damage"),
        "block": card.get("block"),
        "magic_number": card.get("magic_number"),
        "misc": card.get("misc"),
        "playable": card.get("is_playable", card.get("playable")),
        "requires_target": card.get("has_target", card.get("requires_target")),
        "upgraded": _number(card.get("upgrades")) > 0.0 or bool(card.get("upgraded")),
        "upgrade_count": card.get("upgrades", card.get("upgrade_count")),
        "exhausts": card.get("exhausts"),
        "ethereal": card.get("ethereal"),
        "retain": card.get("retain"),
        "innate": card.get("innate"),
    }


def _normalize_communicationmod_monster(monster: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": monster.get("id", monster.get("monster_id")),
        "name": monster.get("name"),
        "intent": monster.get("intent"),
        "move_id": monster.get("move_id"),
        "last_move_id": monster.get("last_move_id"),
        "second_last_move_id": monster.get("second_last_move_id"),
        "current_hp": monster.get("current_hp"),
        "max_hp": monster.get("max_hp"),
        "block": monster.get("block"),
        "alive": _communicationmod_monster_alive(monster),
        "targetable": _communicationmod_monster_alive(monster),
        "attacking": _communicationmod_monster_attacking(monster),
        "move_base_damage": monster.get("move_base_damage"),
        "move_hits": monster.get("move_hits"),
        "powers": list(_sequence(monster.get("powers"))),
        "half_dead": monster.get("half_dead"),
    }


def _normalize_communicationmod_potion(potion: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": potion.get("id", potion.get("numeric_id")),
        "numeric_id": potion.get("numeric_id"),
        "name": potion.get("name"),
        "can_use": potion.get("can_use", potion.get("is_usable")),
        "requires_target": potion.get("requires_target", potion.get("has_target")),
    }


def _normalize_communicationmod_relic(relic: Any) -> dict[str, Any]:
    if isinstance(relic, str):
        return {"id": relic}
    raw = _mapping(relic)
    return {
        "id": raw.get("id", raw.get("relic_id")),
        "name": raw.get("name"),
        "counter": raw.get("counter", raw.get("amount")),
    }


def _communicationmod_monster_alive(monster: Mapping[str, Any]) -> bool:
    if monster.get("is_gone") is True:
        return False
    return _number(monster.get("current_hp")) > 0.0


def _communicationmod_monster_attacking(monster: Mapping[str, Any]) -> bool:
    return _intent_has_attack(monster.get("intent"))


def _communicationmod_potion_present(potion: Mapping[str, Any]) -> bool:
    potion_id = _identity_label(potion.get("id", potion.get("name", "")))
    return potion_id not in {"", "Potion Slot"}


def _communicationmod_power_amount(
    actor: Mapping[str, Any], power_ids: str | Sequence[str]
) -> int | None:
    if "powers" not in actor:
        return None
    candidates = {power_ids} if isinstance(power_ids, str) else set(power_ids)
    for power in _sequence(actor.get("powers")):
        raw = _mapping(power)
        if str(raw.get("id")) in candidates or str(raw.get("name")) in candidates:
            value = raw.get("amount")
            return (
                int(value)
                if isinstance(value, (int, float)) and not isinstance(value, bool)
                else 1
            )
    return 0


def _identity(data: Mapping[str, Any], category: str, *keys: str) -> dict[str, str]:
    values: list[str] = []
    for key in keys:
        value = _identity_label(data.get(key))
        if value:
            values.append(value)
    value = next((item for item in values if not _numeric_identity(item)), "")
    if not value and values:
        value = values[0]
    if not value:
        return {
            "value": "__MISSING__",
            "status": "missing",
            "vocabulary_version": IDENTITY_VOCABULARY_VERSION,
        }
    known_values = _IDENTITY_VOCABULARIES[category]
    status = (
        "known"
        if any(value.casefold() == item.casefold() for item in known_values)
        else "unknown"
    )
    return {
        "value": value,
        "status": status,
        "vocabulary_version": IDENTITY_VOCABULARY_VERSION,
    }


def _identity_code(identity: Mapping[str, Any]) -> float:
    value = ""
    for key in ("value", "stable_id", "action_id"):
        value = _identity_label(identity.get(key))
        if value:
            break
    if not value:
        return 0.0
    number = 2166136261
    for byte in value.encode("utf-8"):
        number ^= byte
        number = (number * 16777619) & 0xFFFFFFFF
    return float(number)


def _categorical_identity(value: str, options: Sequence[str]) -> dict[str, str]:
    """Represent an open public categorical label without collapsing OOV text."""

    return {
        "value": value or "__MISSING__",
        "status": "known" if value in options else "unknown",
        "vocabulary_version": IDENTITY_VOCABULARY_VERSION,
    }


def _identity_status_code(identity: Mapping[str, Any]) -> float:
    return {"missing": 0.0, "known": 1.0, "unknown": 2.0}.get(
        str(identity.get("status")), 0.0
    )


def _normalized_option(value: Any) -> str:
    return _identity_label(value).upper().replace(" ", "_").replace("-", "_")


def _one_hot(value: str, options: Sequence[str]) -> list[float]:
    return [1.0 if value == option else 0.0 for option in options]


def _intent_has_attack(intent: Any) -> bool:
    return "ATTACK" in _normalized_option(intent)


def _action_requires_target(
    action: SimulatorAction, selected_card: Mapping[str, Any]
) -> bool:
    if "target_index" in action.raw or "monster_index" in action.raw:
        return True
    if str(action.kind) in {"potion", "game_potion_use"}:
        return bool(action.raw.get("requires_target"))
    return bool(selected_card.get("requires_target", selected_card.get("has_target")))


def _first_int(data: Mapping[str, Any], *keys: str) -> int | None:
    value = _first_nullable_number(data, *keys)
    return int(value) if value is not None else None


def _first_nullable_number(data: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = _nullable_number(data.get(key))
        if value is not None:
            return value
    return None


def _nullable_number(value: Any, *, fallback: Any = None) -> float | None:
    candidate = value if value is not None else fallback
    if isinstance(candidate, bool):
        return 1.0 if candidate else 0.0
    if isinstance(candidate, (int, float)):
        return float(candidate)
    return None


def _nullable_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _number(value: Any) -> float:
    parsed = _nullable_number(value)
    return parsed if parsed is not None else 0.0


def _bool(value: Any) -> float:
    return 1.0 if value else 0.0


def _identity_label(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _numeric_identity(value: str) -> bool:
    return value.lstrip("+-").isdigit()


def _powers_available(raw: Mapping[str, Any]) -> bool:
    return "powers" in raw or any(name in raw for name in _POWER_SCALAR_FIELDS)


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    return (
        value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes))
        else ()
    )


def _mapping_at(values: Sequence[Any], index: int) -> Mapping[str, Any]:
    return _mapping(values[index]) if 0 <= index < len(values) else {}


def _mapping_at_flexible(values: Sequence[Any], index: int | None) -> Mapping[str, Any]:
    if index is None:
        return {}
    direct = _mapping_at(values, index)
    return direct or _mapping_at(values, index - 1)
