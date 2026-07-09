import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import Icon from "./Icon";
import "./MagicBento.css";

const DEFAULT_GLOW_COLOR = "91, 140, 255"; // matches --accent
const DEFAULT_SPOTLIGHT_RADIUS = 300;
const DEFAULT_PARTICLE_COUNT = 8;
const MOBILE_BREAKPOINT = 768;

function useMobileDetection() {
  const [isMobile, setIsMobile] = useState(() => window.innerWidth <= MOBILE_BREAKPOINT);
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth <= MOBILE_BREAKPOINT);
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);
  return isMobile;
}

function spawnParticle(container, glowColor) {
  const { width, height } = container.getBoundingClientRect();
  const el = document.createElement("span");
  el.className = "bento-particle";
  el.style.left = `${Math.random() * width}px`;
  el.style.top = `${Math.random() * height}px`;
  el.style.background = `rgba(${glowColor}, 0.9)`;
  el.style.boxShadow = `0 0 6px rgba(${glowColor}, 0.6)`;
  el.style.setProperty("--dx", `${(Math.random() - 0.5) * 70}px`);
  el.style.setProperty("--dy", `${(Math.random() - 0.5) * 70}px`);
  container.appendChild(el);
  el.addEventListener("animationend", () => el.remove());
}

function BentoCard({
  item,
  glowColor,
  particleCount,
  enableTilt,
  enableMagnetism,
  enableStars,
  clickEffect,
  disableAnimations,
  textAutoHide,
}) {
  const cardRef = useRef(null);
  const particleTimerRef = useRef(null);

  useEffect(() => {
    const el = cardRef.current;
    if (!el || disableAnimations) return;

    function handleMove(e) {
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      el.style.setProperty("--glow-x", `${(x / rect.width) * 100}%`);
      el.style.setProperty("--glow-y", `${(y / rect.height) * 100}%`);
      el.style.setProperty("--glow-intensity", "1");

      if (enableTilt) {
        el.style.setProperty("--tilt-x", `${((y - rect.height / 2) / (rect.height / 2)) * -6}deg`);
        el.style.setProperty("--tilt-y", `${((x - rect.width / 2) / (rect.width / 2)) * 6}deg`);
      }
      if (enableMagnetism) {
        el.style.setProperty("--magnet-x", `${(x - rect.width / 2) * 0.04}px`);
        el.style.setProperty("--magnet-y", `${(y - rect.height / 2) * 0.04}px`);
      }
    }

    function handleEnter() {
      if (!enableStars) return;
      particleTimerRef.current = setInterval(() => {
        if (el.querySelectorAll(".bento-particle").length < particleCount) {
          spawnParticle(el, glowColor);
        }
      }, 140);
    }

    function handleLeave() {
      el.style.setProperty("--glow-intensity", "0");
      el.style.setProperty("--tilt-x", "0deg");
      el.style.setProperty("--tilt-y", "0deg");
      el.style.setProperty("--magnet-x", "0px");
      el.style.setProperty("--magnet-y", "0px");
      clearInterval(particleTimerRef.current);
    }

    function handleClick(e) {
      if (!clickEffect) return;
      const rect = el.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const maxDistance = Math.max(
        Math.hypot(x, y),
        Math.hypot(x - rect.width, y),
        Math.hypot(x, y - rect.height),
        Math.hypot(x - rect.width, y - rect.height)
      );
      const ripple = document.createElement("span");
      ripple.className = "bento-ripple";
      ripple.style.width = ripple.style.height = `${maxDistance * 2}px`;
      ripple.style.left = `${x - maxDistance}px`;
      ripple.style.top = `${y - maxDistance}px`;
      ripple.style.background = `radial-gradient(circle, rgba(${glowColor}, 0.35) 0%, transparent 70%)`;
      el.appendChild(ripple);
      ripple.addEventListener("animationend", () => ripple.remove());
    }

    el.addEventListener("mousemove", handleMove);
    el.addEventListener("mouseenter", handleEnter);
    el.addEventListener("mouseleave", handleLeave);
    el.addEventListener("click", handleClick);
    return () => {
      el.removeEventListener("mousemove", handleMove);
      el.removeEventListener("mouseenter", handleEnter);
      el.removeEventListener("mouseleave", handleLeave);
      el.removeEventListener("click", handleClick);
      clearInterval(particleTimerRef.current);
    };
  }, [glowColor, particleCount, enableTilt, enableMagnetism, enableStars, clickEffect, disableAnimations]);

  const className = `magic-bento-card magic-bento-card--border-glow${item.wide ? " wide" : ""}`;
  const style = { "--glow-color": glowColor };

  const content = (
    <>
      <div className="bento-card-header">
        <div className="bento-card-icon">
          <Icon name={item.icon} size={16} />
        </div>
        {item.label && <span className="bento-card-label">{item.label}</span>}
      </div>
      <div className="bento-card-content">
        <h3 className={`bento-card-title${textAutoHide ? " autohide" : ""}`}>{item.title}</h3>
        <p className={`bento-card-desc${textAutoHide ? " autohide" : ""}`}>{item.description}</p>
      </div>
    </>
  );

  if (item.to) {
    return (
      <Link to={item.to} ref={cardRef} className={className} style={style}>
        {content}
      </Link>
    );
  }
  return (
    <div ref={cardRef} className={className} style={style}>
      {content}
    </div>
  );
}

export default function MagicBento({
  items,
  glowColor = DEFAULT_GLOW_COLOR,
  spotlightRadius = DEFAULT_SPOTLIGHT_RADIUS,
  particleCount = DEFAULT_PARTICLE_COUNT,
  enableStars = false,
  enableSpotlight = true,
  enableTilt = true,
  enableMagnetism = true,
  clickEffect = true,
  textAutoHide = true,
  disableAnimations = false,
}) {
  const gridRef = useRef(null);
  const isMobile = useMobileDetection();
  const shouldDisable = disableAnimations || isMobile;

  useEffect(() => {
    if (!enableSpotlight || shouldDisable) return;
    const grid = gridRef.current;
    if (!grid) return;

    const spotlight = document.createElement("div");
    spotlight.className = "bento-global-spotlight";
    spotlight.style.background = `radial-gradient(circle, rgba(${glowColor}, 0.12) 0%, rgba(${glowColor}, 0.05) 30%, transparent 65%)`;
    document.body.appendChild(spotlight);

    function handleMove(e) {
      const rect = grid.getBoundingClientRect();
      const inside =
        e.clientX >= rect.left && e.clientX <= rect.right && e.clientY >= rect.top && e.clientY <= rect.bottom;
      spotlight.style.opacity = inside ? "1" : "0";
      if (inside) {
        spotlight.style.left = `${e.clientX}px`;
        spotlight.style.top = `${e.clientY}px`;
      }
    }
    document.addEventListener("mousemove", handleMove);
    return () => {
      document.removeEventListener("mousemove", handleMove);
      spotlight.remove();
    };
  }, [enableSpotlight, shouldDisable, glowColor]);

  return (
    <div className="magic-bento-grid" ref={gridRef} style={{ "--glow-radius": `${spotlightRadius}px` }}>
      {items.map((item) => (
        <BentoCard
          key={item.id}
          item={item}
          glowColor={glowColor}
          particleCount={particleCount}
          enableTilt={enableTilt}
          enableMagnetism={enableMagnetism}
          enableStars={enableStars}
          clickEffect={clickEffect}
          disableAnimations={shouldDisable}
          textAutoHide={textAutoHide}
        />
      ))}
    </div>
  );
}
