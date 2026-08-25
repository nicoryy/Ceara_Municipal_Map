"""
server.py
Servidor local leve — Flask.

Endpoints:
  GET  /municipios     retorna dados da planilha com cor (cache automatico)
  POST /reload         forca releitura da planilha
  GET  /status         info do cache atual
  GET  /               serve o frontend
"""

import sys
import os
import io
import json
import re
import threading
import time
import uuid
import zipfile
import logging
from datetime import datetime
from flask import Flask, jsonify, send_from_directory, send_file, request
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(__file__))

import config
from planilha_reader import carregar_dados
from levantamento_reader import carregar_levantamento
from transformadores_reader import carregar_transformadores
from areas_inacessiveis_reader import carregar_areas_inacessiveis
from duplicadas import detectar_duplicadas, exportar_xlsx, nome_arquivo_duplicados
from geometria_util import geometria_para
from fotos_reader import buscar_fotos_camera

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "../frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR)
CORS(app)

# Cache em memoria
_estado = {
    "dados":      None,
    "fonte":      None,
    "gerado_em":  None,
    "total":      0,
}


def _get_dados(forcar=False):
    global _estado
    dados, fonte = carregar_dados(config, forcar=forcar)
    _estado = {
        "dados":     dados,
        "fonte":     fonte,
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "total":     len(dados),
    }
    return dados


# Mapa IBGE -> Nome do municipio, lido do GeoJSON do frontend (lazy, 1x).
_ibge_to_nome_cache = None


def _carregar_ibge_to_nome():
    global _ibge_to_nome_cache
    if _ibge_to_nome_cache is not None:
        return _ibge_to_nome_cache
    geojson_path = os.path.join(FRONTEND_DIR, "municipios_ce.geojson")
    with open(geojson_path, "r", encoding="utf-8") as f:
        gj = json.load(f)
    mapa = {}
    for feat in gj.get("features", []):
        props = feat.get("properties", {}) or {}
        ibge = props.get("codigo_ibg") or props.get("codigo_ibge") or props.get("CD_MUN")
        nome = props.get("Municipio") or props.get("NM_MUN") or props.get("municipio")
        if ibge and nome:
            mapa[str(ibge).zfill(7)] = str(nome)
    _ibge_to_nome_cache = mapa
    log.info(f"[geojson] IBGE->Nome carregado: {len(mapa)} municipios")
    return mapa


def _resolver_nome(key: str) -> str:
    """
    Converte a chave da URL no nome do municipio usado para localizar a pasta.
    - 7 digitos numericos: IBGE -> nome via GeoJSON
    - Caso contrario: trata como nome direto (ex: 'FORTALEZA - REGIONAL 5')
    """
    k = key.strip()
    if k.isdigit() and len(k) <= 7:
        mapa = _carregar_ibge_to_nome()
        ibge = k.zfill(7)
        nome = mapa.get(ibge)
        if not nome:
            raise FileNotFoundError(f"IBGE {ibge} nao encontrado no GeoJSON.")
        return nome
    return k


# ─────────────────────────────────────────────────────────────────────────────
# Job runner em memoria — usado por /duplicadas e /galeria, que rodam em
# segundo plano (threading.Thread) pra nao bloquear o Flask dev server
# (que ja roda threaded, entao requests concorrentes continuam respondendo
# enquanto um job roda). Jobs somem sozinhos apos _JOB_TTL_SEGUNDOS.
# ─────────────────────────────────────────────────────────────────────────────

_jobs = {}
_jobs_lock = threading.Lock()
_JOB_TTL_SEGUNDOS = 3600


def _criar_job(tipo: str, total: int = 0) -> str:
    agora = time.time()
    with _jobs_lock:
        expirados = [jid for jid, j in _jobs.items() if agora - j["criado_em"] > _JOB_TTL_SEGUNDOS]
        for jid in expirados:
            del _jobs[jid]
        job_id = uuid.uuid4().hex[:12]
        _jobs[job_id] = {
            "tipo": tipo, "estado": "executando", "feito": 0, "total": total,
            "erro": None, "resultado": None, "fotos": [], "alvo_fotos": 0, "criado_em": agora,
        }
    return job_id


def _atualizar_job(job_id: str, **kwargs):
    with _jobs_lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def _registrar_progresso_fotos(job_id: str, feito: int, total: int, novas_fotos: list):
    """Callback de progresso da galeria (ver fotos_reader.buscar_fotos_camera) —
    vai acumulando o resultado parcial no job pra permitir carregamento
    progressivo no frontend, sem esperar o job inteiro terminar."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job:
            job["feito"] = feito
            job["total"] = total
            job["fotos"].extend(novas_fotos)


def _obter_job(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        copia = dict(job)
        # "fotos" e uma lista mutavel que o thread do job pode continuar
        # alterando (.extend) depois desta copia — copiar tambem a lista,
        # senao um poll concorrente serializa ela num estado inconsistente.
        if isinstance(copia.get("fotos"), list):
            copia["fotos"] = list(copia["fotos"])
        return copia


def _bases_levantamento_ordenadas() -> list:
    """
    Bases de levantamento ordenadas por ano decrescente — sempre comeca pelo
    ano mais recente e cai em fallback ate o mais antigo definido.

    - LEVANTAMENTOS_BASE_PATH e tratada como a base do ano atual (mais recente).
    - LEVANTAMENTOS_BASE_PATH_<ANO> sao bases de anos anteriores; o sufixo
      numerico do attr define a ordem (maior primeiro).
    Entradas vazias/None sao ignoradas.
    """
    base_atual = getattr(config, "LEVANTAMENTOS_BASE_PATH", None)
    anteriores = []
    for attr in dir(config):
        m = re.fullmatch(r"LEVANTAMENTOS_BASE_PATH_(\d{4})", attr)
        if not m:
            continue
        val = getattr(config, attr, None)
        if val:
            anteriores.append((int(m.group(1)), val))
    anteriores.sort(key=lambda t: t[0], reverse=True)
    return [b for b in [base_atual, *(v for _, v in anteriores)] if b]


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/municipios")
def municipios():
    try:
        dados = _get_dados()
    except FileNotFoundError as e:
        return jsonify({"erro": str(e)}), 404
    except PermissionError as e:
        log.warning(f"[municipios] 503: {e}")
        return jsonify({"erro": str(e)}), 503
    except Exception as e:
        log.error(f"Erro ao carregar dados: {e}")
        return jsonify({"erro": str(e)}), 500

    resultado = {}
    for codigo, info in dados.items():
        bruto  = info.get("status", "")
        chave  = config.normalizar_status(bruto)
        cor    = config.STATUS_CORES.get(chave, config.COR_SEM_DADO)
        rotulo = config.STATUS_ROTULOS.get(chave, bruto)
        resultado[codigo] = {
            "status":    rotulo,
            "cor":       cor,
            "ordem":     config.STATUS_ORDEM.get(chave, 999),
            "tipo":      info.get("tipo", ""),
            "ano":       info.get("ano", ""),
            "municipio": info.get("municipio", ""),
        }

    return jsonify(resultado)


@app.route("/reload", methods=["POST"])
def reload_dados():
    try:
        dados = _get_dados(forcar=True)
        return jsonify({
            "ok":        True,
            "total":     len(dados),
            "fonte":     _estado["fonte"],
            "gerado_em": _estado["gerado_em"],
        })
    except PermissionError as e:
        log.warning(f"[reload] 503: {e}")
        return jsonify({"ok": False, "erro": str(e)}), 503
    except Exception as e:
        log.error(f"Erro no reload: {e}")
        return jsonify({"ok": False, "erro": str(e)}), 500


@app.route("/transformadores/<path:key>")
def transformadores(key):
    try:
        nome = _resolver_nome(key)
        grupos = carregar_transformadores(config, nome)
        total = sum(len(g.get("pontos", [])) for g in grupos)
        return jsonify({
            "municipio": nome,
            "total":     total,
            "arquivos":  grupos,
        })
    except FileNotFoundError as e:
        log.warning(f"[transformadores] 404: {e}")
        return jsonify({"erro": str(e)}), 404
    except PermissionError as e:
        log.warning(f"[transformadores] 503: {e}")
        return jsonify({"erro": str(e)}), 503
    except Exception as e:
        log.error(f"[transformadores] 500 ({key}): {e}")
        return jsonify({"erro": str(e)}), 500


@app.route("/areas_inacessiveis/<path:key>")
def areas_inacessiveis(key):
    try:
        nome = _resolver_nome(key)
        res  = carregar_areas_inacessiveis(config, nome)
        return jsonify({
            "municipio": nome,
            "arquivos":  res["arquivos"],
            "total":     len(res["features"]),
            "features":  res["features"],
        })
    except FileNotFoundError as e:
        log.warning(f"[areas] 404: {e}")
        return jsonify({"erro": str(e)}), 404
    except PermissionError as e:
        log.warning(f"[areas] 503: {e}")
        return jsonify({"erro": str(e)}), 503
    except Exception as e:
        log.error(f"[areas] 500 ({key}): {e}")
        return jsonify({"erro": str(e)}), 500


@app.route("/levantamento/<path:key>")
def levantamento(key):
    try:
        nome  = _resolver_nome(key)
        bases = _bases_levantamento_ordenadas()
        log.info(f"[levantamento] {nome} -> bases={bases}")
        resultado = carregar_levantamento(config, nome, bases=bases)
        pontos = resultado["pontos"]
        return jsonify({
            "municipio":  nome,
            "total":      len(pontos),
            "pontos":     pontos,
            "categorias": resultado.get("categorias", []),
            "entrega":    resultado.get("entrega", False),
            "stale":      resultado.get("stale", False),
            "gerado_em":  resultado.get("gerado_em"),
        })
    except FileNotFoundError as e:
        log.warning(f"[levantamento] 404: {e}")
        return jsonify({"erro": str(e)}), 404
    except PermissionError as e:
        log.warning(f"[levantamento] 503: {e}")
        return jsonify({"erro": str(e)}), 503
    except ValueError as e:
        log.warning(f"[levantamento] 400: {e}")
        return jsonify({"erro": str(e)}), 400
    except Exception as e:
        log.error(f"[levantamento] 500 ({key}): {e}")
        return jsonify({"erro": str(e)}), 500


@app.route("/duplicadas/<path:key>", methods=["POST"])
def duplicadas_iniciar(key):
    """Inicia em segundo plano a deteccao de duplicadas (porte do script
    QGIS — ver backend/duplicadas.py) e devolve um job_id pra acompanhar o
    progresso em /duplicadas/progresso/<job_id> e baixar o resultado em
    /duplicadas/download/<job_id>."""
    try:
        nome = _resolver_nome(key)
    except FileNotFoundError as e:
        return jsonify({"erro": str(e)}), 404

    job_id = _criar_job("duplicadas", total=1)

    def _run():
        try:
            bases = _bases_levantamento_ordenadas()
            resultado_lev = carregar_levantamento(config, nome, bases=bases)
            pontos = resultado_lev["pontos"]
            geometria = geometria_para(key, nome)
            resultado = detectar_duplicadas(
                pontos, geometria=geometria, raio_metros=config.DUPLICADAS_RAIO_METROS
            )
            buf = exportar_xlsx(resultado, config.COLUNAS_LEVANTAMENTO)
            _atualizar_job(job_id, estado="concluido", feito=1, resultado={
                "arquivo":        nome_arquivo_duplicados(nome),
                "bytes":          buf.getvalue(),
                "total_clusters": len(resultado["clusters"]),
                "total_pontos":   sum(len(c["pontos"]) for c in resultado["clusters"]),
                "excluidos_fora_limite": resultado["excluidos_fora_limite"],
            })
        except Exception as e:
            log.error(f"[duplicadas] job {job_id} falhou: {e}")
            _atualizar_job(job_id, estado="erro", erro=str(e))

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id, "municipio": nome})


@app.route("/duplicadas/progresso/<job_id>")
def duplicadas_progresso(job_id):
    job = _obter_job(job_id)
    if not job or job["tipo"] != "duplicadas":
        return jsonify({"erro": "Job nao encontrado"}), 404
    resp = {"estado": job["estado"], "feito": job["feito"], "total": job["total"], "erro": job["erro"]}
    if job["estado"] == "concluido":
        r = job["resultado"]
        resp["total_clusters"] = r["total_clusters"]
        resp["total_pontos"]   = r["total_pontos"]
    return jsonify(resp)


@app.route("/duplicadas/download/<job_id>")
def duplicadas_download(job_id):
    job = _obter_job(job_id)
    if not job or job["tipo"] != "duplicadas" or job["estado"] != "concluido":
        return jsonify({"erro": "Job nao encontrado ou nao concluido"}), 404
    r = job["resultado"]
    buf = io.BytesIO(r["bytes"])
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=r["arquivo"],
    )


ALVO_FOTOS_PADRAO = 60   # 2 paginas de 30 — usado se o frontend nao mandar alvo_fotos


@app.route("/galeria/iniciar", methods=["POST"])
def galeria_iniciar():
    """Inicia em segundo plano a busca das fotos de camera (ver
    backend/fotos_reader.py) para a lista de pontos filtrados que o
    frontend ja calculou. Corpo: {"municipio": <key>, "pontos": [{"id_ponto","link"}],
    "alvo_fotos": N}. So busca fotos ate acumular `alvo_fotos` e entao pausa —
    o resto so e liberado via POST /galeria/liberar/<job_id> (ver essa rota),
    conforme o usuario navega pelas paginas da galeria."""
    body = request.get_json(silent=True) or {}
    key    = str(body.get("municipio", "")).strip()
    pontos = body.get("pontos")
    alvo   = body.get("alvo_fotos")

    if not key:
        return jsonify({"erro": "Campo 'municipio' obrigatorio"}), 400
    if not isinstance(pontos, list) or not pontos:
        return jsonify({"erro": "Nenhum ponto com LINK_RELATORIO no filtro atual"}), 400
    if not isinstance(alvo, int) or alvo <= 0:
        alvo = ALVO_FOTOS_PADRAO

    try:
        nome = _resolver_nome(key)
    except FileNotFoundError as e:
        return jsonify({"erro": str(e)}), 404

    slug = re.sub(r"[^\w\-]+", "_", nome.upper()).strip("_") or "MUNICIPIO"
    job_id = _criar_job("galeria", total=len(pontos))
    _atualizar_job(job_id, alvo_fotos=alvo)

    def _progresso(feito, total, novas_fotos):
        _registrar_progresso_fotos(job_id, feito, total, novas_fotos)

    def _pode_continuar():
        job = _obter_job(job_id)
        return bool(job) and len(job.get("fotos", [])) < job.get("alvo_fotos", 0)

    def _run():
        try:
            fotos, erros = buscar_fotos_camera(
                pontos, slug, config.FOTOS_CACHE_DIR,
                max_workers=config.GALERIA_MAX_WORKERS,
                delay_entre_lotes=config.GALERIA_DELAY_ENTRE_LOTES_SEGUNDOS,
                on_progresso=_progresso, pode_continuar=_pode_continuar,
            )
            _atualizar_job(job_id, estado="concluido", resultado={"erros": erros})
        except Exception as e:
            log.error(f"[galeria] job {job_id} falhou: {e}")
            _atualizar_job(job_id, estado="erro", erro=str(e))

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"job_id": job_id, "municipio": nome, "total": len(pontos)})


@app.route("/galeria/liberar/<job_id>", methods=["POST"])
def galeria_liberar(job_id):
    """Aumenta o alvo_fotos de um job de galeria ja em andamento, liberando o
    laco pausado em buscar_fotos_camera pra buscar mais um pouco (ver
    fotos_reader.buscar_fotos_camera: pode_continuar). Chamado quando o
    usuario navega pra uma pagina nova na galeria. So aumenta, nunca diminui."""
    body = request.get_json(silent=True) or {}
    alvo = body.get("alvo_fotos")
    if not isinstance(alvo, int) or alvo < 0:
        return jsonify({"erro": "Campo 'alvo_fotos' invalido"}), 400

    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job or job["tipo"] != "galeria":
            return jsonify({"erro": "Job nao encontrado"}), 404
        job["alvo_fotos"] = max(job.get("alvo_fotos", 0), alvo)
        alvo_atual = job["alvo_fotos"]

    return jsonify({"ok": True, "alvo_fotos": alvo_atual})


@app.route("/galeria/progresso/<job_id>")
def galeria_progresso(job_id):
    """Progresso + fotos acumuladas ate agora (parciais ou finais) — o
    frontend usa isso pra ir preenchendo a galeria conforme cada lote de
    requisicoes termina, em vez de esperar o job inteiro concluir."""
    job = _obter_job(job_id)
    if not job or job["tipo"] != "galeria":
        return jsonify({"erro": "Job nao encontrado"}), 404
    return jsonify({
        "estado": job["estado"], "feito": job["feito"], "total": job["total"],
        "erro": job["erro"], "fotos": job.get("fotos", []),
    })


@app.route("/export/<path:key>")
def export_municipio(key):
    """
    Retorna um ZIP com:
      - <slug>/<AREAS_INACESSIVEIS_SUB>/*.gpkg (raw, se existir)
      - <slug>/<TRANSFORMADORES_LOTES_SUB>/*.kml (raw, se existir)
    Os KMLs gerados (pontos, borda) sao montados pelo frontend.
    """
    try:
        nome = _resolver_nome(key)
    except FileNotFoundError as e:
        return jsonify({"erro": str(e)}), 404

    slug = re.sub(r"[^\w\-]+", "_", nome.upper()).strip("_") or "MUNICIPIO"

    buf = io.BytesIO()
    incluidos = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for base, sub, ext in [
            (config.AREAS_INACESSIVEIS_BASE_PATH, config.AREAS_INACESSIVEIS_SUB, ".gpkg"),
            (config.TRANSFORMADORES_BASE_PATH,    config.TRANSFORMADORES_LOTES_SUB, ".kml"),
        ]:
            try:
                from transformadores_reader import _find_municipio_folder, _normalize
                folder = _find_municipio_folder(base, nome)
            except FileNotFoundError:
                continue
            sub_path = None
            alvo = _normalize(sub)
            for entry in os.listdir(folder):
                full = os.path.join(folder, entry)
                if os.path.isdir(full) and _normalize(entry) == alvo:
                    sub_path = full
                    break
            if not sub_path:
                continue
            for entry in sorted(os.listdir(sub_path)):
                if entry.lower().endswith(ext):
                    src = os.path.join(sub_path, entry)
                    try:
                        zf.write(src, arcname=f"{slug}/{sub}/{entry}")
                        incluidos += 1
                    except Exception as e:
                        log.warning(f"[export] Erro adicionando {src}: {e}")

    if incluidos == 0:
        return jsonify({"erro": "Nenhum arquivo raw para exportar"}), 404

    buf.seek(0)
    return send_file(
        buf,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{slug}_raw.zip",
    )


@app.route("/status")
def status_endpoint():
    return jsonify({
        "cache_ativo":   _estado["dados"] is not None,
        "gerado_em":     _estado["gerado_em"],
        "fonte":         _estado["fonte"],
        "total_municipios": _estado["total"],
        "planilha_path": config.PLANILHA_PATH,
    })


# Serve o frontend
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("=" * 52)
    log.info("  Mapa Municipal")
    log.info("=" * 52)
    log.info(f"  Planilha : {config.PLANILHA_PATH}")
    log.info(f"  Aba      : {config.PLANILHA_ABA}")
    log.info(f"  GeoJSON  : {config.GEOJSON_PATH}")
    log.info(f"  Porta    : {config.SERVER_PORT}")
    log.info("=" * 52)

    try:
        _get_dados()
        log.info(f"  Dados carregados: {_estado['total']} municipios via {_estado['fonte']}")
    except Exception as e:
        log.warning(f"  Aviso na inicializacao: {e}")
        log.warning("  O mapa abrira sem dados. Corrija o .env e clique em Recarregar.")

    log.info(f"  Acesse: http://localhost:{config.SERVER_PORT}")
    log.info("=" * 52)

    app.run(host="0.0.0.0", port=config.SERVER_PORT, debug=False)
