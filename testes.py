#   ============================================================
#   testes.py — TESTES AUTOMATIZADOS
#   Equipe Lumos — FIAP
#
#   Executar:  python testes.py   (ou opção 3 do menu inicial)
#   Não pede nada ao usuário e não altera o dados_sistema.json.
#   Cada grupo FV corresponde a uma task "Testar..." do Trello.
#   ============================================================

import sys

import fotovoltaico as fv
import sistema_analise_casa as sc


def rodar_testes_calculo():
    """PB11-T06 / PB13-T04 — consumo, total e ranking."""
    sc.dados["equipamentos"]["__t"] = {"nome": "Teste", "categoria": "T", "potencia": 100, "pre_cadastrado": False}
    sc.dados["associacoes"]["__a1"] = {"imovel_id": "__im", "equipamento_id": "__t", "quantidade": 2, "tempo_uso": 5}
    sc.dados["associacoes"]["__a2"] = {"imovel_id": "__im", "equipamento_id": "__t", "quantidade": 1, "tempo_uso": 1}
    try:
        assert sc.calcular_consumo_associacao({"equipamento_id": "__x", "quantidade": 1, "tempo_uso": 1}) == 0.0
        assert abs(sc.calcular_consumo_associacao(sc.dados["associacoes"]["__a1"]) - 30.0) < 1e-9
        assert abs(sc.consumo_total_imovel("__im") - 33.0) < 1e-9
        assert sc.consumo_total_imovel("__vazio") == 0.0
        ranking = sc.ranking_consumo_imovel("__im")
        assert ranking[0][1] >= ranking[1][1] and sc.ranking_consumo_imovel("__vazio") == []
        print("[OK] Testes de consumo da etapa anterior (PB11/PB12/PB13)")
        return True
    except AssertionError:
        print("[FALHOU] Testes de consumo da etapa anterior")
        return False
    finally:
        for colecao, chave in (("equipamentos", "__t"), ("associacoes", "__a1"), ("associacoes", "__a2")):
            sc.dados[colecao].pop(chave, None)


def rodar_testes_fotovoltaico():
    """Um grupo de teste para cada task 'Testar...' da sprint FV."""
    ds = fv.carregar_datasets_fv()
    sp = fv.obter_hsp("São Paulo", "SP", ds["hsp"])
    mod = {m["id"]: m for m in ds["modulos"]}
    inv = {i["id"]: i for i in ds["inversores"]}

    def da_erro(funcao, *args):
        try:
            funcao(*args)
        except ValueError:
            return True
        return False

    def t_pb01():
        for cidade, uf, hsp in [("São Paulo", "SP", 5.0), ("natal", "rn", 6.0), ("Brasilia", "DF", 5.6)]:
            h = fv.obter_hsp(cidade, uf, ds["hsp"])
            assert h["hsp"] == hsp and h["fonte"]
        assert da_erro(fv.obter_hsp, "Osasco", "SP", ds["hsp"])               # sem cadastro
        assert da_erro(fv.obter_hsp, "Osasco", "SP", ds["hsp"], 4.9, "")      # manual sem fonte
        assert fv.obter_hsp("Osasco", "SP", ds["hsp"], 4.9, "CRESESB SunData")["hsp"] == 4.9
        assert all(da_erro(fv.validar_hsp, v) for v in (0, 2.5, 9, "abc"))

    def t_pb02():
        assert fv.validar_percentual("80") == 0.8 and fv.validar_percentual("100") == 1.0
        assert all(da_erro(fv.validar_percentual, v) for v in ("0", "-5", "101", "abc", "", None))

    def t_pb03():
        for cm, f, hsp in [(350, 1.0, 5.0), (500, 0.8, 6.0), (200, 0.5, 4.6)]:
            e = fv.energia_mensal_desejada(cm, f)
            assert abs(fv.potencia_fv_necessaria(e, hsp, 30, 0.78) - cm * f / (hsp * 30 * 0.78)) < 1e-9
        assert da_erro(fv.energia_mensal_desejada, 0, 1) and da_erro(fv.energia_mensal_desejada, 300, 1.5)
        assert da_erro(fv.potencia_fv_necessaria, 300, None, 30, 0.78)

    def t_pb04():
        assert fv.quantidade_minima_modulos(3.24, 405) == 8 and fv.quantidade_minima_modulos(3.241, 405) == 9
        assert abs(fv.potencia_instalada(8, 405) - 3.24) < 1e-9
        for m in ds["modulos"]:
            n = fv.quantidade_minima_modulos(5.0, m["potencia_wp"])
            assert fv.potencia_instalada(n, m["potencia_wp"]) >= 5.0 > fv.potencia_instalada(n - 1, m["potencia_wp"])

    def t_pb05():
        config, _ = fv.verificar_modulo_inversor(8, mod["FV006"], inv["INV001"], False)
        assert config and config["n_modulos"] == 8
        _, motivos = fv.verificar_modulo_inversor(8, mod["FV004"], inv["INV001"], False)
        assert any(m.startswith("C4") for m in motivos)
        _, motivos = fv.verificar_modulo_inversor(5, mod["FV006"], inv["INV005"], False)
        assert any(m.startswith("C6") for m in motivos)
        r = fv.dimensionar_fv(700, 100, sp, ds)                # inversor mais barato (3 kW) não aguenta
        assert r["selecao"]["inversor"]["id"] != "INV001"

    def t_pb06():
        assert fv.consumo_diario(360) == 12 and fv.energia_autonomia(12, 6) == 3
        assert abs(fv.capacidade_bateria_necessaria(3, 0.9, 0.95) - 3 / (0.9 * 0.95)) < 1e-9
        sem = fv.dimensionar_fv(350, 100, sp, ds)["armazenamento"]
        assert not sem["ativo"] and sem["capacidade_instalada_kwh"] == 0 and sem["custo"] == 0
        for horas in (2, 6, 12, 24):
            arm = fv.dimensionar_fv(350, 100, sp, ds, True, horas)["armazenamento"]
            assert arm["capacidade_util_kwh"] * 0.95 + 1e-9 >= arm["energia_autonomia_kwh"]
        assert all(da_erro(fv.validar_autonomia, v) for v in (0, -3, 100))

    def t_pb07():
        assert abs(fv.capacidade_util(5.12, 0.9) - 4.608) < 1e-9
        assert fv.quantidade_baterias(4.608, 4.608) == 1 and fv.quantidade_baterias(4.61, 4.608) == 2
        for e_aut in (1.0, 3.3, 12.0):
            for b in ds["baterias"]:
                dod = b["dod_pct"] / 100
                assert (fv.arredondar_para_cima(fv.capacidade_bateria_necessaria(e_aut, dod, 0.95) / b["capacidade_kwh"])
                        == fv.quantidade_baterias(e_aut / 0.95, fv.capacidade_util(b["capacidade_kwh"], dod)))

    def t_pb08():
        assert "C7" in fv.verificar_inversor_bateria(inv["INV002"], ds["baterias"][0])[0]
        assert "C8" in fv.verificar_inversor_bateria(inv["INV006"], dict(ds["baterias"][0], tensao_nominal_v=400))[0]
        assert fv.verificar_inversor_bateria(inv["INV006"], ds["baterias"][0]) == []
        assert fv.dimensionar_fv(350, 100, sp, ds, True, 4)["selecao"]["inversor"]["compativel_bateria"]
        so_ongrid = dict(ds, inversores=[i for i in ds["inversores"] if not i["compativel_bateria"]])
        try:
            fv.dimensionar_fv(350, 100, sp, so_ongrid, True, 4)
            raise AssertionError("on-grid + bateria deveria ser bloqueado")
        except fv.ErroDimensionamento as erro:
            assert "C7" in fv.formatar_incompatibilidades(erro.rejeitados)

    def t_pb09():
        for com in (False, True):
            o = fv.dimensionar_fv(350, 100, sp, ds, com, 12)["orcamento"]
            assert abs(o["c_total"] - o["c_equipamentos"] - o["c_outros"]) < 0.01
            assert abs(o["c_equipamentos"] - sum(i["subtotal"] for i in o["itens"])) < 0.01
            assert (o["c_baterias"] > 0) == com

    def t_pb10():
        for com in (False, True):
            texto = fv.formatar_proposta(fv.dimensionar_fv(350, 100, sp, ds, com, 8))
            for trecho in ("Consumo de referência", "Percentual", "HSP", "Origem do dado", "Potência FV calculada",
                           "Potência instalada", "MÓDULOS", "INVERSOR", "Geração estimada",
                           "CUSTO DOS EQUIPAMENTOS", "Outros custos", "CUSTO TOTAL", "ORIGEM DOS PREÇOS"):
                assert trecho in texto, trecho
            assert ("Capacidade instalada" if com else "Sem armazenamento") in texto

    def t_pb11():
        assert fv.validar_datasets_fv()[0]

    testes = [("FV-PB01-T07 HSP por localização", t_pb01), ("FV-PB02-T05 Percentual", t_pb02),
              ("FV-PB03-T07 Energia e potência", t_pb03), ("FV-PB04-T08 Módulos", t_pb04),
              ("FV-PB05-T07 Inversor", t_pb05), ("FV-PB06-T07 Armazenamento", t_pb06),
              ("FV-PB07-T07 Baterias", t_pb07), ("FV-PB08-T06 Compatibilidade", t_pb08),
              ("FV-PB09-T07 Orçamento", t_pb09), ("FV-PB10-T06 Proposta", t_pb10),
              ("FV-PB11-T08 Datasets", t_pb11)]
    aprovados = 0
    for nome, teste in testes:
        try:
            teste()
            aprovados += 1
            print(f"[OK] {nome}")
        except Exception as erro:
            print(f"[FALHOU] {nome} → {type(erro).__name__}: {erro}")
    print(f"\n{aprovados}/{len(testes)} grupos da sprint FV aprovados.")
    return aprovados == len(testes)


def rodar_todos_os_testes():
    print("==== TESTES AUTOMATIZADOS ====\n")
    ok = rodar_testes_calculo()
    try:
        ok = rodar_testes_fotovoltaico() and ok
        print("\n" + fv.validar_datasets_fv()[1])
    except FileNotFoundError as erro:
        print(f"ERRO: {erro}")
        ok = False
    return ok


if __name__ == "__main__":
    sys.exit(0 if rodar_todos_os_testes() else 1)
