import { geoOrthographic, geoPath, type GeoPermissibleObjects } from "d3-geo";
import { Component, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import Globe, { GlobeMethods } from "react-globe.gl";
import {
  capColor,
  featureLabel,
  isoHighlighted,
  loadCountryFeatures,
  strokeColor,
  type CountryFeature,
} from "../geo/countries";
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

function useCountryFeatures() {
  const [features, setFeatures] = useState<CountryFeature[]>([]);
  useEffect(() => {
    loadCountryFeatures()
      .then(setFeatures)
      .catch(() => setFeatures([]));
  }, []);
  return features;
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
  const [size, setSize] = useState({ w: 0, h: 360 });
  const [failed, setFailed] = useState(false);
  const [textureUrl, setTextureUrl] = useState(LOCAL_EARTH);
  const features = useCountryFeatures();

  const brazil = countries.find((item) => item.iso === "BRA");
  const highlighted = useMemo(() => new Set(countries.filter((item) => item.highlight).map((item) => item.iso)), [countries]);
  const highlightKey = [...highlighted].sort().join(",");
  const arcs = useMemo(
    () =>
      countries
        .filter((item) => item.highlight && item.iso !== "BRA" && brazil)
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
      setSize({ w: entry.contentRect.width, h: Math.max(240, entry.contentRect.height) });
    });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    try {
      globeRef.current?.pointOfView({ lat: -14, lng: -48, altitude: 2.05 }, 0);
    } catch {
      setFailed(true);
    }
  }, [size.w]);

  useEffect(() => {
    const focus = countries.find((item) => item.highlight && item.iso !== "BRA") || brazil;
    if (focus) {
      try {
        globeRef.current?.pointOfView({ lat: focus.lat, lng: focus.lng, altitude: 2.05 }, 800);
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
    }, 2800);
    return () => window.clearTimeout(timer);
  }, [failed, size.w, textureUrl, features.length]);

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
          atmosphereAltitude={0.16}
          polygonsData={features}
          polygonGeoJsonGeometry="geometry"
          polygonCapColor={(d: object) => capColor((d as CountryFeature).properties.iso, highlighted)}
          polygonSideColor={() => "rgba(12, 28, 36, 0.65)"}
          polygonStrokeColor={(d: object) => strokeColor((d as CountryFeature).properties.iso, highlighted)}
          polygonAltitude={(d: object) => {
            const iso = (d as CountryFeature).properties.iso;
            if (iso === "BRA") return 0.014;
            return isoHighlighted(iso, highlighted) ? 0.01 : 0.003;
          }}
          polygonLabel={(d: object) => {
            const feature = d as CountryFeature;
            const name = featureLabel(feature, countries);
            const match = countries.find((item) => item.iso === feature.properties.iso);
            const relation =
              match?.relation == null ? "" : `<div>Relação com o Brasil: ${Math.round(match.relation)}</div>`;
            return `<div class="globe-tip"><b>${name}</b>${relation}</div>`;
          }}
          labelsData={countries.filter((item) => item.highlight || item.iso === "BRA")}
          labelLat="lat"
          labelLng="lng"
          labelText="name"
          labelSize={1.2}
          labelColor={() => "#ebe6d8"}
          labelAltitude={0.16}
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

function FallbackGlobe({ countries }: Props) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; y: number; lng: number; lat: number } | null>(null);
  const [centerLng, setCenterLng] = useState(-48);
  const [centerLat, setCenterLat] = useState(-12);
  const [scale, setScale] = useState(210);
  const [hover, setHover] = useState<string | null>(null);
  const [box, setBox] = useState({ w: 640, h: 420 });
  const features = useCountryFeatures();
  const highlighted = useMemo(() => new Set(countries.filter((item) => item.highlight).map((item) => item.iso)), [countries]);

  useEffect(() => {
    if (!wrapRef.current) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      setBox({ w: Math.max(280, entry.contentRect.width), h: Math.max(220, entry.contentRect.height) });
    });
    observer.observe(wrapRef.current);
    return () => observer.disconnect();
  }, []);

  const cx = box.w / 2;
  const cy = box.h / 2;
  const projection = useMemo(
    () =>
      geoOrthographic()
        .translate([cx, cy])
        .scale(scale)
        .rotate([-centerLng, -centerLat, 0])
        .clipAngle(90),
    [cx, cy, scale, centerLng, centerLat]
  );
  const path = useMemo(() => geoPath(projection), [projection]);

  return (
    <div className="globe-wrap" ref={wrapRef} data-globe-mode="fallback">
      <svg
        viewBox={`0 0 ${box.w} ${box.h}`}
        width="100%"
        height="100%"
        onPointerDown={(event) => {
          drag.current = { x: event.clientX, y: event.clientY, lng: centerLng, lat: centerLat };
          (event.currentTarget as Element).setPointerCapture?.(event.pointerId);
        }}
        onPointerMove={(event) => {
          if (!drag.current) return;
          setCenterLng(drag.current.lng - (event.clientX - drag.current.x) * 0.35);
          setCenterLat(Math.max(-80, Math.min(80, drag.current.lat + (event.clientY - drag.current.y) * 0.25)));
        }}
        onPointerUp={() => {
          drag.current = null;
        }}
        onWheel={(event) => {
          event.preventDefault();
          setScale((value) => Math.max(120, Math.min(420, value - event.deltaY * 0.18)));
        }}
        style={{ cursor: "grab", touchAction: "none" }}
      >
        <defs>
          <radialGradient id="ocean" cx="35%" cy="30%">
            <stop offset="0%" stopColor="#1c4a5c" />
            <stop offset="100%" stopColor="#071018" />
          </radialGradient>
        </defs>
        <circle cx={cx} cy={cy} r={scale + 16} fill="none" stroke="#2f6f56" strokeOpacity="0.35" />
        <circle cx={cx} cy={cy} r={scale} fill="url(#ocean)" stroke="#c9a227" strokeOpacity="0.28" />
        {features.map((feature) => {
          const d = path(feature as GeoPermissibleObjects);
          if (!d) return null;
          const iso = feature.properties.iso;
          const label = featureLabel(feature, countries);
          return (
            <path
              key={iso + feature.properties.name}
              d={d}
              fill={capColor(iso, highlighted)}
              stroke={strokeColor(iso, highlighted)}
              strokeWidth={iso === "BRA" || isoHighlighted(iso, highlighted) ? 1.1 : 0.4}
              onPointerEnter={() => setHover(label)}
              onPointerLeave={() => setHover((current) => (current === label ? null : current))}
            >
              <title>{label}</title>
            </path>
          );
        })}
      </svg>
      {hover && <div className="globe-tip-live">{hover}</div>}
      <div className="globe-caption">Países envolvidos nos acontecimentos recentes · mapa 2D</div>
    </div>
  );
}
