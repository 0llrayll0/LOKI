export function Empty({ title, hint, action }: { title: string; hint?: string; action?: { label: string; onClick: () => void } }) {
  return (
    <div className="empty" role="status">
      <strong>{title}</strong>
      {hint && <span>{hint}</span>}
      {action && <div style={{ marginTop: 10 }}><button className="btn-ghost" onClick={action.onClick}>{action.label}</button></div>}
    </div>
  );
}