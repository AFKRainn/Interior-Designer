"""
JSON Schemas for structured outputs, and the wide-op DTO.

Why schemas and not prompt pleading: "ask if you are unsure" is a request a
model can silently decline, and it does — models recognise ambiguity but keep
it latent unless the output CONTRACT forces disclosure (plan.txt section 15).
A required field cannot be declined.

Strict mode needs every property listed in `required` and
additionalProperties false, so optional values are typed as nullable instead
of omitted. Nulls are stripped before the ops reach Pydantic.
"""
from __future__ import annotations

from typing import Any

from app.models.ops import OP_ADAPTER, Op, OpError


def _obj(properties: dict[str, Any], *, required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required if required is not None else list(properties),
        "additionalProperties": False,
    }


def response_format(name: str, schema: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {"name": name, "strict": True, "schema": schema},
    }


# -- intake ---------------------------------------------------------------

INTAKE_SCHEMA = _obj(
    {
        "typology": {
            "type": "string",
            "enum": ["kitchen", "wardrobe", "storage", "vanity", "other"],
        },
        "notice": {
            "type": "array",
            "description": "Private self-ask. Never shown to the client.",
            "items": _obj({"q": {"type": "string"}, "a": {"type": "string"}}),
        },
        "resolved": {
            "type": "array",
            "description": "Profile fields that are now settled.",
            "items": _obj(
                {
                    "field": {"type": "string"},
                    "value": {"type": "string"},
                    "source": {"type": "string", "enum": ["client", "default"]},
                }
            ),
        },
        "open": {
            "type": "array",
            "description": "Gaps worth asking about. At most 3.",
            "items": _obj(
                {
                    "field": {"type": "string"},
                    "why": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                }
            ),
        },
        "confidence": {"type": "number"},
        "response": {"type": "string", "description": "Client-facing text only."},
        "status": {"type": "string", "enum": ["chat", "ready"]},
    }
)

INTAKE_FORMAT = response_format("intake_turn", INTAKE_SCHEMA)


# -- edit ops -------------------------------------------------------------

OP_KINDS = [
    "set_size",
    "set_flex",
    "set_label",
    "split",
    "merge",
    "add_child",
    "delete",
    "set_front",
    "insert_bay",
    "set_wall",
    "set_corner",
    "set_materials",
    "set_hardware",
]

FRONT_TYPES = ["door", "drawer", "open", "glass", "appliance", "panel", "false_front"]


def _nullable(kind: str, **extra: Any) -> dict[str, Any]:
    return {"type": [kind, "null"], **extra}


# One wide object covering every op. A discriminated union of 13 shapes is
# not portable across providers; a flat nullable record is, and Pydantic
# discriminates on `kind` once the nulls are gone.
WIDE_OP_SCHEMA = _obj(
    {
        "kind": {"type": "string", "enum": OP_KINDS},
        "path": _nullable("string", description="wall-a/bay-2/row-1 style address"),
        "wall_id": _nullable("string"),
        "size_cm": _nullable("number"),
        "flex": _nullable("number"),
        "label": _nullable("string"),
        "axis": {"type": ["string", "null"], "enum": ["rows", "cols", None]},
        "count": _nullable("integer"),
        "ratios": {"type": ["array", "null"], "items": {"type": "number"}},
        "index": _nullable("integer"),
        "type": {"type": ["string", "null"], "enum": [*FRONT_TYPES, None]},
        "front_type": {"type": ["string", "null"], "enum": [*FRONT_TYPES, None]},
        "hinge": {
            "type": ["string", "null"],
            "enum": ["left", "right", "top", "bottom", "none", None],
        },
        "handle": _nullable("string"),
        "length": _nullable("number"),
        "height": _nullable("number"),
        "depth": _nullable("number"),
        "reveal_mm": _nullable("number"),
        "cornice_height": _nullable("number"),
        "plinth_height": _nullable("number"),
        "side_left_cm": _nullable("number"),
        "side_right_cm": _nullable("number"),
        "end": {"type": ["string", "null"], "enum": ["start", "end", None]},
        "mode": {"type": ["string", "null"], "enum": ["yield", "take", None]},
        "carcass": _nullable("string"),
        "doors": _nullable("string"),
        "finish": _nullable("string"),
        "style": _nullable("string"),
        "placement": _nullable("string"),
    }
)

EDIT_SCHEMA = _obj(
    {
        "understanding": {
            "type": "string",
            "description": "Restate the change in the drawing's own vocabulary.",
        },
        "targets": {"type": "array", "items": {"type": "string"}},
        "ops": {"type": "array", "items": WIDE_OP_SCHEMA},
        "ambiguities": {
            "type": "array",
            "description": "Anything genuinely unclear. Required field, not optional behaviour.",
            "items": _obj(
                {
                    "question": {"type": "string"},
                    "options": {"type": "array", "items": {"type": "string"}},
                }
            ),
        },
        "confidence": {"type": "number"},
        "action": {"type": "string", "enum": ["clarify", "propose"]},
    }
)

EDIT_FORMAT = response_format("edit_decision", EDIT_SCHEMA)


def parse_ops(raw: list[dict[str, Any]]) -> list[Op]:
    """Wide records -> validated ops. Nulls are absence."""
    ops: list[Op] = []
    for index, item in enumerate(raw, start=1):
        clean = {key: value for key, value in (item or {}).items() if value is not None}
        if not clean.get("kind"):
            raise OpError(f"op {index} has no kind")
        # `set_front` takes `type`; every other op that names a front uses
        # `front_type`. Models mix them up, and it is a free fix.
        if clean["kind"] == "set_front" and "type" not in clean and "front_type" in clean:
            clean["type"] = clean.pop("front_type")
        if clean["kind"] != "set_front":
            clean.pop("type", None)
        try:
            ops.append(OP_ADAPTER.validate_python(clean))
        except Exception as err:  # pydantic ValidationError or worse
            raise OpError(f"op {index} ({clean.get('kind')}) is not valid: {err}") from err
    return ops
