import streamlit as st
import pandas as pd

st.set_page_config(layout="wide")

st.title("📊 Dashboard de Investigación")

# Subir archivo
archivo = st.file_uploader("Sube tu archivo CSV", type=["csv"])

if archivo is None:
    st.stop()

df = pd.read_csv(archivo)

# Vista rápida
st.subheader("Vista previa del dataset")
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
st.subh
