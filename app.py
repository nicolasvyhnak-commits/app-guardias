import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import io

# --- CONFIGURACIÓN ---
EMPLEADOS = [
    "Hornorio Felipe Oleksuk", 
    "Norberto Palacios", 
    "Carla Simonetti", 
    "Marcos Alonso", 
    "Nicolas Vyhñak", 
    "Viviana Ingribelli"
]
ADMINS = ["Nicolas Vyhñak", "Viviana Ingribelli"]
PASSWORD_ADMIN = "mariva2026" # Podés cambiar esta clave

st.set_page_config(page_title="Sistema de Guardias", layout="wide")

# --- CONEXIÓN ---
conn = st.connection("gsheets", type=GSheetsConnection)

def cargar_datos():
    try:
        return conn.read(ttl="0")
    except:
        return pd.DataFrame(columns=["Empleado", "Fecha", "Tipo", "Horas", "Estado"])

df = cargar_datos()

# --- LÓGICA DE SALDOS ---
def obtener_resumen(nombre):
    # Solo cuentan las guardias APROBADAS
    user_df = df[(df["Empleado"] == nombre) & (df["Estado"] == "Aprobado")]
    h_ganadas = user_df[user_df["Tipo"] == "Guardia"]["Horas"].sum()
    d_usados = len(user_df[user_df["Tipo"] == "Día Tomado"])
    
    balance = h_ganadas - (d_usados * 8)
    return h_ganadas, d_usados, (balance // 8), (balance % 8)

# --- INTERFAZ ---
st.title("🏦 Control de Guardias y Compensatorios")

# Selector de usuario con estilo limpio
user_sel = st.selectbox("Identificate para continuar:", ["Seleccionar..."] + EMPLEADOS)

if user_sel != "Seleccionar...":
    es_admin = user_sel in ADMINS
    
    # Si es Admin, pide clave para habilitar funciones de Jefa
    auth_admin = False
    if es_admin:
        with st.expander("🔐 Acceso Administrador / Jefatura"):
            pass_input = st.text_input("Contraseña de seguridad:", type="password")
            if pass_input == PASSWORD_ADMIN:
                auth_admin = True
                st.success("Funciones de aprobación habilitadas.")
            elif pass_input != "":
                st.error("Contraseña incorrecta.")

    # Dashboard de métricas
    h_tot, d_uso, d_disp, h_rem = obtener_resumen(user_sel)
    
    st.markdown(f"### Estado de {user_sel}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Días Disponibles", f"{int(d_disp)}")
    c2.metric("Horas p/ Próximo Día", f"{int(h_rem)}/8 hs")
    c3.metric("Total Horas (Aprobadas)", f"{int(h_tot)} hs")
    c4.metric("Días Ya Tomados", f"{int(d_uso)}")

    # Pestañas de Interacción
    pest_nombres = ["➕ Cargar Guardia", "📜 Mi Historial"]
    if auth_admin:
        pest_nombres.insert(1, "📩 Pendientes de Aprobación")
        pest_nombres.append("📊 Reporte General")
    
    tabs = st.tabs(pest_nombres)

    # TAB 1: CARGAR GUARDIA (Para todos)
    with tabs[0]:
        st.write("Registrá tus horas extras para aprobación.")
        f_g = st.date_input("Fecha de la guardia:", datetime.now())
        if st.button("Enviar para Revisión (+2hs)"):
            nueva = pd.DataFrame([{
                "Empleado": user_sel,
                "Fecha": f_g.strftime("%d/%m/%Y"),
                "Tipo": "Guardia",
                "Horas": 2,
                "Estado": "Pendiente"
            }])
            conn.update(data=pd.concat([df, nueva], ignore_index=True))
            st.toast("Guardia enviada. Pendiente de aprobación por Jefatura.")
            st.rerun()
        
        st.markdown("---")
        if d_disp >= 1:
            if st.button("✅ Solicitar Uso de 1 Día"):
                nueva = pd.DataFrame([{
                    "Empleado": user_sel,
                    "Fecha": datetime.now().strftime("%d/%m/%Y"),
                    "Tipo": "Día Tomado",
                    "Horas": 0,
                    "Estado": "Aprobado" # El día tomado se descuenta directo o podés ponerlo pendiente también
                }])
                conn.update(data=pd.concat([df, nueva], ignore_index=True))
                st.rerun()

    # TAB: PENDIENTES (Solo Jefa/Admin)
    if auth_admin:
        with tabs[1]:
            st.subheader("Solicitudes esperando aprobación")
            pendientes = df[df["Estado"] == "Pendiente"].copy()
            if not pendientes.empty:
                for idx, row in pendientes.iterrows():
                    with st.container(border=True):
                        col_info, col_btn = st.columns([3, 1])
                        col_info.write(f"**{row['Empleado']}** - {row['Fecha']} ({row['Horas']}hs)")
                        if col_btn.button(f"Aprobar", key=f"app_{idx}"):
                            df.at[idx, "Estado"] = "Aprobado"
                            conn.update(data=df)
                            st.rerun()
                        if col_btn.button(f"Rechazar", key=f"rej_{idx}"):
                            df.at[idx, "Estado"] = "Rechazado"
                            conn.update(data=df)
                            st.rerun()
            else:
                st.info("No hay trámites pendientes.")

    # TAB: MI HISTORIAL
    hist_idx = 2 if auth_admin else 1
    with tabs[hist_idx]:
        st.write("Tus últimos movimientos y sus estados:")
        u_df = df[df["Empleado"] == user_sel].copy()
        if not u_df.empty:
            st.dataframe(u_df[["Fecha", "Tipo", "Horas", "Estado"]], use_container_width=True)
            # Solo dejar borrar si está pendiente o si sos admin
            u_df['ID'] = u_df.index
            opciones = u_df.apply(lambda x: f"ID:{x['ID']} | {x['Fecha']} | {x['Tipo']} ({x['Estado']})", axis=1).tolist()
            st.markdown("---")
            borrar = st.selectbox("Anular un registro propio:", opciones)
            if st.button("🗑️ Eliminar"):
                id_borrar = int(borrar.split("|")[0].replace("ID:", "").strip())
                conn.update(data=df.drop(id_borrar))
                st.rerun()

    # TAB: REPORTE GENERAL (Solo Jefa/Admin)
    if auth_admin:
        with tabs[-1]:
            st.subheader("Descargar planilla completa")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 Descargar reporte para RRHH", buffer.getvalue(), "reporte_total.xlsx")
            st.write("Vista global del sector:")
            st.dataframe(df)
