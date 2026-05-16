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
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(__file__))

import config
from planilha_reader import carregar_dados
from levantamento_reader import carregar_levantamento
from transformadores_reader import carregar_transformadores

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
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/municipios")
def municipios():
    try:
        dados = _get_dados()
    except FileNotFoundError as e:
        return jsonify({"erro": str(e)}), 404
    except Exception as e:
        log.error(f"Erro ao carregar dados: {e}")
        return jsonify({"erro": str(e)}), 500

    resultado = {}
    for codigo, info in dados.items():
        status = info.get("status", "")
        cor = config.STATUS_CORES.get(status, config.COR_SEM_DADO)
        resultado[codigo] = {
            "status":    status,
            "cor":       cor,
            "tipo":      info.get("tipo", ""),
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
    except Exception as e:
        log.error(f"Erro no reload: {e}")
        return jsonify({"ok": False, "erro": str(e)}), 500


@app.route("/transformadores/<path:key>")
def transformadores(key):
    try:
        nome = _resolver_nome(key)
        pontos = carregar_transformadores(config, nome)
        return jsonify({
            "municipio": nome,
            "total":     len(pontos),
            "pontos":    pontos,
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


@app.route("/levantamento/<path:key>")
def levantamento(key):
    try:
        nome = _resolver_nome(key)
        dados = carregar_levantamento(config, nome)
        return jsonify({
            "municipio": nome,
            "total":     len(dados),
            "pontos":    dados,
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
    log.info("  Mapa Municipal — SATEL")
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
        log.warning("  O mapa abrira sem dados. Corrija config.py e clique em Recarregar.")

    log.info(f"  Acesse: http://localhost:{config.SERVER_PORT}")
    log.info("=" * 52)

    app.run(host="0.0.0.0", port=config.SERVER_PORT, debug=False)
