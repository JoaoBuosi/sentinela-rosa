from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "raw"

for nome in ["colo_utero", "mama"]:
    df = pd.read_csv(DATA / f"{nome}.csv")
    df["co_anomes"] = df["co_anomes"].astype(str).str.zfill(6)

    df = df[df["co_anomes"] == "202512"].copy()

    municipal = "vl_indicador_calculado_mun"
    estadual = "vl_indicador_calculado_uf"

    resumo = df.groupby("sg_uf").agg(
        municipios=("co_ibge", "nunique"),
        municipios_positivos=(municipal, lambda s: (s > 0).sum()),
        soma_municipios=(municipal, "sum"),
        total_estadual=(estadual, "first"),
        valores_estaduais_distintos=(estadual, "nunique"),
    )

    resumo["diferenca"] = (
        resumo["soma_municipios"] - resumo["total_estadual"]
    )

    print("\n" + "=" * 65)
    print(nome.upper(), "- DEZEMBRO DE 2025")
    print("=" * 65)
    print(resumo.to_string())

    print("\nEstados em que a soma municipal não coincide com o total estadual:")
    divergencias = resumo[resumo["diferenca"].abs() > 0.01]
    print("Nenhuma divergência." if divergencias.empty else divergencias.to_string())