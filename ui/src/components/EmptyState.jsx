import Icon from "./Icon";

export default function EmptyState({ icon = "inbox", size = 30, borderless, action, children }) {
  return (
    <div className="empty-state" style={borderless ? { border: "none" } : undefined}>
      <Icon name={icon} size={size} />
      <p>{children}</p>
      {action}
    </div>
  );
}
