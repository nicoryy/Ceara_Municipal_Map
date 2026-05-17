"""
areas_inacessiveis_reader.py

Le as areas inacessiveis de um municipio a partir dos arquivos .gpkg em:
    <AREAS_INACESSIVEIS_BASE_PATH>/<NOME>/AREAS_INACESSIVEIS/*.gpkg

Cada feature do GeoPackage e extraido e convertido para uma geometria GeoJSON.
Cache por municipio invalidado por hash da lista de (nome_arquivo, mtime, size).

GPKG e um SQLite com geometrias em GeoPackageBinary (header + WKB padrao).
Suporta Point/LineString/Polygon e seus Multi-equivalentes em SRS 4326 (lon/lat).
"""

import json
import os
import re
import struct
import sqlite3
import logging
import unicodedata
from datetime import datetime

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Normalizacao de nomes (reusa estilo do transformadores_reader)
# -----------------------------------------------------------------------------

def _normalize(nome: str) -> str:
    if not nome:
        return ""
    s = unicodedata.normalize("NFD", str(nome))
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _slug_arquivo(nome: str) -> str:
    return re.sub(r"[^\w\-]+", "_", nome.upper()).strip("_") or "MUNICIPIO"


# -----------------------------------------------------------------------------
# Localizacao de pastas / arquivos
# -----------------------------------------------------------------------------

def _find_municipio_folder(base: str, nome: str) -> str:
    log.info(f"[areas-busca] Procurando pasta do municipio '{nome}' em: {base}")
    if not os.path.isdir(base):
        raise FileNotFoundError(f"Diretorio base nao encontrado: {base}")
    alvo = _normalize(nome)
    for entry in os.listdir(base):
        full = os.path.join(base, entry)
        if os.path.isdir(full) and _normalize(entry) == alvo:
            log.info(f"[areas-busca] OK pasta do municipio: {full}")
            return full
    raise FileNotFoundError(f"Pasta nao encontrada para: {nome}")


def _find_areas_folder(municipio_folder: str, sub_alvo: str) -> str:
    alvo = _normalize(sub_alvo)
    for entry in os.listdir(municipio_folder):
        full = os.path.join(municipio_folder, entry)
        if os.path.isdir(full) and _normalize(entry) == alvo:
            log.info(f"[areas-busca] OK subpasta {sub_alvo}: {full}")
            return full
    raise FileNotFoundError(f"Subpasta {sub_alvo} nao encontrada em: {municipio_folder}")


def _list_gpkg_files(folder: str):
    arquivos = []
    for entry in os.listdir(folder):
        if entry.lower().endswith(".gpkg"):
            arquivos.append(os.path.join(folder, entry))
    arquivos.sort()
    log.info(f"[areas-busca] OK {len(arquivos)} arquivo(s) .gpkg")
    return arquivos


# -----------------------------------------------------------------------------
# GeoPackageBinary + WKB parsing (2D)
# -----------------------------------------------------------------------------

# envelope byte sizes por tipo (bits 1-3 das flags)
_ENV_SIZES = {0: 0, 1: 32, 2: 48, 3: 48, 4: 64}


def _parse_gpkg_header(blob: bytes):
    """Retorna (wkb_offset, is_empty) ou levanta ValueError."""
    if len(blob) < 8 or blob[:2] != b"GP":
        raise ValueError("Geometria GPKG invalida (magic ausente)")
    flags = blob[3]
    env_type = (flags >> 1) & 0x07
    is_empty = (flags >> 4) & 0x01
    env_size = _ENV_SIZES.get(env_type, 0)
    return 8 + env_size, bool(is_empty)


def _parse_wkb(buf: bytes, offset: int):
    """Le um WKB a partir de buf[offset]. Retorna (geom_dict, novo_offset)."""
    bo = buf[offset]; offset += 1
    e = "<" if bo == 1 else ">"
    gt = struct.unpack_from(e + "I", buf, offset)[0]; offset += 4

    # Remove flags Z/M (ISO + EWKB)
    base = gt & 0xFF
    if base == 0:
        base = gt % 1000

    # Z/M flags: ISO -> 1000/2000/3000; EWKB -> bits 0x80000000 / 0x40000000
    has_z = bool((gt >= 1000 and gt < 2000) or (gt >= 3000 and gt < 4000) or (gt & 0x80000000))
    has_m = bool((gt >= 2000 and gt < 3000) or (gt >= 3000 and gt < 4000) or (gt & 0x40000000))
    dims = 2 + (1 if has_z else 0) + (1 if has_m else 0)
    pt_size = 8 * dims
    pt_fmt = e + ("d" * dims)

    def read_point():
        nonlocal offset
        vals = struct.unpack_from(pt_fmt, buf, offset); offset += pt_size
        # Mantem so [x, y] na saida (compat GeoJSON 2D)
        return [vals[0], vals[1]]

    def read_ring():
        nonlocal offset
        n = struct.unpack_from(e + "I", buf, offset)[0]; offset += 4
        return [read_point() for _ in range(n)]

    if base == 1:  # Point
        return {"type": "Point", "coordinates": read_point()}, offset
    if base == 2:  # LineString
        n = struct.unpack_from(e + "I", buf, offset)[0]; offset += 4
        return {"type": "LineString", "coordinates": [read_point() for _ in range(n)]}, offset
    if base == 3:  # Polygon
        n = struct.unpack_from(e + "I", buf, offset)[0]; offset += 4
        return {"type": "Polygon", "coordinates": [read_ring() for _ in range(n)]}, offset
    if base in (4, 5, 6):  # Multi*
        n = struct.unpack_from(e + "I", buf, offset)[0]; offset += 4
        subs = []
        for _ in range(n):
            sub, offset = _parse_wkb(buf, offset)
            subs.append(sub["coordinates"])
        nome = {4: "MultiPoint", 5: "MultiLineString", 6: "MultiPolygon"}[base]
        return {"type": nome, "coordinates": subs}, offset
    if base == 7:  # GeometryCollection
        n = struct.unpack_from(e + "I", buf, offset)[0]; offset += 4
        geoms = []
        for _ in range(n):
            g, offset = _parse_wkb(buf, offset)
            geoms.append(g)
        return {"type": "GeometryCollection", "geometries": geoms}, offset
    raise ValueError(f"Tipo WKB nao suportado: {gt}")


def _parse_gpkg_geometry(blob: bytes):
    if blob is None:
        return None
    try:
        wkb_off, empty = _parse_gpkg_header(blob)
        if empty:
            return None
        geom, _ = _parse_wkb(blob, wkb_off)
        return geom
    except Exception as ex:
        log.warning(f"[areas] Geometria invalida: {ex}")
        return None


# -----------------------------------------------------------------------------
# Leitura do GPKG
# -----------------------------------------------------------------------------

def _ler_gpkg_features(path: str):
    """Le todas as feature tables de um .gpkg. Retorna lista de Features GeoJSON."""
    features = []
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        cur = conn.cursor()
        try:
            tabelas = cur.execute(
                "SELECT table_name FROM gpkg_contents WHERE data_type='features'"
            ).fetchall()
        except sqlite3.DatabaseError as e:
            log.warning(f"[areas] {os.path.basename(path)} nao parece ser GPKG: {e}")
            return features

        for (tabela,) in tabelas:
            try:
                geom_col = cur.execute(
                    "SELECT column_name FROM gpkg_geometry_columns WHERE table_name=?",
                    (tabela,)
                ).fetchone()
            except sqlite3.DatabaseError:
                geom_col = None
            col = geom_col[0] if geom_col else "geometry"

            try:
                rows = cur.execute(f'SELECT "{col}" FROM "{tabela}"').fetchall()
            except sqlite3.DatabaseError as e:
                log.warning(f"[areas] Erro lendo {tabela} em {os.path.basename(path)}: {e}")
                continue

            for (blob,) in rows:
                geom = _parse_gpkg_geometry(blob)
                if geom is None:
                    continue
                features.append({
                    "type": "Feature",
                    "properties": {"source": os.path.basename(path), "table": tabela},
                    "geometry": geom,
                })
    finally:
        conn.close()
    return features


# -----------------------------------------------------------------------------
# Cache fingerprint
# -----------------------------------------------------------------------------

def _fingerprint(arquivos):
    return [
        [os.path.basename(p), os.path.getmtime(p), os.path.getsize(p)]
        for p in sorted(arquivos)
    ]


# -----------------------------------------------------------------------------
# Funcao principal
# -----------------------------------------------------------------------------

def carregar_areas_inacessiveis(config, nome_municipio: str):
    """
    Le todas as areas inacessiveis (poligonos) de um municipio.
    Retorna dict: {"features": [...], "arquivos": N}.
    """
    base      = config.AREAS_INACESSIVEIS_BASE_PATH
    sub       = getattr(config, "AREAS_INACESSIVEIS_SUB", "AREAS_INACESSIVEIS")
    cache_dir = config.AREAS_INACESSIVEIS_CACHE_DIR

    folder   = _find_municipio_folder(base, nome_municipio)
    areas    = _find_areas_folder(folder, sub)
    arquivos = _list_gpkg_files(areas)
    fp       = _fingerprint(arquivos)

    slug = _slug_arquivo(nome_municipio)
    cache_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), cache_dir, f"{slug}.json"
    )

    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            if cache.get("fingerprint") == fp:
                log.info(
                    f"[cache-areas] Hit {slug} - {cache.get('total','?')} features"
                )
                return {"features": cache["dados"], "arquivos": cache.get("arquivos", 0)}
            log.info(f"[cache-areas] Invalidado {slug}")
        except Exception as e:
            log.warning(f"[cache-areas] Erro lendo cache {slug}: {e}")

    features = []
    if not arquivos:
        log.info(f"[areas] Sem .gpkg em {areas}")
    else:
        for gpkg in arquivos:
            try:
                feats = _ler_gpkg_features(gpkg)
                features.extend(feats)
                log.info(f"[areas] {os.path.basename(gpkg)}: {len(feats)} features")
            except Exception as e:
                log.warning(f"[areas] Erro processando {os.path.basename(gpkg)}: {e}")

    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    novo = {
        "fingerprint": fp,
        "municipio":   nome_municipio,
        "areas_dir":   areas,
        "gerado_em":   datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "total":       len(features),
        "arquivos":    len(arquivos),
        "dados":       features,
    }
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(novo, f, ensure_ascii=False, indent=2)
        log.info(f"[cache-areas] Salvo {slug} - {len(features)} features")
    except Exception as e:
        log.warning(f"[cache-areas] Nao foi possivel salvar cache {slug}: {e}")

    return {"features": features, "arquivos": len(arquivos)}
