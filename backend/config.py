# =============================================================================
# CONFIGURAÇÃO CENTRAL — edite este arquivo antes de rodar o servidor
# =============================================================================

# Caminho absoluto ou relativo à planilha (xlsx ou xlsm)
# Exemplos:
#   Windows:  r"C:\Users\Nicory\OneDrive\SATEL\mapa_municipios.xlsx"
#   Relativo: "../data/mapa_municipios.xlsx"
PLANILHA_PATH = r"C:\Users\nicory\Downloads\Planilhas\PROJETOS - NOVO.xlsx"

# Nome exato da aba que contém os dados
PLANILHA_ABA = "tecnico"

# Nome exato das colunas na planilha
COLUNA_CODIGO_IBGE = "cod_ibge"      # código de 7 dígitos ex: 2304400
COLUNA_STATUS      = "status"         # ex: "ativo", "pendente", "concluído"
COLUNA_TIPO        = "tipo"           # ex: "ressalva", "normal"
COLUNA_MUNICIPIO   = "CIDADE"         # nome do município
COLUNA_REGIAO      = "REGIAO"         # nome da regional (ex: "Sul", "Norte")
COLUNA_TECNICO     = "TÉCNICO"        # nome do técnico (com acento)
COLUNA_OS          = "OS"             # número da Ordem de Serviço

# Caminho para o GeoJSON dos municípios do Ceará exportado pelo QGIS
GEOJSON_PATH = "../frontend/municipios_ce.geojson"

# Caminho para o GeoJSON das regionais do Ceará (COELCE 2006)
GEOJSON_REGIONAIS_PATH = "../frontend/regionais_ce.geojson"

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
    "CONCLUÍDO": "#22c55e",
    "CANCELADO": "#ef4444",
    "REMOTO": "#3b82f6",
    "RETIRADO": "#f97316",
    "PROGRAMADA": "#a855f7",
    "EM ESPERA": "#eab308",
    "SUSPENSO": "#64748b",
    "IMPRODUTIVO": "#dc2626",
    "NÃO TRATADO": "#94a3b8",
}

# Cor para municípios sem dado na planilha
COR_SEM_DADO = "#B4B2A9"

# Cor da borda dos municípios no mapa
COR_BORDA = "#ffffff"
LARGURA_BORDA = 0
