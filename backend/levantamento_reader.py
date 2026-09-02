"""
levantamento_reader.py

Le a planilha de levantamento de um municipio especifico, formato:
    <BASE>/<NOME>/<LEVANTAMENTO_SUBPASTA_PRIORITARIA>/*.xlsm|.xlsx   (entrega, prioridade)
    <BASE>/<NOME>/<LEVANTAMENTO_SUBPASTA>/<PREFIXO>*.xlsm|.xlsx     (padrao, fallback)

A subpasta prioritaria (quando existe e a planilha mais recente dentro dela
contem a folha obrigatoria LEVANTAMENTO_ABA) tem precedencia sobre a
subpasta padrao. Nesse caso, folhas extras (LEVANTAMENTO_ABAS_EXTRAS) sao
lidas tambem e viram "categorias" de pontos — ver _montar_categorias().

Estrategia:
- Apenas openpyxl em modo somente-leitura (sem xlwings).
- Toda comparacao de nomes (pasta, arquivo, aba, colunas) e case-insensitive.
- Cache por municipio invalidado por mtime do arquivo e pelo proprio caminho
  (troca entre entrega/padrao invalida o cache automaticamente).
- Arquivos-trava do Excel ("~$NOME.xlsm") sao ignorados na busca — ver
  excel_util.eh_arquivo_trava_excel(). Se a planilha estiver aberta no Excel
  e nao puder ser lida diretamente, tenta uma copia temporaria (ver
  excel_util.abrir_workbook_somente_leitura()); se nem isso funcionar, cai
  para o ultimo cache valido em vez de falhar (ver carregar_levantamento()).
"""

import glob
import json
import os
import re
import logging
import warnings
import unicodedata
from datetime import datetime

from excel_util import abrir_workbook_somente_leitura, eh_arquivo_trava_excel, limpar_temp

log = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Resolucao case-insensitive de pasta / arquivo / aba / colunas
# -----------------------------------------------------------------------------

def _normalize(nome: str) -> str:
    """Lowercase + remove acentos + mantem so [a-z0-9]. Para casamento robusto."""
    if not nome:
        return ""
    s = unicodedata.normalize("NFD", str(nome))
    s = s.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def _find_municipio_folder(base: str, nome: str) -> str:
    log.info(f"[busca] Procurando pasta do municipio '{nome}' em: {base}")
    if not os.path.isdir(base):
        log.warning(f"[busca] FALHA: diretorio base nao existe: {base}")
        raise FileNotFoundError(f"Diretorio base nao encontrado: {base}")
    alvo = _normalize(nome)
    for entry in os.listdir(base):
        if _normalize(entry) == alvo:
            full = os.path.join(base, entry)
            if os.path.isdir(full):
                log.info(f"[busca] OK pasta do municipio: {full}")
                return full
    log.warning(
        f"[busca] FALHA: pasta '{nome}' (normalizada='{alvo}') nao encontrada em {base}. "
        f"Entradas existentes: {os.listdir(base)}"
    )
    raise FileNotFoundError(f"Pasta do municipio nao encontrada: {nome}")


def _find_subpasta(municipio_folder: str, nome_subpasta: str) -> str:
    """Localiza uma subpasta (auditoria/entrega/etc) dentro da pasta do municipio,
    comparando nomes normalizados (tolerante a acento/caixa/espaco/hifen)."""
    if not nome_subpasta:
        raise FileNotFoundError("Nome de subpasta nao configurado")
    log.info(f"[busca] Procurando subpasta '{nome_subpasta}' em: {municipio_folder}")
    alvo = _normalize(nome_subpasta)
    for entry in os.listdir(municipio_folder):
        full = os.path.join(municipio_folder, entry)
        if os.path.isdir(full) and _normalize(entry) == alvo:
            log.info(f"[busca] OK subpasta: {full}")
            return full
    subpastas = [
        e for e in os.listdir(municipio_folder)
        if os.path.isdir(os.path.join(municipio_folder, e))
    ]
    log.warning(
        f"[busca] FALHA: subpasta '{nome_subpasta}' nao encontrada em {municipio_folder}. "
        f"Subpastas existentes: {subpastas}"
    )
    raise FileNotFoundError(f"Subpasta '{nome_subpasta}' nao encontrada em: {municipio_folder}")


def _find_arquivo_prefixado(subpasta_path: str, prefixo_arquivo: str) -> str:
    """Planilha .xlsm/.xlsx cujo nome comeca com prefixo_arquivo; se houver
    mais de uma, usa a de mtime mais recente. Usado na subpasta padrao."""
    prefixo_up = prefixo_arquivo.upper()
    log.info(f"[busca] Procurando arquivo '{prefixo_up}*.xls[mx]' em: {subpasta_path}")
    candidatos = []
    for entry in os.listdir(subpasta_path):
        ext = entry.lower()
        if (not eh_arquivo_trava_excel(entry)
                and (ext.endswith(".xlsm") or ext.endswith(".xlsx"))
                and entry.upper().startswith(prefixo_up)):
            candidatos.append(os.path.join(subpasta_path, entry))
    if not candidatos:
        existentes = [e for e in os.listdir(subpasta_path) if not eh_arquivo_trava_excel(e)]
        log.warning(
            f"[busca] FALHA: nenhum '{prefixo_up}*.xls[mx]' em {subpasta_path}. "
            f"Arquivos existentes: {existentes}"
        )
        raise FileNotFoundError(
            f"Nenhum arquivo '{prefixo_up}*.xls[mx]' encontrado em: {subpasta_path}"
        )
    candidatos.sort(key=os.path.getmtime, reverse=True)
    escolhido = candidatos[0]
    if len(candidatos) > 1:
        log.info(f"[busca] OK arquivo (mais recente entre {len(candidatos)}): {escolhido}")
    else:
        log.info(f"[busca] OK arquivo: {escolhido}")
    return escolhido


def _find_arquivo_mais_recente(subpasta_path: str) -> str:
    """Qualquer planilha .xlsm/.xlsx na subpasta, sem filtro de prefixo; se
    houver mais de uma, usa a de mtime mais recente. Usado na subpasta
    prioritaria (entrega) — nao segue a convencao de nome da auditoria."""
    log.info(f"[busca] Procurando planilha (.xlsm/.xlsx) mais recente em: {subpasta_path}")
    candidatos = []
    for entry in os.listdir(subpasta_path):
        ext = entry.lower()
        if not eh_arquivo_trava_excel(entry) and (ext.endswith(".xlsm") or ext.endswith(".xlsx")):
            candidatos.append(os.path.join(subpasta_path, entry))
    if not candidatos:
        existentes = [e for e in os.listdir(subpasta_path) if not eh_arquivo_trava_excel(e)]
        log.warning(
            f"[busca] FALHA: nenhuma planilha .xlsm/.xlsx em {subpasta_path}. "
            f"Arquivos existentes: {existentes}"
        )
        raise FileNotFoundError(f"Nenhuma planilha .xlsm/.xlsx encontrada em: {subpasta_path}")
    candidatos.sort(key=os.path.getmtime, reverse=True)
    escolhido = candidatos[0]
    if len(candidatos) > 1:
        log.info(f"[busca] OK planilha (mais recente entre {len(candidatos)}): {escolhido}")
    else:
        log.info(f"[busca] OK planilha: {escolhido}")
    return escolhido


def _resolver_arquivo_no_municipio(municipio_folder: str, config, somente_padrao: bool = False):
    """
    Retorna (caminho_arquivo, eh_entrega) para a pasta de um municipio ja
    resolvida. Tenta a subpasta prioritaria (entrega) primeiro, a menos que
    somente_padrao=True (usado no fallback quando a entrega existe mas nao
    tem a folha obrigatoria).
    """
    prefixo              = config.LEVANTAMENTO_ARQUIVO_PREFIXO
    subpasta_prioritaria = getattr(config, "LEVANTAMENTO_SUBPASTA_PRIORITARIA", "")
    subpasta_padrao      = config.LEVANTAMENTO_SUBPASTA
    erros = []

    if not somente_padrao and subpasta_prioritaria:
        try:
            sub = _find_subpasta(municipio_folder, subpasta_prioritaria)
            arquivo = _find_arquivo_mais_recente(sub)
            return arquivo, True
        except FileNotFoundError as e:
            erros.append(str(e))

    try:
        sub = _find_subpasta(municipio_folder, subpasta_padrao)
        arquivo = _find_arquivo_prefixado(sub, prefixo)
        return arquivo, False
    except FileNotFoundError as e:
        erros.append(str(e))

    raise FileNotFoundError("; ".join(erros))


def _resolver_arquivo_em_bases(bases_por_ano, nome_municipio: str, config, somente_padrao: bool = False):
    """
    Tenta cada (ano, base) em ordem; dentro de cada uma, tenta a subpasta
    prioritaria (entrega) antes da padrao (auditoria) — ver
    _resolver_arquivo_no_municipio. Retorna (caminho, eh_entrega, ano) da
    primeira fonte encontrada. Levanta FileNotFoundError com o resumo de
    todas as tentativas se nada bater em nenhuma base.

    bases_por_ano: lista de tuplas (ano:int, base:str), ordem de tentativa.
    """
    erros = []
    for ano, base in bases_por_ano:
        try:
            folder = _find_municipio_folder(base, nome_municipio)
        except FileNotFoundError as e:
            erros.append(f"[{base}] {e}")
            continue
        try:
            arquivo, eh_entrega = _resolver_arquivo_no_municipio(folder, config, somente_padrao=somente_padrao)
            return arquivo, eh_entrega, ano
        except FileNotFoundError as e:
            erros.append(f"[{base}] {e}")
            continue
    raise FileNotFoundError(
        "Levantamento nao encontrado em nenhuma base:\n  - " + "\n  - ".join(erros)
    )


def anos_disponiveis(config, nome_municipio: str, bases_por_ano) -> list:
    """
    Sondagem rapida (so sistema de arquivos, nenhum workbook aberto) de em
    quais anos o municipio tem uma planilha de levantamento resolvivel
    (entrega ou padrao). Retorna lista de anos (int), ordem decrescente.
    """
    anos = []
    for ano, base in bases_por_ano:
        try:
            folder = _find_municipio_folder(base, nome_municipio)
            _resolver_arquivo_no_municipio(folder, config)
        except FileNotFoundError:
            continue
        anos.append(ano)
    anos.sort(reverse=True)
    return anos


def _find_sheet(wb, alvo: str) -> str:
    log.info(f"[busca] Procurando aba '{alvo}' (case-insensitive)")
    alvo_up = alvo.strip().upper()
    for nome in wb.sheetnames:
        if nome.strip().upper() == alvo_up:
            log.info(f"[busca] OK aba: '{nome}'")
            return nome
    log.warning(
        f"[busca] FALHA: aba '{alvo}' nao encontrada. "
        f"Abas disponiveis: {wb.sheetnames}"
    )
    raise ValueError(
        f"Aba '{alvo}' nao encontrada. Abas disponiveis: {', '.join(wb.sheetnames)}"
    )


def _indices_case_insensitive(cabecalho, nomes):
    """
    Retorna { nome_canonico_como_em_'nomes': idx_ou_None }.
    """
    norm = [str(c).strip().upper() if c is not None else "" for c in cabecalho]
    resultado = {}
    for nome in nomes:
        n = nome.strip().upper()
        resultado[nome] = norm.index(n) if n in norm else None
    return resultado


def _indice_coluna_id(cabecalho, colunas_id):
    """
    Primeiro indice do cabecalho cujo nome bata (exato, case-insensitive)
    com um dos nomes em colunas_id — varredura da esquerda para a direita.
    Uma segunda coluna com o mesmo nome (ex.: "ID_PONTO" duplicado) e
    ignorada, so a primeira ocorrencia conta.
    """
    alvo = {c.strip().upper() for c in colunas_id}
    norm = [str(c).strip().upper() if c is not None else "" for c in cabecalho]
    for i, nome in enumerate(norm):
        if nome in alvo:
            return i
    return None


# -----------------------------------------------------------------------------
# Parsing de coordenadas (LATITUDE / LONGITUDE com virgula)
# -----------------------------------------------------------------------------

_MINUS_VARIANTS = ("−", "–", "—")  # −, –, —


def _parse_coord(v):
    """Aceita float, int ou string com ',' ou '.'. Retorna float ou None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        f = float(v)
        return f if f == f else None  # rejeita NaN
    s = str(v).strip()
    if not s:
        return None
    for m in _MINUS_VARIANTS:
        s = s.replace(m, "-")
    s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _coord_valida(lat, lng):
    if lat is None or lng is None:
        return False
    if not (-90.0 <= lat <= 90.0):
        return False
    if not (-180.0 <= lng <= 180.0):
        return False
    if lat == 0.0 and lng == 0.0:
        return False
    return True


# -----------------------------------------------------------------------------
# Processamento das linhas
# -----------------------------------------------------------------------------

def _valor(linha, idx):
    if idx is None or idx >= len(linha):
        return ""
    v = linha[idx]
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y %H:%M:%S")
    return str(v).strip()


def _parse_pontos_de_linhas(linhas, idx_map, idx_lat, idx_lon, colunas, idx_id):
    """
    linhas    -> iteravel de tuplas (linhas de dados, sem cabecalho)
    idx_map   -> { nome_canonico: idx_ou_None } das colunas a expor
    idx_lat   -> indice da coluna LATITUDE
    idx_lon   -> indice da coluna LONGITUDE
    colunas   -> lista ordenada de nomes canonicos (preserva ordem no dict)
    idx_id    -> indice da coluna de identidade (ID_PONTO/ID) ou None

    Nao calcula __stacked/__stack_size aqui — isso e feito uma unica vez,
    sobre o conjunto ja mesclado de todas as categorias (ver
    _computar_stacking), senao pontos da mesma coordenada em folhas
    diferentes ficariam em grupos de stacking separados.
    """
    pontos = []
    for linha in linhas:
        if not linha:
            continue
        lat = _parse_coord(linha[idx_lat]) if idx_lat is not None and idx_lat < len(linha) else None
        lng = _parse_coord(linha[idx_lon]) if idx_lon is not None and idx_lon < len(linha) else None
        if not _coord_valida(lat, lng):
            continue

        ponto = {"lat": lat, "lng": lng}
        for nome in colunas:
            ponto[nome] = _valor(linha, idx_map.get(nome))

        valor_id = _valor(linha, idx_id) if idx_id is not None else ""
        ponto["__id"] = valor_id.strip().upper()
        if not ponto.get("ID_PONTO") and valor_id:
            ponto["ID_PONTO"] = valor_id

        pontos.append(ponto)

    return pontos


def _computar_stacking(pontos):
    """Anota __stacked/__stack_size/__stack_key por coordenada (arredondada
    a 6 casas), sobre a lista completa (todas as categorias mescladas)."""
    grupos = {}
    for p in pontos:
        chave = f"{round(p['lat'], 6)},{round(p['lng'], 6)}"
        grupos.setdefault(chave, []).append(p)
    for chave, grupo in grupos.items():
        stacked = len(grupo) > 1
        for p in grupo:
            p["__stacked"] = stacked
            p["__stack_size"] = len(grupo)
            p["__stack_key"] = chave
    return pontos


# -----------------------------------------------------------------------------
# Leitura multi-folha (categorias) — usada quando o arquivo veio da subpasta
# prioritaria (entrega)
# -----------------------------------------------------------------------------

def _ler_folha_workbook(wb, nome_sheet, col_lat, col_lon, colunas, colunas_id):
    sheet  = wb[nome_sheet]
    linhas = list(sheet.iter_rows(values_only=True))
    if not linhas:
        return []
    cabecalho = linhas[0]
    idx_map = _indices_case_insensitive(cabecalho, colunas)
    lat_map = _indices_case_insensitive(cabecalho, [col_lat])
    lon_map = _indices_case_insensitive(cabecalho, [col_lon])
    idx_lat = lat_map[col_lat]
    idx_lon = lon_map[col_lon]
    if idx_lat is None or idx_lon is None:
        raise ValueError(
            f"Colunas {col_lat}/{col_lon} nao encontradas na folha '{nome_sheet}'. "
            f"Cabecalho: {', '.join(str(c) for c in cabecalho)}"
        )
    idx_id = _indice_coluna_id(cabecalho, colunas_id)
    return _parse_pontos_de_linhas(linhas[1:], idx_map, idx_lat, idx_lon, colunas, idx_id)


def _montar_categorias(wb, config, eh_entrega: bool):
    """
    Le a folha obrigatoria e, se eh_entrega, as folhas extras configuradas
    em LEVANTAMENTO_ABAS_EXTRAS. Retorna (pontos, categorias) ou None se a
    folha obrigatoria nao existir neste workbook — sinal para o chamador
    cair para a subpasta padrao (auditoria).

    Regras (ver CLAUDE.md / plano da feature):
    - Um ponto (identificado pela coluna ID_PONTO/ID) aparece em uma unica
      categoria; se repetir em folha posterior, a repeticao e descartada.
    - Excecao: a folha "sobreposta" (LEVANTAMENTO_ABA_SOBREPOSTA, tipicamente
      transformadores) tem pontos que TAMBEM existem na folha obrigatoria.
      Ela nao participa do dedup; em vez disso, os pontos correspondentes da
      folha obrigatoria sao marcados __coberto=True (o frontend os esconde
      quando essa categoria e marcada, dando lugar ao ponto sobreposto).
    - Categoria derivada "origem + alvo": pontos da folha de origem
      (LEVANTAMENTO_ABA_CIRCUITO_ORIGEM) cujo circuito (COLUNA_CIRCUITO) nao
      existe na folha alvo (LEVANTAMENTO_ABA_CIRCUITO_ALVO) saem da
      categoria de origem e formam uma categoria propria.
    """
    col_lat    = config.COLUNA_LAT
    col_lon    = config.COLUNA_LON
    colunas    = list(config.COLUNAS_LEVANTAMENTO)
    colunas_id = getattr(config, "COLUNAS_ID", ["ID_PONTO", "ID"])
    aba_obrig  = config.LEVANTAMENTO_ABA

    try:
        sheet_obrig = _find_sheet(wb, aba_obrig)
    except ValueError:
        return None

    pontos_base = _ler_folha_workbook(wb, sheet_obrig, col_lat, col_lon, colunas, colunas_id)
    for p in pontos_base:
        p["__cat"] = "base"
    log.info(f"[levantamento] Folha obrigatoria: {len(pontos_base)} pontos")

    categoria_base = {
        "id": "base", "rotulo": aba_obrig, "cor": None,
        "total": len(pontos_base), "papel": "base", "padrao_visivel": True,
    }

    if not eh_entrega:
        todos = pontos_base
        _computar_stacking(todos)
        return todos, [categoria_base]

    abas_extras     = list(getattr(config, "LEVANTAMENTO_ABAS_EXTRAS", []))
    aba_sobreposta  = getattr(config, "LEVANTAMENTO_ABA_SOBREPOSTA", None)
    aba_circ_origem = getattr(config, "LEVANTAMENTO_ABA_CIRCUITO_ORIGEM", None)
    aba_circ_alvo   = getattr(config, "LEVANTAMENTO_ABA_CIRCUITO_ALVO", None)
    col_circuito    = getattr(config, "COLUNA_CIRCUITO", "MEDIDOR_NC")
    paleta          = getattr(config, "PALETA_CATEGORIAS", None) or ["#7C6FF7"]

    ids_vistos = {p["__id"] for p in pontos_base if p["__id"]}

    categorias          = [categoria_base]
    pontos_extras       = {}   # nome_folha (normalizado) -> pontos ja deduplicados, com __cat
    pontos_sobrepostos  = []
    cat_id_por_folha    = {}
    idx_cat = 0

    for nome_folha in abas_extras:
        chave_folha = nome_folha.strip().upper()
        try:
            sheet_name = _find_sheet(wb, nome_folha)
        except ValueError:
            log.info(f"[levantamento] Folha extra '{nome_folha}' ausente — ignorada")
            continue
        try:
            pontos_folha = _ler_folha_workbook(wb, sheet_name, col_lat, col_lon, colunas, colunas_id)
        except ValueError as e:
            log.warning(f"[levantamento] Folha extra '{nome_folha}' invalida — ignorada: {e}")
            continue

        eh_sobreposta = bool(aba_sobreposta) and chave_folha == aba_sobreposta.strip().upper()
        if eh_sobreposta:
            for p in pontos_folha:
                p["__cat"] = "sobreposta"
            pontos_sobrepostos = pontos_folha
            categorias.append({
                "id": "sobreposta", "rotulo": nome_folha,
                "cor": paleta[idx_cat % len(paleta)],
                "total": len(pontos_folha), "papel": "sobreposta",
                "padrao_visivel": False,
            })
            idx_cat += 1
            continue

        cat_id = f"c{idx_cat}"
        novos = []
        for p in pontos_folha:
            pid = p["__id"]
            if pid and pid in ids_vistos:
                continue
            if pid:
                ids_vistos.add(pid)
            p["__cat"] = cat_id
            novos.append(p)

        pontos_extras[chave_folha] = novos
        cat_id_por_folha[chave_folha] = cat_id
        categorias.append({
            "id": cat_id, "rotulo": nome_folha,
            "cor": paleta[idx_cat % len(paleta)],
            "total": len(novos), "papel": "normal", "padrao_visivel": True,
        })
        idx_cat += 1
        log.info(
            f"[levantamento] Folha extra '{nome_folha}': "
            f"{len(novos)}/{len(pontos_folha)} pontos novos (resto duplicado, descartado)"
        )

    # --- categoria derivada: pontos de origem cujo circuito nao esta no alvo ---
    if aba_circ_origem and aba_circ_alvo:
        chave_origem = aba_circ_origem.strip().upper()
        chave_alvo   = aba_circ_alvo.strip().upper()
        pontos_origem = pontos_extras.get(chave_origem)
        pontos_alvo   = pontos_extras.get(chave_alvo)
        if pontos_origem is not None and pontos_alvo is not None:
            circuitos_alvo = {
                str(p.get(col_circuito, "")).strip().upper()
                for p in pontos_alvo
                if str(p.get(col_circuito, "")).strip()
            }
            cat_id_origem   = cat_id_por_folha[chave_origem]
            cat_id_derivada = f"c{idx_cat}"
            movidos = 0
            for p in pontos_origem:
                circ = str(p.get(col_circuito, "")).strip().upper()
                if circ and circ not in circuitos_alvo:
                    p["__cat"] = cat_id_derivada
                    movidos += 1
            if movidos:
                for c in categorias:
                    if c["id"] == cat_id_origem:
                        c["total"] -= movidos
                        break
                categorias.append({
                    "id": cat_id_derivada,
                    "rotulo": f"{aba_circ_origem} + {aba_circ_alvo}",
                    "cor": paleta[idx_cat % len(paleta)],
                    "total": movidos, "papel": "derivada", "padrao_visivel": True,
                })
                idx_cat += 1
            log.info(
                f"[levantamento] Categoria derivada '{aba_circ_origem} + {aba_circ_alvo}': "
                f"{movidos} pontos"
            )
        else:
            log.info(
                "[levantamento] Categoria derivada nao calculada — "
                "folha de origem ou de alvo ausente/invalida nesta planilha"
            )

    # --- sobreposicao: pontos da base cobertos por um ponto da folha sobreposta ---
    if pontos_sobrepostos:
        ids_sobrepostos = {p["__id"] for p in pontos_sobrepostos if p["__id"]}
        cobertos = 0
        for p in pontos_base:
            if p["__id"] and p["__id"] in ids_sobrepostos:
                p["__coberto"] = True
                cobertos += 1
        log.info(f"[levantamento] {cobertos} pontos da base cobertos por pontos sobrepostos")

    todos = list(pontos_base)
    for pontos_folha in pontos_extras.values():
        todos.extend(pontos_folha)
    todos.extend(pontos_sobrepostos)

    _computar_stacking(todos)
    return todos, categorias


# -----------------------------------------------------------------------------
# Cache slug
# -----------------------------------------------------------------------------

def _slug(nome: str) -> str:
    return re.sub(r"[^\w\-]+", "_", nome.upper()).strip("_") or "MUNICIPIO"


# -----------------------------------------------------------------------------
# Abertura do workbook + orquestracao do cache
# -----------------------------------------------------------------------------

CACHE_SCHEMA = 2  # bump quando o formato do cache (categorias/entrega/ano) mudar


def _tentar_ler_arquivo(xlsm: str, eh_entrega: bool, config):
    """
    Abre o workbook e monta pontos/categorias via _montar_categorias().
    Retorna None se a folha obrigatoria nao existir neste arquivo — sinal
    para o chamador tentar a subpasta padrao.
    """
    log.info(
        f"[levantamento] Lendo {os.path.basename(xlsm)}"
        + (" (entrega)" if eh_entrega else "")
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        try:
            wb, tmp = abrir_workbook_somente_leitura(xlsm)
        except PermissionError:
            raise
        except Exception as e:
            raise RuntimeError(f"Erro ao abrir planilha: {e}")

        try:
            return _montar_categorias(wb, config, eh_entrega)
        finally:
            wb.close()
            limpar_temp(tmp)


def _ler_cache(cache_path: str, slug: str):
    """Le o cache bruto do disco (dict) ou None se nao existir/for invalido.
    Nao valida schema/mtime/arquivo — quem chama decide o que fazer."""
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log.warning(f"[cache-lev] Erro lendo cache {slug}: {e}")
        return None


def _cache_path_do_ano(config, slug: str, ano) -> str:
    cache_dir = config.LEVANTAMENTOS_CACHE_DIR
    nome = f"{slug}__{ano}.json" if ano is not None else f"{slug}.json"
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), cache_dir, nome)


def carregar_levantamento(config, nome_municipio: str, bases=None):
    """
    Le o levantamento do municipio. Usa cache por mtime + caminho do arquivo,
    um arquivo de cache por ano (ver _cache_path_do_ano). Retorna
    {"pontos": [...], "categorias": [...], "entrega": bool, "ano": int|None}.

    bases: lista de tuplas (ano:int, base:str) para procurar em ordem.
    Quando None, usa config.LEVANTAMENTOS_BASES_POR_ANO (todos os anos
    configurados, do mais recente ao mais antigo).

    Prioridade dentro de cada base: subpasta prioritaria (entrega) antes da
    subpasta padrao (auditoria) — ver _resolver_arquivo_em_bases. Se a
    entrega existir mas nao tiver a folha obrigatoria, cai para a subpasta
    padrao na mesma base (a "categorias" fica vazia nesse caso).

    Se a planilha existir mas nao puder ser lida (Excel/OneDrive segurando a
    trava mesmo apos a tentativa de copia temporaria — ver excel_util), o
    ultimo cache valido para este municipio e servido no lugar, com
    "stale": True, em vez de propagar o erro.
    """
    slug = _slug(nome_municipio)

    if not bases:
        bases = config.LEVANTAMENTOS_BASES_POR_ANO

    xlsm, eh_entrega, ano = _resolver_arquivo_em_bases(bases, nome_municipio, config)
    mtime = os.path.getmtime(xlsm)
    cache_path = _cache_path_do_ano(config, slug, ano)

    # Tenta cache
    cache = _ler_cache(cache_path, slug)
    if (cache and cache.get("schema") == CACHE_SCHEMA
            and cache.get("mtime") == mtime and cache.get("arquivo") == xlsm):
        log.info(
            f"[cache-lev] Hit {slug} ({ano}) - {cache.get('total_pontos', '?')} pontos "
            f"({cache.get('gerado_em', '?')})"
        )
        return {
            "pontos":     cache["dados"],
            "categorias": cache.get("categorias", []),
            "entrega":    cache.get("entrega", False),
            "ano":        cache.get("ano", ano),
            "stale":      False,
        }
    if cache:
        log.info(f"[cache-lev] Invalidado {slug} ({ano}) (mtime/arquivo/schema mudou)")

    try:
        resultado = _tentar_ler_arquivo(xlsm, eh_entrega, config)

        if resultado is None:
            if not eh_entrega:
                raise ValueError(
                    f"Folha obrigatoria '{config.LEVANTAMENTO_ABA}' nao encontrada em "
                    f"{os.path.basename(xlsm)}"
                )
            log.warning(
                f"[levantamento] Entrega ({os.path.basename(xlsm)}) sem a folha obrigatoria "
                f"'{config.LEVANTAMENTO_ABA}' — tentando subpasta padrao"
            )
            xlsm, eh_entrega, ano = _resolver_arquivo_em_bases(bases, nome_municipio, config, somente_padrao=True)
            mtime = os.path.getmtime(xlsm)
            cache_path = _cache_path_do_ano(config, slug, ano)
            resultado = _tentar_ler_arquivo(xlsm, eh_entrega, config)
            if resultado is None:
                raise ValueError(
                    f"Folha obrigatoria '{config.LEVANTAMENTO_ABA}' nao encontrada em "
                    f"{os.path.basename(xlsm)}"
                )
    except PermissionError:
        if not cache or cache.get("schema") != CACHE_SCHEMA:
            raise
        log.warning(
            f"[cache-lev] Planilha em uso — servindo ultimo cache de {slug} ({ano}) "
            f"({cache.get('gerado_em', '?')})"
        )
        return {
            "pontos":     cache["dados"],
            "categorias": cache.get("categorias", []),
            "entrega":    cache.get("entrega", False),
            "ano":        cache.get("ano", ano),
            "stale":      True,
            "gerado_em":  cache.get("gerado_em"),
        }

    pontos, categorias = resultado
    log.info(f"[levantamento] {len(pontos)} pontos validos em {slug} ({ano})")

    # Salva cache
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    novo = {
        "schema":        CACHE_SCHEMA,
        "mtime":         mtime,
        "arquivo":       xlsm,
        "municipio":     nome_municipio,
        "entrega":       eh_entrega,
        "ano":           ano,
        "gerado_em":     datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "total_pontos":  len(pontos),
        "categorias":    categorias,
        "dados":         pontos,
    }
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(novo, f, ensure_ascii=False, indent=2)
        log.info(f"[cache-lev] Salvo {slug} ({ano})")
    except Exception as e:
        log.warning(f"[cache-lev] Nao foi possivel salvar cache {slug} ({ano}): {e}")

    return {"pontos": pontos, "categorias": categorias, "entrega": eh_entrega, "ano": ano, "stale": False}
