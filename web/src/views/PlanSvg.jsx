export function PlanSvg({ svg }) {
  if (!svg) return null;
  return (
    <div className="svg-frame" dangerouslySetInnerHTML={{ __html: svg }} />
  );
}
