# =============================================================================
# CONFIGURAÇÃO CENTRAL — edite este arquivo antes de rodar o servidor
# =============================================================================

# Caminho absoluto ou relativo à planilha (xlsx ou xlsm)
# Exemplos:
#   Windows:  r"C:\Users\Nicory\OneDrive\SATEL\mapa_municipios.xlsx"
#   Relativo: "../data/mapa_municipios.xlsx"
PLANILHA_PATH = r"C:\Users\SeuUsuario\OneDrive\sua_planilha.xlsx"

# Nome exato da aba que contém os dados
PLANILHA_ABA = "Municípios"

# Nome exato das colunas na planilha
COLUNA_CODIGO_IBGE = "codigo_ibge"   # deve conter o código de 7 dígitos ex: 2304400
COLUNA_STATUS      = "status"        # ex: "ativo", "pendente", "concluído"

# Caminho para o GeoJSON do Ceará exportado pelo QGIS
GEOJSON_PATH = "../data/municipios_ce.geojson"

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
    "ativo":      "#1D9E75",   # verde
    "pendente":   "#EF9F27",   # amarelo
    "concluído":  "#378ADD",   # azul
    "bloqueado":  "#E24B4A",   # vermelho
    # Adicione mais conforme necessário...
}

# Cor para municípios sem dado na planilha
COR_SEM_DADO = "#B4B2A9"

# Cor da borda dos municípios no mapa
COR_BORDA = "#ffffff"
LARGURA_BORDA = 0.8
