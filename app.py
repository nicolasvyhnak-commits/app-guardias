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
PASSWORD_ADMIN = "mariva2026" 

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
    # Solo cuentan las guardias APROBADAS (y que no estén en proceso de baja)
    user_df = df[(df["Empleado"] == nombre) & (df["Estado"] == "Aprobado")]
    h_ganadas = user_df[user_df["Tipo"] == "Guardia"]["Horas"].sum()
    d_usados = len(user_df[user_df["Tipo"] == "Día Tomado"])
    
    balance = h_ganadas - (d_usados * 8)
    return h_ganadas, d_usados, (balance // 8), (balance % 8)

# --- INTERFAZ ---
st.title("🏦 Control de Guardias y Compensatorios")

user_sel = st.selectbox("Identificate para continuar:", ["Seleccionar..."] + EMPLEADOS)

if user_sel != "Seleccionar...":
    es_admin = user_sel in ADMINS
    auth_admin = False
    
    if es_admin:
        with st.expander("🔐 Administrador"):
            pass_input = st.text_input("Contraseña de seguridad:", type="password")
            if pass_input == PASSWORD_ADMIN:
                auth_admin = True
                st.success("Funciones de validación habilitadas.")
            elif pass_input != "":
                st.error("Contraseña incorrecta.")

    h_tot, d_uso, d_disp, h_rem = obtener_resumen(user_sel)
    
    st.markdown(f"### Estado de {user_sel}")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Días Disponibles", f"{int(d_disp)}")
    c2.metric("Horas p/ Próximo Día", f"{int(h_rem)}/8 hs")
    c3.metric("Total Horas (Aprobadas)", f"{int(h_tot)} hs")
    c4.metric("Días Ya Tomados", f"{int(d_uso)}")

    pest_nombres = ["➕ Cargar Guardia", "📜 Mi Historial"]
    if auth_admin:
        pest_nombres.insert(1, "📩 Validaciones Pendientes")
        pest_nombres.append("📊 Reporte General")
    
    tabs = st.tabs(pest_nombres)

    # TAB: CARGAR
    with tabs[0]:
        st.write("Registrá tus horas extras o uso de días.")
        f_g = st.date_input("Fecha de la guardia:", datetime.now())
        if st.button("Enviar Guardia para Revisión (+2hs)"):
            nueva = pd.DataFrame([{"Empleado": user_sel, "Fecha": f_g.strftime("%d/%m/%Y"), "Tipo": "Guardia", "Horas": 2, "Estado": "Pendiente"}])
            conn.update(data=pd.concat([df, nueva], ignore_index=True))
            st.toast("Guardia enviada.")
            st.rerun()
        
        st.markdown("---")
        if d_disp >= 1:
            if st.button("✅ Solicitar Uso de 1 Día"):
                nueva = pd.DataFrame([{"Empleado": user_sel, "Fecha": datetime.now().strftime("%d/%m/%Y"), "Tipo": "Día Tomado", "Horas": 0, "Estado": "Aprobado"}])
                conn.update(data=pd.concat([df, nueva], ignore_index=True))
                st.rerun()

    # TAB: VALIDACIONES (Solo Admin)
    if auth_admin:
        with tabs[1]:
            st.subheader("Trámites esperando resolución")
            # Filtramos tanto ingresos nuevos como pedidos de baja
            pendientes = df[df["Estado"].isin(["Pendiente", "Baja Pendiente"])].copy()
            
            if not pendientes.empty:
                for idx, row in pendientes.iterrows():
                    with st.container(border=True):
                        col_info, col_btn = st.columns([3, 1])
                        accion = "ALTA" if row['Estado'] == "Pendiente" else "ELIMINACIÓN"
                        col_info.write(f"**{row['Empleado']}** | {row['Fecha']} | {row['Tipo']} | Solicitud de **{accion}**")
                        
                        if row['Estado'] == "Pendiente":
                            if col_btn.button(f"Aprobar Alta", key=f"app_{idx}"):
                                df.at[idx, "Estado"] = "Aprobado"
                                conn.update(data=df)
                                st.rerun()
                        else: # Es Baja Pendiente
                            if col_btn.button(f"Confirmar Borrado", key=f"del_{idx}"):
                                conn.update(data=df.drop(idx))
                                st.rerun()
                        
                        if col_btn.button(f"Rechazar", key=f"rej_{idx}"):
                            # Si rechaza una baja, vuelve a estar Aprobado. Si rechaza un alta, queda Rechazado.
                            df.at[idx, "Estado"] = "Aprobado" if row['Estado'] == "Baja Pendiente" else "Rechazado"
                            conn.update(data=df)
                            st.rerun()
            else:
                st.info("No hay solicitudes pendientes.")

    # TAB: MI HISTORIAL
    hist_idx = 2 if auth_admin else 1
    with tabs[hist_idx]:
        st.write("Tus movimientos:")
        u_df = df[df["Empleado"] == user_sel].copy()
        if not u_df.empty:
            st.dataframe(u_df[["Fecha", "Tipo", "Horas", "Estado"]], use_container_width=True)
            u_df['ID'] = u_df.index
            opciones = u_df.apply(lambda x: f"ID:{x['ID']} | {x['Fecha']} | {x['Tipo']} ({x['Estado']})", axis=1).tolist()
            st.markdown("---")
            borrar = st.selectbox("Seleccioná un registro para anular:", opciones)
            
            if st.button("🗑️ Solicitar Eliminación"):
                idx_sel = int(borrar.split("|")[0].replace("ID:", "").strip())
                
                if auth_admin:
                    # Si ya está logueado como admin, borra de una
                    conn.update(data=df.drop(idx_sel))
                    st.success("Registro eliminado directamente por administrador.")
                    st.rerun()
                else:
                    # Si es usuario común, lo pasa a estado de revisión
                    df.at[idx_sel, "Estado"] = "Baja Pendiente"
                    conn.update(data=df)
                    st.warning("Solicitud de eliminación enviada a revisión.")
                    st.rerun()

    # TAB: REPORTE (Solo Admin)
    if auth_admin:
        with tabs[-1]:
            st.subheader("Reporte General del Sector")
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                df.to_excel(writer, index=False)
            st.download_button("📥 Descargar Excel", buffer.getvalue(), "reporte_guardias.xlsx")
            st.dataframe(df)
