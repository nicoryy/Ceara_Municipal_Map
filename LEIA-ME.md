# LEIA-ME — Como rodar o Mapa Municipal (SATEL)

Este guia serve para qualquer colega conseguir rodar o sistema em um computador Windows **sem precisar perguntar nada a mais**. Siga as 3 verificações abaixo, na ordem.

> ⚡ **Atalho:** dê 2 cliques em [`iniciar.bat`](iniciar.bat), na raiz do projeto. Ele faz essas 3 verificações sozinho, avisa o que estiver faltando e, se tudo estiver certo, já abre o sistema. As seções abaixo explicam o que o script verifica e como resolver manualmente, caso ele aponte algum problema.

---

## Checklist rápido

| # | Verificação | Como checar | Se estiver faltando |
|---|---|---|---|
| 1 | Python 3.10+ instalado | `python --version` no terminal | Instalar pela Microsoft Store |
| 2 | Bibliotecas Python instaladas | `pip show flask` no terminal | `pip install -r backend\requirements.txt` |
| 3 | Pasta "Portal - Censo IP" sincronizada no OneDrive | Ver se a pasta existe em `%OneDrive%` | Adicionar atalho da pasta no OneDrive e aguardar sincronizar |

Se as três estiverem OK, o sistema **vai funcionar sem nenhum problema**.

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

Se o comando terminar sem erros em vermelho, está tudo pronto. Para confirmar, rode:

```
python -c "import flask, flask_cors, openpyxl; print('OK')"
```

Se imprimir `OK`, as dependências estão instaladas corretamente.

---

## 3. Você tem o Portal Censo IP vinculado no seu OneDrive?

O sistema lê a planilha diretamente desta pasta:

```
C:\Users\<seu usuário>\OneDrive - SATEL\Portal - Censo IP\Censo IP 2026.xlsm
```

Se essa pasta não existir no seu computador, o sistema não vai encontrar a planilha e vai mostrar um erro de "arquivo não encontrado".

### Como vincular

1. Abra o link do Portal Censo IP no SharePoint/OneDrive: **`[COLE AQUI O LINK DO SHAREPOINT DO "Portal - Censo IP"]`**
2. Clique com o botão direito na pasta **"Portal - Censo IP"**.
3. Selecione **"Adicionar atalho ao OneDrive"** (ou **"Enviar a atalhos"**, dependendo da versão).
4. Abra o OneDrive (ícone de nuvem na bandeja do Windows, perto do relógio) e aguarde a sincronização terminar (o ícone para de girar quando termina).
5. Confirme que a pasta apareceu em `Este PC > OneDrive - SATEL > Portal - Censo IP`.

> ⚠️ **Preencha o link acima** antes de repassar este arquivo aos colegas — sem ele, essa etapa fica manual (peça o link para quem administra o SharePoint da SATEL).

---

## Como rodar o sistema

### Opção A — Script automático (recomendado)

Dê 2 cliques em **`iniciar.bat`** na raiz do projeto. Ele confere os 3 itens acima, oferece instalar o que faltar e, se tudo estiver certo, inicia o servidor e abre o navegador automaticamente em `http://localhost:5000`.

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
| `Arquivo não encontrado aberto no Excel` / erro ao ler planilha | Pasta do OneDrive não sincronizada, ou planilha com nome/caminho diferente | Confirme o passo 3; confira `backend/config.py` → `PLANILHA_PATH` |
| `ModuleNotFoundError: No module named 'flask'` (ou similar) | Dependências não instaladas | Rode o comando do passo 2 |
| Página abre mas o mapa fica cinza / sem dados | A planilha foi encontrada mas os nomes de aba/coluna não batem | Confira `PLANILHA_ABA` e as colunas em `backend/config.py` contra a planilha real |
| `OSError: [WinError 10048]` / porta em uso | Já existe um servidor rodando na porta 5000 | Feche a outra instância do `python server.py`, ou mude `SERVER_PORT` em `backend/config.py` |
| Levantamentos por município / transformadores / áreas inacessíveis não aparecem | Esses caminhos em `backend/config.py` (`LEVANTAMENTOS_BASE_PATH`, `TRANSFORMADORES_BASE_PATH`, `AREAS_INACESSIVEIS_BASE_PATH`) estão fixos com o usuário `Satel` — se seu usuário do Windows for diferente, o caminho não bate | Ajuste esses caminhos em `config.py` para o seu usuário, ou combine um valor fixo de equipe |

---

## Resumo técnico (para quem for além do básico)

- **Backend:** Python 3.10+, Flask, xlwings (leitura ao vivo) + openpyxl (fallback)
- **Frontend:** HTML/CSS/JS puro (Leaflet.js), servido pelo próprio Flask — não precisa de Node/npm
- **Configuração central:** `backend/config.py` — caminhos de planilha, nomes de coluna e cores de status
- **Porta padrão:** `5000`
