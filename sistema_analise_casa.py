#   ============================================================
#   SISTEMA DE DIMENSIONAMENTO ENERGÉTICO RESIDENCIAL
#   Equipe Lumos — FIAP
#   ============================================================
#
#   O sistema está dividido em 3 arquivos:
#     sistema_analise_casa.py  → este: telas, menus e dados do usuário
#     fotovoltaico.py          → cálculos, datasets, compatibilidade,
#                                orçamento e proposta da parte solar
#     testes.py                → testes automatizados
#
#   ETAPA ANTERIOR (PB01 a PB18)
#   PB01 Cadastro de usuário          PB10 Editar/remover associação
#   PB02 Login                        PB11 Consumo mensal por equipamento
#   PB03 Cadastro de imóvel           PB12 Consumo total do imóvel
#   PB04 Editar/excluir imóvel        PB13 Ranking de consumo
#   PB05 Cadastro de equipamento      PB14 Resumo do imóvel
#   PB06 Editar/excluir equipamento   PB15 Gráfico de consumo
#   PB07 Catálogo pré-cadastrado      PB16 Validação de dados
#   PB08 Associação imóvel-equip.     PB17 Persistência (JSON)
#   PB09 Quantidade e tempo de uso    PB18 Privacidade
#
#   EVOLUÇÃO FOTOVOLTAICA: tarefas com prefixo "FV-" (ver fotovoltaico.py).
#   Neste arquivo ficam as telas da parte solar.
#
#   Executar:  python sistema_analise_casa.py
#   Testes:    python testes.py   (ou opção 3 do menu inicial)
#   ============================================================

import os
import re
import json
import hashlib

import fotovoltaico as fv


ARQUIVO_DADOS = "dados_sistema.json"

# PB17 — tudo o que precisa sobreviver ao fechamento do programa
dados = {
    "usuarios": {},          # email -> {nome, telefone, senha_hash}
    "imoveis": {},           # id -> {endereco, numero, apelido, tipo, dono_email, localizacao}
    "equipamentos": {},      # id -> {nome, categoria, potencia, pre_cadastrado}
    "associacoes": {},       # id -> {imovel_id, equipamento_id, quantidade, tempo_uso}
    "dimensionamentos": {},  # FV-PB02-T03 — id -> cenário FV salvo
    "next_ids": {"imovel": 1, "equipamento": 1, "associacao": 1, "dimensionamento": 1},
}
sessao = {"email_logado": None}   # PB02-T05

TIPOS_IMOVEL = {"1": "Casa", "2": "Apartamento", "3": "Outro"}
UFS = {"AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
       "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"}


# ==================================================================
# UTILIDADES, PERSISTÊNCIA (PB17) E VALIDAÇÃO (PB16)
# ==================================================================

def limpar_terminal():
    os.system("cls" if os.name == "nt" else "clear")


def pausar():
    input("\nPressione ENTER para continuar...")


def concluir(mensagem=None):
    if mensagem:
        print(f"\n{mensagem}")
    pausar()
    limpar_terminal()


def salvar_dados():
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)


def carregar_dados():
    if os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
            dados.update(json.load(f))
        dados.setdefault("dimensionamentos", {})          # arquivos antigos
        dados["next_ids"].setdefault("dimensionamento", 1)
    else:
        popular_catalogo_inicial()
        salvar_dados()


def proximo_id(tipo):
    novo = str(dados["next_ids"][tipo])
    dados["next_ids"][tipo] += 1
    return novo


def validar_nao_vazio(texto):
    return texto.strip() != ""


def validar_email_formato(email):
    return re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email) is not None


def validar_numero_positivo(texto):
    try:
        return float(texto) > 0
    except ValueError:
        return False


def validar_inteiro_positivo(texto):
    try:
        return int(texto) > 0
    except ValueError:
        return False


def validar_intervalo_horas(texto):
    try:
        return 0 <= float(texto) <= 24
    except ValueError:
        return False


def ler(mensagem, valido=validar_nao_vazio, erro="ERRO: O campo não pode ficar vazio!", padrao=""):
    """Pergunta até receber um valor válido. ENTER mantém o 'padrao', se houver."""
    while True:
        texto = input(mensagem).strip()
        if texto == "" and padrao != "":
            return str(padrao)
        if valido(texto):
            return texto
        print(erro)


def ler_validado(mensagem, funcao):
    """Para validadores que lançam ValueError com a mensagem de erro (FV-PB02-T04)."""
    while True:
        try:
            return funcao(input(mensagem).strip())
        except ValueError as erro:
            print(f"ERRO: {erro}")


def ler_opcao_inteira(minimo, maximo):
    texto = ler(f"\nPOR FAVOR DIGITE UMA OPÇÃO ({minimo}-{maximo})...: ",
                lambda t: t.isdigit() and minimo <= int(t) <= maximo,
                f"ERRO: Escolha um número entre {minimo} e {maximo}.")
    return int(texto)


def ler_sim_nao(mensagem):
    return ler(mensagem, lambda t: t.upper() in ("S", "SIM", "N", "NAO", "NÃO"),
               "ERRO: Responda S ou N.").upper().startswith("S")


def confirmar(mensagem):
    return input(f"\n{mensagem} Digite SIM para confirmar...: ").strip().upper() == "SIM"


def ler_tipo_imovel():
    print("\nTIPO DO IMÓVEL: 1. Casa  2. Apartamento  3. Outro")
    return TIPOS_IMOVEL[ler("ESCOLHA UMA OPÇÃO...: ", lambda t: t in TIPOS_IMOVEL, "ERRO: Escolha 1, 2 ou 3.")]


def ler_localizacao():
    """FV-PB01-T01 — cidade e UF do imóvel."""
    cidade = ler("\nCIDADE DO IMÓVEL...: ")
    uf = ler("UF (ex.: SP)...: ", lambda t: t.upper() in UFS, "ERRO: Digite uma sigla de UF válida.").upper()
    return {"cidade": cidade, "uf": uf}


def executar_menu(titulo, opcoes):
    """Menu genérico: opcoes = [(texto, funcao), ...]. A última opção é sempre Voltar."""
    while True:
        print(f" ==== {titulo} ==== \n")
        for i, (texto, _) in enumerate(opcoes, start=1):
            print(f"{i}. {texto}")
        print(f"{len(opcoes) + 1}. Voltar")
        escolha = ler_opcao_inteira(1, len(opcoes) + 1)
        limpar_terminal()
        if escolha == len(opcoes) + 1:
            return
        opcoes[escolha - 1][1]()


# ==================================================================
# PB01 / PB02 — Usuário e login
# ==================================================================

def cadastro_user():
    print(" ==== CADASTRO DE CONTAS ==== \n")
    nome = ler("POR FAVOR DIGITE SEU NOME...: ")

    while True:
        email = ler("\nPOR FAVOR DIGITE O SEU EMAIL...: ")
        if not validar_email_formato(email):
            print("ERRO: Formato de e-mail inválido (ex: nome@dominio.com)!")
        elif email in dados["usuarios"]:
            print("ERRO: Este email já está cadastrado! Por favor, faça login.")
        else:
            break

    telefone = ler("\nPOR FAVOR DIGITE SEU TELEFONE (apenas números)...: ", str.isdigit,
                   "ERRO: Digite apenas números no telefone!")
    senha = ler("\nCRIE UMA SENHA PARA SUA CONTA...: ")

    dados["usuarios"][email] = {"nome": nome, "telefone": telefone,
                                "senha_hash": hashlib.sha256(senha.encode()).hexdigest()}
    salvar_dados()
    concluir("==== CADASTRO CONCLUÍDO COM SUCESSO ====")


def login():
    print("==== TELA DE LOGIN ====")
    email = ler("\nPOR FAVOR DIGITE SEU EMAIL CADASTRADO...: ")
    if email not in dados["usuarios"]:
        print("EMAIL NÃO CADASTRADO. POR FAVOR, SIGA PARA A PÁGINA DE CADASTRO.")
        return False

    usuario = dados["usuarios"][email]
    while True:
        senha = ler(f"\nBEM VINDO DE VOLTA {usuario['nome']} | DIGITE A SENHA...: ")
        if hashlib.sha256(senha.encode()).hexdigest() == usuario["senha_hash"]:
            break
        print("ERRO: Senha incorreta! Tente novamente.")

    sessao["email_logado"] = email
    concluir("==== LOG IN EFETUADO COM SUCESSO ====")
    return True


# ==================================================================
# PB18 — Privacidade: o usuário só enxerga os próprios imóveis
# ==================================================================

def imoveis_do_usuario_logado():
    return {i: im for i, im in dados["imoveis"].items() if im["dono_email"] == sessao["email_logado"]}


def selecionar_imovel_do_usuario():
    meus = imoveis_do_usuario_logado()
    if not meus:
        print("\nVOCÊ AINDA NÃO TEM NENHUM IMÓVEL CADASTRADO.")
        return None
    print("\n==== SEUS IMÓVEIS ====")
    for i, im in meus.items():
        loc = im.get("localizacao")
        local = f" — {loc['cidade']}/{loc['uf']}" if loc else ""
        print(f"{i}. {im['apelido']} — {im['endereco']}, {im['numero']} ({im['tipo']}){local}")
    return ler("\nEscolha o imóvel pelo número...: ", lambda t: t in meus,
               "ERRO: Número inválido ou este imóvel não pertence a você.")


# ==================================================================
# PB03 / PB04 — Imóveis
# ==================================================================

def cadastro_imovel():
    print("==== CADASTRO DE IMÓVEIS ====")
    imovel = {
        "endereco": ler("\nENDEREÇO DO IMÓVEL...: "),
        "numero": ler("\nNÚMERO DA RESIDÊNCIA...: "),
        "apelido": ler("\nAPELIDO PARA A RESIDÊNCIA...: "),
        "tipo": ler_tipo_imovel(),
        "localizacao": ler_localizacao(),          # FV-PB01-T01
        "dono_email": sessao["email_logado"],      # PB03-T06
    }
    dados["imoveis"][proximo_id("imovel")] = imovel
    salvar_dados()
    concluir("==== RESIDÊNCIA CADASTRADA COM SUCESSO ====")


def modificar_imovel():
    print("==== MODIFICAÇÃO DE IMÓVEL ====")
    id_imovel = selecionar_imovel_do_usuario()
    if id_imovel is None:
        return concluir()
    imovel = dados["imoveis"][id_imovel]
    loc = imovel.get("localizacao")
    print(f"\nEndereço: {imovel['endereco']} | Número: {imovel['numero']} | Apelido: {imovel['apelido']}"
          f" | Tipo: {imovel['tipo']} | Local: {loc['cidade'] + '/' + loc['uf'] if loc else '(não informado)'}")

    print("\n1. ENDEREÇO  2. NÚMERO  3. APELIDO  4. TIPO  5. LOCALIZAÇÃO")
    opcao = ler_opcao_inteira(1, 5)
    if opcao in (1, 2, 3):
        campo = ["endereco", "numero", "apelido"][opcao - 1]
        imovel[campo] = ler(f"\nATUAL: {imovel[campo]}\nNOVO VALOR...: ")
    elif opcao == 4:
        imovel["tipo"] = ler_tipo_imovel()
    else:
        imovel["localizacao"] = ler_localizacao()
    salvar_dados()
    concluir("DADO ATUALIZADO COM SUCESSO...")


def excluir_imovel():
    """PB04-T04/T05 — remove também associações e dimensionamentos do imóvel."""
    print("==== EXCLUSÃO DE IMÓVEL ====")
    id_imovel = selecionar_imovel_do_usuario()
    if id_imovel is None:
        return concluir()
    if not confirmar(f"EXCLUIR '{dados['imoveis'][id_imovel]['apelido']}' e os equipamentos e "
                     f"dimensionamentos associados a ele?"):
        return concluir("EXCLUSÃO CANCELADA.")
    for colecao in ("associacoes", "dimensionamentos"):
        for i in [i for i, reg in dados[colecao].items() if reg["imovel_id"] == id_imovel]:
            del dados[colecao][i]
    del dados["imoveis"][id_imovel]
    salvar_dados()
    concluir("==== IMÓVEL EXCLUÍDO COM SUCESSO ====")


# ==================================================================
# PB05 / PB06 / PB07 — Equipamentos e catálogo
# ==================================================================

CATALOGO_INICIAL = [
    ("Geladeira", "Cozinha", 133), ("Chuveiro elétrico", "Banheiro", 5500),
    ("Televisão", "Sala", 100), ("Ar-condicionado", "Quarto", 1200),
    ("Micro-ondas", "Cozinha", 1200), ("Ferro de passar", "Lavanderia", 1000),
    ("Máquina de lavar roupa", "Lavanderia", 500), ("Computador desktop", "Escritório", 200),
    ("Notebook", "Escritório", 65), ("Lâmpada LED", "Geral", 10),
]


def popular_catalogo_inicial():
    """PB07-T02/T03 — catálogo base criado na primeira execução."""
    for nome, categoria, potencia in CATALOGO_INICIAL:
        dados["equipamentos"][proximo_id("equipamento")] = {
            "nome": nome, "categoria": categoria, "potencia": potencia, "pre_cadastrado": True}


def listar_equipamentos():
    if not dados["equipamentos"]:
        print("\nNENHUM EQUIPAMENTO CADASTRADO AINDA.")
    for i, eq in dados["equipamentos"].items():
        origem = "(catálogo)" if eq.get("pre_cadastrado") else ""
        print(f"{i}. {eq['nome']} — {eq['categoria']} — {eq['potencia']}W {origem}")


def selecionar_equipamento():
    print("\n==== EQUIPAMENTOS CADASTRADOS ====")
    listar_equipamentos()
    if not dados["equipamentos"]:
        return None
    return ler("\nEscolha o equipamento pelo número...: ", lambda t: t in dados["equipamentos"],
               "ERRO: Número inválido.")


def cadastro_equipamento():
    """PB05 — do zero ou partindo de um item do catálogo (PB07), com potência > 0."""
    print("==== CADASTRO DE EQUIPAMENTO ====\n")
    catalogo = {i: eq for i, eq in dados["equipamentos"].items() if eq.get("pre_cadastrado")}
    for i, eq in catalogo.items():
        print(f"{i}. {eq['nome']} ({eq['categoria']}) — {eq['potencia']}W")
    print("0. Cadastrar um equipamento novo do zero")
    escolha = ler("\nESCOLHA UM NÚMERO...: ", lambda t: t == "0" or t in catalogo, "ERRO: Opção inválida.")
    base = catalogo.get(escolha, {"nome": "", "categoria": "", "potencia": ""})
    dica = " (ENTER mantém o valor entre colchetes)" if escolha != "0" else ""

    novo = {
        "nome": ler(f"\nNOME [{base['nome']}]{dica}...: ", padrao=base["nome"]),
        "categoria": ler(f"\nCATEGORIA [{base['categoria']}]...: ", padrao=base["categoria"]),
        "potencia": float(ler(f"\nPOTÊNCIA EM WATTS [{base['potencia']}]...: ", validar_numero_positivo,
                              "ERRO: Digite um número maior que zero.", padrao=base["potencia"])),
        "pre_cadastrado": False,
    }
    dados["equipamentos"][proximo_id("equipamento")] = novo
    salvar_dados()
    concluir("==== EQUIPAMENTO CADASTRADO COM SUCESSO ====")


def modificar_equipamento():
    print("==== MODIFICAÇÃO DE EQUIPAMENTO ====")
    id_eq = selecionar_equipamento()
    if id_eq is None:
        return concluir()
    eq = dados["equipamentos"][id_eq]
    print(f"\nATUAL: {eq['nome']} — {eq['categoria']} — {eq['potencia']}W")
    print("1. Nome  2. Categoria  3. Potência")
    opcao = ler_opcao_inteira(1, 3)
    if opcao == 3:
        eq["potencia"] = float(ler("\nNOVA POTÊNCIA (W)...: ", validar_numero_positivo,
                                   "ERRO: Digite um número maior que zero."))
    else:
        eq["nome" if opcao == 1 else "categoria"] = ler("\nNOVO VALOR...: ")
    salvar_dados()
    concluir("EQUIPAMENTO ATUALIZADO COM SUCESSO...")


def excluir_equipamento():
    """PB06-T04/T05 — avisa se o equipamento está em uso antes de excluir."""
    print("==== EXCLUSÃO DE EQUIPAMENTO ====")
    id_eq = selecionar_equipamento()
    if id_eq is None:
        return concluir()
    em_uso = [i for i, a in dados["associacoes"].items() if a["equipamento_id"] == id_eq]
    if em_uso and not confirmar(f"AVISO: equipamento associado a {len(em_uso)} imóvel(is). "
                                f"Excluir remove essas associações."):
        return concluir("EXCLUSÃO CANCELADA.")
    for i in em_uso:
        del dados["associacoes"][i]
    del dados["equipamentos"][id_eq]
    salvar_dados()
    concluir("==== EQUIPAMENTO EXCLUÍDO COM SUCESSO ====")


# ==================================================================
# PB08 / PB09 / PB10 — Associação imóvel-equipamento
# ==================================================================

def ler_quantidade():
    return int(ler("\nQUANTIDADE deste equipamento no imóvel...: ", validar_inteiro_positivo,
                   "ERRO: Digite um número inteiro maior que zero."))


def ler_tempo_uso():
    return float(ler("\nTEMPO DE USO DIÁRIO em horas (0 a 24)...: ", validar_intervalo_horas,
                     "ERRO: Digite um valor numérico entre 0 e 24."))


def associar_equipamento():
    print("==== ASSOCIAR EQUIPAMENTO A UM IMÓVEL ====")
    id_imovel = selecionar_imovel_do_usuario()
    id_eq = selecionar_equipamento() if id_imovel else None
    if id_eq is None:
        return concluir()
    dados["associacoes"][proximo_id("associacao")] = {
        "imovel_id": id_imovel, "equipamento_id": id_eq,
        "quantidade": ler_quantidade(), "tempo_uso": ler_tempo_uso()}
    salvar_dados()
    concluir("==== EQUIPAMENTO ASSOCIADO COM SUCESSO ====")


def listar_associacoes_do_imovel(id_imovel):
    return {i: a for i, a in dados["associacoes"].items() if a["imovel_id"] == id_imovel}


def selecionar_associacao():
    id_imovel = selecionar_imovel_do_usuario()
    if id_imovel is None:
        return None
    associacoes = listar_associacoes_do_imovel(id_imovel)
    if not associacoes:
        print("\nNENHUM EQUIPAMENTO ASSOCIADO A ESTE IMÓVEL AINDA.")
        return None
    for i, a in associacoes.items():
        print(f"{i}. {dados['equipamentos'][a['equipamento_id']]['nome']} — "
              f"qtd: {a['quantidade']} — {a['tempo_uso']}h/dia")
    return ler("\nESCOLHA O NÚMERO DA ASSOCIAÇÃO...: ", lambda t: t in associacoes, "ERRO: Número inválido.")


def editar_associacao():
    print("==== EDITAR ASSOCIAÇÃO ====")
    id_assoc = selecionar_associacao()
    if id_assoc is None:
        return concluir()
    print("\n1. Quantidade  2. Tempo de uso")
    if ler_opcao_inteira(1, 2) == 1:
        dados["associacoes"][id_assoc]["quantidade"] = ler_quantidade()
    else:
        dados["associacoes"][id_assoc]["tempo_uso"] = ler_tempo_uso()
    salvar_dados()
    concluir("ASSOCIAÇÃO ATUALIZADA COM SUCESSO...")


def remover_associacao():
    print("==== REMOVER EQUIPAMENTO DO IMÓVEL ====")
    id_assoc = selecionar_associacao()
    if id_assoc is None:
        return concluir()
    if not confirmar("CONFIRMA A REMOÇÃO?"):
        return concluir("REMOÇÃO CANCELADA.")
    del dados["associacoes"][id_assoc]
    salvar_dados()
    concluir("==== ASSOCIAÇÃO REMOVIDA COM SUCESSO ====")


# ==================================================================
# PB11 a PB15 — Consumo, ranking, resumo e gráfico
# ==================================================================

def calcular_consumo_associacao(assoc):
    """PB11 — potência (W) × quantidade × horas/dia × 30 / 1000 = kWh/mês. Dado faltando → 0."""
    eq = dados["equipamentos"].get(assoc.get("equipamento_id"))
    try:
        return eq["potencia"] * assoc["quantidade"] * assoc["tempo_uso"] * 30 / 1000
    except (TypeError, KeyError):
        return 0.0


def consumo_total_imovel(id_imovel):
    """PB12."""
    return sum(calcular_consumo_associacao(a) for a in listar_associacoes_do_imovel(id_imovel).values())


def ranking_consumo_imovel(id_imovel):
    """PB13 — do maior para o menor."""
    itens = [(dados["equipamentos"][a["equipamento_id"]]["nome"], calcular_consumo_associacao(a))
             for a in listar_associacoes_do_imovel(id_imovel).values()]
    return sorted(itens, key=lambda item: item[1], reverse=True)


def exibir_relatorio(tipo):
    """PB13 (ranking), PB14 (resumo) e PB15 (gráfico ASCII)."""
    id_imovel = selecionar_imovel_do_usuario()
    if id_imovel is None:
        return concluir()
    imovel = dados["imoveis"][id_imovel]
    ranking = ranking_consumo_imovel(id_imovel)

    if tipo == "resumo":
        print(f"\n==== RESUMO — {imovel['apelido']} ====")
        print(f"Endereço: {imovel['endereco']}, {imovel['numero']} | Tipo: {imovel['tipo']}")
        print(f"Quantidade de equipamentos: {len(ranking)}")
        print(f"Consumo total estimado: {consumo_total_imovel(id_imovel):.2f} kWh/mês\n")
    if not ranking:
        return concluir("ESTE IMÓVEL NÃO TEM EQUIPAMENTOS ASSOCIADOS.")

    maior = ranking[0][1] or 1
    for posicao, (nome, consumo) in enumerate(ranking, start=1):
        if tipo == "grafico":
            print(f"{nome:<25} {'█' * int(consumo / maior * 40)} {consumo:.2f}")
        elif tipo == "ranking":
            print(f"{posicao}º {nome} — {consumo:.2f} kWh/mês")
        else:
            print(f"  - {nome}: {consumo:.2f} kWh/mês")
    concluir()


# ==================================================================
# TELAS DA PARTE SOLAR (a lógica está em fotovoltaico.py)
# ==================================================================

def novo_dimensionamento_fv():
    print("==== DIMENSIONAMENTO FOTOVOLTAICO ====")
    id_imovel = selecionar_imovel_do_usuario()                 # PB18
    if id_imovel is None:
        return concluir()
    imovel = dados["imoveis"][id_imovel]
    try:
        ds = fv.carregar_datasets_fv()
    except FileNotFoundError as erro:
        return concluir(f"ERRO: {erro}")

    # FV-PB01 — localização e HSP (imóveis antigos recebem a pergunta aqui)
    if not imovel.get("localizacao") or ler_sim_nao(
            f"\nLocalização: {imovel['localizacao']['cidade']}/{imovel['localizacao']['uf']}. Alterar? (S/N)...: "):
        imovel["localizacao"] = ler_localizacao()
        salvar_dados()
    loc = imovel["localizacao"]
    try:
        hsp_info = fv.obter_hsp(loc["cidade"], loc["uf"], ds["hsp"])
    except ValueError:
        print(f"\nNão há HSP cadastrado para {loc['cidade']}/{loc['uf']}. Consulte o CRESESB SunData.")
        hsp = ler_validado("HSP do município (kWh/m²/dia)...: ", fv.validar_hsp)
        fonte = ler("Origem do valor (ex.: CRESESB SunData - Osasco/SP)...: ")
        hsp_info = fv.obter_hsp(loc["cidade"], loc["uf"], ds["hsp"], hsp, fonte)
    print(f"HSP utilizado: {fv.num(hsp_info['hsp'])} kWh/m²/dia — origem: {hsp_info['fonte']}")   # FV-PB01-T06

    # FV-PB03-T01 — consumo de referência
    calculado = consumo_total_imovel(id_imovel)
    print(f"\nConsumo calculado pelos equipamentos: {fv.num(calculado)} kWh/mês")
    if calculado > 0 and ler_sim_nao("Usar este consumo? (S = sim / N = informar média da conta de luz)...: "):
        consumo, origem = calculado, "calculado pelos equipamentos do imóvel"
    else:
        consumo = ler_validado("Consumo médio mensal da conta (kWh/mês)...: ", lambda t: fv.positivo("Consumo", t))
        origem = "média da conta de luz"

    percentual = ler_validado("\nPERCENTUAL DO CONSUMO A ATENDER (1 a 100)...: ",
                              lambda t: fv.validar_percentual(t) * 100)            # FV-PB02-T01/T02/T04
    com_bateria = ler_sim_nao("\nDESEJA BATERIAS? (S/N)...: ")                  # FV-PB06-T01
    autonomia = ler_validado("AUTONOMIA DESEJADA (horas, até 72)...: ", fv.validar_autonomia) if com_bateria else None

    try:
        r = fv.dimensionar_fv(consumo, percentual, hsp_info, ds, com_bateria, autonomia, origem)
    except fv.ErroDimensionamento as erro:                                         # FV-PB08-T04/T05
        return concluir(f"NÃO FOI POSSÍVEL MONTAR A SOLUÇÃO: {erro}\n{fv.formatar_incompatibilidades(erro.rejeitados)}")
    except ValueError as erro:                                                  # FV-PB03-T05
        return concluir(f"ERRO NOS DADOS DE ENTRADA: {erro}")

    limpar_terminal()
    print(fv.formatar_proposta(r, imovel["apelido"]))                              # FV-PB10-T02
    if ler_sim_nao("\nVer combinações bloqueadas por incompatibilidade? (S/N)...: "):
        print(fv.formatar_incompatibilidades(r["rejeitados"]))

    # FV-PB02-T03 — cenário salvo no dados_sistema.json
    arm, sel = r["armazenamento"], r["selecao"]
    id_dim = proximo_id("dimensionamento")
    dados["dimensionamentos"][id_dim] = {
        "imovel_id": id_imovel, "data": r["data"], "consumo_kwh_mes": round(consumo, 2),
        "percentual": r["percentual"], "localidade": f"{loc['cidade']}/{loc['uf']}",
        "hsp": hsp_info["hsp"], "fonte_hsp": hsp_info["fonte"],
        "potencia_calculada_kwp": round(r["p_fv"], 3), "potencia_instalada_kwp": round(r["p_inst"], 3),
        "modulo_id": sel["modulo"]["id"], "n_modulos": sel["config"]["n_modulos"],
        "inversor_id": sel["inversor"]["id"],
        "bateria_id": arm["bateria"]["id"] if arm["ativo"] else None, "n_baterias": arm["n_baterias"],
        "capacidade_instalada_kwh": arm["capacidade_instalada_kwh"],
        "c_equipamentos": r["orcamento"]["c_equipamentos"], "c_total": r["orcamento"]["c_total"],
    }
    salvar_dados()
    concluir(f"DIMENSIONAMENTO #{id_dim} SALVO.")


def listar_dimensionamentos_fv():
    print("==== DIMENSIONAMENTOS SALVOS ====")
    id_imovel = selecionar_imovel_do_usuario()
    if id_imovel is None:
        return concluir()
    salvos = {i: d for i, d in dados["dimensionamentos"].items() if d["imovel_id"] == id_imovel}
    if not salvos:
        print("\nNenhum dimensionamento salvo para este imóvel.")
    for i, d in salvos.items():
        bat = f"{d['n_baterias']}× {d['bateria_id']}" if d["bateria_id"] else "sem baterias"
        print(f"\n#{i} {d['data']} | {fv.num(d['consumo_kwh_mes'])} kWh/mês × {fv.num(d['percentual'], 0)}% | "
              f"HSP {fv.num(d['hsp'])} | {fv.num(d['potencia_instalada_kwp'])} kWp ({d['n_modulos']}× {d['modulo_id']}) | "
              f"{d['inversor_id']} | {bat} | total {fv.brl(d['c_total'])}")
    concluir()


def tela_validar_datasets():
    try:
        print(fv.validar_datasets_fv()[1])
    except FileNotFoundError as erro:
        print(f"ERRO: {erro}")
    concluir()


# ==================================================================
# MENUS
# ==================================================================

def menu_residencia():
    executar_menu("SISTEMA DE RESIDÊNCIAS", [
        ("CADASTRO DE IMÓVEL", cadastro_imovel),
        ("MODIFICAR INFORMAÇÕES DO IMÓVEL", modificar_imovel),
        ("EXCLUIR IMÓVEL", excluir_imovel),
        ("ADICIONAR/GERENCIAR EQUIPAMENTOS", lambda: executar_menu("EQUIPAMENTOS", [
            ("Cadastrar equipamento", cadastro_equipamento),
            ("Listar equipamentos", lambda: (listar_equipamentos(), concluir())),
            ("Editar equipamento", modificar_equipamento),
            ("Excluir equipamento", excluir_equipamento),
            ("Associar equipamento a um imóvel", associar_equipamento),
            ("Editar associação (quantidade/tempo de uso)", editar_associacao),
            ("Remover associação", remover_associacao)])),
        ("ECONOMIA DO IMÓVEL", lambda: executar_menu("ECONOMIA DO IMÓVEL", [
            ("Resumo do imóvel", lambda: exibir_relatorio("resumo")),
            ("Ranking de consumo por equipamento", lambda: exibir_relatorio("ranking")),
            ("Gráfico de distribuição do consumo", lambda: exibir_relatorio("grafico"))])),
        ("ENERGIA SOLAR FOTOVOLTAICA", lambda: executar_menu("ENERGIA SOLAR FOTOVOLTAICA", [
            ("Novo dimensionamento / proposta preliminar", novo_dimensionamento_fv),
            ("Ver dimensionamentos salvos de um imóvel", listar_dimensionamentos_fv),
            ("Validar datasets", tela_validar_datasets)])),
    ])


def iniciar_user():
    while True:
        print(" ==== SISTEMA DE CADASTRO DE USUÁRIOS ==== \n")
        print("1. CADASTRO DE CONTA\n2. LOG IN\n3. RODAR TESTES AUTOMATIZADOS (QA)\n4. SAIR DO SISTEMA")
        opcao = ler_opcao_inteira(1, 4)
        limpar_terminal()
        if opcao == 1:
            cadastro_user()
        elif opcao == 2:
            if login():
                menu_residencia()
                sessao["email_logado"] = None      # PB02/PB18: encerra a sessão
            else:
                concluir()
        elif opcao == 3:
            import testes            # carregado só quando pedido
            testes.rodar_todos_os_testes()
            concluir()
        else:
            print("Até a próxima!")
            break


if __name__ == "__main__":
    carregar_dados()
    iniciar_user()
