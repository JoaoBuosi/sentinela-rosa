
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "raw"

arquivos = {
    "Colo do útero": DATA / "colo_utero.csv",
    "Mama": DATA / "mama.csv",
}

for nome, caminho in arquivos.items():
    print("\n" + "=" * 70)
    print(f"ANÁLISE: {nome}")
    print("=" * 70)

    df = pd.read_csv(caminho)

    df["co_anomes"] = df["co_anomes"].astype(str).str.zfill(6)
    df["valor"] = pd.to_numeric(
        df["vl_indicador_calculado_mun"], errors="coerce"
    )

    print(f"\nPeríodo inicial: {df['co_anomes'].min()}")
    print(f"Período final: {df['co_anomes'].max()}")
    print(f"Competências distintas: {df['co_anomes'].nunique()}")
    print(f"Municípios distintos: {df['co_ibge'].nunique()}")
    print(f"Linhas: {len(df):,}")

    print("\n--- LINHAS POR COMPETÊNCIA ---")
    print(df.groupby("co_anomes").size().to_string())

    print("\n--- MUNICÍPIOS POR COMPETÊNCIA ---")
    print(
        df.groupby("co_anomes")["co_ibge"]
        .nunique()
        .to_string()
    )

    print("\n--- DISTRIBUIÇÃO DO INDICADOR MUNICIPAL ---")
    print(df["valor"].describe().to_string())

    zeros = (df["valor"] == 0).sum()
    positivos = (df["valor"] > 0).sum()

    print(f"\nValores iguais a zero: {zeros:,} "
          f"({zeros / len(df) * 100:.2f}%)")
    print(f"Valores positivos: {positivos:,} "
          f"({positivos / len(df) * 100:.2f}%)")
    print(f"Valores negativos: {(df['valor'] < 0).sum():,}")

    duplicados = df.duplicated(
        subset=["co_ibge", "co_anomes"]
    ).sum()

    print(f"\nDuplicatas município-competência: {duplicados:,}")

    print("\n--- EXEMPLOS DE VALORES POSITIVOS ---")
    print(
        df.loc[df["valor"] > 0,
               ["co_anomes", "co_ibge", "no_municipio", "valor"]]
        .head(10)
        .to_string(index=False)
    )
