# LEIA-ME — Como rodar o Mapa Municipal

Este guia serve para qualquer colega conseguir rodar o sistema em um computador Windows **sem precisar perguntar nada a mais**. Siga as verificações abaixo, na ordem.

> ⚡ **Atalho:** dê 2 cliques em [`iniciar.bat`](iniciar.bat), na raiz do projeto. Ele faz essas verificações sozinho, avisa o que estiver faltando e, se tudo estiver certo, já abre o sistema. As seções abaixo explicam o que o script verifica e como resolver manualmente, caso ele aponte algum problema.

> 🔒 **Nota de segurança:** os caminhos reais de rede/OneDrive e nomes internos da empresa **não ficam no código** — ficam só no seu arquivo `.env` local, que nunca é enviado ao git. Veja o passo 3.

---

## Checklist rápido

| # | Verificação | Como checar | Se estiver faltando |
|---|---|---|---|
| 1 | Python 3.10+ instalado | `python --version` no terminal | Instalar pela Microsoft Store |
| 2 | Bibliotecas Python instaladas | `pip show flask` no terminal | `pip install -r backend\requirements.txt` |
| 3 | Arquivo `.env` configurado com os caminhos da sua pasta sincronizada | Ver se existe `.env` na raiz do projeto | Copiar `.env.example` para `.env` e preencher os caminhos |

Se os três estiverem OK, o sistema **vai funcionar sem nenhum problema**.

---

## 1. Você tem Python instalado?

Abra o **Terminal** (tecla Windows → digite `terminal` ou `cmd` → Enter) e rode:

```
python --version
```

- **Se aparecer algo como** `Python 3.13.x` → ok, pode pular para o passo 2.
- **Se aparecer erro** (`'python' não é reconhecido...` ou abrir a Microsoft Store sozinho) → o Python não está instalado.

### Como instalar

1. Abra a **Microsoft Store** (tecla Windows → digite `Store`).
2. Pesquise por **"Python 3.13"** (ou a versão mais recente disponível, qualquer uma ≥ 3.10 serve).
3. Clique em **Instalar/Obter**.
4. Feche e abra o terminal de novo, rode `python --version` para confirmar.

Link direto pela Store (pode colar na barra de endereço do Windows): `ms-windows-store://pdp/?productid=9PNRBTZXMB4Z`

---

## 2. As dependências (`requirements.txt`) estão instaladas?

No terminal, **dentro da pasta do projeto**, rode:

```
pip install -r backend\requirements.txt
```

Isso instala automaticamente:
- `flask` — servidor web
- `flask-cors` — libera o frontend a consultar o backend
- `openpyxl` — leitura da planilha quando ela está fechada
- `xlwings` — leitura da planilha **ao vivo**, enquanto ela está aberta no Excel (opcional, mas recomendado)
- `python-dotenv` — carrega o arquivo `.env` do passo 3

Se o comando terminar sem erros em vermelho, está tudo pronto. Para confirmar, rode:

```
python -c "import flask, flask_cors, openpyxl; print('OK')"
```

Se imprimir `OK`, as dependências estão instaladas corretamente.

---

## 3. Você configurou o arquivo `.env` com os caminhos da sua pasta sincronizada?

O sistema lê a planilha e as pastas por município a partir de caminhos que **variam por empresa e por computador** — por isso eles não ficam no código, ficam num arquivo `.env` local (nunca commitado).

### Como configurar

1. Copie o arquivo [`.env.example`](.env.example) (raiz do projeto) e renomeie a cópia para **`.env`**.
2. Abra o `.env` num editor de texto e preencha cada caminho.

   ⚠️ **Importante:** não inclua `C:\Users\<seu usuário>` — o sistema detecta seu usuário do Windows automaticamente e monta essa parte sozinho. Coloque só o trecho que vem **depois** do usuário, começando com `\`. Assim o mesmo `.env` funciona em qualquer computador da equipe, sem precisar editar o caminho do usuário toda vez.

   Exemplo — se o caminho real na sua máquina é:
   ```
   C:\Users\joao\<sua pasta sincronizada>\<planilha>.xlsm
   ```
   o que vai no `.env` é:
   ```
   PLANILHA_PATH=\<sua pasta sincronizada>\<planilha>.xlsm
   LEVANTAMENTOS_BASE_PATH=\<sua pasta sincronizada>\2026\Municipios
   ```
3. Confirme que essa pasta está sincronizada no seu OneDrive/rede local antes de rodar o sistema — caso contrário, os arquivos não serão encontrados. Se precisar adicionar um atalho de uma pasta compartilhada ao seu OneDrive: clique com o botão direito na pasta de origem → **"Adicionar atalho ao OneDrive"** (ou **"Enviar a atalhos"**) → aguarde a sincronização terminar (ícone de nuvem para de girar).
4. Peça o link da pasta compartilhada e os nomes/caminhos exatos a quem já roda o sistema, caso não os tenha.

> ⚠️ **Nunca** adicione o arquivo `.env` ao git — ele já está no `.gitignore`, mas confira antes de fazer commit se tiver dúvida (`git status` não deve listar `.env`).

---

## Como rodar o sistema

### Opção A — Script automático (recomendado)

Dê 2 cliques em **`iniciar.bat`** na raiz do projeto. Ele confere os itens acima — inclusive criando o `.env` a partir do `.env.example` automaticamente, se ainda não existir — e, se tudo estiver certo, inicia o servidor e abre o navegador em `http://localhost:5000`.

### Opção B — Manual

```
cd backend
python server.py
```

Depois, abra o navegador em: **http://localhost:5000**

Para parar o servidor, volte ao terminal e pressione `Ctrl+C`.

---

## Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `'python' não é reconhecido como um comando` | Python não instalado ou não está no PATH | Reinstale pela Microsoft Store (passo 1) e reabra o terminal |
| `RuntimeError: Variavel de ambiente 'PLANILHA_PATH' nao definida` | Arquivo `.env` não existe ou está incompleto | Confira o passo 3 — copie `.env.example` para `.env` e preencha |
| `Arquivo não encontrado aberto no Excel` / erro ao ler planilha | Pasta sincronizada não existe/não sincronizou, ou caminho no `.env` está errado | Confirme o passo 3; confira o valor de `PLANILHA_PATH` no seu `.env` |
| `ModuleNotFoundError: No module named 'flask'` (ou similar) | Dependências não instaladas | Rode o comando do passo 2 |
| Página abre mas o mapa fica cinza / sem dados | A planilha foi encontrada mas os nomes de aba/coluna não batem | Confira `PLANILHA_ABA` no `.env` e as colunas em `backend/config.py` contra a planilha real |
| `OSError: [WinError 10048]` / porta em uso | Já existe um servidor rodando na porta 5000 | Feche a outra instância do `python server.py`, ou mude `SERVER_PORT` no seu `.env` |
| Levantamentos por município / transformadores / áreas inacessíveis não aparecem | As variáveis opcionais no `.env` (`LEVANTAMENTOS_BASE_PATH_2025/2024`, `TRANSFORMADORES_BASE_PATH`, `AREAS_INACESSIVEIS_BASE_PATH`) estão vazias ou com caminho errado | Preencha/corrija essas linhas no seu `.env` |

---

## Resumo técnico (para quem for além do básico)

- **Backend:** Python 3.10+, Flask, xlwings (leitura ao vivo) + openpyxl (fallback)
- **Frontend:** HTML/CSS/JS puro (Leaflet.js), servido pelo próprio Flask — não precisa de Node/npm
- **Configuração central:** `backend/config.py` (regras fixas, não sensíveis) + `.env` (caminhos e nomes sensíveis, local e não versionado)
- **Porta padrão:** `5000`
