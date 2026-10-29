
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "raw"

arquivos = {
    "Colo do útero": DATA / "colo_utero.csv",
    "Mama": DATA / "mama.csv",
}

for nome, caminho in arquivos.items():
    df = pd.read_csv(caminho)
    df["co_anomes"] = df["co_anomes"].astype(str).str.zfill(6)

    valor = "vl_indicador_calculado_mun"

    print("\n" + "=" * 75)
    print(nome.upper())
    print("=" * 75)

    resumo = df.groupby("co_anomes").agg(
        municipios=("co_ibge", "nunique"),
        municipios_positivos=(valor, lambda s: (s > 0).sum()),
        municipios_zero=(valor, lambda s: (s == 0).sum()),
        soma_municipal=(valor, "sum"),
        mediana_municipal=(valor, "median"),
        maximo_municipal=(valor, "max"),
        total_brasil=("vl_indicador_calculado_br", "first"),
        total_uf=("vl_indicador_calculado_uf", "sum"),
    )

    print("\n--- RESUMO POR COMPETÊNCIA ---")
    print(resumo.to_string())

    print("\n--- SÉRIE HISTÓRICA DE ALGUNS MUNICÍPIOS ---")
    municipios = (
        df.groupby(["co_ibge", "no_municipio"])[valor]
        .apply(lambda s: (s > 0).sum())
        .sort_values(ascending=False)
        .head(5)
        .index
    )

    for codigo, municipio in municipios:
        historico = df.loc[
            df["co_ibge"] == codigo,
            ["co_anomes", valor]
        ].sort_values("co_anomes")

        print(f"\n{municipio} (IBGE {codigo})")
        print(historico.to_string(index=False))

    print("\n--- CONSISTÊNCIA DOS TOTAIS ---")
    comparacao = df.groupby("co_anomes").agg(
        soma_municipios=(valor, "sum"),
        total_brasil=("vl_indicador_calculado_br", "first"),
    )
    comparacao["diferenca"] = (
        comparacao["soma_municipios"] - comparacao["total_brasil"]
    )
    print(comparacao.to_string())
