import { Component, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import Globe, { GlobeMethods } from "react-globe.gl";
import type { MapCountry } from "../types";

interface Props {
  countries: MapCountry[];
}

const LOCAL_EARTH = "/globe/earth-night.jpg";
const SOFTWARE_GL = /llvmpipe|swiftshader|softpipe|microsoft basic render|mesa offscreen/i;

class GlobeBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function forcedFallback() {
  if (typeof window === "undefined") return false;
  const params = new URLSearchParams(window.location.search);
  return params.get("globe") === "fallback" || params.get("globe") === "svg";
}

function hardwareWebGlAvailable() {
  if (typeof document === "undefined") return false;
  try {
    const canvas = document.createElement("canvas");
    const gl =
      canvas.getContext("webgl", { failIfMajorPerformanceCaveat: true }) ||
      canvas.getContext("experimental-webgl", { failIfMajorPerformanceCaveat: true });
    if (!gl || !(gl instanceof WebGLRenderingContext)) {
      return false;
    }
    const info = gl.getExtension("WEBGL_debug_renderer_info");
    if (info) {
      const renderer = String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL) || "");
      if (SOFTWARE_GL.test(renderer)) {
        return false;
      }
    }
    return true;
  } catch {
    return false;
  }
}

function canvasLooksEmpty(canvas: HTMLCanvasElement) {
  try {
    const gl = canvas.getContext("webgl") || canvas.getContext("webgl2");
    if (!gl) return true;
    const width = 32;
    const height = 32;
    const x = Math.max(0, Math.floor(canvas.width / 2 - width / 2));
    const y = Math.max(0, Math.floor(canvas.height / 2 - height / 2));
    const pixels = new Uint8Array(width * height * 4);
    gl.readPixels(x, y, width, height, gl.RGBA, gl.UNSIGNED_BYTE, pixels);
    let minSum = 765;
    let maxSum = 0;
    let total = 0;
    let count = 0;
    for (let i = 0; i < pixels.length; i += 4) {
      const sum = pixels[i] + pixels[i + 1] + pixels[i + 2];
      minSum = Math.min(minSum, sum);
      maxSum = Math.max(maxSum, sum);
      total += sum;
      count += 1;
    }
    if (count === 0) return true;
    return maxSum - minSum < 12 && total / count < 40;
  } catch {
    return true;
  }
}

export default function GlobeView({ countries }: Props) {
  const [allowWebgl] = useState(() => !forcedFallback() && hardwareWebGlAvailable());
  if (!allowWebgl) {
    return <FallbackGlobe countries={countries} />;
  }
  return (
    <GlobeBoundary fallback={<FallbackGlobe countries={countries} />}>
      <WebGlGlobe countries={countries} />
    </GlobeBoundary>
  );
}

function WebGlGlobe({ countries }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const globeRef = useRef<GlobeMethods | undefined>(undefined);
  const [size, setSize] = useState({ w: 0, h: 520 });
  const [failed, setFailed] = useState(false);
  const [textureUrl, setTextureUrl] = useState(LOCAL_EARTH);

  const brazil = countries.find((item) => item.iso === "BRA");
  const highlighted = countries.filter((item) => item.highlight);
  const highlightKey = highlighted.map((item) => item.iso).join(",");
  const arcs = useMemo(
    () =>
      highlighted
        .filter((item) => item.iso !== "BRA" && brazil)
        .map((item) => ({
          startLat: brazil!.lat,
          startLng: brazil!.lng,
          endLat: item.lat,
          endLng: item.lng,
        })),
    [highlightKey, brazil]
  );

  useEffect(() => {
    const image = new Image();
    image.onload = () => setTextureUrl(LOCAL_EARTH);
    image.onerror = () => setFailed(true);
    image.src = LOCAL_EARTH;
  }, []);

  useEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      setSize({ w: entry.contentRect.width, h: Math.max(420, entry.contentRect.height) });
    });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    try {
      globeRef.current?.pointOfView({ lat: -12, lng: -48, altitude: 2.15 }, 0);
    } catch {
      setFailed(true);
    }
  }, [size.w]);

  useEffect(() => {
    const focus = highlighted.find((item) => item.iso !== "BRA") || brazil;
    if (focus) {
      try {
        globeRef.current?.pointOfView({ lat: focus.lat, lng: focus.lng, altitude: 2.2 }, 800);
      } catch {
        setFailed(true);
      }
    }
  }, [highlightKey]);

  useEffect(() => {
    if (failed || size.w <= 0) return;
    const timer = window.setTimeout(() => {
      const canvas = ref.current?.querySelector("canvas");
      if (!canvas || canvasLooksEmpty(canvas)) {
        setFailed(true);
      }
    }, 2500);
    return () => window.clearTimeout(timer);
  }, [failed, size.w, textureUrl]);

  if (failed) {
    return <FallbackGlobe countries={countries} />;
  }

  return (
    <div className="globe-wrap" ref={ref} data-globe-mode="webgl">
      {size.w > 0 && (
        <Globe
          ref={globeRef}
          width={size.w}
          height={size.h}
          backgroundColor="#050b10"
          globeImageUrl={textureUrl}
          atmosphereColor="#6aa88a"
          atmosphereAltitude={0.18}
          pointsData={countries}
          pointLat="lat"
          pointLng="lng"
          pointAltitude={(d: object) => ((d as MapCountry).highlight ? 0.12 : 0.03)}
          pointRadius={(d: object) => {
            const item = d as MapCountry;
            if (item.iso === "BRA") return 1.15;
            return item.highlight ? 0.85 : 0.45;
          }}
          pointColor={(d: object) => {
            const item = d as MapCountry;
            if (item.iso === "BRA") return "#c9a227";
            return item.highlight ? "#4ea37a" : "#3d5d70";
          }}
          labelsData={highlighted}
          labelLat="lat"
          labelLng="lng"
          labelText="name"
          labelSize={1.35}
          labelColor={() => "#ebe6d8"}
          labelAltitude={0.14}
          labelDotRadius={0}
          arcsData={arcs}
          arcColor={() => ["#c9a227", "#4ea37a"]}
          arcDashLength={0.4}
          arcDashGap={0.2}
          arcDashAnimateTime={2800}
          arcAltitude={0.18}
        />
      )}
      <div className="globe-caption">Países envolvidos nos acontecimentos recentes</div>
    </div>
  );
}

function project(lat: number, lng: number, centerLng: number) {
  const latR = (lat * Math.PI) / 180;
  const lngR = ((lng - centerLng) * Math.PI) / 180;
  const x = Math.cos(latR) * Math.sin(lngR);
  const y = Math.sin(latR);
  const z = Math.cos(latR) * Math.cos(lngR);
  return { x, y, z };
}

function FallbackGlobe({ countries }: Props) {
  const [centerLng, setCenterLng] = useState(-48);
  const drag = useRef<{ x: number; lng: number } | null>(null);
  const width = 640;
  const height = 480;
  const cx = width / 2;
  const cy = height / 2;
  const radius = 180;

  const points = countries
    .map((item) => {
      const p = project(item.lat, item.lng, centerLng);
      if (p.z < 0) return null;
      return { ...item, px: cx + p.x * radius, py: cy - p.y * radius, z: p.z };
    })
    .filter((item): item is MapCountry & { px: number; py: number; z: number } => item !== null);

  return (
    <div className="globe-wrap" data-globe-mode="fallback">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        width="100%"
        height="100%"
        onPointerDown={(event) => {
          drag.current = { x: event.clientX, lng: centerLng };
          (event.target as Element).setPointerCapture?.(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (!drag.current) return;
          setCenterLng(drag.current.lng - (event.clientX - drag.current.x) * 0.35);
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
        style={{ cursor: "grab", touchAction: "none" }}
      >
        <defs>
          <radialGradient id="ocean" cx="35%" cy="30%">
            <stop offset="0%" stopColor="#1c4a5c" />
            <stop offset="100%" stopColor="#071018" />
          </radialGradient>
        </defs>
        <circle cx={cx} cy={cy} r={radius + 18} fill="none" stroke="#2f6f56" strokeOpacity="0.35" />
        <circle cx={cx} cy={cy} r={radius} fill="url(#ocean)" stroke="#c9a227" strokeOpacity="0.35" />
        {points.map((item) => (
          <g key={item.iso}>
            <circle
              cx={item.px}
              cy={item.py}
              r={item.iso === "BRA" ? 8 : item.highlight ? 6 : 3.5}
              fill={item.iso === "BRA" ? "#c9a227" : item.highlight ? "#4ea37a" : "#4d6d7c"}
            />
            {item.highlight && (
              <text x={item.px + 10} y={item.py - 8} fill="#ebe6d8" fontSize="12">
                {item.name}
              </text>
            )}
          </g>
        ))}
      </svg>
      <div className="globe-caption">Países envolvidos nos acontecimentos recentes · mapa 2D</div>
    </div>
  );
}
