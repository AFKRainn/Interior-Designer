"""
Completeness profiles — the code gate that replaced the council (plan 10.1).

A model told to "be thorough" is being asked for a disposition. A model that
cannot mark a brief ready until every field a maker needs is either answered
or explicitly defaulted is being held to a contract. Only the second one is
checkable, so only the second one is here.

Fields are what a MAKER needs, not what a chatbot finds interesting. Each is
keyed, because the gate matches keys, not prose.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Field:
    key: str
    prompt: str
    """What the field means, shown to the model so it asks a real question."""


@dataclass(frozen=True)
class Profile:
    name: str
    label: str
    fields: tuple[Field, ...] = field(default_factory=tuple)

    def keys(self) -> list[str]:
        return [item.key for item in self.fields]


# Every piece needs an envelope and a way of being made.
COMMON = (
    Field("envelope.width", "overall width of the run or piece, cm"),
    Field("envelope.height", "overall height, cm, floor to top"),
    Field("envelope.depth", "overall depth, cm"),
    Field("layout", "straight, L, U, galley, or a single free-standing piece"),
    Field("plinth", "plinth or legs: type and height in cm, or none"),
    Field("top", "what happens at the top: cornice, open, scribe to ceiling"),
    Field("sides", "exposed ends, returns, or scribes against a wall"),
    Field("fronts", "what the fronts are, bay by bay, left to right"),
    Field("hardware", "handle style and placement, or handleless"),
    Field("materials.carcass", "carcass material"),
    Field("materials.doors", "door and drawer front material"),
    Field("materials.finish", "finish and colour"),
)

KITCHEN = Profile(
    "kitchen",
    "Kitchen run",
    COMMON
    + (
        Field("appliances", "appliances to house, with sizes and clearances"),
        Field("worktop", "worktop material and thickness"),
        Field("sink", "sink position and type"),
        Field("splashback", "splashback material and height"),
        Field("services", "sockets, extraction, plumbing that constrain the layout"),
    ),
)

WARDROBE = Profile(
    "wardrobe",
    "Wardrobe or closet",
    COMMON
    + (
        Field("door_action", "hinged, sliding, or open"),
        Field("internals", "hanging, shelving and drawer split per bay"),
        Field("hanging_heights", "long-hang and short-hang heights, cm"),
    ),
)

STORAGE = Profile(
    "storage",
    "Shelving or storage unit",
    COMMON
    + (
        Field("shelves", "shelf count and spacing per bay, fixed or adjustable"),
        Field("back_panel", "backed, open, or scribed to the wall"),
    ),
)

VANITY = Profile(
    "vanity",
    "Bathroom vanity",
    COMMON
    + (
        Field("basin", "basin type, size and position"),
        Field("plumbing", "waste and supply positions that constrain the carcass"),
        Field("worktop", "worktop material and thickness"),
    ),
)

OTHER = Profile("other", "Freestanding piece", COMMON)

PROFILES: dict[str, Profile] = {
    profile.name: profile for profile in (KITCHEN, WARDROBE, STORAGE, VANITY, OTHER)
}


def profile_for(typology: str | None) -> Profile:
    return PROFILES.get((typology or "").strip().lower(), OTHER)


def missing_fields(typology: str | None, resolved_keys: list[str]) -> list[Field]:
    """Which required fields are still neither answered nor defaulted."""
    have = {key.strip() for key in resolved_keys}
    return [item for item in profile_for(typology).fields if item.key not in have]


def checklist(typology: str | None) -> str:
    """The profile rendered for a prompt."""
    profile = profile_for(typology)
    lines = [f"{profile.label} — a maker needs all of these:"]
    lines.extend(f"  {item.key}: {item.prompt}" for item in profile.fields)
    return "\n".join(lines)
