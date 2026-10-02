#   ============================================================
#   fotovoltaico.py — REGRAS DE NEGÓCIO DA EVOLUÇÃO FOTOVOLTAICA
#   Equipe Lumos — FIAP
#
#   Só cálculos e dados: este arquivo NÃO faz perguntas ao usuário
#   nem mexe no dados_sistema.json. As telas ficam no
#   sistema_analise_casa.py e os testes em testes.py.
#
#   O CSV de tasks da sprint FV recomeça em PB01, por isso aqui se
#   usa o prefixo "FV-" (ex.: FV-PB04-T05 = cartão "PB04 - T05").
#   FV-PB01 Localização/HSP           FV-PB07 Baterias
#   FV-PB02 Percentual de atendimento FV-PB08 Compatibilidade
#   FV-PB03 Energia e potência FV     FV-PB09 Orçamento
#   FV-PB04 Módulos                   FV-PB10 Proposta preliminar
#   FV-PB05 Inversor                  FV-PB11 Base de equipamentos
#   FV-PB06 Armazenamento opcional
#   ============================================================

import os
import csv
import math
import unicodedata
from datetime import datetime

# pasta dados_fv/ ao lado deste arquivo (funciona de qualquer diretório)
PASTA_FV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados_fv")


# FV-PB03-T03 / FV-PB09-T03 — parâmetros e premissas (fontes no README)
PARAMETROS_FV = {
    "dias_mes": 30,             # D (enunciado)
    "eta_global": 0.78,         # η — performance ratio típico 75-80% (EPE, NT DEA-SEE 009/2023)
    "eta_bateria": 0.95,        # η_bat — eficiência típica LiFePO4 (premissa da equipe)
    "hsp_min": 3.0,             # FV-PB01-T05 — faixa plausível no Brasil (CRESESB/Atlas 2017)
    "hsp_max": 7.0,
    "fator_voc_frio": 1.10,     # margem: tensão sobe no frio
    "fator_vmp_quente": 0.90,   # margem: tensão cai no calor
    "ratio_dc_ac_min": 0.60,    # on-grid
    "ratio_dc_ac_min_hibrido": 0.30,
    "ratio_dc_ac_max": 1.35,
    "autonomia_max_h": 72,
    "outros_custos_pct": {"Estrutura de fixação": 8, "Cabeamento e conectores": 4,
                          "Proteções / string box": 5},   # % sobre equipamentos
    "instalacao_por_kwp": 500.0,
    "projeto_homologacao": 800.0,
}

# FV-PB04-T01 / FV-PB05-T01 / FV-PB07-T01 / FV-PB11-T01 — schema de cada dataset
# (arquivo, mínimo de itens, campos de texto obrigatórios, campos numéricos obrigatórios)
# Obs.: FV-PB04-T02 cita "paineis.csv"; FV-PB11 exige "modulos.csv" — padronizado modulos.csv.
RASTREIO = ["fornecedor", "data_coleta", "url_fonte"]
DATASETS_FV = {
    "modulos": ("modulos.csv", 10, ["id", "fabricante", "modelo"] + RASTREIO,
                ["potencia_wp", "voc_v", "isc_a", "vmp_v", "imp_a", "eficiencia_pct", "preco_brl"]),
    "inversores": ("inversores.csv", 8, ["id", "fabricante", "modelo", "tipo", "compativel_bateria"] + RASTREIO,
                   ["potencia_nominal_w", "potencia_max_fv_w", "tensao_max_entrada_v", "faixa_mppt_min_v",
                    "faixa_mppt_max_v", "corrente_max_entrada_a", "numero_mppt", "strings_por_mppt",
                    "tensao_bateria_min_v", "tensao_bateria_max_v", "preco_brl"]),
    "baterias": ("baterias.csv", 6, ["id", "fabricante", "modelo", "tecnologia"] + RASTREIO,
                 ["tensao_nominal_v", "capacidade_ah", "capacidade_kwh", "dod_pct", "ciclos", "preco_brl"]),
}


# ------------------------------------------------------------------
# Leitura e validação dos datasets
# ------------------------------------------------------------------

def ler_csv(nome_arquivo):
    """Lê um CSV de dados_fv/ convertendo para float tudo que for número (FV-PB11-T06)."""
    caminho = os.path.join(PASTA_FV, nome_arquivo)
    if not os.path.exists(caminho):
        raise FileNotFoundError(f"Arquivo '{caminho}' não encontrado. Deixe a pasta {PASTA_FV}/ ao lado do sistema.")
    with open(caminho, "r", encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f))
    for linha in linhas:
        for campo, valor in linha.items():
            valor = (valor or "").strip()
            try:
                linha[campo] = float(valor)
            except ValueError:
                linha[campo] = valor
    return linhas


def carregar_dataset(categoria):
    """
    FV-PB04-T03 / FV-PB05-T03 / FV-PB07-T03 — devolve (validos, pendentes).
    Linha pendente = item incompleto, sem preço ou sem link: fica fora dos cálculos.
    """
    arquivo, _, textos, numeros = DATASETS_FV[categoria]
    validos, pendentes = [], []
    for item in ler_csv(arquivo):
        if any(item.get(c, "") == "" for c in textos):
            motivo = "campo de texto vazio"
        elif any(not isinstance(item.get(c), float) for c in numeros):
            motivo = "campo numérico vazio ou inválido"
        elif item["preco_brl"] <= 0 or not str(item["url_fonte"]).startswith("http"):
            motivo = "sem preço ou sem URL de fonte"
        else:
            motivo = None
        if motivo:
            pendentes.append((item.get("id", "?"), motivo))
        else:
            validos.append(item)
    if categoria == "inversores":
        for inv in validos:
            inv["compativel_bateria"] = str(inv["compativel_bateria"]).upper() == "SIM"
    return validos, pendentes


def normalizar_localidade(cidade, uf):
    texto = unicodedata.normalize("NFKD", f"{cidade.strip()}/{uf.strip()}".upper())
    return "".join(c for c in texto if not unicodedata.combining(c))


def carregar_datasets_fv():
    """Carrega tudo o que o dimensionamento usa. FV-PB01-T03: HSP + origem do dado."""
    hsp = {normalizar_localidade(l["cidade"], l["uf"]): {
        "cidade": l["cidade"], "uf": l["uf"], "hsp": l["hsp_kwh_m2_dia"],
        "fonte": l["fonte"], "url_fonte": l["url_fonte"]} for l in ler_csv("hsp_localidades.csv")}
    ds = {cat: carregar_dataset(cat)[0] for cat in DATASETS_FV}
    ds["hsp"] = hsp
    return ds


def validar_datasets_fv():
    """FV-PB11-T08 — quantidade mínima, dados completos, rastreabilidade de fonte e preço."""
    aprovado, linhas = True, ["==== VALIDAÇÃO DOS DATASETS (FV-PB11-T08) ===="]
    for categoria, (arquivo, minimo, _, _) in DATASETS_FV.items():
        validos, pendentes = carregar_dataset(categoria)
        ids = [v["id"] for v in validos]
        ok = len(validos) >= minimo and len(ids) == len(set(ids))
        aprovado = aprovado and ok
        linhas.append(f"[{'OK' if ok else 'PENDENTE'}] {arquivo}: {len(validos)} válidos / mínimo {minimo}")
        linhas += [f"   - pendente {pid}: {motivo}" for pid, motivo in pendentes]
        conferir = [v["id"] for v in validos if str(v.get("status_validacao", "")).startswith("CONFERIR")]
        if conferir:
            linhas.append(f"   - conferir datasheet/preço antes da entrega: {', '.join(conferir)}")
    linhas.append(f"RESULTADO GERAL: {'APROVADO' if aprovado else 'COM PENDÊNCIAS'}")
    return aprovado, "\n".join(linhas)


# ------------------------------------------------------------------
# Fórmulas (funções puras). FV-PB03-T05: dado ausente/inválido → ValueError
# ------------------------------------------------------------------

def positivo(nome, valor):
    try:
        valor = float(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        raise ValueError(f"{nome} não informado ou não numérico.")
    if not math.isfinite(valor) or valor <= 0:
        raise ValueError(f"{nome} deve ser maior que zero.")
    return valor


def arredondar_para_cima(valor):
    """Evita que 8.0000000001 vire 9 por erro de ponto flutuante."""
    return math.ceil(round(valor, 9))


def validar_percentual(texto):
    """FV-PB02-T02 — aceita (0, 100]. 0% não gera sistema. Devolve a fração f."""
    p = positivo("Percentual", str(texto).replace("%", ""))
    if p > 100:
        raise ValueError("Percentual deve ser no máximo 100%.")
    return p / 100


def validar_hsp(valor):
    """FV-PB01-T05 — faixa plausível 3,0 a 7,0 kWh/m²/dia."""
    hsp = positivo("HSP", valor)
    if not PARAMETROS_FV["hsp_min"] <= hsp <= PARAMETROS_FV["hsp_max"]:
        raise ValueError(f"HSP {hsp} fora da faixa plausível (3,0 a 7,0 kWh/m²/dia).")
    return hsp


def validar_autonomia(valor):
    """FV-PB06-T02 — autonomia em (0, 72] horas."""
    horas = positivo("Autonomia", valor)
    if horas > PARAMETROS_FV["autonomia_max_h"]:
        raise ValueError("Autonomia máxima aceita: 72 h.")
    return horas


def energia_mensal_desejada(cm, f):
    """FV-PB03-T02 — E_FV = Cm × f"""
    if positivo("Fração de atendimento", f) > 1:
        raise ValueError("Fração de atendimento não pode passar de 1 (100%).")
    return positivo("Consumo de referência", cm) * f


def potencia_fv_necessaria(e_fv, hsp, dias, eta):
    """FV-PB03-T04 — P_FV = E_FV / (HSP × D × η)   [kWp]"""
    if positivo("η", eta) > 1:
        raise ValueError("η deve estar entre 0 e 1.")
    return positivo("Energia desejada", e_fv) / (positivo("HSP", hsp) * positivo("Dias", dias) * eta)


def quantidade_minima_modulos(p_fv, p_modulo):
    """FV-PB04-T05 — N = ⌈(P_FV × 1000) / P_módulo⌉"""
    return arredondar_para_cima(positivo("P_FV", p_fv) * 1000 / positivo("Potência do módulo", p_modulo))


def potencia_instalada(n, p_modulo):
    """FV-PB04-T06 — P_instalada = (N × P_módulo) / 1000   [kWp]"""
    return positivo("Quantidade de módulos", n) * positivo("Potência do módulo", p_modulo) / 1000


def consumo_diario(cm):
    """FV-PB06-T03 — E_d = Cm / 30"""
    return positivo("Consumo mensal", cm) / 30


def energia_autonomia(e_d, horas):
    """FV-PB06-T04 — E_autonomia = E_d × (A / 24)"""
    return positivo("Consumo diário", e_d) * positivo("Autonomia", horas) / 24


def capacidade_bateria_necessaria(e_aut, dod, eta_bat):
    """FV-PB06-T05 — C_bat = E_autonomia / (DoD × η_bat)   [kWh nominais]"""
    if positivo("DoD", dod) > 1 or positivo("η_bat", eta_bat) > 1:
        raise ValueError("DoD e η_bat devem estar entre 0 e 1.")
    return positivo("Energia de autonomia", e_aut) / (dod * eta_bat)


def capacidade_util(c_nominal, dod):
    """FV-PB07-T04 — C_útil = C_nominal × DoD"""
    return positivo("Capacidade nominal", c_nominal) * positivo("DoD", dod)


def quantidade_baterias(c_necessaria, c_util):
    """
    FV-PB07-T05 — N_bat = ⌈C_necessária / C_útil⌉, com C_necessária = E_autonomia / η_bat.
    Usar C_bat (já dividido pelo DoD) contra C_útil (já multiplicado pelo DoD) contaria o DoD
    duas vezes. Equivale a ⌈C_bat / C_nominal⌉ (conferido nos testes).
    """
    return arredondar_para_cima(positivo("Capacidade necessária", c_necessaria) / positivo("C_útil", c_util))


def obter_hsp(cidade, uf, tabela, hsp_manual=None, fonte_manual=None):
    """FV-PB01-T04 — HSP da tabela; cidade fora da tabela exige valor E fonte."""
    if hsp_manual is not None:
        if not str(fonte_manual or "").strip():
            raise ValueError("Informe a origem do HSP (ex.: 'CRESESB SunData - Osasco/SP').")
        return {"cidade": cidade, "uf": uf.upper(), "hsp": validar_hsp(hsp_manual),
                "fonte": fonte_manual.strip(), "url_fonte": "informado pelo usuário"}
    registro = tabela.get(normalizar_localidade(cidade, uf))
    if registro is None:
        raise ValueError(f"Não há HSP cadastrado para {cidade}/{uf}.")
    validar_hsp(registro["hsp"])
    return dict(registro)


# ------------------------------------------------------------------
# FV-PB08-T01 — CRITÉRIOS DE COMPATIBILIDADE
#  C1 Voc_string × 1,10 ≤ tensão máx. de entrada do inversor
#  C2 Vmp_string ≤ faixa MPPT máxima
#  C3 Vmp_string × 0,90 ≥ faixa MPPT mínima
#  C4 corrente das strings em paralelo ≤ corrente máx. por MPPT
#  C5 P_instalada ≤ potência FV máxima do inversor            (FV-PB05-T04)
#  C6 razão DC/AC dentro da faixa (on-grid 0,60-1,35; híbrido 0,30-1,35)
#  C7 com armazenamento → inversor híbrido
#  C8 tensão da bateria dentro da faixa de bateria do inversor
# ------------------------------------------------------------------

def verificar_modulo_inversor(n_minimo, mod, inv, com_bateria, P=PARAMETROS_FV):
    """
    FV-PB05-T05 + FV-PB08-T02/T04 — devolve (configuração ou None, motivos de bloqueio).
    Monta o menor número de strings iguais com pelo menos n_minimo módulos; por isso o
    N final pode ficar um pouco acima do N mínimo.
    """
    motivos = []
    if com_bateria and not inv["compativel_bateria"]:
        motivos.append("C7: armazenamento pedido, mas o inversor não é híbrido")

    serie_max = min(math.floor(inv["tensao_max_entrada_v"] / (mod["voc_v"] * P["fator_voc_frio"])),
                    math.floor(inv["faixa_mppt_max_v"] / mod["vmp_v"]))
    serie_min = math.ceil(inv["faixa_mppt_min_v"] / (mod["vmp_v"] * P["fator_vmp_quente"]))
    paralelo_max = min(int(inv["strings_por_mppt"]), math.floor(inv["corrente_max_entrada_a"] / mod["imp_a"]))

    if paralelo_max < 1:
        motivos.append(f"C4: corrente do módulo ({mod['imp_a']} A) > máx. do inversor ({inv['corrente_max_entrada_a']} A)")
    if serie_max < 1 or serie_min > serie_max:
        motivos.append("C1-C3: nenhuma quantidade de módulos em série cabe na faixa de tensão do inversor")
    if motivos:
        return None, motivos

    n_strings = math.ceil(n_minimo / serie_max)
    if n_strings > int(inv["numero_mppt"]) * paralelo_max:
        return None, [f"C1-C4: {n_minimo} módulos não cabem nas entradas do inversor"]
    por_string = max(math.ceil(n_minimo / n_strings), serie_min)
    n_final = n_strings * por_string
    p_inst = potencia_instalada(n_final, mod["potencia_wp"])
    ratio = p_inst * 1000 / inv["potencia_nominal_w"]
    ratio_min = P["ratio_dc_ac_min_hibrido"] if inv["compativel_bateria"] else P["ratio_dc_ac_min"]

    if p_inst * 1000 > inv["potencia_max_fv_w"]:
        motivos.append(f"C5: {p_inst * 1000:.0f} Wp > máximo do inversor ({inv['potencia_max_fv_w']:.0f} W)")
    if not ratio_min <= ratio <= P["ratio_dc_ac_max"]:
        motivos.append(f"C6: razão DC/AC {ratio:.2f} fora da faixa {ratio_min}-{P['ratio_dc_ac_max']}")
    if motivos:
        return None, motivos
    return {"n_modulos": n_final, "n_strings": n_strings, "por_string": por_string,
            "potencia_instalada_kwp": p_inst, "ratio_dc_ac": ratio,
            "voc_string_v": por_string * mod["voc_v"] * P["fator_voc_frio"],
            "vmp_string_v": por_string * mod["vmp_v"]}, []


def verificar_inversor_bateria(inv, bat):
    """FV-PB08-T03 — devolve lista de motivos (vazia = compatível)."""
    if not inv["compativel_bateria"]:
        return ["C7: inversor on-grid não aceita baterias"]
    if not inv["tensao_bateria_min_v"] <= bat["tensao_nominal_v"] <= inv["tensao_bateria_max_v"]:
        return [f"C8: bateria de {bat['tensao_nominal_v']} V fora da faixa do inversor "
                f"({inv['tensao_bateria_min_v']:.0f}-{inv['tensao_bateria_max_v']:.0f} V)"]
    return []


def selecionar_modulo_inversor(p_fv, ds, com_bateria):
    """
    FV-PB04-T04 + FV-PB05-T06 — testa todas as combinações módulo × inversor, bloqueia as
    incompatíveis e só então escolhe a mais barata (preço não decide sozinho).
    """
    candidatos, rejeitados = [], []
    for mod in ds["modulos"]:
        n_min = quantidade_minima_modulos(p_fv, mod["potencia_wp"])
        for inv in ds["inversores"]:
            config, motivos = verificar_modulo_inversor(n_min, mod, inv, com_bateria)
            if config is None:
                rejeitados.append((f"{mod['id']} × {inv['id']}", motivos))
            else:
                custo = config["n_modulos"] * mod["preco_brl"] + inv["preco_brl"]
                candidatos.append((custo, config["potencia_instalada_kwp"],
                                   {"modulo": mod, "inversor": inv, "n_minimo": n_min, "config": config}))
    if not candidatos:
        return None, rejeitados
    candidatos.sort(key=lambda c: (c[0], c[1]))          # menor custo; desempate: menor sobra
    escolhido = candidatos[0][2]
    escolhido["alternativas_validas"] = len(candidatos)
    return escolhido, rejeitados


def selecionar_bateria(e_aut, baterias, inv):
    """FV-PB07 — entre as baterias compatíveis com o inversor, a de menor custo total."""
    eta = PARAMETROS_FV["eta_bateria"]
    candidatos, rejeitados = [], []
    for bat in baterias:
        motivos = verificar_inversor_bateria(inv, bat)
        if motivos:
            rejeitados.append((f"{inv['id']} × {bat['id']}", motivos))
            continue
        dod = bat["dod_pct"] / 100
        c_util = capacidade_util(bat["capacidade_kwh"], dod)
        n_bat = quantidade_baterias(e_aut / eta, c_util)
        candidatos.append({
            "ativo": True, "bateria": bat, "n_baterias": n_bat,
            "c_bat_kwh": capacidade_bateria_necessaria(e_aut, dod, eta),
            "capacidade_instalada_kwh": n_bat * bat["capacidade_kwh"],
            "capacidade_util_kwh": n_bat * c_util,
            "custo": round(n_bat * bat["preco_brl"], 2)})
    if not candidatos:
        return None, rejeitados
    return min(candidatos, key=lambda c: c["custo"]), rejeitados


def calcular_orcamento(sel, arm):
    """
    FV-PB09-T01/T02 — C_equipamentos = módulos + inversor + baterias (preços dos datasets)
    FV-PB09-T03     — outros custos (premissas)    FV-PB09-T04 — sem bateria → 0
    FV-PB09-T05     — C_total = C_equipamentos + outros
    """
    mod, inv, cfg = sel["modulo"], sel["inversor"], sel["config"]
    itens = [(cfg["n_modulos"], f"Módulo {mod['fabricante']} {mod['modelo']}", mod),
             (1, f"Inversor {inv['fabricante']} {inv['modelo']}", inv)]
    if arm["ativo"]:
        b = arm["bateria"]
        itens.append((arm["n_baterias"], f"Bateria {b['fabricante']} {b['modelo']}", b))
    itens = [{"qtd": q, "item": nome, "subtotal": round(q * eq["preco_brl"], 2),
              "fonte": f"{eq['fornecedor']} ({eq['data_coleta']}) {eq['url_fonte']}"} for q, nome, eq in itens]

    c_baterias = arm["custo"] if arm["ativo"] else 0.0
    c_equip = round(sum(i["subtotal"] for i in itens), 2)
    outros = [(nome, c_equip * pct / 100, f"{pct}% dos equipamentos")
              for nome, pct in PARAMETROS_FV["outros_custos_pct"].items()]
    outros.append(("Instalação (mão de obra)", PARAMETROS_FV["instalacao_por_kwp"] * cfg["potencia_instalada_kwp"],
                   f"R$ {PARAMETROS_FV['instalacao_por_kwp']:.0f}/kWp"))
    outros.append(("Projeto e homologação", PARAMETROS_FV["projeto_homologacao"], "valor fixo"))
    c_outros = round(sum(v for _, v, _ in outros), 2)
    return {"itens": itens, "c_baterias": c_baterias, "c_equipamentos": c_equip,
            "outros": outros, "c_outros": c_outros, "c_total": round(c_equip + c_outros, 2)}


class ErroDimensionamento(Exception):
    """FV-PB08-T04 — combinação bloqueada; guarda os motivos para exibir (FV-PB08-T05)."""

    def __init__(self, mensagem, rejeitados):
        super().__init__(mensagem)
        self.rejeitados = rejeitados


def dimensionar_fv(consumo, percentual, hsp_info, ds, com_bateria=False, autonomia=None, origem="informado"):
    """Fluxo completo: consumo → HSP → P_FV → equipamentos → baterias → orçamento (FV-PB10-T01)."""
    P = PARAMETROS_FV
    f = validar_percentual(percentual)                                              # FV-PB03-T01
    e_fv = energia_mensal_desejada(consumo, f)
    p_fv = potencia_fv_necessaria(e_fv, hsp_info["hsp"], P["dias_mes"], P["eta_global"])  # FV-PB03-T03/T04

    sel, rejeitados = selecionar_modulo_inversor(p_fv, ds, com_bateria)
    if sel is None:
        raise ErroDimensionamento("Nenhuma combinação módulo × inversor é compatível.", rejeitados)

    if com_bateria:
        autonomia = validar_autonomia(autonomia)
        e_d = consumo_diario(consumo)
        e_aut = energia_autonomia(e_d, autonomia)
        arm, rej_bat = selecionar_bateria(e_aut, ds["baterias"], sel["inversor"])
        rejeitados += rej_bat
        if arm is None:
            raise ErroDimensionamento("Nenhuma bateria é compatível com o inversor escolhido.", rej_bat)
        arm.update({"autonomia_h": autonomia, "consumo_diario_kwh": e_d, "energia_autonomia_kwh": e_aut})
    else:
        # FV-PB06-T06 — sem armazenamento: capacidade e custo zerados
        arm = {"ativo": False, "bateria": None, "n_baterias": 0, "autonomia_h": 0,
               "capacidade_instalada_kwh": 0.0, "capacidade_util_kwh": 0.0, "custo": 0.0}

    p_inst = sel["config"]["potencia_instalada_kwp"]
    geracao = p_inst * hsp_info["hsp"] * P["dias_mes"] * P["eta_global"]   # estimativa de geração
    return {"data": datetime.now().strftime("%Y-%m-%d %H:%M"), "consumo": float(consumo),
            "origem_consumo": origem, "percentual": f * 100, "hsp_info": hsp_info,
            "e_fv": e_fv, "p_fv": p_fv, "selecao": sel, "p_inst": p_inst, "geracao": geracao,
            "armazenamento": arm, "orcamento": calcular_orcamento(sel, arm), "rejeitados": rejeitados}


# ------------------------------------------------------------------
# FV-PB10 — Proposta preliminar (e exibições FV-PB01-T06, PB03-T06,
# PB04-T07, PB07-T06, PB09-T06)
# ------------------------------------------------------------------

def brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def num(valor, casas=2):
    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_proposta(r, apelido=""):
    s, arm, orc, h = r["selecao"], r["armazenamento"], r["orcamento"], r["hsp_info"]
    mod, inv, cfg = s["modulo"], s["inversor"], s["config"]
    L = ["=" * 66, f"  PROPOSTA PRELIMINAR — SISTEMA FOTOVOLTAICO  {apelido}", f"  Gerada em {r['data']}", "=" * 66,
         "\n[1] CONSUMO E META",
         f"  Consumo de referência .... {num(r['consumo'])} kWh/mês ({r['origem_consumo']})",
         f"  Percentual de atendimento  {num(r['percentual'], 0)} %",
         f"  Energia mensal pretendida  {num(r['e_fv'])} kWh/mês  (E_FV = Cm × f)",
         "\n[2] RECURSO SOLAR",
         f"  {h['cidade']}/{h['uf']} — HSP {num(h['hsp'])} kWh/m²/dia",
         f"  Origem do dado: {h['fonte']} — {h['url_fonte']}",
         "\n[3] GERAÇÃO",
         f"  Potência FV calculada .... {num(r['p_fv'], 3)} kWp  (E_FV / (HSP × 30 × 0,78))",
         f"  Potência instalada ....... {num(r['p_inst'], 3)} kWp",
         f"  Geração estimada ......... {num(r['geracao'], 1)} kWh/mês ({num(r['geracao'] / r['consumo'] * 100, 1)} % do consumo)",
         "\n[4] MÓDULOS",
         f"  {cfg['n_modulos']} × {mod['fabricante']} {mod['modelo']} ({mod['potencia_wp']:.0f} Wp)",
         f"  N mínimo {s['n_minimo']} → N final {cfg['n_modulos']} ({cfg['n_strings']} string(s) de {cfg['por_string']})",
         "\n[5] INVERSOR",
         f"  {inv['fabricante']} {inv['modelo']} ({inv['tipo']}, {inv['potencia_nominal_w']:.0f} W)",
         f"  Voc string {num(cfg['voc_string_v'], 1)} V | Vmp string {num(cfg['vmp_string_v'], 1)} V | "
         f"DC/AC {num(cfg['ratio_dc_ac'])} | combinações válidas: {s['alternativas_validas']}",
         "\n[6] ARMAZENAMENTO"]
    if arm["ativo"]:
        b = arm["bateria"]
        L += [f"  Autonomia {num(arm['autonomia_h'], 1)} h | E_d {num(arm['consumo_diario_kwh'], 3)} kWh/dia | "
              f"E_autonomia {num(arm['energia_autonomia_kwh'], 3)} kWh | C_bat {num(arm['c_bat_kwh'], 3)} kWh",
              f"  {arm['n_baterias']} × {b['fabricante']} {b['modelo']} ({num(b['capacidade_kwh'])} kWh, DoD {b['dod_pct']:.0f} %)",
              f"  Capacidade instalada: {num(arm['capacidade_instalada_kwh'])} kWh nominais / "
              f"{num(arm['capacidade_util_kwh'])} kWh úteis"]
    else:
        L.append("  Sem armazenamento — capacidade 0 kWh, custo R$ 0,00.")
    L.append("\n[7] ORÇAMENTO ESTIMADO")
    L += [f"  {i['qtd']:>3} × {i['item'][:42]:<42} {brl(i['subtotal']):>15}" for i in orc["itens"]]
    L.append(f"  {'CUSTO DOS EQUIPAMENTOS':<48} {brl(orc['c_equipamentos']):>15}")
    L.append("  Outros custos (premissas da equipe):")
    L += [f"     {nome:<26} {regra:<20} {brl(valor):>15}" for nome, valor, regra in orc["outros"]]
    L.append(f"  {'CUSTO TOTAL ESTIMADO':<48} {brl(orc['c_total']):>15}")
    L.append("\n[8] ORIGEM DOS PREÇOS")
    L += [f"  - {i['item']}: {i['fonte']}" for i in orc["itens"]]
    L += ["\nAviso: estimativa acadêmica. Não substitui projeto elétrico, ART nem vistoria.", "=" * 66]
    return "\n".join(L)


def formatar_incompatibilidades(rejeitados, limite=12):
    """FV-PB08-T05 — explica por que cada combinação foi bloqueada."""
    linhas = [f"Combinações bloqueadas: {len(rejeitados)}"]
    linhas += [f"  ✗ {par}: {'; '.join(motivos)}" for par, motivos in rejeitados[:limite]]
    if len(rejeitados) > limite:
        linhas.append(f"  ... e mais {len(rejeitados) - limite}.")
    return "\n".join(linhas)
