import pandas as pd

for nome in ["colo_utero", "mama"]:
    df = pd.read_csv(f"data/raw/{nome}.csv")
    df["co_anomes"] = df["co_anomes"].astype(str).str.zfill(6)

    atual = df[df["co_anomes"] == "202512"].copy()
    atual["valor"] = pd.to_numeric(
        atual["vl_indicador_calculado_mun"], errors="coerce"
    )

    print("\n", "=" * 60)
    print(nome.upper(), "- DEZEMBRO DE 2025")
    print("=" * 60)
    print("Linhas:", len(atual))
    print("Municípios únicos:", atual["co_ibge"].nunique())
    print("Granularidades:")
    print(atual["ds_granularidade"].value_counts(dropna=False))
    print("Unidades de medida:")
    print(atual["ds_unidade_medida"].value_counts(dropna=False))
    print("Valores positivos:", (atual["valor"] > 0).sum())
    print("Soma municipal:", atual["valor"].sum())
    print("\nMaiores valores:")
    print(
        atual.nlargest(15, "valor")[
            ["co_ibge", "no_municipio", "vl_indicador_calculado_mun"]
        ].to_string(index=False)
    )
