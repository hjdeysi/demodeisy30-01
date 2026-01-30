# app.py
# Dashboard para investigadores (Streamlit)
# - Carga CSV / Excel
# - Filtros por categorías y rango de fechas
# - KPIs + tablas de calidad
# - Gráficos interactivos (Plotly)
# - Matriz de correlación
# - Descarga del dataset filtrado

from __future__ import annotations

import io
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px


# ----------------------------
# Config
# ----------------------------
st.set_page_config(
    page_title="Dashboard de Investigación",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📊 Dashboard de Investigación (Streamlit)")
st.caption("Carga tu dataset (CSV/Excel), filtra, explora métricas, visualiza patrones y exporta resultados.")


# ----------------------------
# Helpers
# ----------------------------
def _safe_to_datetime(series: pd.Series) -> pd.Series:
    """Intenta convertir a datetime sin romper el flujo."""
    try:
        return pd.to_datetime(series, errors="coerce", infer_datetime_format=True)
    except Exception:
        return pd.Series([pd.NaT] * len(series))


@st.cache_data(show_spinner=False)
def load_data(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """Carga CSV/Excel desde bytes."""
    name = filename.lower()
    if name.endswith(".csv"):
        # intenta encodings comunes
        for enc in ("utf-8", "utf-8-sig", "latin-1"):
            try:
                return pd.read_csv(io.BytesIO(file_bytes), encoding=enc)
            except Exception:
                continue
        # último intento
        return pd.read_csv(io.BytesIO(file_bytes))
    elif name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(file_bytes))
    else:
        raise ValueError("Formato no soportado. Sube un .csv, .xlsx o .xls")


def demo_dataset(n: int = 600) -> pd.DataFrame:
    """Dataset de ejemplo cuando el usuario no sube archivo."""
    rng = np.random.default_rng(7)
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    df = pd.DataFrame(
        {
            "fecha": dates,
            "pais": rng.choice(["Perú", "Colombia", "México", "Chile"], size=n, p=[0.4, 0.2, 0.25, 0.15]),
            "area": rng.choice(["Salud", "Educación", "Finanzas", "Industria"], size=n),
            "grupo": rng.choice(["Control", "Tratamiento A", "Tratamiento B"], size=n, p=[0.35, 0.35, 0.30]),
            "score": np.clip(rng.normal(72, 12, size=n), 0, 100),
            "tiempo_min": np.clip(rng.normal(45, 15, size=n), 5, 180),
            "costo_usd": np.clip(rng.normal(120, 35, size=n), 10, 500),
        }
    )
    # agrega un poco de missing
    mask = rng.random(n) < 0.03
    df.loc[mask, "score"] = np.nan
    return df


def dataframe_quality(df: pd.DataFrame) -> pd.DataFrame:
    """Resumen rápido de calidad de datos."""
    total = len(df)
    out = []
    for col in df.columns:
        miss = df[col].isna().sum()
        out.append(
            {
                "columna": col,
                "tipo": str(df[col].dtype),
                "missing": int(miss),
                "% missing": float((miss / total) * 100) if total else 0.0,
                "n únicos": int(df[col].nunique(dropna=True)),
            }
        )
    return pd.DataFrame(out).sort_values(by=["% missing", "n únicos"], ascending=[False, True])


def to_csv_download(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


# ----------------------------
# Sidebar: carga de datos
# ----------------------------
st.sidebar.header("⚙️ Configuración")

uploaded = st.sidebar.file_uploader(
    "Sube tu dataset (CSV/Excel)",
    type=["csv", "xlsx", "xls"],
    help="Para Streamlit Community Cloud: evita archivos gigantes o considera muestreo.",
)

use_demo = st.sidebar.toggle("Usar dataset de ejemplo", value=(uploaded is None))

if uploaded is None and not use_demo:
    st.info("Sube un archivo o activa 'Usar dataset de ejemplo' en la barra lateral.")
    st.stop()

if use_demo:
    df_raw = demo_dataset()
    st.sidebar.success("Dataset de ejemplo cargado.")
else:
    try:
        df_raw = load_data(uploaded.getvalue(), uploaded.name)
        st.sidebar.success(f"Archivo cargado: {uploaded.name}")
    except Exception as e:
        st.error(f"No se pudo cargar el archivo: {e}")
        st.stop()

if df_raw.empty:
    st.warning("El dataset está vacío.")
    st.stop()

# copia de trabajo
df = df_raw.copy()


# ----------------------------
# Tipos de columna y selección de fecha
# ----------------------------
st.sidebar.subheader("🧭 Columnas")
all_cols = list(df.columns)

# detectar columnas candidatas a fecha (por nombre o dtype)
date_candidates = []
for c in all_cols:
    if "date" in c.lower() or "fecha" in c.lower():
        date_candidates.append(c)

# si hay datetime ya, añadir
for c in all_cols:
    if np.issubdtype(df[c].dtype, np.datetime64) and c not in date_candidates:
        date_candidates.append(c)

date_col = st.sidebar.selectbox(
    "Columna de fecha (opcional)",
    options=["(ninguna)"] + date_candidates + [c for c in all_cols if c not in date_candidates],
    index=0,
)

if date_col != "(ninguna)":
    df[date_col] = _safe_to_datetime(df[date_col])

# separar numéricas y categóricas
num_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
cat_cols = [c for c in df.columns if (df[c].dtype == "object") or pd.api.types.is_categorical_dtype(df[c])]

# ----------------------------
# Filtros
# ----------------------------
st.sidebar.subheader("🎛️ Filtros")

# filtro por rango de fechas
if date_col != "(ninguna)":
    valid_dates = df[date_col].dropna()
    if not valid_dates.empty:
        dmin, dmax = valid_dates.min(), valid_dates.max()
        date_range = st.sidebar.date_input(
            "Rango de fechas",
            value=(dmin.date(), dmax.date()),
            min_value=dmin.date(),
            max_value=dmax.date(),
        )
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start, end = pd.to_datetime(date_range[0]), pd.to_datetime(date_range[1])
            df = df[(df[date_col].notna()) & (df[date_col] >= start) & (df[date_col] <= end)]
    else:
        st.sidebar.info("La columna de fecha no tiene valores válidos.")

# filtros por categóricas (hasta 4 para mantener simple)
max_cat_filters = 4
chosen_cat_filters = st.sidebar.multiselect(
    "Columnas categóricas para filtrar",
    options=cat_cols,
    default=cat_cols[: min(len(cat_cols), 2)],
)

for col in chosen_cat_filters[:max_cat_filters]:
    options = df[col].dropna().astype(str).unique().tolist()
    options.sort()
    selected = st.sidebar.multiselect(f"{col}", options=options, default=options)
    if selected:
        df = df[df[col].astype(str).isin(selected)]

# muestreo para rendimiento
st.sidebar.subheader("🚀 Rendimiento")
sample_n = st.sidebar.slider("Muestreo (filas) para gráficos", min_value=200, max_value=20000, value=3000, step=200)
if len(df) > sample_n:
    df_plot = df.sample(sample_n, random_state=42)
    st.sidebar.info(f"Mostrando {sample_n:,} filas para gráficos (de {len(df):,}).")
else:
    df_plot = df


# ----------------------------
# Layout principal
# ----------------------------
tab1, tab2, tab3 = st.tabs(["📌 Resumen", "📈 Visualizaciones", "🧪 Correlación / Calidad"])


# ----------------------------
# TAB 1: Resumen
# ----------------------------
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Filas", f"{len(df):,}")
    c2.metric("Columnas", f"{df.shape[1]:,}")
    c3.metric("Missing (total)", f"{int(df.isna().sum().sum()):,}")
    c4.metric("% missing", f"{(df.isna().sum().sum() / (df.size) * 100):.2f}%" if df.size else "0.00%")

    st.subheader("Vista previa")
    st.dataframe(df.head(50), use_container_width=True)

    st.subheader("Estadísticos descriptivos (numéricos)")
    if num_cols:
        st.dataframe(df[num_cols].describe().T, use_container_width=True)
    else:
        st.info("No se detectaron columnas numéricas.")

    st.subheader("Descargar dataset filtrado")
    st.download_button(
        "⬇️ Descargar CSV (filtrado)",
        data=to_csv_download(df),
        file_name="dataset_filtrado.csv",
        mime="text/csv",
    )


# ----------------------------
# TAB 2: Visualizaciones
# ----------------------------
with tab2:
    st.subheader("Configuración de gráficos")

    left, right = st.columns([1, 1])

    with left:
        metric_col = st.selectbox("Métrica (numérica)", options=num_cols if num_cols else ["(no hay)"])
        dim_col = st.selectbox("Dimensión (categórica)", options=["(ninguna)"] + cat_cols)
    with right:
        chart_type = st.selectbox(
            "Tipo de gráfico",
            options=[
                "Serie temporal (si hay fecha)",
                "Barras (promedio por categoría)",
                "Histograma (distribución)",
                "Boxplot (por categoría)",
                "Scatter (relación entre 2 numéricas)",
            ],
        )

    if not num_cols:
        st.warning("Necesitas al menos una columna numérica para graficar.")
    else:
        if chart_type == "Serie temporal (si hay fecha)":
            if date_col == "(ninguna)":
                st.info("Selecciona una columna de fecha en la barra lateral para usar serie temporal.")
            else:
                agg = st.selectbox("Agregación", options=["mean", "median", "sum"])
                freq = st.selectbox("Frecuencia", options=["D (diario)", "W (semanal)", "M (mensual)"])
                freq_map = {"D (diario)": "D", "W (semanal)": "W", "M (mensual)": "M"}

                temp = df_plot[[date_col, metric_col]].dropna().copy()
                temp = temp.set_index(date_col).sort_index()
                temp = temp.resample(freq_map[freq]).agg({metric_col: agg}).reset_index()

                fig = px.line(temp, x=date_col, y=metric_col, markers=True, title=f"{metric_col} ({agg}) por tiempo")
                st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "Barras (promedio por categoría)":
            if dim_col == "(ninguna)":
                st.info("Elige una columna categórica como dimensión.")
            else:
                topn = st.slider("Top N categorías", 5, 50, 12)
                temp = (
                    df_plot[[dim_col, metric_col]]
                    .dropna()
                    .groupby(dim_col, as_index=False)[metric_col]
                    .mean()
                    .sort_values(metric_col, ascending=False)
                    .head(topn)
                )
                fig = px.bar(temp, x=dim_col, y=metric_col, title=f"Promedio de {metric_col} por {dim_col} (Top {topn})")
                st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "Histograma (distribución)":
            bins = st.slider("Bins", 10, 120, 35)
            fig = px.histogram(df_plot, x=metric_col, nbins=bins, title=f"Distribución de {metric_col}")
            st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "Boxplot (por categoría)":
            if dim_col == "(ninguna)":
                st.info("Elige una columna categórica como dimensión.")
            else:
                fig = px.box(
                    df_plot.dropna(subset=[dim_col, metric_col]),
                    x=dim_col,
                    y=metric_col,
                    points="outliers",
                    title=f"Boxplot de {metric_col} por {dim_col}",
                )
                st.plotly_chart(fig, use_container_width=True)

        elif chart_type == "Scatter (relación entre 2 numéricas)":
            x_col = st.selectbox("Eje X (numérica)", options=num_cols, index=0)
            y_col = st.selectbox("Eje Y (numérica)", options=num_cols, index=min(1, len(num_cols) - 1))
            color_col = st.selectbox("Color (opcional)", options=["(ninguno)"] + cat_cols)

            fig = px.scatter(
                df_plot.dropna(subset=[x_col, y_col]),
                x=x_col,
                y=y_col,
                color=None if color_col == "(ninguno)" else color_col,
                trendline="ols",
                title=f"Relación entre {x_col} y {y_col}",
            )
            st.plotly_chart(fig, use_container_width=True)


# ----------------------------
# TAB 3: Correlación / Calidad
# ----------------------------
with tab3:
    c1, c2 = st.columns([1, 1])

    with c1:
        st.subheader("Calidad de datos (missing y tipos)")
        q = dataframe_quality(df)
        st.dataframe(q, use_container_width=True, height=420)

    with c2:
        st.subheader("Matriz de correlación (numéricas)")
        if len(num_cols) >= 2:
            corr_method = st.selectbox("Método", options=["pearson", "spearman", "kendall"], index=0)
            corr = df[num_cols].corr(method=corr_method)
            fig = px.imshow(corr, text_auto=True, title=f"Correlación ({corr_method})")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Se requieren al menos 2 columnas numéricas para correlación.")

    st.subheader("Notas rápidas para investigación")
    st.markdown(
        """
- Usa **filtros** para comparar grupos (tratamientos, cohortes, países, etc.).
- Revisa **missing** y considera imputación/depuración antes de modelar.
- La correlación **no implica causalidad**; úsala como guía exploratoria.
        """.strip()
    )

st.sidebar.markdown("---")
st.sidebar.caption("Sugerencia: sube CSV/Excel limpio, con nombres de columnas claros y una columna de fecha si aplica.")
