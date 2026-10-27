import streamlit as st
import pandas as pd
import io
import importlib
from datetime import date
import database as db
import pdf_extractor

# Recargar pdf_extractor
importlib.reload(pdf_extractor)

st.set_page_config(
    page_title="Control de Ventas y Cobranzas - Centroamérica",
    page_icon="🌎",
    layout="wide"
)

# Inicializar Base de Datos
db.init_db()

# Session State Notificaciones
if "mensaje_exito" not in st.session_state:
    st.session_state.mensaje_exito = None
if "mensaje_error" not in st.session_state:
    st.session_state.mensaje_error = None

st.title("🌎 Control de Ventas y Cuentas por Cobrar (Multipaís)")
st.caption("Gestión regional con desglose automático de IVA, múltiples monedas y carga masiva")

# --- FILTROS GLOBALES EN BARRA LATERAL ---
st.sidebar.header("📌 Filtros Regionales")

PAISES_DISPONIBLES = ["Todos", "El Salvador", "Guatemala", "Honduras", "Nicaragua", "Costa Rica"]
pais_seleccionado = st.sidebar.selectbox("Seleccionar País", PAISES_DISPONIBLES)

if pais_seleccionado == "Guatemala":
    monedas_opciones = ["Todas", "GTQ (Q)", "USD ($)"]
elif pais_seleccionado == "Honduras":
    monedas_opciones = ["Todas", "HNL (L)"]
elif pais_seleccionado == "Todos":
    monedas_opciones = ["Todas", "USD ($)", "GTQ (Q)", "HNL (L)"]
else:
    monedas_opciones = ["Todas", "USD ($)"]

moneda_seleccionada = st.sidebar.selectbox("Seleccionar Moneda", monedas_opciones)

st.sidebar.divider()
st.sidebar.markdown("**ℹ️ Tasas de IVA / ISV Aplicables:**")
st.sidebar.markdown("- 🇸🇻 El Salvador: 13% IVA (USD)")
st.sidebar.markdown("- 🇬🇹 Guatemala: 12% IVA (GTQ / USD)")
st.sidebar.markdown("- 🇭🇳 Honduras: 15% ISV (HNL)")
st.sidebar.markdown("- 🇳🇮 Nicaragua: 15% IVA (USD - Manual)")
st.sidebar.markdown("- 🇨🇷 Costa Rica: 13% IVA (USD)")

# Cargar datos filtrados
df_ventas = db.obtener_ventas(pais=pais_seleccionado, moneda=moneda_seleccionada)
df_abonos = db.obtener_abonos()

# --- MÉTRICAS GENERALES (KPIs) ---
if not df_ventas.empty:
    total_neto = df_ventas['monto_neto'].sum()
    total_iva = df_ventas['monto_iva'].sum()
    total_facturado = df_ventas['monto_total'].sum()
    total_pendiente = df_ventas['saldo_pendiente'].sum()
    total_cobrado = total_facturado - total_pendiente
    pct_recuperacion = (total_cobrado / total_facturado * 100) if total_facturado > 0 else 0
else:
    total_neto = total_iva = total_facturado = total_cobrado = total_pendiente = pct_recuperacion = 0.0

col_simbolo = "$" if moneda_seleccionada in ["USD ($)", "Todas"] else ("Q" if moneda_seleccionada == "GTQ (Q)" else "L")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Monto Neto", f"{col_simbolo} {total_neto:,.2f}")
col2.metric("Total IVA / ISV", f"{col_simbolo} {total_iva:,.2f}")
col3.metric("Total Facturado", f"{col_simbolo} {total_facturado:,.2f}")
col4.metric("Saldo Pendiente", f"{col_simbolo} {total_pendiente:,.2f}", delta_color="inverse")
col5.metric("% Recuperación", f"{pct_recuperacion:.1f}%")

st.divider()

if st.session_state.mensaje_exito:
    st.success(st.session_state.mensaje_exito)
    st.session_state.mensaje_exito = None

if st.session_state.mensaje_error:
    st.warning(st.session_state.mensaje_error)
    st.session_state.mensaje_error = None

# --- NAVEGACIÓN POR PESTAÑAS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Resumen de Ventas", 
    "➕ Nueva Venta Individual", 
    "📂 Carga Masiva (Excel/CSV/PDF)",
    "💵 Registrar Abono", 
    "📥 Exportar Reportes"
])

# 1. TABLA PRINCIPAL DE VENTAS
with tab1:
    st.subheader(f"Listado de Facturas Registradas ({pais_seleccionado} / {moneda_seleccionada})")
    
    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        filtro_estado = st.multiselect(
            "Filtrar por Estado",
            options=["Pendiente", "Parcial", "Pagado"],
            default=["Pendiente", "Parcial", "Pagado"]
        )
    with col_filtro2:
        busqueda_cliente = st.text_input("Buscar por Cliente o N° Factura")

    df_filtrado = df_ventas.copy()
    if filtro_estado and not df_filtrado.empty:
        df_filtrado = df_filtrado[df_filtrado['estado'].isin(filtro_estado)]
    if busqueda_cliente and not df_filtrado.empty:
        df_filtrado = df_filtrado[
            df_filtrado['cliente'].str.contains(busqueda_cliente, case=False, na=False) |
            df_filtrado['num_factura'].str.contains(busqueda_cliente, case=False, na=False)
        ]

    st.dataframe(
        df_filtrado,
        use_container_width=True,
        column_config={
            "id": "ID",
            "num_factura": "N° Factura",
            "cliente": "Cliente / Empresa",
            "fecha": "Fecha",
            "pais": "País",
            "moneda": "Moneda",
            "monto_neto": st.column_config.NumberColumn("Valor Neto", format="%.2f"),
            "monto_iva": st.column_config.NumberColumn("Monto IVA", format="%.2f"),
            "monto_total": st.column_config.NumberColumn("Total Facturado", format="%.2f"),
            "saldo_pendiente": st.column_config.NumberColumn("Saldo Pendiente", format="%.2f"),
            "estado": "Estado"
        },
        hide_index=True
    )
    
    # SECCIÓN DE EDICIÓN Y ELIMINACIÓN DE FACTURAS
    st.divider()
    with st.expander("⚙️ Modificar o Eliminar una Factura Registrada"):
        if df_ventas.empty:
            st.info("No hay facturas registradas disponibles para editar o eliminar.")
        else:
            opciones_edicion = {
                row['id']: f"[{row['pais']}] Factura: {row['num_factura']} | Cliente: {row['cliente']} | Total: {row['moneda']} {row['monto_total']:,.2f}"
                for _, row in df_ventas.iterrows()
            }
            
            id_factura_sel = st.selectbox(
                "Selecciona la factura que deseas modificar o eliminar:",
                options=list(opciones_edicion.keys()),
                format_func=lambda x: opciones_edicion[x],
                key="sel_factura_gestion"
            )
            
            factura_sel = df_ventas[df_ventas['id'] == id_factura_sel].iloc[0]
            
            col_ed1, col_ed2 = st.columns(2)
            
            with col_ed1:
                st.markdown("#### ✏️ Editar Datos de la Factura")
                with st.form("form_editar_factura"):
                    e_num_factura = st.text_input("Número de Factura / DTE", value=str(factura_sel['num_factura']))
                    e_cliente = st.text_input("Cliente / Empresa", value=str(factura_sel['cliente']))
                    
                    try:
                        fecha_val = date.fromisoformat(str(factura_sel['fecha']))
                    except Exception:
                        fecha_val = date.today()
                        
                    e_fecha = st.date_input("Fecha de Emisión", value=fecha_val)
                    
                    lista_paises = ["El Salvador", "Guatemala", "Honduras", "Nicaragua", "Costa Rica"]
                    idx_pais = lista_paises.index(factura_sel['pais']) if factura_sel['pais'] in lista_paises else 0
                    e_pais = st.selectbox("País", lista_paises, index=idx_pais)
                    
                    monedas_disp = db.MONEDAS_POR_PAIS[e_pais]
                    idx_moneda = monedas_disp.index(factura_sel['moneda']) if factura_sel['moneda'] in monedas_disp else 0
                    e_moneda = st.selectbox("Moneda", monedas_disp, index=idx_moneda)
                    
                    e_monto_total = st.number_input("Monto Total Incorporado con IVA", value=float(factura_sel['monto_total']), min_value=0.01, step=10.0, format="%.2f")
                    
                    btn_actualizar = st.form_submit_button("💾 Guardar Cambios")
                    if btn_actualizar:
                        exito, msj = db.actualizar_venta(
                            id_factura_sel, e_num_factura, e_cliente, e_fecha, e_pais, e_moneda, e_monto_total
                        )
                        if exito:
                            st.session_state.mensaje_exito = msj
                            st.rerun()
                        else:
                            st.error(msj)
                            
            with col_ed2:
                st.markdown("#### 🗑️ Eliminar Factura")
                st.warning("⚠️ **Atención:** Al eliminar esta factura, también se eliminarán todos los abonos registrados vinculados a ella de forma permanente.")
                
                confirmar_eliminar = st.checkbox(f"Confirmo que deseo eliminar la factura N° {factura_sel['num_factura']}")
                if st.button("🔴 Eliminar Definitivamente", type="primary", disabled=not confirmar_eliminar):
                    exito, msj = db.eliminar_venta(id_factura_sel)
                    if exito:
                        st.session_state.mensaje_exito = msj
                        st.rerun()
                    else:
                        st.error(msj)

# 2. NUEVA VENTA INDIVIDUAL
with tab2:
    st.subheader("Registrar Venta Individual (Manual)")
    with st.form("form_nueva_venta", clear_on_submit=True):
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            pais_form = st.selectbox("País de Destino / Operación *", ["El Salvador", "Guatemala", "Honduras", "Nicaragua", "Costa Rica"])
            moneda_opciones_form = db.MONEDAS_POR_PAIS[pais_form]
            moneda_form = st.selectbox("Moneda de Facturación *", moneda_opciones_form)
            num_factura = st.text_input("Número de Factura / DTE *")
        with col_p2:
            cliente = st.text_input("Nombre del Cliente / Empresa *")
            fecha_venta = st.date_input("Fecha de Emisión", value=date.today())
            monto_total = st.number_input("Monto Total Incorporado con IVA *", min_value=0.01, step=10.0, format="%.2f")

        tasa_iva_actual = db.TASAS_IVA[pais_form]
        st.info(f"💡 Para **{pais_form}**, la tasa de impuesto aplicada es del **{int(tasa_iva_actual*100)}%**.")

        submitted_venta = st.form_submit_button("Guardar Factura")
        if submitted_venta:
            if not num_factura or not cliente or monto_total <= 0:
                st.error("Por favor completa los campos obligatorios.")
            else:
                exito, msj = db.registrar_venta(num_factura, cliente, fecha_venta, pais_form, moneda_form, monto_total)
                if exito:
                    st.session_state.mensaje_exito = msj
                    st.rerun()
                else:
                    st.error(msj)

# 3. CARGA MASIVA E INTERACTIVA DE FACTURAS (EXCEL / CSV / PDF)
with tab3:
    st.subheader("📂 Carga Masiva y Revisión Interactiva (PDF, Excel o CSV)")
    st.write("Sube tus archivos PDF o listas en Excel/CSV. Revisa o edita cualquier campo en la tabla antes de hacer clic en Confirmar.")
    
    col_plantilla1, col_plantilla2 = st.columns([2, 1])
    with col_plantilla1:
        st.markdown("**Estructura de columnas para Excel/CSV:**")
        st.code("num_factura, cliente, fecha, pais, moneda, monto_total", language="text")
    with col_plantilla2:
        df_ejemplo = pd.DataFrame([
            {"num_factura": "FACT-001", "cliente": "Empresa Alfa", "fecha": str(date.today()), "pais": "El Salvador", "moneda": "USD ($)", "monto_total": 113.00},
            {"num_factura": "FACT-002", "cliente": "Guatemala Trans", "fecha": str(date.today()), "pais": "Guatemala", "moneda": "GTQ (Q)", "monto_total": 1120.00},
            {"num_factura": "FACT-003", "cliente": "Logística San José", "fecha": str(date.today()), "pais": "Costa Rica", "moneda": "USD ($)", "monto_total": 565.00}
        ])
        buffer_ejemplo = io.BytesIO()
        with pd.ExcelWriter(buffer_ejemplo, engine='openpyxl') as writer:
            df_ejemplo.to_excel(writer, sheet_name='Plantilla', index=False)
        st.download_button(
            label="📥 Descargar Plantilla Excel Ejemplo",
            data=buffer_ejemplo.getvalue(),
            file_name="Plantilla_Carga_Masiva_Ventas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
    st.divider()
    
    archivos_subidos = st.file_uploader(
        "Selecciona uno o varios archivos (PDF, Excel o CSV)", 
        type=["xlsx", "csv", "pdf"],
        accept_multiple_files=True,
        key="uploader_masivo"
    )
    
    if archivos_subidos:
        lista_facturas = []
        
        for archivo in archivos_subidos:
            nombre = archivo.name
            if nombre.endswith('.pdf'):
                datos_pdf = pdf_extractor.extraer_datos_factura_pdf(archivo, filename=nombre)
                lista_facturas.append(datos_pdf)
            elif nombre.endswith('.csv'):
                try:
                    df_c = pd.read_csv(archivo)
                    lista_facturas.extend(df_c.to_dict('records'))
                except Exception as e:
                    st.error(f"Error al leer CSV '{nombre}': {e}")
            elif nombre.endswith('.xlsx'):
                try:
                    df_e = pd.read_excel(archivo)
                    lista_facturas.extend(df_e.to_dict('records'))
                except Exception as e:
                    st.error(f"Error al leer Excel '{nombre}': {e}")
                    
        if lista_facturas:
            df_base = pd.DataFrame(lista_facturas)
            
            # Recalcular desgloses
            netos = []
            ivas = []
            for _, row in df_base.iterrows():
                pais_r = str(row.get('pais', 'Honduras'))
                tot_r = float(row.get('monto_total', 0.0))
                
                m_neto = row.get('monto_neto', None)
                m_iva = row.get('monto_iva', None)
                
                if pd.isnull(m_neto) or pd.isnull(m_iva) or (m_neto == 0 and m_iva == 0 and tot_r > 0):
                    n_calc, i_calc = db.calcular_desglose_iva(tot_r, pais_r)
                    netos.append(n_calc)
                    ivas.append(i_calc)
                else:
                    netos.append(float(m_neto))
                    ivas.append(float(m_iva))
                    
            df_base['monto_neto'] = netos
            df_base['monto_iva'] = ivas
            
            cols_deseadas = ['num_factura', 'cliente', 'fecha', 'pais', 'moneda', 'monto_neto', 'monto_iva', 'monto_total']
            for c in cols_deseadas:
                if c not in df_base.columns:
                    df_base[c] = ""
                    
            df_base = df_base[cols_deseadas]
            
            st.subheader("📝 Vista Previa Editable")
            st.info("💡 Haz doble clic sobre cualquier celda para corregir datos si es necesario antes de confirmar.")
            
            df_editado = st.data_editor(
                df_base,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "num_factura": st.column_config.TextColumn("N° Factura", required=True),
                    "cliente": st.column_config.TextColumn("Cliente / Empresa", required=True),
                    "fecha": st.column_config.TextColumn("Fecha"),
                    "pais": st.column_config.SelectboxColumn("País", options=["El Salvador", "Guatemala", "Honduras", "Nicaragua", "Costa Rica"]),
                    "moneda": st.column_config.SelectboxColumn("Moneda", options=["USD ($)", "GTQ (Q)", "HNL (L)"]),
                    "monto_neto": st.column_config.NumberColumn("Valor Neto", format="%.2f"),
                    "monto_iva": st.column_config.NumberColumn("Monto IVA/ISV", format="%.2f"),
                    "monto_total": st.column_config.NumberColumn("Monto Total", format="%.2f", required=True)
                },
                hide_index=True,
                key="editor_datos_facturas"
            )
            
            if st.button("✅ OK / Confirmar y Registrar Facturas en el Sistema", type="primary"):
                exitosos, errores = db.registrar_ventas_masivas(df_editado)
                
                msg_final = ""
                if exitosos > 0:
                    msg_final += f"🎉 ¡Éxito! Se registraron **{exitosos}** facturas en la base de datos."
                if errores:
                    msg_final += f"\n\n⚠️ Detalles u omisiones ({len(errores)}):\n" + "\n".join([f"- {e}" for e in errores])
                    st.session_state.mensaje_error = msg_final
                else:
                    st.session_state.mensaje_exito = msg_final
                    
                st.rerun()

# 4. REGISTRAR ABONO
with tab4:
    st.subheader("Aplicar Abono a Factura")
    ventas_pendientes = df_ventas[df_ventas['saldo_pendiente'] > 0]
    
    if ventas_pendientes.empty:
        st.info("No hay facturas pendientes de cobro para el país y moneda seleccionados.")
    else:
        opciones_factura = {
            row['id']: f"[{row['pais']} - {row['moneda']}] {row['num_factura']} - {row['cliente']} (Saldo: {row['saldo_pendiente']:,.2f})"
            for _, row in ventas_pendientes.iterrows()
        }
        
        with st.form("form_abono", clear_on_submit=True):
            venta_id_sel = st.selectbox(
                "Selecciona la Factura *",
                options=list(opciones_factura.keys()),
                format_func=lambda x: opciones_factura[x]
            )
            
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                monto_abono = st.number_input("Monto del Abono *", min_value=0.01, step=5.0, format="%.2f")
                fecha_abono = st.date_input("Fecha de Cobro", value=date.today())
            with col_a2:
                metodo_pago = st.selectbox("Método de Pago", ["Transferencia Bancaria", "Cheque", "Efectivo", "Tarjeta"])
                referencia = st.text_input("N° de Referencia / Comprobante")

            submitted_abono = st.form_submit_button("Registrar Abono")
            if submitted_abono:
                if monto_abono <= 0:
                    st.error("El monto debe ser mayor a 0.")
                else:
                    exito, msj = db.registrar_abono(venta_id_sel, fecha_abono, monto_abono, metodo_pago, referencia)
                    if exito:
                        st.session_state.mensaje_exito = msj
                        st.rerun()
                    else:
                        st.error(msj)

# 5. EXPORTACIÓN A EXCEL
with tab5:
    st.subheader("Exportar Reportes Consolidados")
    st.write("Genera un reporte completo en Excel (`.xlsx`) filtrado por tus parámetros regionales actualizados.")
    
    if st.button("📊 Generar Reporte Excel"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_ventas.to_excel(writer, sheet_name='Ventas_Facturas', index=False)
            df_abonos.to_excel(writer, sheet_name='Historial_Abonos', index=False)
            
        st.download_button(
            label="💾 Descargar Archivo Excel",
            data=buffer.getvalue(),
            file_name=f"Reporte_Ventas_{pais_seleccionado}_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
