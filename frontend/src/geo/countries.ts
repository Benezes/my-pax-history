import type { MapCountry } from "../types";

export interface CountryFeature {
  type: "Feature";
  properties: { iso: string; name: string };
  geometry: { type: string; coordinates: unknown };
}

export const EU_ISO = new Set([
  "AUT",
  "BEL",
  "BGR",
  "HRV",
  "CYP",
  "CZE",
  "DNK",
  "EST",
  "FIN",
  "FRA",
  "DEU",
  "GRC",
  "HUN",
  "IRL",
  "ITA",
  "LVA",
  "LTU",
  "LUX",
  "MLT",
  "NLD",
  "POL",
  "PRT",
  "ROU",
  "SVK",
  "SVN",
  "ESP",
  "SWE",
]);

let pending: Promise<CountryFeature[]> | null = null;

export function loadCountryFeatures(): Promise<CountryFeature[]> {
  if (!pending) {
    pending = fetch("/globe/countries.geojson")
      .then((response) => {
        if (!response.ok) throw new Error("map");
        return response.json();
      })
      .then((data: { features?: CountryFeature[] }) => data.features || []);
  }
  return pending;
}

export function isoHighlighted(iso: string, highlighted: Set<string>) {
  if (highlighted.has(iso)) return true;
  return highlighted.has("EU") && EU_ISO.has(iso);
}

export function featureLabel(feature: CountryFeature, countries: MapCountry[]) {
  const match = countries.find((item) => item.iso === feature.properties.iso);
  return match?.name || feature.properties.name;
}

export function capColor(iso: string, highlighted: Set<string>) {
  if (iso === "BRA") return "rgba(201, 162, 39, 0.88)";
  if (isoHighlighted(iso, highlighted)) return "rgba(78, 163, 122, 0.82)";
  return "rgba(28, 62, 78, 0.55)";
}

export function strokeColor(iso: string, highlighted: Set<string>) {
  if (iso === "BRA") return "#e6c768";
  if (isoHighlighted(iso, highlighted)) return "#8ad4ad";
  return "rgba(120, 160, 176, 0.35)";
}
