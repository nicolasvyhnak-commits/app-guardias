import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import io

# --- CONFIGURACIÓN Y LISTA DE EMPLEADOS ---
# Agregá o quitá nombres de esta lista según tu sector
LISTA_EMPLEADOS = ["Santi", "Nicolas", "Maria", "Juan", "Pedro", "Elena"]
PASSWORD_JEFA = "sector123" # Podés cambiar esta clave

st.set_page_config(page_title="Control de Guardias v2", layout="centered")

# --- CONEXIÓN Y DATOS ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    df = conn.read(ttl="0")
except Exception:
    df = pd.DataFrame(columns=["Empleado", "Fecha", "Tipo", "Horas"])

# --- LÓGICA DE CÁLCULO ---
def calcular_estado(nombre_empleado):
    user_df = df[df["Empleado"] == nombre_empleado]
    horas_ganadas = user_df[user_df["Tipo"] == "Guardia"]["Horas"].sum()
    dias_tomados_count = len(user_df[user_df["Tipo"] == "Día Tomado"])
    balance_horas = horas_ganadas - (dias_tomados_count * 8)
    return horas_ganadas, dias_tomados_count, (balance_horas // 8), (balance_horas % 8)

# --- INTERFAZ LATERAL (ADMIN) ---
with st.sidebar:
    st.header("🔐 Área de Control")
    modo_admin = st.checkbox("Modo Jefa")
    if modo_admin:
        clave = st.text_input("Contraseña:", type="password")
        if clave == PASSWORD_JEFA:
            st.success("Acceso Autorizado")
            st.subheader("Descargar Reporte")
            
            # Crear Excel en memoria
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False, sheet_name='Reporte_Guardias')
            
            st.download_button(
                label="📥 Descargar Todo en Excel",
                data=buffer.getvalue(),
                file_name=f"reporte_guardias_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
                mime="application/vnd.ms-excel"
            )
        elif clave != "":
            st.error("Clave incorrecta")

# --- CUERPO PRINCIPAL ---
st.title("📊 Control de Guardias y Vacaciones")
st.markdown("---")

# Selección de Nombre Predeterminado
nombre_sel = st.selectbox("Seleccioná tu nombre:", ["Seleccionar..."] + sorted(LISTA_EMPLEADOS))

if nombre_sel != "Seleccionar...":
    empleado = nombre_sel.lower()
    h_totales, d_usados, d_disp, h_rem = calcular_estado(empleado)
    
    # Métricas
    c1, c2, c3 = st.columns(3)
    c1.metric("Días Disponibles", f"{int(d_disp)}")
    c2.metric("Horas Acumuladas", f"{int(h_rem)}/8 hs")
    c3.metric("Días Usados", f"{int(d_usados)}")

    tab1, tab2, tab3 = st.tabs(["➕ Cargar Guardia", "📅 Pedir Día", "📜 Mi Historial"])

    with tab1:
        st.subheader("Registrar nueva guardia")
        f_g = st.date_input("Fecha:", datetime.now())
        if st.button("Confirmar +2hs"):
            nueva = pd.DataFrame([{"Empleado": empleado, "Fecha": f_g.strftime("%d/%m/%Y"), "Tipo": "Guardia", "Horas": 2}])
            conn.update(data=pd.concat([df, nueva], ignore_index=True))
            st.success("Guardado.")
            st.rerun()

    with tab2:
        st.subheader("Solicitar día")
        if d_disp >= 1:
            if st.button("✅ Usar 1 Día"):
                nueva = pd.DataFrame([{"Empleado": empleado, "Fecha": datetime.now().strftime("%d/%m/%Y"), "Tipo": "Día Tomado", "Horas": 0}])
                conn.update(data=pd.concat([df, nueva], ignore_index=True))
                st.rerun()
        else:
            st.warning("No tenés horas suficientes.")

    with tab3:
        st.subheader("Mis movimientos")
        u_df = df[df["Empleado"] == empleado].copy()
        if not u_df.empty:
            st.dataframe(u_df[["Fecha", "Tipo", "Horas"]], use_container_width=True)
            
            st.markdown("---")
            st.caption("Anulaciones")
            u_df['ID'] = u_df.index
            ops = u_df.apply(lambda x: f"ID:{x['ID']} | {x['Fecha']} | {x['Tipo']}", axis=1).tolist()
            borrar = st.selectbox("Eliminar registro:", ops)
            if st.button("🗑️ Borrar Seleccionado"):
                idx = int(borrar.split("|")[0].replace("ID:", "").strip())
                conn.update(data=df.drop(idx))
                st.rerun()
