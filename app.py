import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Control de Guardias", layout="centered")
st.title("📊 Control de Guardias y Compensatorios")
st.markdown("---")

# Conexión a Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Intentar cargar datos
try:
    df = conn.read(ttl="0")
except Exception:
    df = pd.DataFrame(columns=["Empleado", "Fecha", "Tipo", "Horas"])

def calcular_estado(nombre_empleado):
    user_df = df[df["Empleado"] == nombre_empleado]
    horas_ganadas = user_df[user_df["Tipo"] == "Guardia"]["Horas"].sum()
    dias_tomados_list = user_df[user_df["Tipo"] == "Día Tomado"]["Fecha"].tolist()
    horas_consumidas = len(dias_tomados_list) * 8
    
    balance_horas = horas_ganadas - horas_consumidas
    dias_disponibles = balance_horas // 8
    horas_remanentes = balance_horas % 8
    
    return horas_ganadas, dias_tomados_list, dias_disponibles, horas_remanentes

empleado = st.text_input("Ingresa tu nombre o legajo:", "").strip().lower()

if empleado:
    h_totales, d_lista, d_disp, h_rem = calcular_estado(empleado)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Días Disponibles", f"{int(d_disp)}")
    col2.metric("Horas Acumuladas", f"{int(h_rem)}hs")
    col3.metric("Total Horas Extra", f"{int(h_totales)}hs")

    st.markdown("### Acciones")
    tab1, tab2, tab3 = st.tabs(["➕ Registrar Guardia", "📅 Gestionar Días", "📜 Historial"])

    with tab1:
        fecha_g = st.date_input("Fecha de la guardia:", datetime.now())
        if st.button("Registrar +2 Horas"):
            nueva_fila = pd.DataFrame([{
                "Empleado": empleado,
                "Fecha": fecha_g.strftime("%d/%m/%Y"),
                "Tipo": "Guardia",
                "Horas": 2
            }])
            updated_df = pd.concat([df, nueva_fila], ignore_index=True)
            conn.update(data=updated_df)
            st.success("Guardia registrada.")
            st.rerun()

    with tab2:
        col_a, col_b = st.columns(2)
        with col_a:
            if d_disp >= 1:
                if st.button("✅ Pedir un Día"):
                    nueva_fila = pd.DataFrame([{
                        "Empleado": empleado,
                        "Fecha": datetime.now().strftime("%d/%m/%Y"),
                        "Tipo": "Día Tomado",
                        "Horas": 0
                    }])
                    updated_df = pd.concat([df, nueva_fila], ignore_index=True)
                    conn.update(data=updated_df)
                    st.rerun()
            else:
                st.warning("No tienes horas suficientes para un día.")

        with col_b:
            if d_lista:
                dia_a_cancelar = st.selectbox("Cancelar día tomado el:", d_lista)
                if st.button("❌ Cancelar este día"):
                    index_to_drop = df[(df["Empleado"] == empleado) & 
                                       (df["Tipo"] == "Día Tomado") & 
                                       (df["Fecha"] == dia_a_cancelar)].index.max()
                    updated_df = df.drop(index_to_drop)
                    conn.update(data=updated_df)
                    st.rerun()

    with tab3:
        st.write(f"Movimientos de {empleado.capitalize()}:")
        st.dataframe(df[df["Empleado"] == empleado][["Fecha", "Tipo", "Horas"]], use_container_width=True)
