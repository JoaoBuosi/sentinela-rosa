
from pathlib import Path
import io

import pandas as pd
import plotly.express as px
import streamlit as st


# ============================================================
# SENTINELA ROSA — PAINEL DE INDICADORES DE PREVENÇÃO
# ============================================================

st.set_page_config(
    page_title="Sentinela Rosa | Saúde Pública",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "raw"

ARQUIVOS = {
    "Colo do útero": DATA_DIR / "colo_utero.csv",
    "Mama": DATA_DIR / "mama.csv",
}

COLUNAS_ESSENCIAIS = [
    "co_anomes",
    "co_ibge",
    "no_municipio",
    "sg_uf",
    "vl_indicador_calculado_mun",
    "ds_unidade_medida",
]

MESES = {
    1: "Janeiro",
    2: "Fevereiro",
    3: "Março",
    4: "Abril",
    5: "Maio",
    6: "Junho",
    7: "Julho",
    8: "Agosto",
    9: "Setembro",
    10: "Outubro",
    11: "Novembro",
    12: "Dezembro",
}


# ============================================================
# LEITURA E TRATAMENTO DOS DADOS
# ============================================================

@st.cache_data(show_spinner=False)
def carregar_csv(caminho: str) -> pd.DataFrame:
    """Carrega o CSV tentando detectar separador e codificação."""
    erros = []

    for encoding in ("utf-8-sig", "utf-8", "latin1"):
        try:
            df = pd.read_csv(
                caminho,
                sep=None,
                engine="python",
                encoding=encoding,
            )
            if len(df.columns) > 1:
                break
        except Exception as exc:
            erros.append(str(exc))
    else:
        raise ValueError(
            "Não foi possível ler o arquivo CSV. "
            + " | ".join(erros)
        )

    # Normaliza os nomes das colunas.
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.replace("\ufeff", "", regex=False)
    )

    # Confere se o arquivo possui as colunas necessárias.
    faltantes = [
        coluna for coluna in COLUNAS_ESSENCIAIS
        if coluna not in df.columns
    ]

    if faltantes:
        raise ValueError(
            f"Colunas obrigatórias ausentes: {', '.join(faltantes)}"
        )

    # Mantém somente os campos essenciais para esta análise.
    df = df[COLUNAS_ESSENCIAIS].copy()

    # Normaliza a competência para AAAAMM.
    df["co_anomes"] = (
        df["co_anomes"]
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(6)
    )

    df = df[df["co_anomes"].str.fullmatch(r"\d{6}", na=False)].copy()

    # Normaliza códigos e nomes.
    df["co_ibge"] = df["co_ibge"].astype(str).str.strip()
    df["no_municipio"] = df["no_municipio"].astype(str).str.strip()
    df["sg_uf"] = df["sg_uf"].astype(str).str.strip().str.upper()
    df["ds_unidade_medida"] = (
        df["ds_unidade_medida"].astype(str).str.strip()
    )

    # Converte os valores numéricos, respeitando formatos brasileiros.
    valores = df["vl_indicador_calculado_mun"].astype(str).str.strip()
    valores = valores.str.replace(" ", "", regex=False)

    # Os CSVs podem usar vírgula como decimal ou ponto como milhar.
    tem_virgula_decimal = valores.str.contains(",", regex=False).any()
    if tem_virgula_decimal:
        valores = (
            valores.str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )

    df["vl_indicador_calculado_mun"] = pd.to_numeric(
        valores, errors="coerce"
    )

    df = df.dropna(
        subset=["co_anomes", "co_ibge", "vl_indicador_calculado_mun"]
    ).copy()

    # A chave de identificação da observação é município + competência.
    # Não usamos os valores estaduais/nacionais repetidos como indicadores.
    df = df.drop_duplicates(
        subset=["co_anomes", "co_ibge"],
        keep="last",
    )

    return df


def rotulo_competencia(competencia: str) -> str:
    """Transforma AAAAMM em um rótulo legível."""
    ano = int(competencia[:4])
    mes = int(competencia[4:6])
    nome_mes = MESES.get(mes, f"Mês {mes}")
    return f"{nome_mes} de {ano}"


def formatar_numero(valor, casas=0) -> str:
    """Formata números no padrão brasileiro."""
    if pd.isna(valor):
        return "—"
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def criar_csv(df: pd.DataFrame) -> bytes:
    """Gera um CSV compatível com Excel em português."""
    return df.to_csv(
        index=False,
        sep=";",
        encoding="utf-8-sig",
    ).encode("utf-8-sig")


# ============================================================
# ESTILO E CABEÇALHO
# ============================================================

st.markdown(
    """
    <style>
        .block-container {
            padding-top: 1.8rem;
            padding-bottom: 2.5rem;
        }

        .sr-subtitle {
            color: #6b7280;
            font-size: 1rem;
            margin-top: -0.4rem;
            margin-bottom: 1.2rem;
        }

        .sr-note {
            padding: 0.9rem 1rem;
            border: 1px solid #e5e7eb;
            border-radius: 0.6rem;
            background: rgba(128, 128, 128, 0.06);
            margin-bottom: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🌸 Sentinela Rosa")
st.markdown(
    '<p class="sr-subtitle">'
    "Painel territorial de indicadores publicados sobre exames "
    "de prevenção do câncer do colo do útero e de mama."
    "</p>",
    unsafe_allow_html=True,
)


# ============================================================
# CARREGAMENTO DOS ARQUIVOS
# ============================================================

dados = {}

for procedimento, caminho in ARQUIVOS.items():
    if not caminho.exists():
        st.error(
            f"Arquivo não encontrado: `{caminho}`. "
            "Confira se os CSVs estão na pasta `data/raw/`."
        )
        st.stop()

    try:
        dados[procedimento] = carregar_csv(str(caminho))
    except Exception as exc:
        st.error(
            f"Erro ao carregar os dados de {procedimento}: {exc}"
        )
        st.stop()


# ============================================================
# FILTROS
# ============================================================

st.sidebar.header("Filtros")

procedimento = st.sidebar.selectbox(
    "Procedimento",
    options=list(ARQUIVOS.keys()),
)

df_completo = dados[procedimento].copy()

competencias = sorted(df_completo["co_anomes"].unique().tolist())

if not competencias:
    st.error("O arquivo selecionado não possui competências válidas.")
    st.stop()

st.sidebar.caption(
    "Escolha o intervalo de competências disponível no arquivo."
)

# Sugere dezembro de 2025 e julho de 2026 quando ambos existem.
inicio_padrao = (
    competencias.index("202512")
    if "202512" in competencias
    else 0
)

fim_padrao = (
    competencias.index("202607")
    if "202607" in competencias
    else len(competencias) - 1
)

col_inicio, col_fim = st.sidebar.columns(2)

with col_inicio:
    competencia_inicio = st.selectbox(
        "Início",
        options=competencias,
        index=inicio_padrao,
        format_func=rotulo_competencia,
    )

with col_fim:
    competencia_fim = st.selectbox(
        "Fim",
        options=competencias,
        index=fim_padrao,
        format_func=rotulo_competencia,
    )

if competencia_inicio > competencia_fim:
    st.sidebar.error("A competência inicial deve ser anterior à final.")
    st.stop()

# Inclui somente competências existentes entre os limites selecionados.
df_periodo = df_completo[
    (df_completo["co_anomes"] >= competencia_inicio)
    & (df_completo["co_anomes"] <= competencia_fim)
].copy()

if df_periodo.empty:
    st.warning("Não há registros no intervalo selecionado.")
    st.stop()

ufs = sorted(df_periodo["sg_uf"].dropna().unique().tolist())

estados_selecionados = st.sidebar.multiselect(
    "Estados",
    options=ufs,
    default=[],
    help="Deixe vazio para incluir todos os estados.",
)

if estados_selecionados:
    df_periodo = df_periodo[
        df_periodo["sg_uf"].isin(estados_selecionados)
    ].copy()

if df_periodo.empty:
    st.warning("Nenhum município corresponde aos filtros selecionados.")
    st.stop()

competencias_periodo = sorted(df_periodo["co_anomes"].unique().tolist())

competencia_selecionada = st.sidebar.selectbox(
    "Competência para análise territorial",
    options=competencias_periodo,
    index=len(competencias_periodo) - 1,
    format_func=rotulo_competencia,
)

df_comp = df_periodo[
    df_periodo["co_anomes"] == competencia_selecionada
].copy()

if df_comp.empty:
    st.warning("Não há registros para a competência escolhida.")
    st.stop()

df_comp = df_comp.sort_values(
    "vl_indicador_calculado_mun",
    ascending=False,
)

# Registra o período escolhido para os títulos dos gráficos.
rotulo_inicio = rotulo_competencia(competencia_inicio)
rotulo_fim = rotulo_competencia(competencia_fim)


# ============================================================
# INDICADORES PRINCIPAIS
# ============================================================

st.subheader("Resumo do período")
st.caption(
    f"{procedimento} · {rotulo_inicio} a {rotulo_fim} · "
    f"Análise territorial em {rotulo_competencia(competencia_selecionada)}"
)

total_municipios = df_comp["co_ibge"].nunique()

municipios_com_valor = df_comp.loc[
    df_comp["vl_indicador_calculado_mun"] > 0,
    "co_ibge",
].nunique()

municipios_com_zero = df_comp.loc[
    df_comp["vl_indicador_calculado_mun"] == 0,
    "co_ibge",
].nunique()

soma_valores = df_comp["vl_indicador_calculado_mun"].sum()

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Municípios com registro",
    formatar_numero(total_municipios),
)

col2.metric(
    "Municípios com valor positivo",
    formatar_numero(municipios_com_valor),
)

col3.metric(
    "Municípios com valor igual a zero",
    formatar_numero(municipios_com_zero),
)

col4.metric(
    "Soma dos valores municipais",
    formatar_numero(soma_valores),
)

st.markdown(
    """
    <div class="sr-note">
        <strong>Como interpretar:</strong> estes números descrevem os
        valores publicados na base selecionada. Um valor igual a zero
        não comprova ausência de atendimento, e um valor positivo não
        representa, por si só, cobertura populacional. A soma também
        só deve ser interpretada como quantidade de exames depois da
        confirmação da definição oficial do indicador.
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SÉRIE HISTÓRICA DO PERÍODO
# ============================================================

st.subheader("Evolução nas competências disponíveis")

historico = (
    df_periodo.groupby("co_anomes", as_index=False)
    .agg(
        soma_valores=("vl_indicador_calculado_mun", "sum"),
        municipios=("co_ibge", "nunique"),
        municipios_positivos=(
            "vl_indicador_calculado_mun",
            lambda serie: int((serie > 0).sum()),
        ),
    )
    .sort_values("co_anomes")
)

historico["competencia_rotulo"] = historico["co_anomes"].map(
    rotulo_competencia
)

if historico.empty:
    st.info("Não há dados históricos para os filtros selecionados.")
else:
    fig_historico = px.line(
        historico,
        x="competencia_rotulo",
        y="soma_valores",
        markers=True,
        title="Soma dos valores municipais por competência",
        labels={
            "competencia_rotulo": "Competência",
            "soma_valores": "Soma dos valores municipais",
        },
        hover_data={
            "municipios": True,
            "municipios_positivos": True,
            "competencia_rotulo": False,
            "soma_valores": ":,.0f",
        },
    )

    fig_historico.update_layout(
        xaxis_title="Competência disponível",
        yaxis_title="Soma dos valores publicados",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=60, b=20),
    )

    fig_historico.update_xaxes(
        categoryorder="array",
        categoryarray=historico["competencia_rotulo"].tolist(),
    )

    st.plotly_chart(fig_historico, width="stretch")

    if len(historico) == 1:
        st.info(
            "O intervalo filtrado contém apenas uma competência. "
            "Selecione um intervalo maior para visualizar a evolução."
        )

    st.dataframe(
        historico[
            [
                "competencia_rotulo",
                "municipios",
                "municipios_positivos",
                "soma_valores",
            ]
        ].rename(
            columns={
                "competencia_rotulo": "Competência",
                "municipios": "Municípios com registro",
                "municipios_positivos": "Municípios com valor positivo",
                "soma_valores": "Soma dos valores municipais",
            }
        ),
        width="stretch",
        hide_index=True,
    )

st.caption(
    "A série mostra somente competências presentes no arquivo. "
    "Não são criados valores para meses sem dados."
)


# ============================================================
# COMPARAÇÃO POR ESTADO
# ============================================================

st.subheader("Distribuição territorial por estado")

por_estado = (
    df_comp.groupby("sg_uf", as_index=False)
    .agg(
        soma_valores=("vl_indicador_calculado_mun", "sum"),
        municipios=("co_ibge", "nunique"),
        municipios_positivos=(
            "vl_indicador_calculado_mun",
            lambda serie: int((serie > 0).sum()),
        ),
    )
    .sort_values("soma_valores", ascending=False)
)

if por_estado.empty:
    st.info("Não há dados estaduais para esta seleção.")
else:
    fig_estados = px.bar(
        por_estado,
        x="sg_uf",
        y="soma_valores",
        title=(
            "Soma dos valores municipais por estado — "
            f"{rotulo_competencia(competencia_selecionada)}"
        ),
        labels={
            "sg_uf": "UF",
            "soma_valores": "Soma dos valores municipais",
        },
        hover_data={
            "municipios": True,
            "municipios_positivos": True,
            "soma_valores": ":,.0f",
        },
    )

    fig_estados.update_layout(
        xaxis_title="Estado",
        yaxis_title="Soma dos valores publicados",
        margin=dict(l=20, r=20, t=60, b=20),
    )

    st.plotly_chart(fig_estados, width="stretch")

    st.dataframe(
        por_estado.rename(
            columns={
                "sg_uf": "UF",
                "soma_valores": "Soma dos valores municipais",
                "municipios": "Municípios com registro",
                "municipios_positivos": "Municípios com valor positivo",
            }
        ),
        width="stretch",
        hide_index=True,
    )


# ============================================================
# RANKING MUNICIPAL
# ============================================================

st.subheader("Ranking municipal")

st.write(
    "Consulte os maiores ou menores valores registrados na competência "
    "selecionada. O ranking é descritivo e não representa ranking de "
    "qualidade, risco de câncer ou cobertura de prevenção."
)

col_ordem, col_quantidade = st.columns(2)

with col_ordem:
    ordem_ranking = st.radio(
        "Ordenação",
        options=["Maiores valores", "Menores valores"],
        horizontal=True,
    )

with col_quantidade:
    quantidade = st.selectbox(
        "Municípios exibidos",
        options=[10, 20, 50, 100],
        index=1,
    )

ascendente = ordem_ranking == "Menores valores"

ranking = df_comp.sort_values(
    "vl_indicador_calculado_mun",
    ascending=ascendente,
).head(quantidade)

ranking_exibicao = ranking[
    [
        "co_ibge",
        "no_municipio",
        "sg_uf",
        "vl_indicador_calculado_mun",
        "ds_unidade_medida",
    ]
].rename(
    columns={
        "co_ibge": "Código IBGE",
        "no_municipio": "Município",
        "sg_uf": "UF",
        "vl_indicador_calculado_mun": "Valor publicado",
        "ds_unidade_medida": "Unidade informada",
    }
)

st.dataframe(
    ranking_exibicao,
    width="stretch",
    hide_index=True,
)


# ============================================================
# PESQUISA E TABELA MUNICIPAL
# ============================================================

st.subheader("Explorar municípios")

busca = st.text_input(
    "Pesquisar por município, UF ou código IBGE",
    placeholder="Ex.: São Paulo, SP ou código IBGE",
)

df_tabela = df_comp.copy()

if busca.strip():
    termo = busca.strip().lower()

    mascara = (
        df_tabela["no_municipio"].str.lower().str.contains(
            termo, na=False, regex=False
        )
        | df_tabela["sg_uf"].str.lower().str.contains(
            termo, na=False, regex=False
        )
        | df_tabela["co_ibge"].str.contains(
            termo, na=False, regex=False
        )
    )

    df_tabela = df_tabela[mascara]

df_tabela = df_tabela[
    [
        "co_anomes",
        "co_ibge",
        "no_municipio",
        "sg_uf",
        "vl_indicador_calculado_mun",
        "ds_unidade_medida",
    ]
].copy()

df_tabela["co_anomes"] = df_tabela["co_anomes"].map(
    rotulo_competencia
)

df_tabela = df_tabela.rename(
    columns={
        "co_anomes": "Competência",
        "co_ibge": "Código IBGE",
        "no_municipio": "Município",
        "sg_uf": "UF",
        "vl_indicador_calculado_mun": "Valor publicado",
        "ds_unidade_medida": "Unidade informada",
    }
)

st.caption(f"{len(df_tabela):,} registro(s) encontrado(s).".replace(",", "."))

st.dataframe(
    df_tabela,
    width="stretch",
    hide_index=True,
)

st.download_button(
    label="Baixar tabela filtrada em CSV",
    data=criar_csv(df_tabela),
    file_name="sentinela_rosa_dados_filtrados.csv",
    mime="text/csv",
)


# ============================================================
# METODOLOGIA, LIMITAÇÕES E FONTES
# ============================================================

with st.expander("Metodologia e limitações dos dados"):
    st.markdown(
        """
        **Campos utilizados nesta versão**

        - `co_anomes`: competência publicada na base.
        - `co_ibge`: código do município.
        - `no_municipio`: nome do município.
        - `sg_uf`: sigla da unidade federativa.
        - `vl_indicador_calculado_mun`: valor municipal publicado.
        - `ds_unidade_medida`: unidade indicada nos metadados.

        **Cuidados de interpretação**

        1. A base informa unidade de medida como número; isso, isoladamente,
           não confirma todos os detalhes do significado do indicador.
        2. Não calculamos cobertura populacional, pois não foi incluído um
           denominador populacional compatível.
        3. Não interpretamos valor zero como ausência comprovada de serviço.
        4. Não somamos colunas estaduais, regionais ou nacionais repetidas
           em cada linha municipal.
        5. As competências disponíveis são tratadas como observações
           distintas. Não são interpolados meses ausentes.
        6. Antes de comparar dezembro de 2025 com julho de 2026, é necessário
           confirmar se os períodos de apuração são equivalentes e se a
           competência mais recente é parcial.
        7. Os dados são agregados por município; não permitem prever o
           diagnóstico ou o risco individual de uma pessoa.

        **Próximo passo de validação**

        Confirmar no dicionário de dados a definição de
        `vl_indicador_calculado_mun`, a localização geográfica usada
        (residência ou estabelecimento de saúde) e a regra de apuração
        de cada competência antes de criar indicadores compostos ou modelos
        preditivos.
        """
    )

st.markdown("### Fontes oficiais")

st.markdown(
    """
    - [Portal de Dados Abertos do Ministério da Saúde — prevenção do câncer de colo do útero e mama](https://dadosabertos.saude.gov.br/dataset/mgdi-prevencao-do-cancer-de-colo-e-mama)
    - [SISCAN — Sistema de Informação do Câncer (DATASUS)](https://datasus.saude.gov.br/acesso-a-informacao/sistema-de-informacao-do-cancer-siscan-colo-do-utero-e-mama/)
    """
)

st.divider()

st.caption(
    "Sentinela Rosa · Protótipo para exploração de dados públicos. "
    "Os resultados devem ser validados com a documentação oficial "
    "antes de orientar decisões de saúde pública."
)
