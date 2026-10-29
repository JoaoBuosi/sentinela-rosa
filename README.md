# Sentinela Rosa

Dashboard interativo para exploração e análise territorial de indicadores públicos relacionados ao câncer de mama e ao câncer do colo do útero no Brasil.

## Funcionalidades

- Visão geral dos indicadores.
- Estatística descritiva e avançada.
- Análise temporal.
- Análise territorial por município e estado.
- Mapas municipais.
- Exploração de população e serviços de saúde.
- Auditoria da qualidade dos dados.
- Consulta às fontes e metodologia.
- Exportação dos dados filtrados.

## Tecnologias

- Python
- Streamlit
- Pandas
- NumPy
- Plotly
- Requests
- APIs públicas do IBGE

## Instalação

Clone o repositório:

```bash
git clone https://github.com/JoaoBuosi/sentinela-rosa.git
cd sentinela-rosa
```

Crie e ative um ambiente virtual no Windows:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
python -m pip install -r requirements.txt
```

Adicione os arquivos de dados necessários ao diretório `data/raw/`. As bases não são distribuídas neste repositório; confira a origem, a licença e as condições de uso antes de redistribuí-las.

Execute o dashboard:

```powershell
python -m streamlit run app.py
```

## Fontes de dados

O projeto integra serviços públicos do IBGE, incluindo o SIDRA, a API de Localidades e a API de Malhas Territoriais.

## Observação

O painel é uma ferramenta de exploração de dados públicos. Seus resultados dependem da cobertura, da consistência e da metodologia das bases utilizadas. Não substitui avaliações clínicas ou epidemiológicas.

## Autor

**João Vitor Fernandes Buosi**

- GitHub: https://github.com/JoaoBuosi
- LinkedIn: https://www.linkedin.com/in/joaovitorbuosi/
