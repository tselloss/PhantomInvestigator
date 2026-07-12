import Icon from "./Icon";

export default function Button({
  variant,
  loading = false,
  icon,
  iconSize = 14,
  className = "",
  disabled,
  children,
  ...rest
}) {
  const cls = [variant, className].filter(Boolean).join(" ");
  return (
    <button className={cls || undefined} disabled={disabled || loading} {...rest}>
      {loading ? (
        <span className="btn-spinner" aria-hidden="true" />
      ) : icon ? (
        <Icon name={icon} size={iconSize} />
      ) : null}
      {children}
    </button>
  );
}
