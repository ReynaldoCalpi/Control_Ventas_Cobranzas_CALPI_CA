import streamlit as st
import pandas as pd
import io
from datetime import date
import database as db

st.set_page_config(
    page_title="Control de Ventas y Cobranzas - Centroamérica",
    page_icon="🌎",
    layout="wide"
)

# Inicializar Base de Datos
db.init_db()

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

# Resumen de tasas de IVA regionales
st.sidebar.divider()
st.sidebar.markdown("**ℹ️ Tasas de IVA / ISV Aplicables:**")
st.sidebar.markdown("- 🇸🇻 El Salvador: 13% IVA (USD)")
st.sidebar.markdown("- 🇬🇹 Guatemala: 12% IVA (GTQ / USD)")
st.sidebar.markdown("- 🇭🇳 Honduras: 15% ISV (HNL)")
st.sidebar.markdown("- 🇳🇮 Nicaragua: 15% IVA (USD)")
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

# --- NAVEGACIÓN POR PESTAÑAS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📋 Resumen de Ventas", 
    "➕ Nueva Venta Individual", 
    "📂 Carga Masiva (Excel/CSV)",
    "💵 Registrar Abono", 
    "📥 Exportar Reportes"
])

# 1. TABLA PRINCIPAL DE VENTAS
with tab1:
    st.subheader(f"Listado de Facturas ({pais_seleccionado} / {moneda_seleccionada})")
    
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

# 2. NUEVA VENTA INDIVIDUAL
with tab2:
    st.subheader("Registrar Venta Individual")
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
        st.info(f"💡 Para **{pais_form}**, la tasa de impuesto aplicada es del **{int(tasa_iva_actual*100)}%**. El sistema desglosará automáticamente el Valor Neto y el IVA.")

        submitted_venta = st.form_submit_button("Guardar Factura")
        if submitted_venta:
            if not num_factura or not cliente or monto_total <= 0:
                st.error("Por favor completa los campos obligatorios.")
            else:
                exito, msj = db.registrar_venta(num_factura, cliente, fecha_venta, pais_form, moneda_form, monto_total)
                if exito:
                    st.success(msj)
                    st.rerun()
                else:
                    st.error(msj)

# 3. CARGA MASIVA DE FACTURAS
with tab3:
    st.subheader("📂 Carga Masiva de Facturas desde Archivo Local")
    st.write("Sube un archivo **Excel (.xlsx)** o **CSV (.csv)** con tus facturas. Podrás previsualizar los cálculos netos e IVA antes de confirmar el registro.")
    
    col_plantilla1, col_plantilla2 = st.columns([2, 1])
    with col_plantilla1:
        st.markdown("**Estructura de columnas requerida en el archivo:**")
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
    
    archivo_subido = st.file_uploader("Selecciona tu archivo de facturas", type=["xlsx", "csv"])
    
    if archivo_subido is not None:
        try:
            if archivo_subido.name.endswith('.csv'):
                df_cargado = pd.read_csv(archivo_subido)
            else:
                df_cargado = pd.read_excel(archivo_subido)
                
            columnas_requeridas = {'num_factura', 'cliente', 'fecha', 'pais', 'moneda', 'monto_total'}
            columnas_presentes = set(df_cargado.columns)
            
            if not columnas_requeridas.issubset(columnas_presentes):
                st.error(f"El archivo no contiene todas las columnas requeridas: {columnas_requeridas - columnas_presentes}")
            else:
                df_preview = df_cargado.copy()
                
                netos = []
                ivas = []
                for _, row in df_preview.iterrows():
                    pais_row = row['pais']
                    total_row = float(row['monto_total'])
                    neto_calc, iva_calc = db.calcular_desglose_iva(total_row, pais_row)
                    netos.append(neto_calc)
                    ivas.append(iva_calc)
                    
                df_preview['monto_neto'] = netos
                df_preview['monto_iva'] = ivas
                
                cols_orden = ['num_factura', 'cliente', 'fecha', 'pais', 'moneda', 'monto_neto', 'monto_iva', 'monto_total']
                df_preview = df_preview[cols_orden]
                
                st.subheader("👁️ Vista Previa del Archivo a Cargar")
                st.info(f"Se identificaron **{len(df_preview)}** registros. Revisa el desglose de Neto e IVA calculado.")
                
                st.dataframe(df_preview, use_container_width=True)
                
                if st.button("✅ OK / Confirmar y Registrar Facturas en el Sistema", type="primary"):
                    exitosos, errores = db.registrar_ventas_masivas(df_preview)
                    if exitosos > 0:
                        st.success(f"🎉 Se registraron exitosamente **{exitosos}** facturas.")
                    if errores:
                        st.warning(f"⚠️ Se encontraron {len(errores)} omisiones o duplicados:")
                        for err in errores:
                            st.write(f"- {err}")
                    st.rerun()
        except Exception as e:
            st.error(f"Ocurrió un error al procesar el archivo: {str(e)}")

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
                        st.success(msj)
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
