# entregavel_CP2_SERS
Continuação do checkpoint 1 


# Sistema de Dimensionamento Energético Residencial — Evolução Fotovoltaica

**Equipe Lumos · FIAP · Análise e Desenvolvimento de Sistemas**

Sistema de terminal em Python que cadastra usuários, imóveis e equipamentos, calcula o consumo de energia do imóvel e, nesta etapa, faz o **pré-dimensionamento de um sistema de energia solar**: quantos painéis, qual inversor, baterias opcionais, verificação de compatibilidade técnica e orçamento estimado, tudo apresentado numa proposta preliminar ao cliente.

---

## 1. Como executar

Requer **Python 3.9 ou superior**. Não precisa instalar nenhuma biblioteca (só usa a biblioteca padrão).

```bash
# Usar o sistema normalmente
python sistema_analise_casa.py

# Rodar todos os testes automatizados, sem interação
python testes.py
```

> Os três arquivos `.py` e a pasta `dados_fv/` precisam ficar **na mesma pasta**.
> Se a pasta `dados_fv/` não estiver lá, a parte solar avisa qual arquivo está faltando (o restante do sistema continua funcionando).

---

## 2. Estrutura dos arquivos

```
📁 projeto/
├── sistema_analise_casa.py     ← telas, menus e dados do usuário (é o que se executa)
├── fotovoltaico.py             ← cálculos e regras da parte solar
├── testes.py                   ← testes automatizados
├── dados_sistema.json          ← criado ao usar o sistema (usuários, imóveis, etc.)
└── 📁 dados_fv/                ← bases de dados da parte solar
    ├── modulos.csv             ← 10 painéis solares
    ├── inversores.csv          ← 8 inversores
    ├── baterias.csv            ← 6 baterias
    └── hsp_localidades.csv     ← quanto sol cada cidade recebe
```

---

## 3. Os arquivos de código

O código está dividido em três arquivos, cada um com uma responsabilidade:

| Arquivo | O que tem | Conversa com o usuário? |
|---|---|---|
| `sistema_analise_casa.py` | Etapa anterior inteira (PB01 a PB18), as **telas** da parte solar e os menus. É o arquivo que se executa. | Sim |
| `fotovoltaico.py` | **Regras** da parte solar: leitura dos CSVs, fórmulas, compatibilidade, seleção, orçamento e texto da proposta. | Não — só recebe dados e devolve resultados |
| `testes.py` | Testes automatizados da etapa anterior e da sprint solar. | Não |

Essa separação deixa as contas testáveis sem precisar digitar nada: `testes.py` chama direto as funções de `fotovoltaico.py`. No `sistema_analise_casa.py`, tudo que vem da parte solar aparece com o prefixo `fv.` (ex.: `fv.dimensionar_fv(...)`), então dá para ver na hora de qual arquivo a função vem.

### `sistema_analise_casa.py` — etapa anterior (PB01 a PB18) e telas

É o sistema que já existia: cadastro e login de usuário (com senha criptografada), cadastro de imóveis, cadastro de equipamentos, associação de equipamentos ao imóvel, cálculo de consumo mensal, ranking, resumo e gráfico. Tudo é salvo em `dados_sistema.json`.

**Funções auxiliares** no início do arquivo (`ler`, `ler_validado`, `ler_sim_nao`, `confirmar`, `concluir`, `executar_menu`) concentram as perguntas, validações e menus, para não repetir o mesmo laço `while True` em cada tela.

**O que mudou nesta parte:**
- O cadastro de imóvel agora pede **cidade e UF** (necessário para saber quanto sol a região recebe).
- A edição de imóvel ganhou a opção **5. Localização**.
- Ao excluir um imóvel, os dimensionamentos solares dele também são apagados.
- O menu de residências ganhou a opção **6. Energia Solar Fotovoltaica**.
- As **telas da parte solar** ficam aqui (`novo_dimensionamento_fv`, `listar_dimensionamentos_fv`, `tela_validar_datasets`): fazem as perguntas (localização, consumo, percentual, baterias), chamam `fotovoltaico.py` e salvam o cenário no JSON. Tasks FV-PB01-T01, PB02-T01/T03/T04, PB06-T01/T02, PB08-T05, PB10-T02.

### `fotovoltaico.py` — Evolução Fotovoltaica (sprint FV)

> **Sobre a numeração:** o CSV de tasks do Trello desta sprint recomeça em PB01, número que já existe no backlog anterior. Para não confundir, todo comentário da parte solar usa o prefixo **`FV-`**. Exemplo: `FV-PB04-T05` é o cartão "PB04 - T05" do Trello da sprint solar. Use Ctrl+F no código para achar qualquer cartão.

O arquivo segue esta ordem:

| Bloco | O que faz | Tasks |
|---|---|---|
| **Parâmetros** (`PARAMETROS_FV`) | Números fixos adotados pela equipe: 30 dias, eficiência 0,78, margens de tensão, % de outros custos. A fonte de cada valor está no comentário ao lado. | FV-PB03-T03, FV-PB09-T03 |
| **Schemas** (`DATASETS_FV`) | Para cada CSV: nome do arquivo, quantidade mínima, campos de texto e campos numéricos obrigatórios. | FV-PB04-T01, PB05-T01, PB07-T01, PB11-T01 |
| **Leitura dos CSVs** | Lê os arquivos, converte os números e separa linhas válidas das pendentes (incompletas, sem preço ou sem link). | FV-PB04-T03, PB05-T03, PB07-T03, PB11-T06 |
| **Validação dos datasets** | Confere quantidade mínima (10/8/6), IDs repetidos, link da fonte e data de coleta. | FV-PB11-T08 |
| **Fórmulas** | Uma função para cada fórmula do enunciado. Só fazem conta, sem perguntar nada ao usuário. | FV-PB02, PB03, PB04, PB06, PB07 |
| **HSP da localização** | Busca o sol da cidade na tabela. Se a cidade não estiver lá, aceita um valor digitado **desde que venha com a fonte**. | FV-PB01-T04 |
| **Compatibilidade** | Testa se o painel funciona com o inversor e se a bateria funciona com o inversor (regras C1 a C8). | FV-PB05, PB08 |
| **Seleção** | Testa todas as combinações painel × inversor, descarta as incompatíveis e escolhe a mais barata entre as que sobraram. | FV-PB04-T04, PB05-T06 |
| **Orçamento** | Soma preços dos equipamentos, calcula outros custos e o total. | FV-PB09 |
| **Dimensionamento** (`dimensionar_fv`) | O "chefe": chama tudo acima na ordem certa e junta o resultado. | FV-PB03, PB06-T06, PB10-T01 |
| **Proposta** (`formatar_proposta`) | Monta o texto que o cliente vê. | FV-PB10 |

### Fórmulas implementadas

| Fórmula | O que calcula | Função |
|---|---|---|
| `E_FV = Cm × f` | Energia que o cliente quer gerar por mês | `energia_mensal_desejada` |
| `P_FV = E_FV / (HSP × D × η)` | Potência solar necessária (kWp) | `potencia_fv_necessaria` |
| `N = ⌈(P_FV × 1000) / P_módulo⌉` | Quantidade mínima de painéis | `quantidade_minima_modulos` |
| `P_instalada = N × P_módulo / 1000` | Potência realmente instalada | `potencia_instalada` |
| `E_gerada = P_instalada × HSP × D × η` | Geração estimada por mês | `geracao_estimada_mensal` |
| `E_d = Cm / 30` | Consumo médio por dia | `consumo_diario` |
| `E_autonomia = E_d × A / 24` | Energia para as horas de autonomia | `energia_autonomia` |
| `C_bat = E_autonomia / (DoD × η_bat)` | Capacidade nominal de bateria necessária | `capacidade_bateria_necessaria` |
| `C_útil = C_nominal × DoD` | Quanto de uma bateria pode ser usado | `capacidade_util` |
| `N_bat = ⌈C_necessária / C_útil⌉` | Quantidade de baterias | `quantidade_baterias` |

**Legenda:** Cm = consumo mensal · f = percentual de atendimento (80% → 0,8) · HSP = horas de sol pleno · D = 30 dias · η = eficiência global (0,78) · A = autonomia em horas · DoD = profundidade de descarga · η_bat = eficiência da bateria (0,95).

**Observação sobre N_bat:** se a conta usasse `C_bat` (já dividido pelo DoD) contra `C_útil` (já multiplicado pelo DoD), o DoD seria aplicado duas vezes e o sistema compraria baterias demais. Por isso usamos `C_necessária = E_autonomia / η_bat`. Um teste confirma que isso dá o mesmo resultado que `⌈C_bat / C_nominal⌉`.

**Observação sobre N:** o N da fórmula é o mínimo. O sistema divide os painéis no menor número possível de fileiras (strings) iguais que caibam na tensão do inversor; por isso o N final às vezes fica um pouco acima do mínimo. A proposta mostra os dois valores.

### Regras de compatibilidade (C1 a C8)

| Regra | O que verifica | Em palavras simples |
|---|---|---|
| C1 | `Voc da string × 1,10 ≤ tensão máx. do inversor` | Em dia frio a tensão sobe; não pode queimar o inversor |
| C2 | `Vmp da string ≤ faixa MPPT máxima` | A tensão de trabalho cabe na faixa do inversor |
| C3 | `Vmp da string × 0,90 ≥ faixa MPPT mínima` | Em dia quente a tensão cai; não pode ficar abaixo do mínimo |
| C4 | `corrente do painel ≤ corrente máx. por entrada` | O inversor aguenta a corrente dos painéis |
| C5 | `potência instalada ≤ potência FV máx. do inversor` | Não passa do limite de painéis do inversor |
| C6 | `razão DC/AC dentro da faixa` | Inversor nem pequeno nem grande demais para os painéis |
| C7 | com bateria → inversor híbrido | Inversor comum (on-grid) não aceita bateria |
| C8 | tensão da bateria dentro da faixa do inversor | A bateria "conversa" com o inversor |

Combinações que falham em qualquer regra são **bloqueadas**, e o sistema mostra o motivo de cada bloqueio.

---

## 4. Os arquivos CSV (`dados_fv/`)

Todos seguem as mesmas convenções:
- **Separador:** vírgula. **Decimal:** ponto (ex.: `21.3`).
- **Unidade no nome da coluna:** `_w` = watts, `_wp` = watt-pico, `_v` = volts, `_a` = ampères, `_kwh` = quilowatt-hora, `_pct` = porcentagem, `_brl` = reais.
- **Data:** formato `AAAA-MM-DD`.
- Podem ser abertos e editados no Excel. O sistema lê a versão que estiver na pasta.

### Colunas de rastreabilidade (presentes nos três CSVs de equipamentos)

| Coluna | Significado |
|---|---|
| `preco_brl` | Preço exibido na loja na data de coleta |
| `fornecedor` | Loja onde o preço foi coletado |
| `data_coleta` | Dia em que o preço foi consultado |
| `url_fonte` | Link da página do produto |
| `fonte_especificacao` | De onde vieram os dados técnicos (datasheet do fabricante ou página da loja) |
| `status_validacao` | Situação da conferência (ver tabela abaixo) |

| Status | Significado |
|---|---|
| `OK_PAGINA` | Dados conferidos na página da fonte |
| `CONFERIR_DATASHEET` | Dados técnicos transcritos do datasheet; **abrir o PDF e confirmar antes da entrega** |
| `CONFERIR_PRECO` | Produto indisponível ou preço possivelmente desatualizado |

Uma linha **sem preço ou com campo obrigatório vazio** não quebra o sistema: ela fica como "pendente" e é ignorada nos cálculos (aparece no relatório de validação).

### `modulos.csv` — painéis solares (10 itens, mínimo exigido: 10)

| Coluna | Significado |
|---|---|
| `id` | Código interno (FV001...) |
| `fabricante`, `modelo` | Identificação do painel |
| `potencia_wp` | Potência do painel em watt-pico |
| `voc_v` | Tensão de circuito aberto (usada na regra C1) |
| `isc_a` | Corrente de curto-circuito |
| `vmp_v` | Tensão de máxima potência (regras C2 e C3) |
| `imp_a` | Corrente de máxima potência (regra C4) |
| `eficiencia_pct` | Eficiência do painel |

### `inversores.csv` — inversores (8 itens, mínimo exigido: 8)

| Coluna | Significado |
|---|---|
| `tipo` | `on-grid` (só rede) ou `hibrido` (aceita bateria) |
| `potencia_nominal_w` | Potência de saída do inversor |
| `potencia_max_fv_w` | Máximo de painéis que pode receber (regra C5) |
| `tensao_max_entrada_v` | Tensão máxima de entrada (regra C1) |
| `faixa_mppt_min_v`, `faixa_mppt_max_v` | Faixa de tensão de trabalho (regras C2 e C3) |
| `corrente_max_entrada_a` | Corrente máxima por entrada (regra C4) |
| `numero_mppt` | Quantas entradas independentes o inversor tem |
| `strings_por_mppt` | Quantas fileiras podem ser ligadas em cada entrada |
| `compativel_bateria` | `SIM` ou `NAO` (regra C7) |
| `tensao_bateria_min_v`, `tensao_bateria_max_v` | Faixa de tensão de bateria aceita (regra C8); `0` em inversores on-grid |

> Os campos `strings_por_mppt` e `tensao_bateria_*` não estavam no schema da task FV-PB05-T01, mas foram acrescentados porque sem eles é impossível verificar a compatibilidade com baterias (FV-PB08-T03).

### `baterias.csv` — baterias (6 itens, mínimo exigido: 6)

| Coluna | Significado |
|---|---|
| `tecnologia` | Química da bateria (todas LiFePO4) |
| `tensao_nominal_v` | Tensão da bateria (regra C8) |
| `capacidade_ah` | Capacidade em ampère-hora |
| `capacidade_kwh` | Capacidade nominal em kWh (usada no cálculo) |
| `dod_pct` | Profundidade de descarga: quanto % pode ser usado sem danificar |
| `ciclos` | Vida útil em ciclos de carga/descarga |

### `hsp_localidades.csv` — recurso solar por cidade

| Coluna | Significado |
|---|---|
| `cidade`, `uf` | Localidade (a busca ignora acentos e maiúsculas) |
| `hsp_kwh_m2_dia` | Horas de sol pleno: média diária de energia solar na região |
| `fonte`, `url_fonte` | Origem do dado (base CRESESB/SunData, Atlas Brasileiro de Energia Solar 2017) |

Para uma cidade que não está na tabela, o sistema pede o HSP **e a fonte** (ex.: "CRESESB SunData - Osasco/SP"). Valores fora de 3,0 a 7,0 são rejeitados.

---

## 5. Como usar a parte solar

1. Cadastre-se e faça login.
2. Cadastre um imóvel (com cidade/UF) e associe os equipamentos dele.
3. No menu de residências, escolha **6. Energia Solar Fotovoltaica → 1. Novo dimensionamento**.
4. Responda: consumo de referência (calculado pelo sistema ou média da conta de luz), percentual a atender e se quer baterias (e quantas horas de autonomia). O sistema escolhe sozinho a combinação compatível mais barata.
5. O sistema mostra a **proposta preliminar** com 8 seções: consumo e meta, recurso solar, geração, módulos, inversor, armazenamento, orçamento e origem dos preços.
6. O dimensionamento é salvo e pode ser revisto na opção **2**. A opção **3** roda a validação dos datasets.

---

## 6. Testes

`python testes.py` executa:
- os testes de cálculo da etapa anterior;
- **11 grupos de teste da sprint solar**, um para cada task "Testar..." do Trello (FV-PB01-T07, PB02-T05, PB03-T07, PB04-T08, PB05-T07, PB06-T07, PB07-T07, PB08-T06, PB09-T07, PB10-T06, PB11-T08);
- o relatório de validação dos datasets.

Os testes não alteram o `dados_sistema.json`. A mesma bateria de testes está no menu inicial, opção **3**.

---

## 7. Decisões tomadas sobre as especificações

| Ponto | Decisão |
|---|---|
| FV-PB04-T02 cita `paineis.csv`, FV-PB11 exige `modulos.csv` | Padronizado `modulos.csv` |
| FV-PB02-T02 diz "0 a 100%" | Aceito **maior que 0 e até 100**, pois 0% zera a potência e não gera sistema |
| Fórmula de N_bat aplicaria o DoD duas vezes | Usada `C_necessária = E_autonomia / η_bat` (ver seção 3) |
| Inversor "não considerar apenas preço" | Preço só decide **entre as combinações que passaram nas regras técnicas** |
| Outros custos (FV-PB09-T03) | Estrutura 8%, cabos 4%, proteções 5%, instalação R$ 500/kWp, projeto R$ 800 — premissas da equipe, mostradas separadas do custo de equipamentos |

---

## 8. Pendências antes da entrega

- Conferir no datasheet os itens marcados `CONFERIR_DATASHEET` e `CONFERIR_PRECO`, e guardar prints das páginas de preço.
- Substituir links de busca do Mercado Livre (`lista.mercadolivre.com.br/...`) pelo link do anúncio exato.
- Se possível, consultar o HSP direto no SunData com as coordenadas do imóvel e guardar o print.

---

> **Aviso:** resultado acadêmico de pré-dimensionamento. Não substitui projeto elétrico executivo, ART, análise de sombreamento nem vistoria da distribuidora.
