"""Sealed photoreal packets. Prompt is code. One image call per shot."""
from __future__ import annotations

import base64
from typing import Any, Optional, Protocol

from pydantic import BaseModel

from app.models.furniture_spec import BaySpec, FurnitureSpec
from app.planner.views import CameraJob, elevation_sheet_name, plan_views
from app.render.raster import elevation_png, plan_cone_png, png_bytes


class PhotorealError(Exception):
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


def build_packets(spec: FurnitureSpec) -> list[RenderPacket]:
    plan = plan_views(spec)
    return [build_packet(spec, job) for job in plan.cameras]


def build_packet(spec: FurnitureSpec, job: CameraJob) -> RenderPacket:
    refs: list[PacketRef] = []
    for wall_id in job.walls:
        image = elevation_png(spec, wall_id)
        refs.append(
            PacketRef(
                name=elevation_sheet_name(wall_id),
                wall_id=wall_id,
                data=_b64(png_bytes(image)),
            )
        )
    refs.append(
        PacketRef(
            name="plan-cone.svg",
            data=_b64(png_bytes(plan_cone_png(spec, job))),
        )
    )
    expected = list(job.references)
    got = [ref.name for ref in refs]
    if got != expected:
        raise PhotorealError(
            f"{job.shot_id} refs {got} != planner {expected}"
        )
    return RenderPacket(
        shot_id=job.shot_id,
        camera=job.camera,
        walls=list(job.walls),
        frame=job.frame.model_dump(),
        exclude=list(job.exclude),
        references=refs,
        prompt=sealed_prompt(spec, job),
    )


def packet_for_shot(spec: FurnitureSpec, shot_id: str) -> RenderPacket:
    for packet in build_packets(spec):
        if packet.shot_id == shot_id:
            return packet
    raise PhotorealError(f"unknown shot {shot_id}")


def sealed_prompt(spec: FurnitureSpec, job: CameraJob) -> str:
    lines = [
        "Photorealistic interior photograph of the locked furniture design.",
        "This is a photograph, not a drawing, floor plan, or elevation sheet.",
        f"Project: {spec.name or spec.project_id}",
        f"Camera: {job.camera}",
        f"Shot: {job.shot_id}",
        "",
        _frame_block(spec, job, "LEFT", job.frame.left),
    ]
    if job.frame.right:
        lines.append(_frame_block(spec, job, "RIGHT", job.frame.right))

    if job.exclude:
        labels = [
            f"{wid} ({spec.layout_wall(wid).label or wid})"
            for wid in job.exclude
        ]
        lines.append("Do not show these walls: " + ", ".join(labels) + ".")
        lines.append("Do not invent extra cabinet runs.")

    mat = spec.materials
    hw = spec.hardware
    material_bits = [
        f"{key}={value}"
        for key, value in (
            ("carcass", mat.carcass),
            ("doors", mat.doors),
            ("finish", mat.finish),
        )
        if value
    ]
    if material_bits:
        lines.append("Materials: " + "; ".join(material_bits))
    hardware_bits = [bit for bit in (hw.style, hw.placement) if bit]
    if hardware_bits:
        lines.append("Hardware: " + "; ".join(hardware_bits))
    if spec.render_notes.strip():
        lines.append("Render notes: " + spec.render_notes.strip())

    lines.append("")
    lines.append("Attached reference images, in order:")
    for index, name in enumerate(job.references, start=1):
        if name == "plan-cone.svg":
            meaning = (
                "plan with this shot's camera cone marked. "
                "Photograph from that viewpoint. Only cone-marked walls are in frame."
            )
        elif name.startswith("elev-") and index == 1:
            meaning = "front elevation of the LEFT wall. Copy this layout exactly."
        else:
            meaning = "front elevation of the RIGHT wall. Copy this layout exactly."
        lines.append(f"{index}. {name} — {meaning}")
    lines.append(
        "Elevations are measured CAD. Copy bay count, widths, "
        "module stack (first module is at the plinth / bottom), cornice, and plinth."
    )
    return "\n".join(lines)


async def render_packet(client: ImageClient, packet: RenderPacket) -> tuple[str, str]:
    result = await client.generate_image(
        prompt=packet.prompt,
        reference_images=[
            {"data": ref.data, "mime_type": ref.mime_type}
            for ref in packet.references
        ],
    )
    images = result.get("images") or []
    if not images or not images[0].get("data"):
        raise PhotorealError(f"{packet.shot_id}: image model returned no image")
    image = images[0]
    return image["data"], image.get("mime_type") or "image/png"


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


def _frame_block(spec: FurnitureSpec, job: CameraJob, side: str, wall_id: str) -> str:
    layout = spec.layout_wall(wall_id)
    design = spec.design_wall(wall_id)
    label = layout.label or wall_id
    bays = job.bays_by_wall.get(wall_id) or design.bay_ids()
    bay_lines = []
    for bay_id in bays:
        bay = next(item for item in design.bays if item.id == bay_id)
        bay_lines.append("    " + _describe_bay(bay))
    body = "\n".join(bay_lines) if bay_lines else "    (no bays)"
    return (
        f"{side} of frame: {wall_id} ({label}), "
        f"{layout.length:.0f} cm long, {design.height:.0f} cm high, "
        f"{design.depth:.0f} cm deep.\n{body}"
    )


def _describe_bay(bay: BaySpec) -> str:
    parts = []
    for module in bay.modules:
        bit = module.type
        if module.count > 1:
            bit += f" x{module.count}"
        if module.height:
            bit += f" {module.height:.0f}cm"
        parts.append(bit)
    stack = ", then ".join(parts) if parts else "empty"
    return f"{bay.label or bay.id} {bay.width:.0f}cm (bottom to top: {stack})"


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")
