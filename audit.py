
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "raw"
REPORT_DIR = BASE_DIR / "reports"

FILES = {
    "CANCER_COLO_UTERO": DATA_DIR / "colo_utero.csv",
    "CANCER_MAMA": DATA_DIR / "mama.csv",
}

REPORT_DIR.mkdir(parents=True, exist_ok=True)


def load_csv(path: Path) -> pd.DataFrame:
    """Identifica a codificação e tenta detectar o separador do CSV."""
    if not path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path}")

    errors = []

    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            df = pd.read_csv(
                path,
                sep=None,
                engine="python",
                encoding=encoding,
                on_bad_lines="warn",
            )

            if len(df.columns) == 1:
                for separator in (";", ",", "\t", "|"):
                    candidate = pd.read_csv(
                        path,
                        sep=separator,
                        encoding=encoding,
                        on_bad_lines="warn",
                    )

                    if len(candidate.columns) > 1:
                        return candidate

            return df

        except (UnicodeDecodeError, pd.errors.ParserError) as exc:
            errors.append(f"{encoding}: {exc}")

    raise RuntimeError(
        f"Não foi possível ler {path.name}.\n" + "\n".join(errors)
    )


def audit_dataframe(name: str, path: Path) -> str:
    df = load_csv(path)

    lines = [
        "=" * 80,
        f"ARQUIVO: {name}",
        f"CAMINHO: {path}",
        f"LINHAS: {len(df):,}",
        f"COLUNAS: {len(df.columns)}",
        f"TAMANHO: {path.stat().st_size / (1024 * 1024):.2f} MB",
        "",
        "--- NOMES DAS COLUNAS ---",
    ]

    for column in df.columns:
        lines.append(f"{column!r} | tipo={df[column].dtype}")

    lines.extend([
        "",
        "--- AMOSTRA: PRIMEIRAS 5 LINHAS ---",
        df.head().to_string(index=False),
        "",
        "--- VALORES AUSENTES ---",
    ])

    missing = pd.DataFrame({
        "ausentes": df.isna().sum(),
        "percentual": (df.isna().mean() * 100).round(2),
    }).sort_values("percentual", ascending=False)

    lines.append(missing.to_string())

    lines.extend([
        "",
        "--- DUPLICATAS ---",
        f"Linhas inteiramente duplicadas: {df.duplicated().sum():,}",
        "",
        "--- ESTATÍSTICAS NUMÉRICAS ---",
        df.describe(include="number").to_string(),
        "",
        "--- POSSÍVEIS COLUNAS IMPORTANTES ---",
    ])

    keywords = (
        "munic", "ibge", "uf", "estado", "ano", "mes", "data",
        "quant", "exame", "mamog", "cito", "popul", "idade",
        "faixa", "total", "cobert", "regiao", "period"
    )

    for column in df.columns:
        if any(word in str(column).lower() for word in keywords):
            examples = df[column].dropna().head(5).tolist()
            lines.append(f"{column!r}: exemplos={examples}")

    for column in df.columns:
        normalized = str(column).lower()

        if "munic" in normalized or "ibge" in normalized:
            lines.extend([
                "",
                f"--- IDENTIFICADOR CANDIDATO: {column} ---",
                f"Tipo atual: {df[column].dtype}",
                f"Valores únicos: {df[column].nunique(dropna=True):,}",
                f"Exemplos: {df[column].dropna().astype(str).head(10).tolist()}",
            ])

    lines.append("")
    return "\n".join(lines)


def main():
    reports = []

    for name, path in FILES.items():
        try:
            report = audit_dataframe(name, path)
            reports.append(report)
            print(report)

        except Exception as exc:
            message = f"\nERRO em {name}: {exc}\n"
            print(message)
            reports.append(message)

    report_path = REPORT_DIR / "auditoria_inicial.txt"
    report_path.write_text("\n".join(reports), encoding="utf-8")

    print(f"\nRelatório salvo em: {report_path}")


if __name__ == "__main__":
    main()
