"""
transformadores_reader.py

Le os transformadores de um municipio a partir dos arquivos .kml em:
    <TRANSFORMADORES_BASE_PATH>/<NOME>/LOTES/*.kml

Cada Placemark/Point e extraido como {lat, lng}. Cache por municipio
invalidado por hash da lista de (nome_arquivo, mtime).

Tolerante a inconsistencias de caixa nas pastas (ex: 'ACOPIARA' vs 'Acopiara',
'FORTALEZA-REGIONAL 4' vs 'fortaleza-regional-4'): nomes sao normalizados
para apenas alfanumericos em lowercase antes de comparar.
"""

import glob
import json
import os
import re
import logging
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Normalizacao de nomes (folder lookup robusto)
# -----------------------------------------------------------------------------

def _normalize(nome: str) -> str:
    """Lowercase + remove acentos + mantem so [a-z0-9]. Usado para casamento."""
    if not nome:
        return ""
    # remove acentos
    s = unicodedata.normalize("NFD", str(nome))
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _slug_arquivo(nome: str) -> str:
    """Slug seguro para nome de arquivo (cache JSON)."""
    return re.sub(r"[^\w\-]+", "_", nome.upper()).strip("_") or "MUNICIPIO"


# -----------------------------------------------------------------------------
# Localizacao de pastas / arquivos
# -----------------------------------------------------------------------------

def _find_municipio_folder(base: str, nome: str) -> str:
    log.info(f"[trafo-busca] Procurando pasta do municipio '{nome}' em: {base}")
    if not os.path.isdir(base):
        log.warning(f"[trafo-busca] FALHA: diretorio base nao existe: {base}")
        raise FileNotFoundError(f"Diretorio base INTERNO_ANALISE nao encontrado: {base}")
    alvo = _normalize(nome)
    candidatos = []
    for entry in os.listdir(base):
        full = os.path.join(base, entry)
        if os.path.isdir(full) and _normalize(entry) == alvo:
            candidatos.append(full)
    if not candidatos:
        log.warning(
            f"[trafo-busca] FALHA: pasta '{nome}' (normalizada='{alvo}') nao encontrada em {base}. "
            f"Pastas existentes: {sorted(os.listdir(base))}"
        )
        raise FileNotFoundError(f"Pasta de transformadores nao encontrada para: {nome}")
    escolhida = candidatos[0]
    log.info(f"[trafo-busca] OK pasta do municipio: {escolhida}")
    return escolhida


def _find_lotes_folder(municipio_folder: str, sub_alvo: str) -> str:
    log.info(f"[trafo-busca] Procurando subpasta {sub_alvo} em: {municipio_folder}")
    alvo = _normalize(sub_alvo)
    for entry in os.listdir(municipio_folder):
        full = os.path.join(municipio_folder, entry)
        if os.path.isdir(full) and _normalize(entry) == alvo:
            log.info(f"[trafo-busca] OK subpasta {sub_alvo}: {full}")
            return full
    log.warning(
        f"[trafo-busca] FALHA: subpasta {sub_alvo} nao encontrada em {municipio_folder}. "
        f"Subpastas: {[e for e in os.listdir(municipio_folder) if os.path.isdir(os.path.join(municipio_folder, e))]}"
    )
    raise FileNotFoundError(f"Subpasta {sub_alvo} nao encontrada em: {municipio_folder}")


def _list_kml_files(lotes_folder: str):
    log.info(f"[trafo-busca] Listando arquivos .kml em: {lotes_folder}")
    arquivos = []
    for entry in os.listdir(lotes_folder):
        if entry.lower().endswith(".kml"):
            arquivos.append(os.path.join(lotes_folder, entry))
    arquivos.sort()
    log.info(f"[trafo-busca] OK {len(arquivos)} arquivo(s) .kml encontrado(s)")
    return arquivos


# -----------------------------------------------------------------------------
# Parsing de KML (namespace-agnostic)
# -----------------------------------------------------------------------------

def _local_tag(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def _parse_kml(path: str):
    """
    Extrai pontos de um KML. Retorna lista de {lat, lng}.
    Trabalha de forma namespace-agnostic e tolera Placemark sem coords ou
    coordenadas invalidas (apenas pula a entrada).
    """
    pontos = []
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        log.warning(f"[trafo-busca] XML invalido em {os.path.basename(path)}: {e}")
        return pontos
    root = tree.getroot()
    for elem in root.iter():
        if _local_tag(elem.tag) != "Point":
            continue
        for child in elem:
            if _local_tag(child.tag) != "coordinates" or not child.text:
                continue
            # KML coordinates: "lng,lat[,alt]"; pode ter multiplos coords (LineString),
            # mas Point usa um unico. Pega o primeiro token.
            primeiro = child.text.strip().split()[0]
            partes = primeiro.split(",")
            if len(partes) < 2:
                continue
            try:
                lng = float(partes[0])
                lat = float(partes[1])
            except ValueError:
                continue
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
                continue
            if lat == 0.0 and lng == 0.0:
                continue
            pontos.append({"lat": lat, "lng": lng})
    return pontos


# -----------------------------------------------------------------------------
# Cache fingerprint
# -----------------------------------------------------------------------------

def _fingerprint(arquivos):
    """
    Identificador estavel do conjunto de KMLs: lista ordenada de (basename, mtime, size).
    Mudou qualquer um -> cache invalidado.
    """
    return [
        [os.path.basename(p), os.path.getmtime(p), os.path.getsize(p)]
        for p in sorted(arquivos)
    ]


# -----------------------------------------------------------------------------
# Funcao principal
# -----------------------------------------------------------------------------

def carregar_transformadores(config, nome_municipio: str):
    """
    Le todos os transformadores de um municipio (todos os KMLs em LOTES).
    Retorna lista de dicts {lat, lng}.
    """
    base       = config.TRANSFORMADORES_BASE_PATH
    sub        = getattr(config, "TRANSFORMADORES_LOTES_SUB", "LOTES")
    cache_dir  = config.TRANSFORMADORES_CACHE_DIR

    folder    = _find_municipio_folder(base, nome_municipio)
    lotes     = _find_lotes_folder(folder, sub)
    arquivos  = _list_kml_files(lotes)
    fp        = _fingerprint(arquivos)

    slug = _slug_arquivo(nome_municipio)
    cache_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), cache_dir, f"{slug}.json"
    )

    # Cache
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
            if cache.get("fingerprint") == fp:
                log.info(
                    f"[cache-trafo] Hit {slug} - {cache.get('total','?')} pontos "
                    f"({cache.get('gerado_em','?')})"
                )
                return cache["dados"]
            log.info(f"[cache-trafo] Invalidado {slug} (fingerprint mudou)")
        except Exception as e:
            log.warning(f"[cache-trafo] Erro lendo cache {slug}: {e}")

    # Parse
    if not arquivos:
        log.info(f"[trafo] Sem arquivos .kml em {lotes} - retornando lista vazia")
        pontos = []
    else:
        pontos = []
        for kml in arquivos:
            extraidos = _parse_kml(kml)
            pontos.extend(extraidos)
            log.info(f"[trafo] {os.path.basename(kml)}: {len(extraidos)} pontos (acumulado {len(pontos)})")

    # Salva cache
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    novo = {
        "fingerprint": fp,
        "municipio":   nome_municipio,
        "lotes_dir":   lotes,
        "gerado_em":   datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "total":       len(pontos),
        "arquivos":    len(arquivos),
        "dados":       pontos,
    }
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(novo, f, ensure_ascii=False, indent=2)
        log.info(f"[cache-trafo] Salvo {slug} - {len(pontos)} pontos de {len(arquivos)} arquivo(s)")
    except Exception as e:
        log.warning(f"[cache-trafo] Nao foi possivel salvar cache {slug}: {e}")

    return pontos
