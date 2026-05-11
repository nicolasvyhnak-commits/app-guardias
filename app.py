import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Control de Guardias", layout="centered")
st.title("📊 Control de Guardias y Compensatorios")
st.markdown("---")

# Conexión a Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Cargar datos
try:
    df = conn.read(ttl="0")
except Exception:
    df = pd.DataFrame(columns=["Empleado", "Fecha", "Tipo", "Horas"])

def calcular_estado(nombre_empleado):
    user_df = df[df["Empleado"] == nombre_empleado]
    # Suma de todas las guardias de 2hs
    horas_ganadas = user_df[user_df["Tipo"] == "Guardia"]["Horas"].sum()
    # Conteo de días de 8hs tomados
    dias_tomados_count = len(user_df[user_df["Tipo"] == "Día Tomado"])
    horas_consumidas = dias_tomados_count * 8
    
    balance_horas = horas_ganadas - horas_consumidas
    dias_disponibles = balance_horas // 8
    horas_remanentes = balance_horas % 8
    
    return horas_ganadas, dias_tomados_count, dias_disponibles, horas_remanentes

empleado = st.text_input("Ingresa tu nombre o legajo:", "").strip().lower()

if empleado:
    h_totales, d_usados, d_disp, h_rem = calcular_estado(empleado)
    
    # Tablero de control
    col1, col2, col3 = st.columns(3)
    col1.metric("Días Disponibles", f"{int(d_disp)}")
    col2.metric("Horas p/ próximo día", f"{int(h_rem)}/8 hs")
    col3.metric("Días ya usados", f"{int(d_usados)}")

    st.markdown("### Acciones")
    tab1, tab2, tab3 = st.tabs(["➕ Registrar Guardia", "📅 Pedir Día", "📜 Historial y Anulaciones"])

    with tab1:
        st.markdown("#### Registrar 2 horas extras")
        fecha_g = st.date_input("Fecha de la guardia:", datetime.now())
        if st.button("Confirmar Guardia (+2hs)"):
            nueva_fila = pd.DataFrame([{
                "Empleado": empleado,
                "Fecha": fecha_g.strftime("%d/%m/%Y"),
                "Tipo": "Guardia",
                "Horas": 2
            }])
            updated_df = pd.concat([df, nueva_fila], ignore_index=True)
            conn.update(data=updated_df)
            st.success("Guardia guardada en la planilla.")
            st.rerun()

    with tab2:
        st.markdown("#### Canjear 8hs por 1 día de descanso")
        if d_disp >= 1:
            st.info(f"Tenés {int(d_disp)} días para usar.")
            if st.button("✅ Usar 1 Día de Vacaciones"):
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
            st.warning(f"Aún no llegás a las 8hs. Te faltan {8 - int(h_rem)} horas.")

    with tab3:
        st.markdown("#### Revisar o eliminar movimientos")
        user_df = df[df["Empleado"] == empleado].copy()
        
        if not user_df.empty:
            # Mostramos la tabla
            st.dataframe(user_df[["Fecha", "Tipo", "Horas"]], use_container_width=True)
            
            # Opción para borrar
            st.markdown("---")
            st.subheader("🗑️ Zona de corrección")
            # Creamos una lista de opciones para el buscador (ID de fila + info)
            user_df['ID'] = user_df.index
            opciones = user_df.apply(lambda x: f"ID:{x['ID']} | {x['Fecha']} | {x['Tipo']}", axis=1).tolist()
            
            movimiento_a_borrar = st.selectbox("Seleccioná qué movimiento querés ELIMINAR:", opciones)
            
            if st.button("⚠️ Eliminar Movimiento Seleccionado"):
                id_a_borrar = int(movimiento_a_borrar.split("|")[0].replace("ID:", "").strip())
                updated_df = df.drop(id_a_borrar)
                conn.update(data=updated_df)
                st.success("Movimiento eliminado y balance recalculado.")
                st.rerun()
        else:
            st.write("No hay movimientos registrados para este usuario.")
