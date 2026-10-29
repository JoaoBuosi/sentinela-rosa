from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "raw"

for nome in ["colo_utero", "mama"]:
    df = pd.read_csv(DATA / f"{nome}.csv")
    df["co_anomes"] = df["co_anomes"].astype(str).str.zfill(6)

    valor = "vl_indicador_calculado_mun"
    atual = df[df["co_anomes"] == "202512"].copy()

    historico = df.groupby("co_ibge")[valor].agg(
        total_historico="sum",
        anos_positivos=lambda s: (s > 0).sum(),
    )

    atual = atual.join(historico, on="co_ibge")
    atual["valor"] = pd.to_numeric(atual[valor], errors="coerce")

    print("\n" + "=" * 65)
    print(nome.upper())
    print("=" * 65)

    print("\nSituação dos municípios em 2025:")
    print("Total:", len(atual))
    print("Com valor positivo:", (atual["valor"] > 0).sum())
    print("Zerados em 2025, mas positivos em algum ano anterior:")
    print(
        (
            (atual["valor"] == 0)
            & (atual["anos_positivos"] > 0)
        ).sum()
    )
    print("Zerados em todos os períodos:")
    print((atual["total_historico"] == 0).sum())

    print("\nMunicípios positivos por estado em 2025:")
    por_estado = atual.groupby("sg_uf").agg(
        municipios=("co_ibge", "nunique"),
        positivos=("valor", lambda s: (s > 0).sum()),
    )
    por_estado["percentual_positivos"] = (
        100 * por_estado["positivos"] / por_estado["municipios"]
    )
    print(por_estado.sort_values("percentual_positivos").to_string())

    print("\nExemplos de municípios zerados em 2025, mas positivos no histórico:")
    exemplos = atual.loc[
        (atual["valor"] == 0) & (atual["anos_positivos"] > 0),
        ["co_ibge", "no_municipio", "sg_uf", "anos_positivos", "total_historico"],
    ].head(15)
    print(exemplos.to_string(index=False))