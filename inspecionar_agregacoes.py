from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent

colunas = [
    "co_anomes",
    "co_ibge",
    "no_municipio",
    "sg_uf",
    "no_regiao_saude",
    "vl_indicador_calculado_mun",
    "vl_indicador_calculado_rs",
    "vl_indicador_calculado_ms",
    "vl_indicador_calculado_uf",
    "vl_indicador_calculado_reg",
    "vl_indicador_calculado_br",
    "vl_indicador_calculado_al",
    "ds_unidade_medida",
    "sg_granularidade",
    "ds_granularidade",
]

for nome in ["colo_utero", "mama"]:
    df = pd.read_csv(BASE / "data" / "raw" / f"{nome}.csv")
    df["co_anomes"] = df["co_anomes"].astype(str).str.zfill(6)

    recorte = df[
        (df["co_anomes"] == "202512")
        & (
            df["sg_uf"].isin(["SP", "AM", "PA"])
        )
    ]

    print("\n" + "=" * 80)
    print(nome.upper())
    print("=" * 80)

    print(
        recorte[colunas]
        .sort_values(["sg_uf", "vl_indicador_calculado_mun"],
                     ascending=[True, False])
        .groupby("sg_uf", group_keys=False)
        .head(3)
        .to_string(index=False)
    )

    print("\nQuantidade de valores distintos por coluna agregada:")
    agregadas = [c for c in colunas if c.startswith("vl_indicador")]
    print(recorte[agregadas].nunique().to_string())