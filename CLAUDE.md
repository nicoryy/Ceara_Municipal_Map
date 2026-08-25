# CLAUDE.md — Ceará Municipal Map

## Contexto do projeto

Aplicação web local (local-first) para visualização territorial dos 184 municípios do Ceará com status operacional lido de uma planilha Excel. Roda via Flask + Leaflet.js no browser.

**Stack:**
- Backend: Python 3.10+, Flask, xlwings (leitura ao vivo), openpyxl (fallback)
- Frontend: HTML/CSS/JS puro, Leaflet.js 1.9.4, sem framework
- Dados geográficos: GeoJSON exportado do QGIS (IBGE/IPECE)

---

## Estrutura de arquivos

```
municipios-map/
├── backend/
│   ├── config.py           ← configuração central (paths, colunas, cores)
│   ├── server.py           ← Flask API
│   ├── planilha_reader.py  ← leitura Excel com cache por mtime
│   └── requirements.txt
├── frontend/
│   ├── index.html          ← UI completa em arquivo único
│   ├── municipios_ce.geojson        ← 184 municípios do Ceará
│   └── limites_regionais_fortaleza.geojson  ← 12 regionais de Fortaleza
├── data/
│   └── cache_dados.json    ← gerado automaticamente
└── CLAUDE.md
```

---

## Campos dos GeoJSONs

### `municipios_ce.geojson`
```json
{
  "properties": {
    "codigo_ibg": "2302800",
    "Municipio": "Canindé"
  }
}
```
> Atenção: o campo é `codigo_ibg` (sem o `e` final — truncado pelo QGIS).

### `limites_regionais_fortaleza.geojson`
```json
{
  "properties": {
    "id": 11.0,
    "regiao_adm": "SER 11",
    "area_m2": 18977887.57
  }
}
```
> O campo identificador é `regiao_adm` com valor `"SER 1"` até `"SER 12"`.

---

## Lógica de join — regionais de Fortaleza

A planilha tem uma coluna `MUNICIPIO` onde as regionais aparecem como:
```
FORTALEZA - REGIONAL 1
FORTALEZA - REGIONAL 8
```

O GeoJSON das regionais tem `regiao_adm: "SER 1"`.

O frontend precisa converter:
```
"SER 1"  →  "FORTALEZA - REGIONAL 1"
"SER 11" →  "FORTALEZA - REGIONAL 11"
```

A função responsável por isso é `chaveRegional(props)`:
```javascript
function chaveRegional(props) {
  const ser = String(props.regiao_adm || "").trim();
  const num = ser.replace(/^SER\s*/i, "").trim();
  if (!num) return null;
  return `FORTALEZA - REGIONAL ${num}`;
}
```

---

## Dados retornados pela API `/municipios`

```json
{
  "2304400": {
    "status": "ENTREGA REALIZADA",
    "cor": "#1D9E75",
    "ordem": 10,
    "tipo": "NORMAL",
    "municipio": "FORTALEZA - REGIONAL 3"
  }
}
```

> Municípios normais: `municipio` vazio ou nome do município.
> Regionais de Fortaleza: `municipio` = `"FORTALEZA - REGIONAL X"`.

O frontend mantém dois índices:
- `dadosPlanilha` — indexado por `codigo_ibge` (para os 183 municípios)
- `dadosPorMunicipio` — indexado por nome do município (para as 12 regionais)

---

## Comportamento esperado no mapa

1. O polígono de Fortaleza é **removido** do GeoJSON de municípios (IBGE `2304400`)
2. Os 12 polígonos do GeoJSON de regionais são adicionados **no lugar**
3. Cada regional recebe cor pelo seu status (via `dadosPorMunicipio`)
4. Filtros de status e tipo afetam regionais e municípios igualmente
5. Busca retorna regionais junto com municípios
6. Click em regional abre painel lateral com nome, status e tipo

---

## Problema atual a resolver

**Erro:**
```
ReferenceError: chaveRegional is not defined
    at style (index.html:730)
    at carregarRegionais (index.html:728)
```

**Causa raiz:**
A função `chaveRegional` está sendo chamada dentro do callback `style` do `L.geoJSON(regionaisData, { style: f => getEstiloRegional(chaveRegional(f.properties)) })` — mas a função `chaveRegional` foi declarada **depois** no arquivo, ou dentro de um escopo onde não está acessível no momento da execução.

Em JavaScript, funções declaradas com `function foo()` sofrem hoisting e ficam disponíveis em todo o escopo. Funções declaradas com `const foo = () =>` ou `let foo = function()` **não** sofrem hoisting — se `chaveRegional` foi declarada assim, não está disponível no momento em que `carregarRegionais` é chamada.

**O que fazer:**
1. Verificar como `chaveRegional` está declarada no `index.html`
2. Se for `const chaveRegional = ...` ou `let chaveRegional = ...`, converter para declaração de função:
   ```javascript
   // de:
   const chaveRegional = (props) => { ... }
   
   // para:
   function chaveRegional(props) { ... }
   ```
3. Garantir que `chaveRegional` está declarada **fora** de qualquer outro bloco `async function` ou IIFE
4. A mesma verificação se aplica a `getEstiloRegional` e `buscarDadoRegional` — todas devem ser declarações de função (`function foo()`) e não arrow functions atribuídas a variáveis

**Verificação rápida:** no `index.html`, todas as funções auxiliares do mapa devem seguir o padrão:
```javascript
function chaveRegional(props) { ... }
function getEstiloRegional(chave, opcoes = {}) { ... }
function buscarDadoRegional(chave) { ... }
function selecionarRegional(chave, layer) { ... }
function aplicarEstiloSelecionadoRegional(layer, chave) { ... }
```

---

## Config atual relevante

Caminhos reais (planilha, pastas por ano/município, prefixo de arquivo) **não ficam em `config.py`** — são sensíveis (nome da empresa e do portal interno) e vêm de um `.env` na raiz do projeto, nunca commitado (veja `.env.example` para o template e `LEIA-ME.md` para instruções). `config.py` só lê essas variáveis via `os.environ` e falha com uma mensagem clara se `.env` não existir.

O que permanece fixo em `backend/config.py` (não sensível):

```python
# backend/config.py
PLANILHA_ABA       = "tecnico"          # valor padrão, sobrescrevível via .env
COLUNA_CODIGO_IBGE = "codigo_ibge"
COLUNA_STATUS      = "status"
COLUNA_TIPO        = "tipo"
COLUNA_MUNICIPIO   = "MUNICIPIO"

STATUS_DEFINICOES = [
    # ("valor_na_planilha", "cor_hex") — a ordem define a ordem da legenda
    ("CAMPO NAO INICIADO",     "#B4B2A9"),  # cinza
    ("ESPERANDO CAMPO",        "#6B6A66"),  # cinza escuro
    ("AUDITORIAS",             "#2F80ED"),  # azul
    ("AGUARDANDO AUDITORIAS",  "#2F80ED"),  # azul
    ("INFORMAR ERRO %",        "#2F80ED"),  # azul
    ("PRIORIDADE EDIÇÃO",      "#E24B4A"),  # vermelho
    ("REEDIÇÃO",               "#E24B4A"),  # vermelho
    ("ENTREGA",                "#E24B4A"),  # vermelho
    ("DUPLICADAS",             "#8E44AD"),  # roxo
    ("ANÁLISE EDIÇÃO",         "#EF9F27"),  # laranja
    ("ENTREGA REALIZADA",      "#1D9E75"),  # verde
    ("AJUSTE FINAL",           "#7B1F2B"),  # vinho
    ("AUDITORIA FINAL",        "#7B1F2B"),  # vinho
]
# STATUS_CORES / STATUS_ROTULOS / STATUS_ORDEM são derivados desta lista,
# normalizando a chave (uppercase, sem acento) para tolerar variação na planilha.

COR_SEM_DADO  = "#1e2236"
GEOJSON_PATH  = "../frontend/municipios_ce.geojson"
CACHE_PATH    = "../data/cache_dados.json"
SERVER_PORT   = 5000                    # valor padrão, sobrescrevível via .env
```

---

## Convenções do código frontend

- Todas as funções auxiliares como declarações (`function foo()`) — nunca `const foo = () =>`
- Estado global no topo do script: `dadosPlanilha`, `dadosPorMunicipio`, `geojsonLayer`, `regionaisLayer`, `featureLayers`, `regionaisLayers`, `selectedLayer`, `filtros`
- Estilos via `getEstilo(ibge, opcoes)` e `getEstiloRegional(chave, opcoes)` — nunca `setStyle` direto sem passar por essas funções
- Filtros cumulativos: `filtros = { status: null, tipo: null }` — ambos aplicados em `getEstilo` e `getEstiloRegional`
- Toda atualização de estilos passa por `reaplicarEstilos()` que itera sobre `geojsonLayer` e `regionaisLayer`