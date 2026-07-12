export default function Card({ status, center, className = "", children, ...rest }) {
  const cls = ["card", status ? `card-${status}` : "", center ? "card-center" : "", className]
    .filter(Boolean)
    .join(" ");
  return (
    <div className={cls} {...rest}>
      {children}
    </div>
  );
}
