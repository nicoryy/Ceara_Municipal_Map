"""
Gera uma versao reduzida do GeoJSON de municipios.

Reducoes aplicadas:
  - Coordenadas truncadas para 6 casas decimais (~11cm de precisao).
  - Geometrias simplificadas via Douglas-Peucker (shapely.simplify).
  - Apenas as propriedades usadas pelo frontend sao mantidas
    (codigo_ibg / codigo_ibge, Municipio).

Uso:
  python scripts/simplify_geojson.py
  python scripts/simplify_geojson.py --tolerance 0.0002

Saida: frontend/municipios_ce.min.geojson
"""
import argparse
import json
import os
import sys
from shapely.geometry import shape, mapping

ROOT      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_PATH  = os.path.join(ROOT, "frontend", "municipios_ce.geojson")
DST_PATH  = os.path.join(ROOT, "frontend", "municipios_ce.min.geojson")

KEEP_PROPS = ("codigo_ibg", "codigo_ibge", "CD_MUN", "Municipio", "NM_MUN")


def round_coords(coords, ndigits):
    if isinstance(coords, (list, tuple)):
        if coords and isinstance(coords[0], (int, float)):
            return [round(c, ndigits) for c in coords]
        return [round_coords(c, ndigits) for c in coords]
    return coords


def simplify_feature(feat, tolerance, ndigits):
    geom_in = feat.get("geometry")
    if not geom_in:
        return None
    geom = shape(geom_in)
    if geom.is_empty:
        return None
    simplified = geom.simplify(tolerance, preserve_topology=True)
    if simplified.is_empty:
        simplified = geom
    geom_out = mapping(simplified)
    geom_out["coordinates"] = round_coords(geom_out["coordinates"], ndigits)
    props_in = feat.get("properties", {}) or {}
    props_out = {k: props_in[k] for k in KEEP_PROPS if k in props_in}
    return {
        "type": "Feature",
        "properties": props_out,
        "geometry": geom_out,
    }


def count_vertices(coords):
    if isinstance(coords, list):
        if coords and isinstance(coords[0], (int, float)):
            return 1
        return sum(count_vertices(c) for c in coords)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tolerance", type=float, default=0.0002,
                    help="Tolerancia Douglas-Peucker em graus (~22m). Default 0.0002.")
    ap.add_argument("--precision", type=int, default=6,
                    help="Casas decimais nas coordenadas. Default 6.")
    ap.add_argument("--src", default=SRC_PATH)
    ap.add_argument("--dst", default=DST_PATH)
    args = ap.parse_args()

    if not os.path.exists(args.src):
        print(f"[erro] arquivo nao encontrado: {args.src}", file=sys.stderr)
        return 2

    src_size = os.path.getsize(args.src)
    with open(args.src, "r", encoding="utf-8") as f:
        gj = json.load(f)

    feats_in = gj.get("features", [])
    feats_out = []
    v_in = v_out = 0
    for feat in feats_in:
        v_in += count_vertices(feat.get("geometry", {}).get("coordinates", []))
        new_feat = simplify_feature(feat, args.tolerance, args.precision)
        if new_feat is None:
            continue
        v_out += count_vertices(new_feat["geometry"]["coordinates"])
        feats_out.append(new_feat)

    out = {"type": "FeatureCollection", "features": feats_out}
    with open(args.dst, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)

    dst_size = os.path.getsize(args.dst)
    print(f"  features : {len(feats_in)} -> {len(feats_out)}")
    print(f"  vertices : {v_in:,} -> {v_out:,}  ({v_out / v_in * 100:.1f}%)")
    print(f"  arquivo  : {src_size/1024:.0f} KB -> {dst_size/1024:.0f} KB  "
          f"({dst_size / src_size * 100:.1f}%)")
    print(f"  saida    : {args.dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
