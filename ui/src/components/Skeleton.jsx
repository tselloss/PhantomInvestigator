export default function Skeleton({ width = "100%", height = 14, radius = 6, circle, className = "", style }) {
  return (
    <div
      className={"skeleton " + className}
      style={{
        width: circle ? height : width,
        height,
        borderRadius: circle ? "50%" : radius,
        ...style,
      }}
    />
  );
}
