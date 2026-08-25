# =============================================================================
# CONFIGURAÇÃO CENTRAL
# Caminhos e nomes específicos da empresa/portal ficam no .env (nunca no git).
# Copie .env.example para .env na raiz do projeto e preencha os valores.
# =============================================================================

import os
import unicodedata
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
# MAPEAMENTO DE STATUS → COR
# Adicione/remova status conforme sua planilha.
# A ordem da lista define a ordem de exibição na legenda do mapa.
# Municípios sem dado (ou com status não reconhecido) aparecem em COR_SEM_DADO.
# =============================================================================

def normalizar_status(valor):
    """Uppercase, sem acento, espaços colapsados — para lookup tolerante a
    variação de caixa/acentuação na planilha."""
    txt = unicodedata.normalize("NFKD", str(valor or ""))
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return " ".join(txt.upper().split())

STATUS_DEFINICOES = [
    # ("valor_na_planilha", "cor_hex")
    ("CAMPO NAO INICIADO",     "#f58686ff"),  # cinza
    ("ESPERANDO CAMPO",        "#6B6A66"),  # cinza escuro
    ("AUDITORIAS",             "#2F80ED"),  # azul
    ("AGUARDANDO AUDITORIAS",  "#2F80ED"),  # azul
    ("INFORMAR ERRO %",        "#2F80ED"),  # azul
    ("PRIORIDADE EDIÇÃO",      "#E24B4A"),  # vermelho
    ("REEDIÇÃO",               "#E24B4A"),  # vermelho
    ("AGUARDANDO ENTREGA",     "#E24B4A"),  # vermelho
    ("DUPLICADAS",             "#8E44AD"),  # roxo
    ("ANÁLCISE EDIÇÃO",        "#EF9F27"),  # laranja
    ("CADASTRO PARALISADO",    "#EF9F27"),  # laranja
    ("EM ANDAMENTO",           "#ffe600ff"),
    ("Z-ENTREGA REALIZADA",    "#1D9E75"),  # verde
    ("AJUSTE FINAL",           "#7B1F2B"),  # vinho
    ("AUDITORIA FINAL",        "#7B1F2B"),  # vinho
    ("NÃO SOLICITADO",         "#b1b1b1ff"),
    # Adicione mais conforme necessário...
]

STATUS_CORES   = {normalizar_status(rotulo): cor for rotulo, cor in STATUS_DEFINICOES}
STATUS_ROTULOS = {normalizar_status(rotulo): rotulo for rotulo, _ in STATUS_DEFINICOES}
STATUS_ORDEM   = {normalizar_status(rotulo): i for i, (rotulo, _) in enumerate(STATUS_DEFINICOES)}

# Cor para municípios sem dado na planilha (ou com status não reconhecido)
COR_SEM_DADO = "#1e2236"

# Cor da borda dos municípios no mapa
COR_BORDA = "#ffffff"
LARGURA_BORDA = 0

# =============================================================================
# LEVANTAMENTO — planilhas por município (somente leitura)
# =============================================================================
# Base path onde ficam as pastas dos municípios. Estrutura esperada:
#   <BASE>/<NOME_MUNICIPIO>/<LEVANTAMENTO_SUBPASTA>/<PREFIXO>*.xlsm
#   <BASE>/<NOME_MUNICIPIO>/<LEVANTAMENTO_SUBPASTA_PRIORITARIA>/<PREFIXO>*.xlsm
# A subpasta prioritária (quando existe e contém planilha válida — com a
# folha obrigatória LEVANTAMENTO_ABA) tem precedência sobre a subpasta
# padrão. Comparação de nomes é case-insensitive em todas as etapas.
# LEVANTAMENTOS_BASE_PATH e a base do ano atual (obrigatoria). As demais
# LEVANTAMENTOS_BASE_PATH_<ANO> (anos anteriores) sao opcionais — o server
# descobre automaticamente todas as que existirem no .env.
LEVANTAMENTOS_BASE_PATH      = _caminho_obrigatorio("LEVANTAMENTOS_BASE_PATH")
LEVANTAMENTOS_BASE_PATH_2025 = _caminho_opcional("LEVANTAMENTOS_BASE_PATH_2025")
LEVANTAMENTOS_BASE_PATH_2024 = _caminho_opcional("LEVANTAMENTOS_BASE_PATH_2024")

# Prefixo do nome do arquivo de levantamento dentro da subpasta
LEVANTAMENTO_ARQUIVO_PREFIXO = _env_opcional("LEVANTAMENTO_ARQUIVO_PREFIXO", "FECHAMENTO")

# Diretório onde os caches por município são gravados
LEVANTAMENTOS_CACHE_DIR = "../data/cache_levantamentos"

# Nomes de pasta e de folha são sensíveis (identificam a operação interna) —
# vêm inteiramente do .env, nunca ficam hardcoded aqui.
LEVANTAMENTO_SUBPASTA             = _env_opcional("LEVANTAMENTO_SUBPASTA")
LEVANTAMENTO_SUBPASTA_PRIORITARIA = _env_opcional("LEVANTAMENTO_SUBPASTA_PRIORITARIA")

# Folha obrigatória — sempre usada, em qualquer uma das duas subpastas.
LEVANTAMENTO_ABA = os.environ.get("LEVANTAMENTO_ABA")
if not LEVANTAMENTO_ABA:
    raise RuntimeError(
        "Variavel de ambiente 'LEVANTAMENTO_ABA' nao definida.\n"
        "Copie .env.example para .env na raiz do projeto e preencha o nome "
        "da folha obrigatoria da planilha de levantamento."
    )

# Folhas extras — só existem na planilha da subpasta prioritária. Cada uma
# vira uma categoria de pontos no mapa, na ordem declarada. Lista vazia se
# não houver subpasta prioritária configurada.
LEVANTAMENTO_ABAS_EXTRAS = [
    a.strip() for a in _env_opcional("LEVANTAMENTO_ABAS_EXTRAS").split("|") if a.strip()
]

# Qual folha extra (se houver) tem pontos que também existem na folha
# obrigatória e devem sobrepor o ponto correspondente quando marcada.
LEVANTAMENTO_ABA_SOBREPOSTA = _env_opcional("LEVANTAMENTO_ABA_SOBREPOSTA") or None

# Par origem/alvo para a categoria derivada "origem + alvo" (ver
# levantamento_reader.py). None se o par não estiver configurado.
LEVANTAMENTO_ABA_CIRCUITO_ORIGEM = _env_opcional("LEVANTAMENTO_ABA_CIRCUITO_ORIGEM") or None
LEVANTAMENTO_ABA_CIRCUITO_ALVO   = _env_opcional("LEVANTAMENTO_ABA_CIRCUITO_ALVO") or None

# Coluna de circuito usada para calcular a categoria derivada acima.
COLUNA_CIRCUITO = "MEDIDOR_NC"

# Nomes de coluna aceitos para a identidade do ponto (dedup entre folhas).
# Sempre a PRIMEIRA coluna do cabeçalho cujo nome bata com um destes.
COLUNAS_ID = ["ID_PONTO", "ID"]

# Paleta usada para colorir as categorias extras, por posição em
# LEVANTAMENTO_ABAS_EXTRAS. A folha obrigatória mantém sua própria lógica
# de cor (MEDICAO/PONTOTRAFO) e não usa esta paleta.
PALETA_CATEGORIAS = [
    "#7C6FF7", "#22D3EE", "#F97316", "#E879F9",
    "#84CC16", "#F43F5E", "#38BDF8", "#FBBF24",
]

# Aba e colunas usadas no levantamento
COLUNA_LAT = "LATITUDE"
COLUNA_LON = "LONGITUDE"

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
#   <BASE>/<NOME_MUNICIPIO>/<TRANSFORMADORES_LOTES_SUB>/*.kml
# Nomes podem variar de caixa/acentos; o matching e feito normalizando
# nomes para apenas alfanumericos em lowercase.
TRANSFORMADORES_BASE_PATH = _caminho_opcional("TRANSFORMADORES_BASE_PATH")
TRANSFORMADORES_LOTES_SUB = _env_opcional("TRANSFORMADORES_SUBPASTA")
TRANSFORMADORES_CACHE_DIR = "../data/cache_transformadores"

# =============================================================================
# AREAS INACESSIVEIS (GPKG) - visualizacao opcional de poligonos por municipio
# =============================================================================
# Estrutura esperada:
#   <BASE>/<NOME_MUNICIPIO>/<AREAS_INACESSIVEIS_SUB>/*.gpkg
# Mesma logica do transformadores, mas le .gpkg (GeoPackage) ao inves de .kml.
AREAS_INACESSIVEIS_BASE_PATH = _caminho_opcional("AREAS_INACESSIVEIS_BASE_PATH")
AREAS_INACESSIVEIS_SUB       = _env_opcional("AREAS_INACESSIVEIS_SUBPASTA")
AREAS_INACESSIVEIS_CACHE_DIR = "../data/cache_areas_inacessiveis"

# =============================================================================
# DUPLICADAS - deteccao de pontos duplicados (porte do script QGIS)
# =============================================================================
# Raio (metros) usado no agrupamento por proximidade — mesmo valor do
# script QGIS original (detectar_pontos_proximos(raio_metros=10.0)).
DUPLICADAS_RAIO_METROS = 10.0

# =============================================================================
# GALERIA DE FOTOS - extracao de fotos de camera a partir do LINK_RELATORIO
# =============================================================================
# Diretorio onde o cache por municipio (link -> fotos) e gravado.
FOTOS_CACHE_DIR = "../data/cache_fotos"

# Requisicoes a paginas de relatorio (LINK_RELATORIO) sao feitas em lotes,
# nao tudo de uma vez — protege o servidor de relatorios do rate limit dele
# (confirmado na pratica: sem essa pausa, ele passa a rejeitar requisicoes).
GALERIA_MAX_WORKERS = 7                        # requisicoes simultaneas por lote
GALERIA_DELAY_ENTRE_LOTES_SEGUNDOS = 0.25      # pausa entre um lote e o proximo
