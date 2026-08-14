"""
fotos_reader.py

Porte server-side da extensao de navegador censoip-metadata-extension
(content.js) usada pra ler os metadados das fotos de uma pagina de
relatorio (LINK_RELATORIO do levantamento). A pagina responde sem
autenticacao e ja traz as <img> no HTML inicial — entao aqui e so
requests.get + regex, nenhum byte de imagem e baixado pelo servidor.

Regras confirmadas contra o content.js original (ver plano da feature,
secao 2):
- Deduplicar pelas <img src> absolutas (o carrossel repete cada imagem).
- So contam as que tem "/wsipsatel/" no path (a extensao original nao
  filtra e produz cards de lixo pra logos/icones).
- Foto de CAMERA = nao tem o padrao UTM<zona>[letra]_<E>_<N>UTM no nome do
  arquivo. Quem tem esse padrao e foto de CELULAR (tem coordenada) — essas
  sao descartadas aqui, so queremos as de camera.
- Tecnico/POS_ID/Upload vem do path da URL:
    .../wsipsatel/<ano>/<mes>/<usuario>//<data_upload>/<pos_id>/<arquivo>
  usuario = parts[idx+3]; offset normalmente 4, mas vira 5 quando
  parts[idx+4] nao e "\\d{8}" e parts[idx+5] e (usuario ocupou 2 segmentos).
- Ponto/Captura vem do NOME do arquivo (nunca de EXIF):
    Ponto:    _{1,2}([A-Za-z0-9-]+)_POS_ID
    Captura:  (\\d{14})\\.ext no final (DDMMAAAAHHMMSS)
"""

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import unquote, urljoin, urlparse

log = logging.getLogger(__name__)

_IMG_RE    = re.compile(r'<img[^>]+src=["\']([^"\']+)["\']', re.IGNORECASE)
_UTM_RE    = re.compile(r'UTM(\d{1,2})[A-Za-z]?_(\d+)_(\d+)UTM', re.IGNORECASE)
_TS_RE     = re.compile(r'(\d{14})\.[A-Za-z0-9]+$')
_PONTO_RE  = re.compile(r'_{1,2}([A-Za-z0-9\-]+)_POS_ID', re.IGNORECASE)
_OITO_DIGITOS_RE = re.compile(r'^\d{8}$')

TIMEOUT_SEGUNDOS  = 15

# Requisicoes concorrentes ao servidor de relatorios sao feitas em lotes
# (nao tudo de uma vez) pra nao estourar o rate limit dele — confirmado na
# pratica: 12 requisicoes simultaneas sem pausa disparava o limite.
LOTE_TAMANHO_PADRAO         = 7
DELAY_ENTRE_LOTES_SEGUNDOS  = 0.25


def _formatar_upload(v: str) -> str:
    if not v or len(v) != 8:
        return v or ""
    return f"{v[6:8]}/{v[4:6]}/{v[0:4]}"


def _data_valida(dd: str, mm: str, aaaa: str) -> bool:
    try:
        d, m, a = int(dd), int(mm), int(aaaa)
        return 1 <= m <= 12 and 1 <= d <= 31 and 1900 <= a <= 2100
    except ValueError:
        return False


def _formatar_captura(ts: str) -> str:
    """
    O content.js original assume sempre DDAAAAMMHHMMSS — correto pras fotos
    de CELULAR (nome com tag UTM, ex.: ..._25072024151005.jpg). Mas fotos de
    CAMERA pura (sem tag, ex.: 20240725151118.jpg — as que essa feature usa)
    seguem AAAAMMDDHHMMSS, um formato diferente: aplicando DDMMAAAA nelas da
    mes=24 (invalido). Confirmado comparando o horario de captura de uma
    foto de celular com o de uma foto de camera do mesmo ponto/sessao (ver
    plano da feature). Aqui tentamos DDMMAAAA primeiro (paridade com a
    extensao); se a data resultante for invalida, cai para AAAAMMDD.
    """
    dd, mm, aaaa = ts[0:2], ts[2:4], ts[4:8]
    if _data_valida(dd, mm, aaaa):
        return f"{dd}/{mm}/{aaaa} {ts[8:10]}:{ts[10:12]}:{ts[12:14]}"
    aaaa2, mm2, dd2 = ts[0:4], ts[4:6], ts[6:8]
    if _data_valida(dd2, mm2, aaaa2):
        return f"{dd2}/{mm2}/{aaaa2} {ts[8:10]}:{ts[10:12]}:{ts[12:14]}"
    return f"{dd}/{mm}/{aaaa} {ts[8:10]}:{ts[10:12]}:{ts[12:14]}"


def _parse_meta(url: str) -> dict:
    """Espelha parseImageMeta() do content.js original."""
    meta = {"url": url, "tecnico": "", "pos_id": "", "upload": "", "captura": "", "arquivo": "", "ponto": ""}
    try:
        partes = [p for p in urlparse(url).path.split("/") if p]

        if "wsipsatel" in partes:
            idx = partes.index("wsipsatel")
            meta["tecnico"] = partes[idx + 3] if idx + 3 < len(partes) else ""

            offset  = 4
            prox     = partes[idx + 4] if idx + 4 < len(partes) else None
            seguinte = partes[idx + 5] if idx + 5 < len(partes) else None
            if prox and not _OITO_DIGITOS_RE.match(prox) and seguinte and _OITO_DIGITOS_RE.match(seguinte):
                offset = 5

            upload_raw    = partes[idx + offset] if idx + offset < len(partes) else ""
            meta["upload"] = _formatar_upload(upload_raw)
            meta["pos_id"] = partes[idx + offset + 1] if idx + offset + 1 < len(partes) else ""

        arquivo = unquote(partes[-1]) if partes else ""
        meta["arquivo"] = arquivo

        m = _TS_RE.search(arquivo)
        if m:
            meta["captura"] = _formatar_captura(m.group(1))

        m = _PONTO_RE.search(arquivo)
        if m:
            meta["ponto"] = m.group(1)
    except Exception:
        meta["erro"] = True
    return meta


def _eh_foto_camera(url: str) -> bool:
    arquivo = unquote(url.rsplit("/", 1)[-1])
    return not _UTM_RE.search(arquivo)


def buscar_fotos_camera_do_link(link: str) -> list:
    """Baixa a pagina de relatorio e retorna as fotos de CAMERA nela (lista
    de dicts, ver _parse_meta). Levanta em erro de rede/HTTP — quem chama
    decide como tratar (o job continua com os outros links)."""
    req = urllib.request.Request(link, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SEGUNDOS) as resp:
        html = resp.read().decode("utf-8", "replace")

    vistos = set()
    fotos = []
    for src in _IMG_RE.findall(html):
        url_abs = urljoin(link, src)
        if url_abs in vistos:
            continue
        vistos.add(url_abs)
        if "/wsipsatel/" not in url_abs:
            continue
        if not _eh_foto_camera(url_abs):
            continue
        fotos.append(_parse_meta(url_abs))
    return fotos


# -----------------------------------------------------------------------------
# Cache em disco por municipio + busca concorrente com progresso
# -----------------------------------------------------------------------------

def _cache_path(cache_dir: str, slug: str) -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), cache_dir, f"{slug}.json")


def _carregar_cache(cache_dir: str, slug: str) -> dict:
    path = _cache_path(cache_dir, slug)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"[fotos] Erro lendo cache {slug}: {e}")
        return {}


def _salvar_cache(cache_dir: str, slug: str, cache: dict):
    path = _cache_path(cache_dir, slug)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False)
    except Exception as e:
        log.warning(f"[fotos] Nao foi possivel salvar cache {slug}: {e}")


def buscar_fotos_camera(pontos, slug: str, cache_dir: str,
                         max_workers: int = LOTE_TAMANHO_PADRAO,
                         delay_entre_lotes: float = DELAY_ENTRE_LOTES_SEGUNDOS,
                         on_progresso=None, pode_continuar=None,
                         espera_pausa_segundos: float = 0.3,
                         timeout_pausa_segundos: float = 120.0):
    """
    pontos -> lista de {"id_ponto": ..., "link": ...} (um LINK_RELATORIO por
    ponto do levantamento, ja filtrado pelo frontend).

    Cache em disco por municipio (cache_dir/<slug>.json), chave = link.
    Links ja cacheados nao sao rebuscados. Links pendentes sao buscados em
    lotes de ate `max_workers` requisicoes simultaneas, com uma pausa de
    `delay_entre_lotes` segundos entre um lote e o proximo — protege o
    servidor de relatorios do rate limit dele.

    `pode_continuar`, se passado, e checado ANTES de cada lote (nao a cada
    requisicao — a pausa acontece nas bordas dos lotes, que ja sao o ponto
    de sincronizacao natural do laco). Enquanto `pode_continuar()` devolver
    False, o laco dorme `espera_pausa_segundos` e testa de novo — usado pela
    galeria pra so buscar fotos suficientes pra pagina atual + a seguinte, em
    vez do filtro inteiro de uma vez (ver server.py). Se ficar pausado por
    `timeout_pausa_segundos` sem ninguem liberar mais (ex.: usuario fechou o
    modal e nao voltou), desiste e devolve o que tiver — evita uma thread
    dormindo pra sempre.

    on_progresso(feito, total, novas_fotos) e chamado apos cada link
    processado (cache hit ou miss), com `novas_fotos` sendo so as fotos
    adicionadas por ESSE link — usado pelo chamador (server.py) pra ir
    acumulando o resultado parcial do job e permitir carregamento
    progressivo na galeria, sem esperar o job inteiro terminar.

    Retorna (fotos, links_com_erro) — fotos e uma lista de dicts com
    id_ponto/link anexados a cada foto (ver _parse_meta pros demais campos).
    """
    id_ponto_por_link = {}
    ordem_links = []
    for p in pontos:
        link = (p.get("link") or "").strip()
        if not link or link in id_ponto_por_link:
            continue
        id_ponto_por_link[link] = p.get("id_ponto", "")
        ordem_links.append(link)

    cache = _carregar_cache(cache_dir, slug)
    total = len(ordem_links)
    feito = 0
    erros = []
    resultado = []

    def _anexar(link, fotos):
        novas = []
        for foto in fotos:
            foto = dict(foto)
            foto["link"] = link
            foto["id_ponto"] = id_ponto_por_link[link]
            resultado.append(foto)
            novas.append(foto)
        return novas

    pendentes = []
    for link in ordem_links:
        if link in cache:
            novas = _anexar(link, cache[link])
            feito += 1
            if on_progresso:
                on_progresso(feito, total, novas)
        else:
            pendentes.append(link)

    for i in range(0, len(pendentes), max_workers):
        if pode_continuar is not None:
            tempo_pausado = 0.0
            while not pode_continuar():
                time.sleep(espera_pausa_segundos)
                tempo_pausado += espera_pausa_segundos
                if tempo_pausado >= timeout_pausa_segundos:
                    log.info(
                        f"[fotos] {slug}: pausado {timeout_pausa_segundos:.0f}s sem liberacao — encerrando "
                        f"({feito}/{total} processados)"
                    )
                    _salvar_cache(cache_dir, slug, cache)
                    return resultado, erros
        lote = pendentes[i:i + max_workers]
        with ThreadPoolExecutor(max_workers=len(lote)) as ex:
            futuros = {ex.submit(buscar_fotos_camera_do_link, link): link for link in lote}
            for fut in as_completed(futuros):
                link = futuros[fut]
                try:
                    fotos = fut.result()
                except Exception as e:
                    log.warning(f"[fotos] Falha em {link}: {e}")
                    fotos = []
                    erros.append(link)
                cache[link] = fotos
                novas = _anexar(link, fotos)
                feito += 1
                if on_progresso:
                    on_progresso(feito, total, novas)
        if i + max_workers < len(pendentes):
            time.sleep(delay_entre_lotes)

    _salvar_cache(cache_dir, slug, cache)
    log.info(f"[fotos] {slug}: {len(resultado)} fotos de camera em {total} links ({len(erros)} erros)")
    return resultado, erros
