import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")

st.title("📊 Dashboard de Investigación")

# Subir archivo
archivo = st.file_uploader("Sube tu archivo CSV", type=["csv"])

if archivo is None:
    st.stop()

df = pd.read_csv(archivo)

# Vista rápida
st.subheader("Vista previa")
st.dataframe(df.head())

# Detectar columnas
numericas = df.select_dtypes(include="number").columns.tolist()
categoricas = df.select_dtypes(include="object").columns.tolist()

if not numericas or not categoricas:
    st.warning("El dataset necesita al menos una columna numérica y una categórica")
    st.stop()

# Selección de variables
col_num = st.selectbox("Variable numérica", numericas)
col_cat = st.selectbox("Variable categórica", categoricas)

# Métricas básicas
st.subheader("Indicadores")
c1, c2, c3 = st.columns(3)
c1.metric("Registros", len(df))
c2.metric("Promedio", round(df[col_num].mean(), 2))
c3.metric("Máximo", round(df[col_num].max(), 2))

# Gráfico
st.subheader("Visualización")
fig = px.bar(df, x=col_cat, y=col_num, title=f"{col_num} por {col_cat}")
st.plotly_chart(fig, use_container_width=True)

# Descargar
st.subheader("Descargar datos")
st.download_button(
    "Descargar CSV",
    df.to_csv(index=False).encode("utf-8"),
    file_name="datos.csv",
    mime="text/csv"
)
