# simulador_dhondt.py
# Versión ultra compatible:
# - Editor en un st.form + botón "Recalcular" => asegura el rerun
# - Usa st.data_editor o st.experimental_data_editor según tu versión
# - Colores únicos por partido
# - Reparto D'Hondt
# - Cuadro de cocientes ÷1..÷4 con top-4 resaltado

import io
import hashlib
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Simulador D'Hondt (Perú)", page_icon="🧮", layout="wide")
st.title("🧮 Simulador de Cifra Repartidora (D’Hondt) – Perú")

REQUIRED_COLS = ["Partido", "Votos"]

INIT = [
    {"Partido": "Fuerza Popular",  "Votos": 71758},
    {"Partido": "Peru Libre",      "Votos": 42691},
    {"Partido": "Renovación",      "Votos": 36004},
    {"Partido": "Accion Popular",  "Votos": 33212},
    {"Partido": "Podemos Perú",    "Votos": 28944},
]

# ---------------- Helpers ----------------
def to_df(obj) -> pd.DataFrame:
    if isinstance(obj, pd.DataFrame):
        df = obj.copy()
    elif isinstance(obj, list):
        df = pd.DataFrame(obj)
    elif isinstance(obj, dict):
        if "data" in obj and isinstance(obj["data"], list):
            df = pd.DataFrame(obj["data"])
        else:
            try:
                df = pd.DataFrame.from_dict(obj)
            except Exception:
                df = pd.DataFrame(INIT)
    else:
        df = pd.DataFrame(INIT)

    df = df.rename(columns={c: str(c).strip() for c in df.columns})
    canon = {}
    for c in df.columns:
        lc = c.lower()
        if lc == "partido": canon[c] = "Partido"
        elif lc in ("votos", "voto", "votes"): canon[c] = "Votos"
    if canon:
        df = df.rename(columns=canon)
    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = 0 if col == "Votos" else ""
    return df[REQUIRED_COLS]

def sanitize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Partido"] = df["Partido"].fillna("").astype(str)
    df["Votos"] = pd.to_numeric(df["Votos"], errors="coerce").fillna(0).clip(lower=0).round().astype(int)
    return df

def dhondt(df_: pd.DataFrame, seats_: int):
    if df_.empty or seats_ <= 0:
        return pd.Series(dtype=int), pd.DataFrame(columns=["Partido","Divisor","Cociente","Rank","GanaEscaño"])
    rows = []
    for idx, r in df_.iterrows():
        v = int(r["Votos"])
        for d in range(1, seats_ + 1):
            rows.append({"idx": idx, "Partido": r["Partido"], "Divisor": d, "Cociente": v / d})
    q = pd.DataFrame(rows).sort_values("Cociente", ascending=False, ignore_index=True)
    q["Rank"] = q.index + 1
    q["GanaEscaño"] = q["Rank"] <= seats_
    alloc = pd.Series(0, index=df_.index, dtype=int)
    for _, r in q[q["GanaEscaño"]].iterrows():
        alloc.loc[r["idx"]] += 1
    return alloc, q

def color_for(name: str):
    h = int(hashlib.md5(name.encode("utf-8")).hexdigest(), 16)
    t = (h % 1000) / 1000.0
    return plt.cm.tab20(t % 1.0)

# ---------------- Estado inicial ----------------
if "store_df" not in st.session_state:
    st.session_state.store_df = pd.DataFrame(INIT, columns=REQUIRED_COLS)

# ---------------- Sidebar ----------------
with st.sidebar:
    seats = st.number_input("Escaños a repartir", min_value=1, max_value=200, value=4, step=1,
                            help="Ejemplo: 4 para Lima Provincias")
    order_chart = st.toggle("Ordenar gráfico por votos (desc.)", value=True)
    st.markdown("---")
    if st.button("Restablecer datos"):
        st.session_state.store_df = pd.DataFrame(INIT, columns=REQUIRED_COLS)

# ---------------- Editor dentro de un FORM (gatilla los cálculos al enviar) ----------------
st.subheader("📋 Partidos y votos")

# Compatibilidad: usa data_editor si existe; si no, experimental_data_editor
try:
    editor_fn = st.data_editor
except AttributeError:
    editor_fn = st.experimental_data_editor  # para versiones antiguas

with st.form("form_editor", clear_on_submit=False):
    edited_df = editor_fn(
        st.session_state.store_df,
        key="editor_df",
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
        column_order=REQUIRED_COLS,
        column_config={
            "Partido": st.column_config.TextColumn("Partido", required=True),
            "Votos":   st.column_config.NumberColumn("Votos", min_value=0, step=1, format="%d"),
        },
    )
    submitted = st.form_submit_button("Recalcular")

# Si enviaste el formulario, actualizamos el store
if submitted:
    st.session_state.store_df = sanitize(to_df(edited_df))

# Fuente de la verdad SIEMPRE
df = st.session_state.store_df.copy()

# ---------------- Cálculos ----------------
total_votes = int(df["Votos"].sum())
df["%"] = (df["Votos"] / total_votes * 100.0).fillna(0).round(2)
alloc, qdf = dhondt(df, int(seats))
df["Escaños"] = alloc

# ---------------- Visualización ----------------
c1, c2 = st.columns([2, 1], gap="large")

with c1:
    st.subheader("📊 Gráfico de votos (colores únicos por partido)")
    plot_df = df.sort_values(["Votos", "Escaños", "Partido"], ascending=[False, False, True]) if order_chart else df
    color_map = {p: color_for(p) for p in df["Partido"]}
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(plot_df["Partido"], plot_df["Votos"], color=[color_map[p] for p in plot_df["Partido"]])
    ax.set_xlabel("Partido"); ax.set_ylabel("Votos")
    ax.tick_params(axis="x", rotation=30)
    st.pyplot(fig, clear_figure=True)

with c2:
    st.subheader("ℹ️ Totales")
    st.metric("Total de votos", f"{total_votes:,}".replace(",", "."))
    winners = df[df["Escaños"] > 0][["Partido","Escaños"]].sort_values(["Escaños","Partido"], ascending=[False, True])
    if winners.empty:
        st.caption("(Sin asignaciones)")
    else:
        st.table(winners.set_index("Partido"))

st.subheader("📑 Tabla con porcentajes y escaños")
st.dataframe(
    df.sort_values("Votos", ascending=False).set_index("Partido")[["Votos","%","Escaños"]],
    use_container_width=True
)

# ---------------- Cuadro de cocientes ÷1..÷4 con top-4 resaltado ----------------
st.subheader("🔍 Cocientes D’Hondt por partido (÷1, ÷2, ÷3, ÷4)")

def quotient_matrix_top4(df_):
    divisores = [1, 2, 3, 4]
    cols = [f"÷{d}" for d in divisores]
    m = pd.DataFrame(index=df_["Partido"], columns=cols, dtype=float)
    for _, r in df_.iterrows():
        for d in divisores:
            m.at[r["Partido"], f"÷{d}"] = r["Votos"] / d
    m_int = m.round(0).astype(int)

    # Top 4 globales
    flat = m_int.stack().sort_values(ascending=False).head(4)
    mask = pd.DataFrame(False, index=m_int.index, columns=m_int.columns)
    for idx, col in flat.index:
        mask.loc[idx, col] = True

    def highlight(row):
        row_index = row.name
        return [
            "background-color: #1f6feb; color: white; font-weight: bold; border: 2px solid #0b4eda"
            if mask.loc[row_index, col] else ""
            for col in row.index
        ]

    # Si pandas no soporta estilos, mostramos sin resaltado
    try:
        styled = (m_int.style
                  .apply(highlight, axis=1)
                  .set_properties(**{"text-align": "center"})
                  .set_table_styles([{"selector": "th", "props": [("text-align", "center"), ("font-weight", "bold")]}]))
        return styled
    except Exception:
        st.warning("Tu versión de pandas no soporta estilos; mostrando la tabla sin resaltado.")
        return m_int

st.write(quotient_matrix_top4(df))

# ---------------- Descargas ----------------
def to_csv_bytes(df_):
    s = io.StringIO(); df_[["Partido","Votos"]].to_csv(s, index=False); return s.getvalue().encode("utf-8")
def to_json_bytes(df_):
    s = io.StringIO(); df_[["Partido","Votos"]].to_json(s, orient="records", force_ascii=False); return s.getvalue().encode("utf-8")

st.download_button("⬇️ CSV (Partidos,Votos)", data=to_csv_bytes(df), file_name="partidos_votos.csv", mime="text/csv")
st.download_button("⬇️ JSON", data=to_json_bytes(df), file_name="partidos_votos.json", mime="application/json")
