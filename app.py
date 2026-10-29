from pathlib import Path
import io
import json
import re
import unicodedata

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# ============================================================
# CONFIGURAÇÃO
# ============================================================

st.set_page_config(
    page_title="Sentinela Rosa",
    page_icon="🎗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "raw"

BASES = {
    "Câncer do colo do útero": "colo_utero.csv",
    "Câncer de mama": "mama.csv",
    "Hospitais de oncologia": "hospitais_oncologia",
    "Laboratórios QualiCito": "laboratorios_qualicito",
    "Serviços de diagnóstico de mama": "servicos_diagnostico_mama",
    "Serviços de referência de colo do útero": "servicos_referencia_colo_utero",
}

COLUNAS_OBRIGATORIAS = [
    "co_anomes",
    "co_ibge",
    "vl_indicador_calculado_mun",
    "no_municipio",
    "sg_uf",
]

UF_CODIGOS = {
    "RO": "11", "AC": "12", "AM": "13", "RR": "14",
    "PA": "15", "AP": "16", "TO": "17", "MA": "21",
    "PI": "22", "CE": "23", "RN": "24", "PB": "25",
    "PE": "26", "AL": "27", "SE": "28", "BA": "29",
    "MG": "31", "ES": "32", "RJ": "33", "SP": "35",
    "PR": "41", "SC": "42", "RS": "43", "MS": "50",
    "MT": "51", "GO": "52", "DF": "53",
}

NOMES_UF = {
    "RO": "Rondônia", "AC": "Acre", "AM": "Amazonas",
    "RR": "Roraima", "PA": "Pará", "AP": "Amapá",
    "TO": "Tocantins", "MA": "Maranhão", "PI": "Piauí",
    "CE": "Ceará", "RN": "Rio Grande do Norte",
    "PB": "Paraíba", "PE": "Pernambuco", "AL": "Alagoas",
    "SE": "Sergipe", "BA": "Bahia", "MG": "Minas Gerais",
    "ES": "Espírito Santo", "RJ": "Rio de Janeiro",
    "SP": "São Paulo", "PR": "Paraná", "SC": "Santa Catarina",
    "RS": "Rio Grande do Sul", "MS": "Mato Grosso do Sul",
    "MT": "Mato Grosso", "GO": "Goiás", "DF": "Distrito Federal",
}

URL_SIDRA = "https://apisidra.ibge.gov.br/values/t/9514/n6/all/v/93/p/2022"

URL_IBGE_MUNICIPIOS = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/"
    "estados/{uf}/municipios"
)

URL_IBGE_MALHA = (
    "https://servicodados.ibge.gov.br/api/v3/malhas/"
    "estados/{uf}?formato=application/vnd.geo+json"
    "&intrarregiao=municipio&qualidade=minima"
)

HEADERS_HTTP = {
    "User-Agent": "SentinelaRosa/1.0",
    "Accept": "application/json",
}


# ============================================================
# FUNÇÕES GERAIS
# ============================================================

def normalizar_texto(valor):
    """Remove acentos e padroniza texto para comparação."""
    if pd.isna(valor):
        return ""

    texto = str(valor).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )
    texto = re.sub(r"\s+", " ", texto)

    return texto


def normalizar_codigo_ibge(valor):
    """
    Normaliza códigos sem inventar dígitos ou truncar códigos longos.
    Códigos incompletos são preservados como incompletos para permitir
    a tentativa de correspondência pelo nome oficial do município.
    """
    if pd.isna(valor):
        return None

    texto = str(valor).strip()

    if texto.endswith(".0"):
        texto = texto[:-2]

    texto = re.sub(r"\D", "", texto)

    if not texto or len(texto) > 7:
        return None

    return texto.zfill(7) if len(texto) == 7 else texto


def formatar_numero(valor, casas=0):
    if pd.isna(valor):
        return "—"

    return f"{valor:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_percentual(valor, casas=2):
    if pd.isna(valor):
        return "—"

    return f"{valor:.{casas}f}%".replace(".", ",")


def converter_numero(serie):
    """
    Converte números de CSV, inclusive quando há separadores
    decimais brasileiros ou valores inválidos.
    """
    texto = serie.astype(str).str.strip()

    texto = texto.replace({
        "": np.nan,
        "nan": np.nan,
        "None": np.nan,
        "null": np.nan,
        "-": np.nan,
    })

    resultado = pd.to_numeric(texto, errors="coerce")

    falhas = resultado.isna() & texto.notna()

    if falhas.any():
        brasileiros = (
            texto.loc[falhas]
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        resultado.loc[falhas] = pd.to_numeric(
            brasileiros,
            errors="coerce",
        )

    return resultado


def requisicao_json(url, timeout=30):
    resposta = requests.get(
        url,
        headers=HEADERS_HTTP,
        timeout=timeout,
    )
    resposta.raise_for_status()
    return resposta.json()


# ============================================================
# CARREGAMENTO DAS BASES
# ============================================================

def localizar_arquivo(nome):
    caminho = DATA_DIR / nome

    if caminho.exists():
        return caminho

    alternativas = [
        DATA_DIR / f"{nome}.csv",
        DATA_DIR / f"{nome}.CSV",
    ]

    for alternativa in alternativas:
        if alternativa.exists():
            return alternativa

    return None


def ler_csv_robusto(caminho):
    """
    Tenta diferentes codificações e separadores.
    Mantém todas as colunas como texto inicialmente.
    """
    erros = []

    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        for separador in (";", ",", "\t"):
            try:
                df = pd.read_csv(
                    caminho,
                    sep=separador,
                    encoding=encoding,
                    dtype=str,
                    low_memory=False,
                )

                if len(df.columns) > 1:
                    df.columns = [
                        str(coluna).strip().replace("\ufeff", "")
                        for coluna in df.columns
                    ]
                    return df

            except Exception as erro:
                erros.append(str(erro))

    raise ValueError(
        f"Não foi possível ler o arquivo {caminho.name}. "
        f"Detalhe: {erros[-1] if erros else 'formato desconhecido'}"
    )


@st.cache_data(show_spinner=False)
def carregar_base(nome_arquivo):
    caminho = localizar_arquivo(nome_arquivo)

    if caminho is None:
        return pd.DataFrame(), {
            "status": "Arquivo não encontrado",
            "arquivo": nome_arquivo,
            "linhas": 0,
            "colunas": 0,
            "faltantes": COLUNAS_OBRIGATORIAS.copy(),
            "erro": f"Arquivo não localizado em {DATA_DIR}",
        }

    try:
        df = ler_csv_robusto(caminho)

        faltantes = [
            coluna
            for coluna in COLUNAS_OBRIGATORIAS
            if coluna not in df.columns
        ]

        if faltantes:
            return df, {
                "status": "Esquema incompatível",
                "arquivo": caminho.name,
                "linhas": len(df),
                "colunas": len(df.columns),
                "faltantes": faltantes,
                "erro": "A base não contém todas as colunas necessárias.",
            }

        # Preserva o código recebido para auditoria e diagnóstico.
        df["co_ibge_original"] = df["co_ibge"].astype(str).str.strip()

        df["co_ibge"] = df["co_ibge"].apply(normalizar_codigo_ibge)
        df["sg_uf"] = df["sg_uf"].astype(str).str.strip().str.upper()
        df["no_municipio"] = df["no_municipio"].astype(str).str.strip()

        df["vl_indicador_calculado_mun"] = converter_numero(
            df["vl_indicador_calculado_mun"]
        )

        df["co_anomes"] = (
            df["co_anomes"]
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
        )

        df["ano"] = pd.to_numeric(
            df["co_anomes"].str[:4],
            errors="coerce",
        )

        df["mes"] = pd.to_numeric(
            df["co_anomes"].str[-2:],
            errors="coerce",
        )

        df["competencia"] = pd.to_datetime(
            df["co_anomes"],
            format="%Y%m",
            errors="coerce",
        )

        linhas_originais = len(df)

        df["codigo_valido"] = df["co_ibge"].str.fullmatch(
            r"\d{7}",
            na=False,
        )

        df["valor_valido"] = df["vl_indicador_calculado_mun"].notna()

        duplicadas = int(
            df.duplicated(
                subset=["co_anomes", "co_ibge"],
                keep="first",
            ).sum()
        )

        df = df.drop_duplicates(
            subset=["co_anomes", "co_ibge"],
            keep="first",
        ).copy()

        auditoria = {
            "status": "OK",
            "arquivo": caminho.name,
            "linhas": len(df),
            "linhas_originais": linhas_originais,
            "colunas": len(df.columns),
            "faltantes": [],
            "duplicadas_removidas": duplicadas,
            "codigos_invalidos": int((~df["codigo_valido"]).sum()),
            "valores_invalidos": int((~df["valor_valido"]).sum()),
            "erro": None,
        }

        return df, auditoria

    except Exception as erro:
        return pd.DataFrame(), {
            "status": "Erro de leitura",
            "arquivo": caminho.name,
            "linhas": 0,
            "colunas": 0,
            "faltantes": [],
            "erro": str(erro),
        }


@st.cache_data(show_spinner=False)
def carregar_todas_as_bases():
    bases = {}
    auditorias = {}

    for nome, arquivo in BASES.items():
        df, auditoria = carregar_base(arquivo)
        bases[nome] = df
        auditorias[nome] = auditoria

    return bases, auditorias


def obter_bases_analiticas(bases):
    return {
        nome: df
        for nome, df in bases.items()
        if not df.empty
        and all(coluna in df.columns for coluna in COLUNAS_OBRIGATORIAS)
    }


# ============================================================
# ESTATÍSTICA
# ============================================================

def calcular_estatisticas(df):
    valores = df["vl_indicador_calculado_mun"].dropna()

    if valores.empty:
        return None

    q1 = valores.quantile(0.25)
    mediana = valores.median()
    q3 = valores.quantile(0.75)
    iqr = q3 - q1

    limite_inferior = q1 - 1.5 * iqr
    limite_superior = q3 + 1.5 * iqr

    outliers = valores[
        (valores < limite_inferior)
        | (valores > limite_superior)
    ]

    return {
        "registros": int(valores.count()),
        "media": valores.mean(),
        "mediana": mediana,
        "desvio_padrao": valores.std(),
        "minimo": valores.min(),
        "q1": q1,
        "q3": q3,
        "maximo": valores.max(),
        "iqr": iqr,
        "outliers": int(len(outliers)),
        "limite_inferior": limite_inferior,
        "limite_superior": limite_superior,
    }


def criar_serie_anual(df):
    """
    Usa somente competências de dezembro para comparações anuais.
    Não trata as competências disponíveis como série mensal completa.
    """
    dados = df[
        (df["mes"] == 12)
        & df["ano"].notna()
        & df["vl_indicador_calculado_mun"].notna()
    ].copy()

    if dados.empty:
        return pd.DataFrame(
            columns=["ano", "total", "municipios"]
        )

    serie = (
        dados.groupby("ano", as_index=False)
        .agg(
            total=("vl_indicador_calculado_mun", "sum"),
            municipios=("co_ibge", "nunique"),
        )
        .sort_values("ano")
    )

    serie["variacao_absoluta"] = serie["total"].diff()
    serie["variacao_percentual"] = serie["total"].pct_change() * 100

    return serie


# ============================================================
# SIDRA — CONSULTA DIRETA, SEM METADADOS
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def consultar_sidra_dados():
    """
    Consulta a rota de dados diretamente.
    O retorno bruto serve para diagnóstico.
    """
    dados = requisicao_json(URL_SIDRA)

    if not isinstance(dados, list) or len(dados) < 2:
        raise ValueError(
            "A API do SIDRA não retornou uma tabela utilizável."
        )

    df = pd.DataFrame(dados)

    if df.empty:
        raise ValueError("A resposta do SIDRA veio vazia.")

    return df


def validar_tabela_populacao_feminina(df_sidra):
    """
    Não considera população feminina validada sem confirmar
    as categorias de sexo e idade.
    """
    if df_sidra is None or df_sidra.empty:
        return False, "A consulta do SIDRA não retornou dados."

    return (
        False,
        "A resposta bruta foi recebida, mas as categorias de sexo "
        "e idade ainda não foram validadas. Nenhuma taxa será calculada.",
    )


# ============================================================
# IBGE — MUNICÍPIOS E MALHAS
# ============================================================

@st.cache_data(ttl=86400, show_spinner=False)
def carregar_municipios_ibge(uf):
    codigo_uf = UF_CODIGOS.get(uf)

    if not codigo_uf:
        raise ValueError(f"UF inválida: {uf}")

    url = URL_IBGE_MUNICIPIOS.format(uf=codigo_uf)
    dados = requisicao_json(url)

    df = pd.DataFrame([
        {
            "codigo_municipio": normalizar_codigo_ibge(item.get("id")),
            "municipio_ibge": item.get("nome"),
            "uf": uf,
        }
        for item in dados
    ])

    df["codigo_municipio"] = df["codigo_municipio"].astype(str)

    return df


@st.cache_data(ttl=86400, show_spinner=False)
def carregar_malha_estado(uf):
    codigo_uf = UF_CODIGOS.get(uf)

    if not codigo_uf:
        raise ValueError(f"UF inválida: {uf}")

    url = URL_IBGE_MALHA.format(uf=codigo_uf)
    dados = requisicao_json(url)

    if not isinstance(dados, dict) or "features" not in dados:
        raise ValueError(
            "A API de malhas do IBGE não retornou GeoJSON válido."
        )

    return dados


def obter_codigo_feature(feature):
    """
    Extrai o código municipal das propriedades do polígono.
    """
    propriedades = feature.get("properties", {}) or {}

    candidatos = [
        propriedades.get("codarea"),
        propriedades.get("codigo"),
        propriedades.get("CD_MUN"),
        propriedades.get("CD_GEOCMU"),
        feature.get("id"),
    ]

    for candidato in candidatos:
        codigo = normalizar_codigo_ibge(candidato)

        if codigo and len(codigo) == 7:
            return codigo

    return None


def associar_dados_malha(geojson, dados, uf):
    """
    Associa registros aos polígonos usando:
    1. Código municipal válido que exista na malha.
    2. Nome oficial do município + UF, quando o código não corresponde.

    A associação por nome só é feita quando o nome é único dentro
    do estado. Nenhum dígito municipal é inventado.
    """
    geojson_limpo = json.loads(json.dumps(geojson))
    codigos_malha = set()

    for feature in geojson_limpo.get("features", []):
        codigo = obter_codigo_feature(feature)

        if not codigo:
            continue

        feature.setdefault("properties", {})
        feature["properties"]["codigo_municipio"] = codigo
        codigos_malha.add(codigo)

    geojson_limpo["features"] = [
        feature
        for feature in geojson_limpo.get("features", [])
        if feature.get("properties", {}).get("codigo_municipio")
    ]

    dados = dados.copy()

    if "co_ibge_original" not in dados.columns:
        dados["co_ibge_original"] = dados["co_ibge"].astype(str)

    dados["co_ibge"] = dados["co_ibge"].apply(
        normalizar_codigo_ibge
    )

    dados["municipio_normalizado"] = dados[
        "no_municipio"
    ].apply(normalizar_texto)

    dados["codigo_mapa"] = dados["co_ibge"].where(
        dados["co_ibge"].isin(codigos_malha)
    )

    # Tenta associar pelo nome quando o código original não corresponde.
    if dados["codigo_mapa"].isna().any():
        municipios_ibge = carregar_municipios_ibge(uf).copy()

        municipios_ibge["municipio_normalizado"] = (
            municipios_ibge["municipio_ibge"]
            .apply(normalizar_texto)
        )

        # Evita associação automática de nomes ambíguos.
        contagens_nomes = municipios_ibge[
            "municipio_normalizado"
        ].value_counts()

        nomes_unicos = contagens_nomes[
            contagens_nomes == 1
        ].index

        municipios_unicos = municipios_ibge[
            municipios_ibge["municipio_normalizado"].isin(nomes_unicos)
        ].copy()

        mapa_nomes = dict(
            zip(
                municipios_unicos["municipio_normalizado"],
                municipios_unicos["codigo_municipio"],
            )
        )

        faltantes = dados["codigo_mapa"].isna()

        dados.loc[faltantes, "codigo_mapa"] = (
            dados.loc[faltantes, "municipio_normalizado"]
            .map(mapa_nomes)
        )

    dados["codigo_mapa"] = dados["codigo_mapa"].apply(
        normalizar_codigo_ibge
    )

    # Só mantém correspondências que realmente existem na malha.
    dados["codigo_mapa"] = dados["codigo_mapa"].where(
        dados["codigo_mapa"].isin(codigos_malha)
    )

    dados_validos = dados[
        dados["codigo_mapa"].notna()
        & dados["vl_indicador_calculado_mun"].notna()
    ].copy()

    codigos_dados = set(
        dados_validos["codigo_mapa"].dropna().unique()
    )

    intersecao = codigos_malha.intersection(codigos_dados)

    diagnostico = {
        "poligonos_com_codigo": len(codigos_malha),
        "codigos_na_base": int(
            dados["co_ibge"].nunique(dropna=True)
        ),
        "codigos_associados": len(intersecao),
        "municipios_associados": len(codigos_dados),
        "registros_associados": len(dados_validos),
        "exemplos_malha": sorted(codigos_malha)[:5],
        "exemplos_base": (
            dados["co_ibge"]
            .dropna()
            .astype(str)
            .drop_duplicates()
            .head(5)
            .tolist()
        ),
        "exemplos_associados": sorted(intersecao)[:5],
    }

    return geojson_limpo, dados_validos, diagnostico


# ============================================================
# INTERFACE
# ============================================================

st.title("🎗️ Sentinela Rosa")
st.caption(
    "Painel de análise territorial e estatística de dados públicos "
    "relacionados à prevenção e ao diagnóstico do câncer."
)

with st.sidebar:
    st.header("Configurações")

    if st.button("Atualizar dados locais", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.caption(f"Diretório de dados: `{DATA_DIR}`")

bases, auditorias = carregar_todas_as_bases()
bases_analiticas = obter_bases_analiticas(bases)

nomes_analiticos = list(bases_analiticas.keys())

if not nomes_analiticos:
    st.error(
        "Nenhuma base analítica foi carregada. Verifique se os arquivos "
        "estão em data/raw/ e se contêm as colunas obrigatórias."
    )

    st.subheader("Diagnóstico de carregamento")

    st.dataframe(
        pd.DataFrame(auditorias).T,
        width="stretch",
    )

    st.stop()


with st.sidebar:
    base_selecionada = st.selectbox(
        "Base para análise",
        nomes_analiticos,
    )

df_base = bases_analiticas[base_selecionada].copy()

ufs_disponiveis = sorted(
    uf for uf in df_base["sg_uf"].dropna().unique()
    if uf in UF_CODIGOS
)

with st.sidebar:
    ufs_selecionadas = st.multiselect(
        "Filtrar estados",
        options=ufs_disponiveis,
        default=ufs_disponiveis,
    )

    anos_disponiveis = sorted(
        int(ano)
        for ano in df_base["ano"].dropna().unique()
    )

    anos_selecionados = st.multiselect(
        "Filtrar anos",
        options=anos_disponiveis,
        default=anos_disponiveis,
    )

df_filtrado = df_base.copy()

if ufs_selecionadas:
    df_filtrado = df_filtrado[
        df_filtrado["sg_uf"].isin(ufs_selecionadas)
    ]
else:
    df_filtrado = df_filtrado.iloc[0:0]

if anos_selecionados:
    df_filtrado = df_filtrado[
        df_filtrado["ano"].isin(anos_selecionados)
    ]
else:
    df_filtrado = df_filtrado.iloc[0:0]

abas = st.tabs([
    "Visão geral",
    "Estatística avançada",
    "Análise temporal",
    "Análise territorial",
    "Mapa interativo",
    "População e serviços",
    "Qualidade dos dados",
    "Fontes e metodologia",
])


# ============================================================
# ABA 1 — VISÃO GERAL
# ============================================================

with abas[0]:
    st.header("Visão geral")

    if df_filtrado.empty:
        st.warning("Não existem registros para os filtros selecionados.")
    else:
        total_registros = len(df_filtrado)
        total_municipios = df_filtrado["co_ibge"].nunique()
        total_estados = df_filtrado["sg_uf"].nunique()
        total_competencias = df_filtrado["co_anomes"].nunique()

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Registros", formatar_numero(total_registros))
        c2.metric("Municípios", formatar_numero(total_municipios))
        c3.metric("Estados", formatar_numero(total_estados))
        c4.metric("Competências", formatar_numero(total_competencias))

        st.info(
            "Os valores apresentados são os registros da variável "
            "`vl_indicador_calculado_mun`. A unidade disponível na base "
            "é Número; não interprete automaticamente os valores como "
            "percentuais, cobertura ou incidência."
        )

        resumo_uf = (
            df_filtrado.groupby("sg_uf", as_index=False)
            .agg(
                total=("vl_indicador_calculado_mun", "sum"),
                municipios=("co_ibge", "nunique"),
            )
            .sort_values("total", ascending=False)
        )

        fig_uf = px.bar(
            resumo_uf,
            x="sg_uf",
            y="total",
            title="Soma dos valores registrados por estado",
            labels={
                "sg_uf": "UF",
                "total": "Soma dos valores",
            },
        )

        st.plotly_chart(fig_uf, width="stretch")

        st.subheader("Registros recentes")

        st.dataframe(
            df_filtrado.sort_values(
                ["competencia", "sg_uf", "no_municipio"],
                ascending=[False, True, True],
            ).head(100),
            width="stretch",
        )


# ============================================================
# ABA 2 — ESTATÍSTICA AVANÇADA
# ============================================================

with abas[1]:
    st.header("Estatística avançada")

    estatisticas = calcular_estatisticas(df_filtrado)

    if estatisticas is None:
        st.warning("Não há valores numéricos válidos para calcular.")
    else:
        c1, c2, c3 = st.columns(3)

        c1.metric("Média", formatar_numero(estatisticas["media"], 2))
        c2.metric("Mediana", formatar_numero(estatisticas["mediana"], 2))
        c3.metric(
            "Desvio padrão",
            formatar_numero(estatisticas["desvio_padrao"], 2),
        )

        c4, c5, c6 = st.columns(3)

        c4.metric("Mínimo", formatar_numero(estatisticas["minimo"], 2))
        c5.metric("Q1", formatar_numero(estatisticas["q1"], 2))
        c6.metric("Q3", formatar_numero(estatisticas["q3"], 2))

        c7, c8, c9 = st.columns(3)

        c7.metric("Máximo", formatar_numero(estatisticas["maximo"], 2))
        c8.metric("Intervalo interquartil", formatar_numero(estatisticas["iqr"], 2))
        c9.metric("Possíveis outliers", formatar_numero(estatisticas["outliers"]))

        st.caption(
            "Os possíveis outliers são identificados pela regra de "
            "1,5 × IQR. Isso aponta valores estatisticamente extremos, "
            "não necessariamente erros nos dados."
        )

        valores = df_filtrado[
            "vl_indicador_calculado_mun"
        ].dropna()

        if not valores.empty:
            fig_hist = px.histogram(
                x=valores,
                nbins=30,
                title="Distribuição dos valores municipais",
                labels={"x": "Valor registrado", "count": "Frequência"},
            )
            st.plotly_chart(fig_hist, width="stretch")

            fig_box = px.box(
                df_filtrado,
                y="vl_indicador_calculado_mun",
                points="outliers",
                title="Boxplot dos valores municipais",
                labels={
                    "vl_indicador_calculado_mun": "Valor registrado"
                },
            )
            st.plotly_chart(fig_box, width="stretch")

        resumo_estatistico = pd.DataFrame(
            [
                {"Métrica": "Registros numéricos", "Valor": estatisticas["registros"]},
                {"Métrica": "Média", "Valor": estatisticas["media"]},
                {"Métrica": "Mediana", "Valor": estatisticas["mediana"]},
                {"Métrica": "Desvio padrão", "Valor": estatisticas["desvio_padrao"]},
                {"Métrica": "Mínimo", "Valor": estatisticas["minimo"]},
                {"Métrica": "Primeiro quartil (Q1)", "Valor": estatisticas["q1"]},
                {"Métrica": "Terceiro quartil (Q3)", "Valor": estatisticas["q3"]},
                {"Métrica": "Máximo", "Valor": estatisticas["maximo"]},
                {"Métrica": "IQR", "Valor": estatisticas["iqr"]},
                {"Métrica": "Possíveis outliers", "Valor": estatisticas["outliers"]},
            ]
        )

        st.dataframe(resumo_estatistico, width="stretch")


# ============================================================
# ABA 3 — ANÁLISE TEMPORAL
# ============================================================

with abas[2]:
    st.header("Análise temporal")

    serie_anual = criar_serie_anual(df_filtrado)

    st.info(
        "A comparação anual usa somente competências de dezembro. "
        "As competências disponíveis não representam uma série mensal "
        "completa, portanto não se deve interpretar lacunas como "
        "ausência de atividade."
    )

    if serie_anual.empty:
        st.warning(
            "Não existem registros de dezembro com valores válidos "
            "para os filtros atuais."
        )
    else:
        fig_serie = px.line(
            serie_anual,
            x="ano",
            y="total",
            markers=True,
            title="Soma dos valores em dezembro de cada ano",
            labels={
                "ano": "Ano",
                "total": "Soma dos valores registrados",
            },
        )

        st.plotly_chart(fig_serie, width="stretch")

        fig_municipios = px.line(
            serie_anual,
            x="ano",
            y="municipios",
            markers=True,
            title="Municípios representados em dezembro",
            labels={
                "ano": "Ano",
                "municipios": "Municípios com registros",
            },
        )

        st.plotly_chart(fig_municipios, width="stretch")

        st.subheader("Variação anual")

        exibicao = serie_anual.copy()

        exibicao["total"] = exibicao["total"].round(2)
        exibicao["variacao_absoluta"] = exibicao[
            "variacao_absoluta"
        ].round(2)

        exibicao["variacao_percentual"] = exibicao[
            "variacao_percentual"
        ].round(2)

        st.dataframe(exibicao, width="stretch")


# ============================================================
# ABA 4 — ANÁLISE TERRITORIAL
# ============================================================

with abas[3]:
    st.header("Análise territorial")

    resumo_municipios = (
        df_filtrado.groupby(
            ["co_ibge", "no_municipio", "sg_uf"],
            as_index=False,
        )
        .agg(
            total=("vl_indicador_calculado_mun", "sum"),
            media=("vl_indicador_calculado_mun", "mean"),
            mediana=("vl_indicador_calculado_mun", "median"),
            competencias=("co_anomes", "nunique"),
        )
        .sort_values("total", ascending=False)
    )

    st.subheader("Municípios com maiores somas registradas")

    st.dataframe(
        resumo_municipios.head(20),
        width="stretch",
    )

    st.subheader("Pesquisar município")

    pesquisa = st.text_input(
        "Digite o nome do município ou código IBGE",
        key="pesquisa_municipio",
    )

    if pesquisa.strip():
        termo = normalizar_texto(pesquisa)
        codigos = resumo_municipios["co_ibge"].fillna("")

        nomes = resumo_municipios["no_municipio"].apply(
            normalizar_texto
        )

        resultado = resumo_municipios[
            nomes.str.contains(termo, na=False)
            | codigos.str.contains(termo, na=False)
        ]

        st.dataframe(resultado, width="stretch")

        if resultado.empty:
            st.info("Nenhum município encontrado com esse termo.")

    st.subheader("Distribuição por estado")

    resumo_estados = (
        df_filtrado.groupby("sg_uf", as_index=False)
        .agg(
            total=("vl_indicador_calculado_mun", "sum"),
            municipios=("co_ibge", "nunique"),
            media=("vl_indicador_calculado_mun", "mean"),
        )
        .sort_values("total", ascending=False)
    )

    st.dataframe(resumo_estados, width="stretch")


# ============================================================
# ABA 5 — MAPA INTERATIVO
# ============================================================

with abas[4]:
    st.header("Mapa municipal")

    st.caption(
        "O mapa utiliza os códigos municipais oficiais do IBGE. "
        "Quando o código da base não corresponde à malha, tenta "
        "associar pelo nome oficial do município e pela UF."
    )

    ufs_mapa = sorted(
        uf for uf in df_filtrado["sg_uf"].dropna().unique()
        if uf in UF_CODIGOS
    )

    if not ufs_mapa:
        st.warning(
            "Selecione pelo menos um estado com registros válidos "
            "na barra lateral."
        )
    else:
        uf_mapa = st.selectbox(
            "Estado para visualizar",
            options=ufs_mapa,
            format_func=lambda uf: f"{uf} — {NOMES_UF.get(uf, uf)}",
            key="uf_mapa",
        )

        dados_mapa = df_filtrado[
            df_filtrado["sg_uf"] == uf_mapa
        ].copy()

        # Agrupa por código original e nome para não misturar municípios
        # diferentes antes de realizar a associação com a malha.
        dados_mapa = (
            dados_mapa.groupby(
                ["co_ibge", "no_municipio"],
                as_index=False,
                dropna=False,
            )
            .agg(
                valor=("vl_indicador_calculado_mun", "sum"),
                competencias=("co_anomes", "nunique"),
            )
        )

        # Preserva os dados que serão necessários para a associação.
        dados_mapa["sg_uf"] = uf_mapa
        dados_mapa["co_ibge_original"] = dados_mapa["co_ibge"].astype(str)

        try:
            with st.spinner("Carregando malha municipal do IBGE..."):
                geojson = carregar_malha_estado(uf_mapa)

                geojson_limpo, dados_mapa, diagnostico = associar_dados_malha(
                    geojson,
                    dados_mapa.rename(
                        columns={"valor": "vl_indicador_calculado_mun"}
                    ),
                    uf_mapa,
                )

            dados_mapa = dados_mapa.rename(
                columns={
                    "vl_indicador_calculado_mun": "valor"
                }
            )

            st.write(
                f"Polígonos com código válido: "
                f"{diagnostico['poligonos_com_codigo']}"
            )
            st.write(
                f"Códigos municipais presentes na base: "
                f"{diagnostico['codigos_na_base']}"
            )
            st.write(
                f"Municípios associados: "
                f"{diagnostico['municipios_associados']}"
            )
            st.write(
                f"Registros associados: "
                f"{diagnostico['registros_associados']}"
            )

            if diagnostico["codigos_associados"] == 0:
                st.error(
                    "Nenhum município foi associado à malha. "
                    "Confira os nomes e códigos da base na aba "
                    "'Qualidade dos dados'."
                )

                c1, c2 = st.columns(2)

                with c1:
                    st.write("Exemplos de códigos na malha")
                    st.write(diagnostico["exemplos_malha"])

                with c2:
                    st.write("Exemplos de códigos na base")
                    st.write(diagnostico["exemplos_base"])

            else:
                # O mapa usa o código oficial resolvido, nunca o código
                # original incompleto quando ele não corresponde à malha.
                dados_mapa = dados_mapa.copy()
                dados_mapa["co_ibge"] = dados_mapa["codigo_mapa"]

                # Se houver mais de uma linha por código oficial, agrega
                # novamente para garantir uma única observação por município.
                dados_mapa = (
                    dados_mapa.groupby(
                        ["co_ibge", "no_municipio"],
                        as_index=False,
                    )
                    .agg(
                        valor=("valor", "sum"),
                        competencias=("competencias", "max"),
                    )
                )

                codigos_malha = {
                    feature["properties"]["codigo_municipio"]
                    for feature in geojson_limpo["features"]
                }

                dados_mapa = dados_mapa[
                    dados_mapa["co_ibge"].isin(codigos_malha)
                ].copy()

                if dados_mapa.empty:
                    st.warning(
                        "A associação foi identificada, mas não restaram "
                        "valores municipais para exibição."
                    )
                else:
                    fig_mapa = px.choropleth_map(
                        dados_mapa,
                        geojson=geojson_limpo,
                        locations="co_ibge",
                        featureidkey="properties.codigo_municipio",
                        color="valor",
                        hover_name="no_municipio",
                        hover_data={
                            "co_ibge": True,
                            "valor": ":.2f",
                            "competencias": True,
                        },
                        map_style="carto-positron",
                        zoom=5.2,
                        center={"lat": -3.5, "lon": -64.5}
                        if uf_mapa == "AM"
                        else {"lat": -15.5, "lon": -47.5},
                        opacity=0.65,
                        title=f"Valores registrados por município — {uf_mapa}",
                        labels={
                            "valor": "Soma dos valores",
                            "co_ibge": "Código IBGE",
                            "competencias": "Competências",
                        },
                    )

                    fig_mapa.update_layout(
                        margin={"r": 0, "t": 50, "l": 0, "b": 0}
                    )

                    st.plotly_chart(fig_mapa, width="stretch")

                    st.caption(
                        "A soma exibida depende dos filtros selecionados. "
                        "Não deve ser interpretada como cobertura, risco "
                        "ou incidência sem validação conceitual e denominador."
                    )

        except Exception as erro:
            st.error(
                "Não foi possível carregar ou associar a malha municipal."
            )
            st.code(str(erro))


# ============================================================
# ABA 6 — POPULAÇÃO E SERVIÇOS
# ============================================================

with abas[5]:
    st.header("População e serviços")

    st.subheader("População — Censo Demográfico 2022")

    st.write(
        "A consulta ao SIDRA é realizada diretamente pela rota de dados, "
        "sem depender dos endpoints de metadados que retornaram HTTP 403."
    )

    st.warning(
        "A tabela 9514 possui classificações de sexo e idade. "
        "Uma consulta genérica não comprova que os registros representam "
        "mulheres nas faixas etárias adequadas para análise de prevenção. "
        "Por isso, este painel não calcula taxas até validar essas categorias."
    )

    if st.button("Testar consulta direta ao SIDRA", key="testar_sidra"):
        try:
            with st.spinner("Consultando o SIDRA..."):
                dados_sidra = consultar_sidra_dados()

            st.success(
                f"Consulta concluída. Foram recebidas "
                f"{len(dados_sidra)} linhas."
            )

            validado, motivo = validar_tabela_populacao_feminina(
                dados_sidra
            )

            if validado:
                st.success(motivo)
            else:
                st.info(motivo)

            st.subheader("Amostra da resposta bruta do SIDRA")

            st.dataframe(
                dados_sidra.head(20),
                width="stretch",
            )

            st.download_button(
                "Exportar amostra bruta do SIDRA em CSV",
                data=dados_sidra.head(1000).to_csv(
                    index=False
                ).encode("utf-8-sig"),
                file_name="sidra_censo_2022_amostra.csv",
                mime="text/csv",
            )

        except Exception as erro:
            st.error(
                "Não foi possível consultar os dados do SIDRA."
            )
            st.code(str(erro))

            st.caption(
                "O endpoint de dados pode sofrer restrições de acesso "
                "ou indisponibilidade. Nenhum valor populacional será "
                "inventado para contornar esse erro."
            )

    st.divider()
    st.subheader("Bases de serviços e estabelecimentos")

    bases_servicos = [
        "Hospitais de oncologia",
        "Laboratórios QualiCito",
        "Serviços de diagnóstico de mama",
        "Serviços de referência de colo do útero",
    ]

    resumo_servicos = []

    for nome in bases_servicos:
        df_servico = bases.get(nome, pd.DataFrame())

        resumo_servicos.append({
            "Base": nome,
            "Linhas carregadas": len(df_servico),
            "Situação": (
                auditorias[nome]["status"]
                if nome in auditorias
                else "Não auditada"
            ),
        })

    st.dataframe(
        pd.DataFrame(resumo_servicos),
        width="stretch",
    )

    st.info(
        "A presença de um estabelecimento em uma base cadastral não "
        "comprova funcionamento atual, capacidade de atendimento, "
        "disponibilidade de agenda ou qualidade do serviço."
    )


# ============================================================
# ABA 7 — QUALIDADE DOS DADOS
# ============================================================

with abas[6]:
    st.header("Qualidade dos dados")

    st.subheader("Auditoria de carregamento")

    tabela_auditoria = []

    for nome, auditoria in auditorias.items():
        tabela_auditoria.append({
            "Base": nome,
            "Arquivo": auditoria.get("arquivo"),
            "Situação": auditoria.get("status"),
            "Linhas": auditoria.get("linhas", 0),
            "Colunas": auditoria.get("colunas", 0),
            "Duplicadas removidas": auditoria.get(
                "duplicadas_removidas",
                None,
            ),
            "Códigos inválidos": auditoria.get(
                "codigos_invalidos",
                None,
            ),
            "Valores inválidos": auditoria.get(
                "valores_invalidos",
                None,
            ),
            "Erro": auditoria.get("erro"),
        })

    st.dataframe(
        pd.DataFrame(tabela_auditoria),
        width="stretch",
    )

    st.subheader("Valores ausentes e integridade")

    if not df_base.empty:
        colunas_relevantes = [
            coluna for coluna in COLUNAS_OBRIGATORIAS
            if coluna in df_base.columns
        ]

        ausentes = pd.DataFrame({
            "Coluna": colunas_relevantes,
            "Valores ausentes": [
                int(df_base[coluna].isna().sum())
                for coluna in colunas_relevantes
            ],
            "Percentual ausente": [
                float(df_base[coluna].isna().mean() * 100)
                for coluna in colunas_relevantes
            ],
        })

        ausentes["Percentual ausente"] = ausentes[
            "Percentual ausente"
        ].round(2)

        st.dataframe(ausentes, width="stretch")

        st.subheader("Competências disponíveis")

        competencias = (
            df_base.groupby("co_anomes", as_index=False)
            .size()
            .rename(columns={"size": "registros"})
            .sort_values("co_anomes")
        )

        st.dataframe(competencias, width="stretch")

        st.subheader("Valores nulos e zeros")

        valores = df_base["vl_indicador_calculado_mun"]

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Valores nulos",
            formatar_numero(valores.isna().sum()),
        )
        c2.metric(
            "Valores iguais a zero",
            formatar_numero((valores == 0).sum()),
        )
        c3.metric(
            "Valores negativos",
            formatar_numero((valores < 0).sum()),
        )

        st.caption(
            "Um zero não comprova ausência de serviço ou atendimento. "
            "Um valor nulo não deve ser substituído por zero sem justificativa."
        )

    st.divider()
    st.subheader("Diagnóstico dos códigos municipais")

    st.write(
        "Confira os códigos originais, os nomes dos municípios e os "
        "códigos normalizados para investigar divergências com o IBGE."
    )

    caminho = localizar_arquivo(BASES[base_selecionada])

    if caminho:
        try:
            original = ler_csv_robusto(caminho)

            colunas_diagnostico = [
                coluna
                for coluna in ["co_ibge", "no_municipio", "sg_uf"]
                if coluna in original.columns
            ]

            if colunas_diagnostico:
                st.write("Valores originais do arquivo CSV")

                st.dataframe(
                    original[colunas_diagnostico]
                    .drop_duplicates()
                    .head(30),
                    width="stretch",
                )

        except Exception as erro:
            st.warning(f"Não foi possível exibir os dados originais: {erro}")

    colunas_normalizadas = [
        coluna
        for coluna in [
            "co_ibge_original",
            "co_ibge",
            "no_municipio",
            "sg_uf",
            "codigo_valido",
        ]
        if coluna in df_base.columns
    ]

    st.write("Valores após a leitura e normalização")

    st.dataframe(
        df_base[colunas_normalizadas]
        .drop_duplicates()
        .head(30),
        width="stretch",
    )


# ============================================================
# ABA 8 — FONTES E METODOLOGIA
# ============================================================

with abas[7]:
    st.header("Fontes e metodologia")

    st.subheader("Fontes de dados")

    st.markdown(
        """
        - [Dados Abertos do Ministério da Saúde — MGDI: prevenção do câncer de colo e mama](https://dadosabertos.saude.gov.br/dataset/mgdi-prevencao-do-cancer-de-colo-e-mama)
        - [DATASUS — Sistema de Informação do Câncer (SISCAN)](https://datasus.saude.gov.br/acesso-a-informacao/sistema-de-informacao-do-cancer-siscan-colo-do-utero-e-mama/)
        - [IBGE — SIDRA, tabela 9514: população residente por sexo e idade](https://sidra.ibge.gov.br/tabela/9514)
        - [IBGE — API de localidades](https://servicodados.ibge.gov.br/api/v1/localidades)
        - [IBGE — API de malhas territoriais](https://servicodados.ibge.gov.br/api/v3/malhas)
        """
    )

    st.subheader("Regras analíticas")

    st.markdown(
        """
        1. **Unidade:** os valores são tratados conforme a variável disponibilizada na base. Não são convertidos automaticamente em percentuais.
        2. **Análise anual:** são utilizadas competências de dezembro para comparação entre anos.
        3. **Estatística descritiva:** média, mediana, desvio padrão, quartis e intervalo interquartil são calculados sobre valores numéricos válidos.
        4. **Outliers:** a regra de 1,5 × IQR identifica observações extremas, mas não prova erro de registro.
        5. **Mapa:** a associação utiliza códigos oficiais do IBGE e, como alternativa, nomes de municípios únicos dentro da UF.
        6. **População:** não são calculadas taxas sem denominadores compatíveis, categorias validadas e definição clara do indicador.
        7. **Serviços:** registros cadastrais não comprovam capacidade ou funcionamento atual.
        8. **Dados ausentes:** valores nulos e zeros são tratados de forma distinta.
        """
    )

    st.subheader("Limitações importantes")

    st.warning(
        "Antes de produzir taxas de cobertura, risco ou incidência, "
        "é necessário confirmar a definição de "
        "`vl_indicador_calculado_mun`, a unidade, a geografia de referência "
        "(residência ou local de atendimento), a população-alvo e o "
        "denominador apropriado. O Censo 2022 é uma referência histórica, "
        "não um denominador anual automaticamente válido para 2016–2026."
    )

    st.subheader("Exportar dados filtrados")

    csv = df_filtrado.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        label="Exportar base filtrada em CSV",
        data=csv,
        file_name="sentinela_rosa_dados_filtrados.csv",
        mime="text/csv",
    )


# ============================================================
# RODAPÉ
# ============================================================

st.divider()

st.caption(
    "Sentinela Rosa — ferramenta de análise exploratória de dados "
    "públicos. Os resultados dependem da qualidade, cobertura e "
    "definição das fontes utilizadas; não substituem avaliação "
    "epidemiológica ou decisão clínica."
)
