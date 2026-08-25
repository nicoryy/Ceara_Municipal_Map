"""
utm.py

Conversao UTM -> lat/lon (WGS84), formula fechada (Snyder/USGS), sem
dependencia externa. Usado so pela galeria de fotos de CELULAR (ver
fotos_reader.py) pra transformar a coordenada que vem no nome do arquivo
(ex.: ..._UTM24M_512345_9432100UTM_...) num ponto que o mapa consegue
centralizar.

O Ceara inteiro cai na zona UTM 24, bandas L/M (hemisferio sul) — por isso,
quando a letra da banda nao vem no nome do arquivo, assumimos sul.
"""

import math

_A  = 6378137.0                 # semi-eixo maior, WGS84
_F  = 1 / 298.257223563         # achatamento, WGS84
_E2 = _F * (2 - _F)             # excentricidade ao quadrado
_E1 = (1 - math.sqrt(1 - _E2)) / (1 + math.sqrt(1 - _E2))
_K0 = 0.9996                    # fator de escala UTM

# Bounding box de sanidade (Ceara ampliado, com folga) — uma conversao que
# cair fora disso indica nome de arquivo/zona malformado; melhor devolver
# None/None do que teleportar o mapa pra outro estado/pais.
_LAT_MIN, _LAT_MAX = -12.0, 2.0
_LON_MIN, _LON_MAX = -45.0, -33.0


def _hemisferio_sul(banda: str) -> bool:
    """Letra da banda UTM -> hemisferio. C..M = sul, N..X = norte.
    Sem letra (banda vazia), assume sul — cobre o caso comum no Ceara."""
    banda = (banda or "").strip().upper()
    if not banda:
        return True
    return banda < "N"


def utm_para_latlon(zona: int, easting: float, northing: float, banda: str = ""):
    """Converte UTM (zona, easting, northing) pra (lat, lon) em graus.
    Retorna (None, None) se a zona for invalida ou o resultado cair fora do
    bounding box de sanidade (ver _LAT_MIN/_LAT_MAX/_LON_MIN/_LON_MAX)."""
    try:
        if not (1 <= int(zona) <= 60):
            return None, None

        x = float(easting) - 500000.0
        y = float(northing)
        if _hemisferio_sul(banda):
            y -= 10_000_000.0

        m = y / _K0
        mu = m / (_A * (1 - _E2 / 4 - 3 * _E2 ** 2 / 64 - 5 * _E2 ** 3 / 256))

        phi1 = (
            mu
            + (3 * _E1 / 2 - 27 * _E1 ** 3 / 32) * math.sin(2 * mu)
            + (21 * _E1 ** 2 / 16 - 55 * _E1 ** 4 / 32) * math.sin(4 * mu)
            + (151 * _E1 ** 3 / 96) * math.sin(6 * mu)
            + (1097 * _E1 ** 4 / 512) * math.sin(8 * mu)
        )

        sen_phi1 = math.sin(phi1)
        cos_phi1 = math.cos(phi1)
        tan_phi1 = math.tan(phi1)

        e_prime2 = _E2 / (1 - _E2)
        n1 = _A / math.sqrt(1 - _E2 * sen_phi1 ** 2)
        t1 = tan_phi1 ** 2
        c1 = e_prime2 * cos_phi1 ** 2
        r1 = _A * (1 - _E2) / (1 - _E2 * sen_phi1 ** 2) ** 1.5
        d = x / (n1 * _K0)

        lat = phi1 - (n1 * tan_phi1 / r1) * (
            d ** 2 / 2
            - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * e_prime2) * d ** 4 / 24
            + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * e_prime2 - 3 * c1 ** 2) * d ** 6 / 720
        )
        lon0 = math.radians((int(zona) - 1) * 6 - 180 + 3)
        lon = lon0 + (
            d
            - (1 + 2 * t1 + c1) * d ** 3 / 6
            + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * e_prime2 + 24 * t1 ** 2) * d ** 5 / 120
        ) / cos_phi1

        lat_graus = math.degrees(lat)
        lon_graus = math.degrees(lon)

        if not (_LAT_MIN <= lat_graus <= _LAT_MAX and _LON_MIN <= lon_graus <= _LON_MAX):
            return None, None

        return lat_graus, lon_graus
    except Exception:
        return None, None
