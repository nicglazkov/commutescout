// Rebuild the style files in src/ca_roads_demo/static/mapstyle/ that
// are ours to generate.
//
//   npm install --no-save @protomaps/basemaps@5.7.2
//   node scripts/build_mapstyles.mjs
//
// Two families of style live in that folder:
//
// - Protomaps layout (slate, grayscale, dark, light): themes over our
//   own map file. This script writes slate.json, a theme tuned for a
//   driving map: cool and quiet, with dark freeways, so the colored
//   alert markers are what stands out. The others were written the same
//   way from the stock themes with calmer water.
// - OpenMapTiles layout (positron, bright): OpenFreeMap's styles, saved
//   as published, minus Bright's points of interest (shops and cafes
//   under road alerts are noise). This script fetches both.
//
// Placeholders the server fills in (mapfiles.style_json):
//   __PMTILES_URL__  the Protomaps-layout file
//   __ASSETS__       fonts and icons for the Protomaps-layout styles
import { writeFileSync } from "node:fs";
import { layers, namedFlavor } from "@protomaps/basemaps";

const OUT = new URL("../src/ca_roads_demo/static/mapstyle/", import.meta.url);
const light = namedFlavor("light");

const SLATE = { ...light,
  background: "#9dbdd6", earth: "#eef1f4", water: "#9dbdd6",
  park_a: "#dbe9df", park_b: "#c2dccb", wood_a: "#dde9df", wood_b: "#c6dccb",
  scrub_a: "#e3ebe4", scrub_b: "#d0dfd3",
  buildings: "#dfe3e8", industrial: "#e4e8ec", hospital: "#ece3e6", school: "#e9e7e0",
  pedestrian: "#e9ecef",
  highway: "#55657a", highway_casing_early: "#2f3b4b", highway_casing_late: "#2f3b4b",
  bridges_highway: "#55657a", bridges_highway_casing: "#2f3b4b",
  major: "#9aa7b6", major_casing_early: "#6f7d8e", major_casing_late: "#6f7d8e",
  bridges_major: "#9aa7b6", bridges_major_casing: "#6f7d8e",
  link: "#7b8a9c", link_casing: "#2f3b4b", bridges_link: "#7b8a9c", bridges_link_casing: "#2f3b4b",
  minor_a: "#ffffff", minor_b: "#ffffff", minor_casing: "#cfd6de",
  minor_service: "#f8fafb", minor_service_casing: "#d6dce3", other: "#eef1f4",
  bridges_minor: "#ffffff", bridges_minor_casing: "#cfd6de",
  boundaries: "#8e99a8", railway: "#aab3bd",
  roads_label_major: "#24303f", roads_label_major_halo: "#ffffff",
  roads_label_minor: "#5b6878", roads_label_minor_halo: "#ffffff",
  city_label: "#16202c", city_label_halo: "#eef1f4",
  subplace_label: "#5b6878", subplace_label_halo: "#eef1f4",
  state_label: "#8591a1", state_label_halo: "#eef1f4", ocean_label: "#4a7397",
  landcover: { ...light.landcover,
    grassland: "rgba(222,234,225,1)", forest: "rgba(204,224,210,1)",
    barren: "rgba(238,238,232,1)", urban_area: "rgba(228,232,236,1)",
    farmland: "rgba(228,236,226,1)", scrub: "rgba(224,233,226,1)" },
};

function write(name, style) {
  writeFileSync(new URL(name + ".json", OUT), JSON.stringify(style));
  console.log(name, style.layers.length, "layers");
}

write("slate", {
  version: 8, name: "commutescout-slate",
  glyphs: "__ASSETS__/fonts/{fontstack}/{range}.pbf",
  sprite: "__ASSETS__/sprites/v4/light",
  sources: { protomaps: { type: "vector", url: "pmtiles://__PMTILES_URL__",
    attribution: "© OpenStreetMap contributors, Protomaps" } },
  layers: layers("protomaps", SLATE, { lang: "en" }).filter((l) => l.id !== "pois"),
});

for (const name of ["positron", "bright"]) {
  const style = await (await fetch("https://tiles.openfreemap.org/styles/" + name)).json();
  style.name = "commutescout-" + name;
  style.layers = style.layers.filter((l) => !/^poi/.test(l.id) && l["source-layer"] !== "poi");
  write(name, style);
}
