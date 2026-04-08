"""
server.py
Servidor local leve — Flask.

Endpoints:
  GET  /municipios        retorna dados da planilha com cor (cache automatico)
  GET  /regionais         retorna dados agregados por regional
  POST /reload            forca releitura da planilha
  GET  /status            info do cache atual
  GET  /                  serve o frontend
  GET  /regionais_ce.geojson  serve o GeoJSON das regionais
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
    "dados_municipios": None,
    "dados_regionais":  None,
    "fonte":            None,
    "gerado_em":        None,
    "total":            0,
}


def _get_dados(forcar=False):
    global _estado
    dados_municipios, dados_regionais, fonte = carregar_dados(config, forcar=forcar)
    _estado = {
        "dados_municipios": dados_municipios,
        "dados_regionais":  dados_regionais,
        "fonte":            fonte,
        "gerado_em":        datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "total":            len(dados_municipios),
    }
    return dados_municipios, dados_regionais


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/municipios")
def municipios():
    try:
        dados_municipios, _ = _get_dados()
    except FileNotFoundError as e:
        return jsonify({"erro": str(e)}), 404
    except Exception as e:
        log.error(f"Erro ao carregar dados: {e}")
        return jsonify({"erro": str(e)}), 500

    resultado = {}
    for codigo, info in dados_municipios.items():
        status = info.get("status", "")
        cor = config.STATUS_CORES.get(status, config.COR_SEM_DADO)
        resultado[codigo] = {
            "status":        status,
            "cor":           cor,
            "tipo":          info.get("tipo", ""),
            "municipio":     info.get("municipio", ""),
            "regiao":        info.get("regiao", ""),
            "os":            info.get("os", []),
            "tecnicos":      info.get("tecnicos", []),
            "resumo_status": info.get("resumo_status", {}),
        }

    return jsonify(resultado)


@app.route("/regionais")
def regionais():
    try:
        _, dados_regionais = _get_dados()
    except FileNotFoundError as e:
        return jsonify({"erro": str(e)}), 404
    except Exception as e:
        log.error(f"Erro ao carregar dados: {e}")
        return jsonify({"erro": str(e)}), 500

    resultado = {}
    for regiao, info in dados_regionais.items():
        # Determina cor dominante da regional
        resumo = info.get("resumo_status", {})
        status_dominante = max(resumo, key=resumo.get) if resumo else ""
        cor = config.STATUS_CORES.get(status_dominante, config.COR_SEM_DADO)
        
        resultado[regiao] = {
            "regiao":        regiao,
            "cor":           cor,
            "status":        status_dominante,
            "os":            info.get("os", []),
            "tecnicos":      info.get("tecnicos", []),
            "resumo_status": resumo,
            "total_os":      info.get("total_os", 0),
            "total_tecnicos": info.get("total_tecnicos", 0),
            "municipios":    info.get("municipios", []),
        }

    return jsonify(resultado)


@app.route("/reload", methods=["POST"])
def reload_dados():
    try:
        dados_municipios, dados_regionais = _get_dados(forcar=True)
        return jsonify({
            "ok":              True,
            "total":           len(dados_municipios),
            "total_regionais": len(dados_regionais),
            "fonte":           _estado["fonte"],
            "gerado_em":       _estado["gerado_em"],
        })
    except Exception as e:
        log.error(f"Erro no reload: {e}")
        return jsonify({"ok": False, "erro": str(e)}), 500


@app.route("/status")
def status_endpoint():
    return jsonify({
        "cache_ativo":       _estado["dados_municipios"] is not None,
        "gerado_em":         _estado["gerado_em"],
        "fonte":             _estado["fonte"],
        "total_municipios":  _estado["total"],
        "total_regionais":   len(_estado.get("dados_regionais", {})),
        "planilha_path":     config.PLANILHA_PATH,
    })


# Serve o frontend
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)


# Serve o GeoJSON das regionais
@app.route("/regionais_ce.geojson")
def regionais_geojson():
    geojson_path = config.GEOJSON_REGIONAIS_PATH
    if not os.path.exists(geojson_path):
        return jsonify({"erro": f"GeoJSON de regionais não encontrado: {geojson_path}"}), 404
    return send_from_directory(os.path.dirname(geojson_path), os.path.basename(geojson_path))


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
    log.info(f"  Regionais: {config.GEOJSON_REGIONAIS_PATH}")
    log.info(f"  Porta    : {config.SERVER_PORT}")
    log.info("=" * 52)

    try:
        dados_mun, dados_reg = _get_dados()
        log.info(f"  Dados carregados: {_estado['total']} municipios, {len(dados_reg)} regionais via {_estado['fonte']}")
    except Exception as e:
        log.warning(f"  Aviso na inicializacao: {e}")
        log.warning("  O mapa abrira sem dados. Corrija config.py e clique em Recarregar.")

    log.info(f"  Acesse: http://localhost:{config.SERVER_PORT}")
    log.info("=" * 52)

    app.run(host="0.0.0.0", port=config.SERVER_PORT, debug=False)
