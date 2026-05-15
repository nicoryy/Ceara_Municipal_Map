# =============================================================================
# CONFIGURAÇÃO CENTRAL — edite este arquivo antes de rodar o servidor
# =============================================================================

# Caminho absoluto ou relativo à planilha (xlsx ou xlsm)
# Exemplos:
#   Windows:  r"C:\Users\Nicory\OneDrive\SATEL\mapa_municipios.xlsx"
#   Relativo: "../data/mapa_municipios.xlsx"
PLANILHA_PATH = r"C:\Users\Satel\OneDrive - SATEL\Portal - Censo IP\Censo IP 2026.xlsm"

# Nome exato da aba que contém os dados
PLANILHA_ABA = "tecnico"

# Nome exato das colunas na planilha
COLUNA_CODIGO_IBGE = "codigo_ibge"   # deve conter o código de 7 dígitos ex: 2304400
COLUNA_STATUS      = "status"        # ex: "ativo", "pendente", "concluído"
COLUNA_TIPO        = "tipo"          # ex: "ressalva", "normal"
COLUNA_MUNICIPIO   = "MUNICIPIO"     # ex: "FORTALEZA - REGIONAL 1" (usado pelas regionais)

# Caminho para o GeoJSON do Ceará exportado pelo QGIS
GEOJSON_PATH = "../frontend/municipios_ce.geojson"

# Caminho para o cache gerado automaticamente pelo servidor
CACHE_PATH = "../data/cache_dados.json"

# Porta do servidor local
SERVER_PORT = 5000

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
#   <BASE>/<NOME_MUNICIPIO>/AUDITORIA/FECHAMENTO CENSO IP*.xlsm
# Comparação de nomes é case-insensitive em todas as etapas.
LEVANTAMENTOS_BASE_PATH = r"C:\Users\Satel\OneDrive - SATEL\Portal - Censo IP\2026\Municipios"

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
