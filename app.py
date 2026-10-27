import streamlit as st
import pandas as pd
import io
from datetime import date
import database as db

st.set_page_config(
    page_title="Control de Ventas y Cobranzas",
    page_icon="📊",
    layout="wide"
)

# Inicializar Base de Datos
db.init_db()

st.title("📊 Control de Ventas y Cuentas por Cobrar")
st.caption("Sistema de gestión de facturación, abonos y control de saldos")

# Cargar datos
df_ventas = db.obtener_ventas()
df_abonos = db.obtener_abonos()

# --- MÉTRICAS GENERALES (KPIs) ---
if not df_ventas.empty:
    total_facturado = df_ventas['monto_total'].sum()
    total_pendiente = df_ventas['saldo_pendiente'].sum()
    total_cobrado = total_facturado - total_pendiente
    pct_recuperacion = (total_cobrado / total_facturado * 100) if total_facturado > 0 else 0
else:
    total_facturado = total_cobrado = total_pendiente = pct_recuperacion = 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Facturado", f"${total_facturado:,.2f}")
col2.metric("Total Cobrado", f"${total_cobrado:,.2f}")
col3.metric("Saldo Pendiente", f"${total_pendiente:,.2f}", delta_color="inverse")
col4.metric("% Recuperación", f"{pct_recuperacion:.1f}%")

st.divider()

# --- NAVEGACIÓN POR PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Resumen de Ventas", 
    "➕ Nueva Venta", 
    "💵 Registrar Abono", 
    "📥 Exportación Excel"
])

# 1. TABLA PRINCIPAL DE VENTAS
with tab1:
    st.subheader("Listado de Facturas")
    
    col_filtro1, col_filtro2 = st.columns(2)
    with col_filtro1:
        filtro_estado = st.multiselect(
            "Filtrar por Estado",
            options=["Pendiente", "Parcial", "Pagado"],
            default=["Pendiente", "Parcial"]
        )
    with col_filtro2:
        busqueda_cliente = st.text_input("Buscar por Cliente o N° Factura")

    # Filtrado
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
            "cliente": "Cliente",
            "fecha": "Fecha",
            "monto_total": st.column_config.NumberColumn("Monto Total", format="$%.2f"),
            "saldo_pendiente": st.column_config.NumberColumn("Saldo Pendiente", format="$%.2f"),
            "estado": "Estado"
        },
        hide_index=True
    )

# 2. NUEVA VENTA
with tab2:
    st.subheader("Registrar Nueva Venta / Factura")
    with st.form("form_nueva_venta", clear_on_submit=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            num_factura = st.text_input("Número de Factura / QCF / DTE *")
            cliente = st.text_input("Nombre del Cliente / Empresa *")
        with col_f2:
            fecha_venta = st.date_input("Fecha de Emisión", value=date.today())
            monto_total = st.number_input("Monto Total ($) *", min_value=0.01, step=10.0, format="%.2f")

        submitted_venta = st.form_submit_button("Guardar Factura")
        if submitted_venta:
            if not num_factura or not cliente or monto_total <= 0:
                st.error("Por favor completa los campos obligatorios.")
            else:
                exito, msj = db.registrar_venta(num_factura, cliente, fecha_venta, monto_total)
                if exito:
                    st.success(msj)
                    st.rerun()
                else:
                    st.error(msj)

# 3. REGISTRAR ABONO
with tab3:
    st.subheader("Aplicar Abono a Factura")
    ventas_pendientes = df_ventas[df_ventas['saldo_pendiente'] > 0]
    
    if ventas_pendientes.empty:
        st.info("No hay facturas pendientes de cobro.")
    else:
        opciones_factura = {
            row['id']: f"{row['num_factura']} - {row['cliente']} (Saldo: ${row['saldo_pendiente']:,.2f})"
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
                monto_abono = st.number_input("Monto del Abono ($) *", min_value=0.01, step=5.0, format="%.2f")
                fecha_abono = st.date_input("Fecha de Cobro", value=date.today())
            with col_a2:
                metodo_pago = st.selectbox("Método de Pago", ["Transferencia Buro/Bancaria", "Cheque", "Efectivo", "Tarjeta"])
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

# 4. EXPORTACIÓN A EXCEL (.XLSX)
with tab4:
    st.subheader("Exportar Reportes a Excel")
    st.write("Genera un libro de trabajo en formato `.xlsx` con hojas separadas para el resumen de facturas y la bitácora de abonos.")
    
    if st.button("📊 Generar Reporte Excel"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df_ventas.to_excel(writer, sheet_name='Ventas_Facturas', index=False)
            df_abonos.to_excel(writer, sheet_name='Historial_Abonos', index=False)
            
        st.download_button(
            label="💾 Descargar Archivo Excel",
            data=buffer.getvalue(),
            file_name=f"Reporte_Ventas_Cobros_{date.today()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )