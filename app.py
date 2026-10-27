import streamlit as st
import pandas as pd
import io
import importlib
from datetime import date
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

import database as db
import pdf_extractor

# Recargar pdf_extractor para actualización en caliente
importlib.reload(pdf_extractor)

st.set_page_config(
    page_title="Control de Ventas y Cobranzas - Centroamérica",
    page_icon="🌎",
    layout="wide"
)

# Inicializar Base de Datos
db.init_db()

# Session State para Notificaciones
if "mensaje_exito" not in st.session_state:
    st.session_state.mensaje_exito = None
if "mensaje_error" not in st.session_state:
    st.session_state.mensaje_error = None

def generar_excel_profesional(df_ventas, df_abonos, pais_sel, moneda_sel):
    wb = openpyxl.Workbook()
    
    # Estilos Corporativos
    font_titulo = Font(name="Calibri", size=16, bold=True, color="1F4E78")
    font_subtitulo = Font(name="Calibri", size=11, italic=True, color="595959")
    font_header = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    font_data = Font(name="Calibri", size=10)
    font_total = Font(name="Calibri", size=11, bold=True, color="1F4E78")
    
    fill_header = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    fill_zebra = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    fill_total = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
    
    thin_border = Side(style='thin', color='D9D9D9')
    thick_top = Side(style='thin', color='1F4E78')
    double_bottom = Side(style='double', color='1F4E78')
    
    border_cell = Border(left=thin_border, right=thin_border, top=thin_border, bottom=thin_border)
    border_total = Border(top=thick_top, bottom=double_bottom, left=thin_border, right=thin_border)

    # ----------------------------------------------------
    # 1. PESTAÑA: RESUMEN DE VENTAS Y COBRANZAS
    # ----------------------------------------------------
    ws_ventas = wb.active
    ws_ventas.title = "Resumen de Ventas"
    ws_ventas.views.sheetView[0].showGridLines = True
    
    # Bloque de Encabezado Institucional
    ws_ventas["A1"] = "TRANSPORTES CALPI, S.A. DE C.V."
    ws_ventas["A1"].font = font_titulo
    ws_ventas["A2"] = f"Resumen de Ventas y Cobranzas del Mes a la Fecha ({date.today().strftime('%d/%m/%Y')})"
    ws_ventas["A2"].font = font_subtitulo
    ws_ventas["A3"] = f"Filtros Aplicados: País = {pais_sel} | Moneda = {moneda_sel}"
    ws_ventas["A3"].font = font_subtitulo

    headers_v = ["ID", "N° Factura", "Cliente / Empresa", "Fecha Emisión", "País", "Moneda Local", "Valor Neto", "Monto IVA/ISV", "Total Facturado", "Saldo Pendiente", "Estado"]
    start_row = 5
    
    for col_num, header_title in enumerate(headers_v, 1):
        cell = ws_ventas.cell(row=start_row, column=col_num, value=header_title)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    numeric_cols_v = [7, 8, 9, 10]
    current_row = start_row + 1
    
    for idx, row in df_ventas.iterrows():
        ws_ventas.cell(row=current_row, column=1, value=row.get("id", ""))
        ws_ventas.cell(row=current_row, column=2, value=str(row.get("num_factura", "")))
        ws_ventas.cell(row=current_row, column=3, value=str(row.get("cliente", "")))
        ws_ventas.cell(row=current_row, column=4, value=str(row.get("fecha", "")))
        ws_ventas.cell(row=current_row, column=5, value=str(row.get("pais", "")))
        ws_ventas.cell(row=current_row, column=6, value=str(row.get("moneda", "")))
        ws_ventas.cell(row=current_row, column=7, value=float(row.get("monto_neto", 0.0)))
        ws_ventas.cell(row=current_row, column=8, value=float(row.get("monto_iva", 0.0)))
        ws_ventas.cell(row=current_row, column=9, value=float(row.get("monto_total", 0.0)))
        ws_ventas.cell(row=current_row, column=10, value=float(row.get("saldo_pendiente", 0.0)))
        ws_ventas.cell(row=current_row, column=11, value=str(row.get("estado", "")))
        
        for col_num in range(1, 12):
            c = ws_ventas.cell(row=current_row, column=col_num)
            c.font = font_data
            c.border = border_cell
            if idx % 2 == 1:
                c.fill = fill_zebra
            
            if col_num in numeric_cols_v:
                c.number_format = '#,##0.00;(#,##0.00);"-"'
                c.alignment = Alignment(horizontal="right")
            elif col_num in [1, 4, 5, 6, 11]:
                c.alignment = Alignment(horizontal="center")
            else:
                c.alignment = Alignment(horizontal="left")
                
        current_row += 1

    # Fila de Totales Generales con Fórmulas Excel
    if not df_ventas.empty:
        ws_ventas.cell(row=current_row, column=3, value="TOTALES GENERALES").font = font_total
        ws_ventas.cell(row=current_row, column=3).alignment = Alignment(horizontal="right")
        
        for col_num, col_letter in [(7, 'G'), (8, 'H'), (9, 'I'), (10, 'J')]:
            cell_tot = ws_ventas.cell(row=current_row, column=col_num)
            cell_tot.value = f"=SUM({col_letter}{start_row + 1}:{col_letter}{current_row - 1})"
            cell_tot.font = font_total
            cell_tot.number_format = '#,##0.00;(#,##0.00);"-"'
            cell_tot.alignment = Alignment(horizontal="right")

        for col_num in range(1, 12):
            c = ws_ventas.cell(row=current_row, column=col_num)
            c.fill = fill_total
            c.border = border_total

    for col in ws_ventas.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_ventas.column_dimensions[col_letter].width = max(max_len + 4, 12)

    # ----------------------------------------------------
    # 2. PESTAÑA: HISTORIAL DE ABONOS Y COBRANZAS
    # ----------------------------------------------------
    ws_abonos = wb.create_sheet(title="Historial de Abonos")
    ws_abonos.views.sheetView[0].showGridLines = True

    ws_abonos["A1"] = "TRANSPORTES CALPI, S.A. DE C.V."
    ws_abonos["A1"].font = font_titulo
    ws_abonos["A2"] = f"Historial de Abonos y Cobranzas Recibidas del Mes a la Fecha ({date.today().strftime('%d/%m/%Y')})"
    ws_abonos["A2"].font = font_subtitulo

    headers_a = ["ID Abono", "ID Venta", "Fecha de Cobro", "Monto Cobrado", "Método de Pago", "Referencia / Comprobante"]
    
    for col_num, header_title in enumerate(headers_a, 1):
        cell = ws_abonos.cell(row=start_row, column=col_num, value=header_title)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    current_row = start_row + 1
    for idx, row in df_abonos.iterrows():
        ws_abonos.cell(row=current_row, column=1, value=row.get("id", ""))
        ws_abonos.cell(row=current_row, column=2, value=row.get("venta_id", ""))
        ws_abonos.cell(row=current_row, column=3, value=str(row.get("fecha", "")))
        ws_abonos.cell(row=current_row, column=4, value=float(row.get("monto", 0.0)))
        ws_abonos.cell(row=current_row, column=5, value=str(row.get("metodo_pago", "")))
        ws_abonos.cell(row=current_row, column=6, value=str(row.get("referencia", "")))

        for col_num in range(1, 7):
            c = ws_abonos.cell(row=current_row, column=col_num)
            c.font = font_data
            c.border = border_cell
            if idx % 2 == 1:
                c.fill = fill_zebra
            
            if col_num == 4:
                c.number_format = '#,##0.00;(#,##0.00);"-"'
                c.alignment = Alignment(horizontal="right")
            elif col_num in [1, 2, 3]:
                c.alignment = Alignment(horizontal="center")
            else:
                c.alignment = Alignment(horizontal="left")
        current_row += 1

    if not df_abonos.empty:
        ws_abonos.cell(row=current_row, column=3, value="TOTAL ABONOS").font = font_total
        ws_abonos.cell(row=current_row, column=3).alignment = Alignment(horizontal="right")
        
        cell_tot_a = ws_abonos.cell(row=current_row, column=4)
        cell_tot_a.value = f"=SUM(D{start_row + 1}:D{current_row - 1})"
        cell_tot_a.font = font_total
        cell_tot_a.number_format = '#,##0.00;(#,##0.00);"-"'
        cell_tot_a.alignment = Alignment(horizontal="right")

        for col_num in range(1, 7):
            c = ws_abonos.cell(row=current_row, column=col_num)
            c.fill = fill_total
            c.border = border_total

    for col in ws_abonos.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws_abonos.column_dimensions[col_letter].width = max(max_len + 4, 14)

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()

st.title("🌎 Control de Ventas y Cuentas por Cobrar (Multipaís)")
st.caption("Gestión regional con desglose automático de IVA/ISV, múltiples monedas y carga masiva")

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
st.sidebar.markdown("- 🇸🇻 El Salvador: 13% IVA (USD $)")
st.sidebar.markdown("- 🇬🇹 Guatemala: 12% IVA (GTQ Q / USD $)")
st.sidebar.markdown("- 🇭🇳 Honduras: 15% ISV (HNL L.)")
st.sidebar.markdown("- 🇳🇮 Nicaragua: 15% IVA (USD $)")
st.sidebar.markdown("- 🇨🇷 Costa Rica: 13% IVA (USD $)")

# Cargar datos filtrados desde SQLite
df_ventas = db.obtener_ventas(pais=pais_seleccionado, moneda=moneda_seleccionada)
df_abonos = db.obtener_abonos()

SIMBOLOS_MONEDA = {
    "USD ($)": "$",
    "GTQ (Q)": "Q",
    "HNL (L)": "L."
}

BANDERAS_PAIS = {
    "El Salvador": "🇸🇻",
    "Guatemala": "🇬🇹",
    "Honduras": "🇭🇳",
    "Nicaragua": "🇳🇮",
    "Costa Rica": "🇨🇷"
}

def get_simbolo(moneda):
    return SIMBOLOS_MONEDA.get(moneda, "$")

# --- DASHBOARD DE MÉTRICAS ---
st.subheader("📊 Resumen General del Dashboard")

if df_ventas.empty:
    st.info("No hay facturas registradas para los filtros seleccionados.")
else:
    monedas_presentes = df_ventas['moneda'].unique()
    paises_presentes = df_ventas['pais'].unique()

    if len(monedas_presentes) == 1 and (pais_seleccionado != "Todos" or len(paises_presentes) == 1):
        moneda_actual = monedas_presentes[0]
        simbolo = get_simbolo(moneda_actual)
        pais_actual = paises_presentes[0] if len(paises_presentes) == 1 else pais_seleccionado
        bandera = BANDERAS_PAIS.get(pais_actual, "🌎")
        
        total_neto = df_ventas['monto_neto'].sum()
        total_iva = df_ventas['monto_iva'].sum()
        total_facturado = df_ventas['monto_total'].sum()
        total_pendiente = df_ventas['saldo_pendiente'].sum()
        total_cobrado = total_facturado - total_pendiente
        pct_recuperacion = (total_cobrado / total_facturado * 100) if total_facturado > 0 else 0.0

        st.markdown(f"##### {bandera} **{pais_actual}** — Moneda Local: **{moneda_actual}**")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Monto Neto", f"{simbolo} {total_neto:,.2f}")
        col2.metric("Total IVA / ISV", f"{simbolo} {total_iva:,.2f}")
        col3.metric("Total Facturado", f"{simbolo} {total_facturado:,.2f}")
        col4.metric("Saldo Pendiente", f"{simbolo} {total_pendiente:,.2f}", delta_color="inverse")
        col5.metric("% Recuperación", f"{pct_recuperacion:.1f}%")

    else:
        st.info("📌 *Cifras agrupadas por país y moneda local para garantizar precisión financiera sin mezclar divisas.*")
        
        df_resumen = df_ventas.groupby(["pais", "moneda"]).agg(
            facturas=("id", "count"),
            monto_neto=("monto_neto", "sum"),
            monto_iva=("monto_iva", "sum"),
            monto_total=("monto_total", "sum"),
            saldo_pendiente=("saldo_pendiente", "sum")
        ).reset_index()

        df_resumen["cobrado"] = df_resumen["monto_total"] - df_resumen["saldo_pendiente"]
        df_resumen["pct_recuperacion"] = df_resumen.apply(
            lambda r: (r["cobrado"] / r["monto_total"] * 100) if r["monto_total"] > 0 else 0.0, axis=1
        )

        for _, row in df_resumen.iterrows():
            p_nom = row["pais"]
            m_nom = row["moneda"]
            bandera = BANDERAS_PAIS.get(p_nom, "🌎")
            simb = get_simbolo(m_nom)

            st.markdown(f"##### {bandera} **{p_nom}** — Divisa: **{m_nom}** ({row['facturas']} factura{'s' if row['facturas'] > 1 else ''})")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Monto Neto", f"{simb} {row['monto_neto']:,.2f}")
            c2.metric("IVA / ISV", f"{simb} {row['monto_iva']:,.2f}")
            c3.metric("Total Facturado", f"{simb} {row['monto_total']:,.2f}")
            c4.metric("Saldo Pendiente", f"{simb} {row['saldo_pendiente']:,.2f}", delta_color="inverse")
            c5.metric("% Recuperación", f"{row['pct_recuperacion']:.1f}%")
            st.write("")

        with st.expander("📋 Ver Cuadro Resumen Consolidado por País y Moneda Local", expanded=False):
            st.dataframe(
                df_resumen,
                use_container_width=True,
                column_config={
                    "pais": "País",
                    "moneda": "Moneda Local",
                    "facturas": "N° Facturas",
                    "monto_neto": st.column_config.NumberColumn("Neto Acumulado", format="%.2f"),
                    "monto_iva": st.column_config.NumberColumn("IVA/ISV Acumulado", format="%.2f"),
                    "monto_total": st.column_config.NumberColumn("Total Facturado", format="%.2f"),
                    "saldo_pendiente": st.column_config.NumberColumn("Saldo Pendiente", format="%.2f"),
                    "cobrado": st.column_config.NumberColumn("Total Cobrado", format="%.2f"),
                    "pct_recuperacion": st.column_config.NumberColumn("% Recuperación", format="%.1f%%")
                },
                hide_index=True
            )

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
            "moneda": "Moneda Local",
            "monto_neto": st.column_config.NumberColumn("Valor Neto", format="%.2f"),
            "monto_iva": st.column_config.NumberColumn("Monto IVA/ISV", format="%.2f"),
            "monto_total": st.column_config.NumberColumn("Total Facturado", format="%.2f"),
            "saldo_pendiente": st.column_config.NumberColumn("Saldo Pendiente", format="%.2f"),
            "estado": "Estado"
        },
        hide_index=True
    )
    
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
                st.warning("⚠️ **Atención:** Al eliminar esta factura, también se eliminarán todos sus abonos de forma permanente.")
                
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
            monto_total = st.number_input("Monto Total Incorporado con IVA/ISV *", min_value=0.01, step=10.0, format="%.2f")

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
            row['id']: f"[{row['pais']} - {row['moneda']}] {row['num_factura']} - {row['cliente']} (Saldo: {row['moneda']} {row['saldo_pendiente']:,.2f})"
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

# 5. EXPORTACIÓN A EXCEL PROFESIONAL
with tab5:
    st.subheader("Exportar Reportes Consolidados")
    st.write("Genera y descarga un reporte profesional en Excel (`.xlsx`) estilizado con encabezados institucionales, sumatorias automáticas y formato de número contable.")
    
    excel_bytes = generar_excel_profesional(df_ventas, df_abonos, pais_seleccionado, moneda_seleccionada)
    
    st.download_button(
        label="📊 Descargar Reporte Excel Profesional (.xlsx)",
        data=excel_bytes,
        file_name=f"Reporte_Ventas_Cobranzas_{pais_seleccionado}_{date.today().strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary"
    )
