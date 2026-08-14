"""
geometria_util.py

Geometria de municipios/regionais para uso server-side (ex.: excluir pontos
fora do limite municipal na deteccao de duplicadas — ver duplicadas.py).

Le os mesmos GeoJSONs que o frontend ja usa para desenhar o mapa
(municipios_ce.geojson e limites_regionais_fortaleza.geojson) e faz apenas
teste de ponto-dentro-de-poligono (ray casting), sem nenhuma dependencia
geoespacial nova (shapely/geopandas).

Para as regionais de Fortaleza, a chave usada e a mesma que o frontend
calcula em chaveRegional() (ver CLAUDE.md): "SER 11" -> "FORTALEZA -
REGIONAL 11".
"""

import json
import logging
import os
import re
import unicodedata

log = logging.getLogger(__name__)

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

_municipios_cache = None   # { "2304400": geometry, ... }  chave = IBGE 7 digitos
_municipios_por_nome = None  # { nome_normalizado: geometry }
_regionais_cache = None   # { "FORTALEZA - REGIONAL 11": geometry, ... }


def _normalize(nome: str) -> str:
    """Mesma normalizacao usada em levantamento_reader._normalize: lowercase,
    remove acentos, mantem so [a-z0-9] — pra casar nomes com grafia/espacos
    diferentes."""
    if not nome:
        return ""
    s = unicodedata.normalize("NFD", str(nome))
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _carregar_municipios():
    global _municipios_cache, _municipios_por_nome
    if _municipios_cache is not None:
        return
    _municipios_cache = {}
    _municipios_por_nome = {}
    path = os.path.join(FRONTEND_DIR, "municipios_ce.geojson")
    try:
        with open(path, "r", encoding="utf-8") as f:
            gj = json.load(f)
    except Exception as e:
        log.warning(f"[geometria] Nao foi possivel ler {path}: {e}")
        return
    for feat in gj.get("features", []):
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry")
        if not geom:
            continue
        ibge = props.get("codigo_ibg") or props.get("codigo_ibge") or props.get("CD_MUN")
        nome = props.get("Municipio") or props.get("NM_MUN") or props.get("municipio")
        if ibge:
            _municipios_cache[str(ibge).zfill(7)] = geom
        if nome:
            _municipios_por_nome[_normalize(nome)] = geom
    log.info(f"[geometria] Geometrias de municipios carregadas: {len(_municipios_cache)}")


def _carregar_regionais():
    global _regionais_cache
    if _regionais_cache is not None:
        return
    _regionais_cache = {}
    path = os.path.join(FRONTEND_DIR, "limites_regionais_fortaleza.geojson")
    try:
        with open(path, "r", encoding="utf-8") as f:
            gj = json.load(f)
    except Exception as e:
        log.warning(f"[geometria] Nao foi possivel ler {path}: {e}")
        return
    for feat in gj.get("features", []):
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry")
        if not geom:
            continue
        ser = str(props.get("regiao_adm") or "").strip()
        num = re.sub(r"^SER\s*", "", ser, flags=re.IGNORECASE).strip()
        if not num:
            continue
        chave = f"FORTALEZA - REGIONAL {num}"
        _regionais_cache[chave] = geom
    log.info(f"[geometria] Geometrias de regionais carregadas: {len(_regionais_cache)}")


_REGIONAL_RE = re.compile(r"^FORTALEZA\s*-\s*REGIONAL\s*(\d+)$", re.IGNORECASE)


def geometria_para(key: str, nome: str):
    """
    Retorna a geometria (dict GeoJSON, Polygon ou MultiPolygon) do municipio
    ou regional, ou None se nao encontrada — chamador deve tratar None como
    "sem limite conhecido, nao filtra por posicao" em vez de erro.

    key  -> o que veio na URL (pode ser IBGE de 7 digitos ou nome)
    nome -> nome ja resolvido (ver server._resolver_nome), usado pro caso
            das regionais de Fortaleza e como fallback de busca por nome.
    """
    k = (key or "").strip()
    if k.isdigit() and len(k) <= 7:
        _carregar_municipios()
        return _municipios_cache.get(k.zfill(7))

    if nome and _REGIONAL_RE.match(nome.strip()):
        _carregar_regionais()
        return _regionais_cache.get(nome.strip().upper())

    _carregar_municipios()
    return _municipios_por_nome.get(_normalize(nome or k))


def _ponto_no_anel(lat: float, lng: float, anel) -> bool:
    """Ray casting padrao (even-odd) sobre um anel [[lon,lat], ...]."""
    dentro = False
    n = len(anel)
    if n < 3:
        return False
    xj, yj = anel[-1][0], anel[-1][1]
    for ponto in anel:
        xi, yi = ponto[0], ponto[1]
        if (yi > lat) != (yj > lat):
            x_intersecao = (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
            if lng < x_intersecao:
                dentro = not dentro
        xj, yj = xi, yi
    return dentro


def _ponto_no_poligono(lat: float, lng: float, aneis) -> bool:
    """aneis[0] = anel externo, aneis[1:] = buracos."""
    if not aneis or not _ponto_no_anel(lat, lng, aneis[0]):
        return False
    for buraco in aneis[1:]:
        if _ponto_no_anel(lat, lng, buraco):
            return False
    return True


def ponto_dentro_geometria(lat: float, lng: float, geometry) -> bool:
    if not geometry:
        return True  # sem geometria conhecida -> nao exclui ninguem
    tipo = geometry.get("type")
    coords = geometry.get("coordinates")
    if not coords:
        return True
    if tipo == "Polygon":
        return _ponto_no_poligono(lat, lng, coords)
    if tipo == "MultiPolygon":
        return any(_ponto_no_poligono(lat, lng, poligono) for poligono in coords)
    return True
