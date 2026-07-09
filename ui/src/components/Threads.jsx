import { useEffect, useRef } from "react";
import "./Threads.css";

const LINE_COUNT = 18;

export default function Threads({
  color = [91, 140, 255],
  amplitude = 1,
  distance = 0,
  enableMouseInteraction = false,
  ...rest
}) {
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const animationFrameId = useRef(0);

  const propsRef = useRef({ color, amplitude, distance, enableMouseInteraction });
  propsRef.current = { color, amplitude, distance, enableMouseInteraction };

  useEffect(() => {
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;
    const ctx = canvas.getContext("2d");

    let width = 0;
    let height = 0;
    const MAX_RENDER_DIM = 1920;

    function resize() {
      const { clientWidth, clientHeight } = container;
      const baseDpr = Math.min(window.devicePixelRatio || 1, 2);
      const longestSide = Math.max(clientWidth, clientHeight) * baseDpr;
      const dpr = longestSide > MAX_RENDER_DIM ? (baseDpr * MAX_RENDER_DIM) / longestSide : baseDpr;
      width = clientWidth;
      height = clientHeight;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    resize();

    const targetMouse = [0.5, 0.5];
    const currentMouse = [0.5, 0.5];

    function handleMouseMove(e) {
      const rect = container.getBoundingClientRect();
      targetMouse[0] = (e.clientX - rect.left) / rect.width;
      targetMouse[1] = (e.clientY - rect.top) / rect.height;
    }
    function handleMouseLeave() {
      targetMouse[0] = 0.5;
      targetMouse[1] = 0.5;
    }
    container.addEventListener("mousemove", handleMouseMove);
    container.addEventListener("mouseleave", handleMouseLeave);

    let isVisible = true;
    const intersectionObserver = new IntersectionObserver(
      (entries) => {
        isVisible = entries[0].isIntersecting;
      },
      { threshold: 0 }
    );
    intersectionObserver.observe(container);

    function draw(t) {
      animationFrameId.current = requestAnimationFrame(draw);
      if (!isVisible || document.hidden || width === 0) return;

      const { color, amplitude, distance, enableMouseInteraction } = propsRef.current;
      const time = t * 0.00035;

      if (enableMouseInteraction) {
        currentMouse[0] += 0.05 * (targetMouse[0] - currentMouse[0]);
        currentMouse[1] += 0.05 * (targetMouse[1] - currentMouse[1]);
      } else {
        currentMouse[0] = 0.5;
        currentMouse[1] = 0.5;
      }

      ctx.clearRect(0, 0, width, height);

      const [r, g, b] = color;
      const mouseAmp = 1 + (currentMouse[1] - 0.5) * 0.6;

      for (let i = 0; i < LINE_COUNT; i++) {
        const p = i / (LINE_COUNT - 1);
        const baseY = height * (0.5 + (p - 0.5) * (0.35 + distance * 0.3));
        const lineAmplitude = amplitude * mouseAmp * (6 + p * 22);
        const phase = time * (0.6 + p * 0.25) + p * 6.28 + currentMouse[0] * 2;
        const opacity = 0.06 + (1 - Math.abs(p - 0.5) * 2) * 0.16;

        ctx.beginPath();
        const step = Math.max(4, Math.round(width / 140));
        for (let x = 0; x <= width; x += step) {
          const nx = x / width;
          const y =
            baseY +
            Math.sin(nx * 3.2 + phase) * lineAmplitude * Math.sin(nx * Math.PI) +
            Math.sin(nx * 7.3 + phase * 1.7) * lineAmplitude * 0.25;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.strokeStyle = `rgba(${r}, ${g}, ${b}, ${opacity})`;
        ctx.lineWidth = 1.4;
        ctx.stroke();
      }
    }
    animationFrameId.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(animationFrameId.current);
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      container.removeEventListener("mousemove", handleMouseMove);
      container.removeEventListener("mouseleave", handleMouseLeave);
    };
  }, []);

  return (
    <div ref={containerRef} className="threads-container" {...rest}>
      <canvas ref={canvasRef} />
    </div>
  );
}
