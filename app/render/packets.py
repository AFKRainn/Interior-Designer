"""
Sealed photoreal packets (plan, stage 3).

One image call per shot. The prompt is written by CODE from the locked spec —
no model decides how many images exist, which walls are in frame, or what the
design is. The image model's only job is to make a photograph of a design
that has already been settled and drawn.

Reference images come from the BROWSER: it rasterises the very sheets the
user approved and posts them at lock. That is why there is no second
server-side renderer to drift out of step (plan 8).
"""
from __future__ import annotations

from typing import Any, Optional, Protocol

from pydantic import BaseModel

from app.models.paths import describe
from app.models.spec import Spec
from app.planner.views import CameraJob, plan_views


class PacketError(Exception):
    pass


class PacketRef(BaseModel):
    name: str
    mime_type: str = "image/png"
    data: str
    wall_id: Optional[str] = None


class RenderPacket(BaseModel):
    shot_id: str
    camera: str
    walls: list[str]
    frame: dict
    exclude: list[str]
    references: list[PacketRef]
    prompt: str


class ImageClient(Protocol):
    async def generate_image(
        self,
        prompt: str,
        reference_images: list[dict] | None = None,
        **kwargs: Any,
    ) -> dict: ...


Sheets = dict[str, str]
"""name -> base64 PNG, as uploaded at lock."""


def build_packets(spec: Spec, sheets: Sheets) -> list[RenderPacket]:
    return [build_packet(spec, job, sheets) for job in plan_views(spec).cameras]


def packet_for_shot(spec: Spec, shot_id: str, sheets: Sheets) -> RenderPacket:
    for job in plan_views(spec).cameras:
        if job.shot_id == shot_id:
            return build_packet(spec, job, sheets)
    raise PacketError(f"unknown shot {shot_id}")


def build_packet(spec: Spec, job: CameraJob, sheets: Sheets) -> RenderPacket:
    refs: list[PacketRef] = []
    for name in job.references:
        data = sheets.get(name)
        if not data:
            raise PacketError(
                f"{job.shot_id}: missing reference sheet '{name}'. "
                f"Lock the drawings again so the browser re-uploads them."
            )
        wall_id = next((w for w in job.walls if name == f"elev-{w}.png"), None)
        refs.append(PacketRef(name=name, data=data, wall_id=wall_id))

    return RenderPacket(
        shot_id=job.shot_id,
        camera=job.camera,
        walls=list(job.walls),
        frame=job.frame.model_dump(),
        exclude=list(job.exclude),
        references=refs,
        prompt=sealed_prompt(spec, job),
    )


def sealed_prompt(spec: Spec, job: CameraJob) -> str:
    lines = [
        "Photorealistic interior photograph of a finished, installed design.",
        "This is a PHOTOGRAPH. Not a drawing, not a floor plan, not an elevation.",
        f"Project: {spec.name or spec.project_id}",
        f"Camera: {job.camera}. Shot {job.shot_id}.",
        "",
        _frame_block(spec, "LEFT", job.frame.left),
    ]
    if job.frame.right:
        lines.append(_frame_block(spec, "RIGHT", job.frame.right))

    if job.exclude:
        labels = [f"{wid} ({spec.layout_wall(wid).label or wid})" for wid in job.exclude]
        lines.append("")
        lines.append("NOT in this photograph: " + ", ".join(labels) + ".")
        lines.append("Do not invent extra cabinet runs, and do not extend the design.")

    materials = [
        f"{key} {value}"
        for key, value in (
            ("carcass:", spec.materials.carcass),
            ("fronts:", spec.materials.doors),
            ("finish:", spec.materials.finish),
        )
        if value
    ]
    if materials:
        lines.append("Materials — " + "; ".join(materials) + ".")
    hardware = [bit for bit in (spec.hardware.style, spec.hardware.placement) if bit]
    if hardware:
        lines.append("Hardware — " + "; ".join(hardware) + ".")
    if spec.render_notes.strip():
        lines.append("Mood and lighting — " + spec.render_notes.strip())

    lines.append("")
    lines.append("Reference images, in order:")
    for index, ref in enumerate(job.references, start=1):
        if ref.startswith("plan-"):
            meaning = (
                "the floor plan. The SHADED runs are the ones in this photograph; "
                "shoot from inside the room looking at them."
            )
        else:
            wall_id = ref.removeprefix("elev-").removesuffix(".png")
            side = "LEFT" if wall_id == job.frame.left else "RIGHT"
            meaning = (
                f"measured front elevation of {wall_id}, the {side} of frame. "
                f"Copy its bay count, widths and front layout exactly."
            )
        lines.append(f"  {index}. {ref} — {meaning}")

    lines.append("")
    lines.append(
        "The elevations are dimensioned CAD drawings, not suggestions. "
        "Match every bay division, front type and proportion shown."
    )
    return "\n".join(lines)


def _frame_block(spec: Spec, side: str, wall_id: str) -> str:
    layout = spec.layout_wall(wall_id)
    design = spec.design_wall(wall_id)
    header = (
        f"{side} of frame — {wall_id} ({layout.label or wall_id}): "
        f"{spec.usable_length(wall_id):.0f} cm run, {design.height:.0f} cm high, "
        f"{design.depth:.0f} cm deep."
    )
    rows = [row for row in describe(spec, wall_id) if row["path"].count("/") == 1]
    body = [f"    {_describe_bay(spec, row)}" for row in rows]
    return "\n".join([header, *body]) if body else header


def _describe_bay(spec: Spec, row: dict) -> str:
    label = row["label"] or row["path"].split("/")[-1]
    if row["front"]:
        return f"{label}: {row['w_cm']:.0f} cm wide, one {row['front']} front"
    children = [
        item
        for item in describe(spec, row["path"].split("/")[0])
        if item["path"].startswith(row["path"] + "/")
        and item["path"].count("/") == row["path"].count("/") + 1
    ]
    parts = [
        f"{child['front'] or child['split']} {child['h_cm']:.0f} cm"
        for child in children
    ]
    order = "top to bottom" if row["split"] == "rows" else "left to right"
    return f"{label}: {row['w_cm']:.0f} cm wide, {order} — " + ", ".join(parts)


async def render_packet(client: ImageClient, packet: RenderPacket) -> tuple[str, str]:
    result = await client.generate_image(
        prompt=packet.prompt,
        reference_images=[
            {"data": ref.data, "mime_type": ref.mime_type} for ref in packet.references
        ],
    )
    images = result.get("images") or []
    if not images or not images[0].get("data"):
        raise PacketError(f"{packet.shot_id}: the image model returned no image")
    return images[0]["data"], images[0].get("mime_type") or "image/png"


def public_packet(packet: RenderPacket) -> dict:
    return {
        "shot_id": packet.shot_id,
        "camera": packet.camera,
        "walls": packet.walls,
        "frame": packet.frame,
        "exclude": packet.exclude,
        "prompt": packet.prompt,
        "references": [ref.name for ref in packet.references],
    }
