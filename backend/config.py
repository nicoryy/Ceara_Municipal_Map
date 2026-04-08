# =============================================================================
# CONFIGURAÇÃO CENTRAL — edite este arquivo antes de rodar o servidor
# =============================================================================

# Caminho absoluto ou relativo à planilha (xlsx ou xlsm)
PLANILHA_PATH = r"C:\Users\nicory\Downloads\Planilhas\PROJETOS - NOVO.xlsx"

# Nome exato da aba que contém os dados
PLANILHA_ABA = "tecnico"

# Nome exato das colunas na planilha
# Colunas disponiveis: OS, CIDADE, REGIAO, TECNICO, STATUS, cod_ibge
COLUNA_CODIGO_IBGE = "cod_ibge"      # código de 7 dígitos ex: 2304400
COLUNA_STATUS      = "STATUS"         # status da OS
COLUNA_TIPO        = ""               # NÃO EXISTE NA PLANILHA ATUAL
COLUNA_MUNICIPIO   = "CIDADE"         # nome do município
COLUNA_REGIAO      = "REGIAO"         # nome da regional (ex: "Sul", "Norte")
COLUNA_TECNICO     = "TÉCNICO"        # nome do técnico
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
# Status reais da planilha atual
# =============================================================================
STATUS_CORES = {
    "CONCLUÍDO":     "#22c55e",  # verde
    "CANCELADO":     "#ef4444",  # vermelho
    "REMOTO":        "#3b82f6",  # azul
    "RETIRADO":      "#f97316",  # laranja
    "PROGRAMADA":    "#a855f7",  # roxo
    "EM ESPERA":     "#eab308",  # amarelo
    "SUSPENSO":      "#64748b",  # cinza
    "IMPRODUTIVO":   "#dc2626",  # vermelho escuro
    "NÃO TRATADO":   "#94a3b8",  # cinza claro
}

# Cor para municípios sem dado na planilha
COR_SEM_DADO = "#B4B2A9"

# Cor da borda dos municípios no mapa
COR_BORDA = "#ffffff"
LARGURA_BORDA = 0
