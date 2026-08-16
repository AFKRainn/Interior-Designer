import { useRef, useState } from "react";

export function ElevationSvg({
  elevation,
  selectedBayId,
  locked,
  onSelectBay,
  onDividerDragEnd,
}) {
  const wrapRef = useRef(null);
  const [drag, setDrag] = useState(null);

  if (!elevation) return null;
  const { svg, svg_width, svg_height, bays, dividers } = elevation;

  function scale() {
    const el = wrapRef.current;
    if (!el || !svg_width) return 1;
    return el.clientWidth / svg_width;
  }

  function onPointerDown(event, divider) {
    if (locked) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    setDrag({
      leftBayId: divider.left_bay_id,
      startX: event.clientX,
      startDividerX: divider.x,
    });
  }

  function onPointerMove(event) {
    if (!drag) return;
    event.preventDefault();
  }

  function onPointerUp(event) {
    if (!drag) return;
    const s = scale();
    const deltaCm = (event.clientX - drag.startX) / s;
    setDrag(null);
    if (Math.abs(deltaCm) < 0.5) return;
    onDividerDragEnd(drag.leftBayId, deltaCm);
  }

  return (
    <div
      className="elev-wrap"
      ref={wrapRef}
      style={{ aspectRatio: `${svg_width} / ${svg_height}` }}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
    >
      <div className="svg-frame" dangerouslySetInnerHTML={{ __html: svg }} />
      {(bays || []).map((bay) => (
        <button
          key={bay.id}
          type="button"
          className={`bay-hit ${selectedBayId === bay.id ? "selected" : ""}`}
          style={{
            left: `${(bay.x / svg_width) * 100}%`,
            top: `${(bay.y / svg_height) * 100}%`,
            width: `${(bay.width / svg_width) * 100}%`,
            height: `${(bay.height / svg_height) * 100}%`,
          }}
          onClick={() => onSelectBay(bay)}
        />
      ))}
      {!locked &&
        (dividers || []).map((divider) => (
          <div
            key={`${divider.left_bay_id}-${divider.right_bay_id}`}
            className="divider-hit"
            style={{
              left: `${(divider.x / svg_width) * 100}%`,
              top: `${(divider.y / svg_height) * 100}%`,
              height: `${(divider.height / svg_height) * 100}%`,
            }}
            onPointerDown={(event) => onPointerDown(event, divider)}
          />
        ))}
    </div>
  );
}
