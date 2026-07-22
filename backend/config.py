# =============================================================================
# CONFIGURAÇÃO CENTRAL
# Caminhos e nomes específicos da empresa/portal ficam no .env (nunca no git).
# Copie .env.example para .env na raiz do projeto e preencha os valores.
# =============================================================================

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"))

# Usuario do Windows logado — detectado automaticamente, nao vem do .env.
# Os caminhos no .env contem so o trecho DEPOIS de "C:\Users\<usuario>\",
# assim o mesmo .env funciona em qualquer PC, independente do nome de usuario.
USERNAME = os.environ.get("USERNAME") or os.environ.get("USER")
if not USERNAME:
    raise RuntimeError("Nao foi possivel detectar o usuario do Windows (variavel USERNAME).")
USER_HOME = rf"C:\Users\{USERNAME}"


def _caminho_obrigatorio(nome):
    sufixo = os.environ.get(nome)
    if not sufixo:
        raise RuntimeError(
            f"Variavel de ambiente '{nome}' nao definida.\n"
            f"Copie .env.example para .env na raiz do projeto e preencha os caminhos "
            rf"(apenas o trecho depois de C:\Users\{USERNAME}\, começando com \)."
        )
    return USER_HOME + sufixo


def _caminho_opcional(nome):
    sufixo = os.environ.get(nome, "")
    return USER_HOME + sufixo if sufixo else ""


def _env_opcional(nome, padrao=""):
    return os.environ.get(nome, padrao)


# Caminho absoluto da planilha principal (xlsx ou xlsm) — definido em .env
PLANILHA_PATH = _caminho_obrigatorio("PLANILHA_PATH")

# Nome exato da aba que contém os dados
PLANILHA_ABA = _env_opcional("PLANILHA_ABA", "tecnico")

# Nome exato das colunas na planilha
COLUNA_CODIGO_IBGE = "codigo_ibge"   # deve conter o código de 7 dígitos ex: 2304400
COLUNA_STATUS      = "status"        # ex: "ativo", "pendente", "concluído"
COLUNA_TIPO        = "tipo"          # ex: "ressalva", "normal"
COLUNA_ANO         = "ano"           # ex: 2025, 2026
COLUNA_MUNICIPIO   = "MUNICIPIO"     # ex: "FORTALEZA - REGIONAL 1" (usado pelas regionais)

# Caminho para o GeoJSON do Ceará exportado pelo QGIS
GEOJSON_PATH = "../frontend/municipios_ce.geojson"

# Caminho para o cache gerado automaticamente pelo servidor
CACHE_PATH = "../data/cache_dados.json"

# Porta do servidor local
SERVER_PORT = int(_env_opcional("SERVER_PORT", "5000"))

# =============================================================================
# MAPEAMENTO DE STATUS → COR (hex ou nome CSS)
# Adicione/remova status conforme sua planilha
# Municípios sem dado na planilha aparecem em CINZA automaticamente
# =============================================================================
STATUS_CORES = {
    # "valor_na_planilha": "cor_hex",
    "CADASTRO FINALIZADO": "#1D9E75",   # verde
    "EM ANDAMENTO":   "#CAA800",   # amarelo
    "CAMPO PARALISADO":  "#CB7841",   # azul
    "NAO INICIADO":  "#E24B4A",   # vermelho
    # Adicione mais conforme necessário...
}

# Cor para municípios sem dado na planilha
COR_SEM_DADO = "#B4B2A9"

# Cor da borda dos municípios no mapa
COR_BORDA = "#ffffff"
LARGURA_BORDA = 0

# =============================================================================
# LEVANTAMENTO — planilhas por município (somente leitura)
# =============================================================================
# Base path onde ficam as pastas dos municípios. Estrutura esperada:
#   <BASE>/<NOME_MUNICIPIO>/AUDITORIA/<LEVANTAMENTO_ARQUIVO_PREFIXO>*.xlsm
# Comparação de nomes é case-insensitive em todas as etapas.
# LEVANTAMENTOS_BASE_PATH e a base do ano atual (obrigatoria). As demais
# LEVANTAMENTOS_BASE_PATH_<ANO> (anos anteriores) sao opcionais — o server
# descobre automaticamente todas as que existirem no .env.
LEVANTAMENTOS_BASE_PATH      = _caminho_obrigatorio("LEVANTAMENTOS_BASE_PATH")
LEVANTAMENTOS_BASE_PATH_2025 = _caminho_opcional("LEVANTAMENTOS_BASE_PATH_2025")
LEVANTAMENTOS_BASE_PATH_2024 = _caminho_opcional("LEVANTAMENTOS_BASE_PATH_2024")

# Prefixo do nome do arquivo de levantamento dentro de AUDITORIA/
LEVANTAMENTO_ARQUIVO_PREFIXO = _env_opcional("LEVANTAMENTO_ARQUIVO_PREFIXO", "FECHAMENTO")

# Diretório onde os caches por município são gravados
LEVANTAMENTOS_CACHE_DIR = "../data/cache_levantamentos"

# Aba e colunas usadas no levantamento
LEVANTAMENTO_ABA = "BASE TRATADA"
COLUNA_LAT       = "LATITUDE"
COLUNA_LON       = "LONGITUDE"

# Colunas que aparecem no painel lateral (na ordem desejada).
# Lookup case-insensitive — colunas ausentes na planilha viram string vazia.
COLUNAS_LEVANTAMENTO = [
    "ID_PONTO",
    "TRANSFORMADOR",
    "IMPRODUTIVO",
    "MEDICAO",
    "MEDIDOR_NC",
    "TIPOLAMPADA",
    "POTENCIA",
    "ESTADO_TECNICO",
    "TIPO_REDE",
    "OBSERVACAO",
    "DATA_REGISTRO",
    "Nome_Cadastrador",
    "LINK_RELATORIO",
    "PONTOTRAFO",
    "PROJETO",
]

# Cores dos pontos conforme coluna MEDICAO
COR_MEDICAO_SIM = "#7CFC00"  # verde lima
COR_MEDICAO_NAO = "#1E3A8A"  # azul escuro

# =============================================================================
# TRANSFORMADORES (KML) — visualizacao opcional de transformadores por municipio
# =============================================================================
# Estrutura esperada:
#   <BASE>/<NOME_MUNICIPIO>/LOTES/*.kml
# Nomes podem variar de caixa/acentos; o matching e feito normalizando
# nomes para apenas alfanumericos em lowercase.
TRANSFORMADORES_BASE_PATH = _caminho_opcional("TRANSFORMADORES_BASE_PATH")
TRANSFORMADORES_LOTES_SUB = "LOTES"
TRANSFORMADORES_CACHE_DIR = "../data/cache_transformadores"

# =============================================================================
# AREAS INACESSIVEIS (GPKG) - visualizacao opcional de poligonos por municipio
# =============================================================================
# Estrutura esperada:
#   <BASE>/<NOME_MUNICIPIO>/AREAS_INACESSIVEIS/*.gpkg
# Mesma logica do transformadores, mas le .gpkg (GeoPackage) ao inves de .kml.
AREAS_INACESSIVEIS_BASE_PATH = _caminho_opcional("AREAS_INACESSIVEIS_BASE_PATH")
AREAS_INACESSIVEIS_SUB       = "AREAS_INACESSIVEIS"
AREAS_INACESSIVEIS_CACHE_DIR = "../data/cache_areas_inacessiveis"
