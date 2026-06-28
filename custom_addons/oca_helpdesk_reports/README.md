# OCA Helpdesk Reports — Documentación técnica

**Módulo:** `oca_helpdesk_reports`  
**Versión:** 18.0.1.0.0  
**Depende de:** `helpdesk_mgmt`, `web`

---

## ¿Qué hace este módulo?

Agrega 4 reportes exportables al módulo de Helpdesk (OCA `helpdesk_mgmt`), accesibles desde el menú **Helpdesk → Reporting**. Cada reporte abre un formulario de filtros (wizard), el usuario hace clic en "Generar reporte" y la tabla de resultados aparece en el mismo diálogo. Desde ahí puede exportar a **Excel (.xlsx)** o **PDF (QWeb)**.

---

## Reportes disponibles

### 1. Reporte Mensual (`Mensual`)

Agrupa tickets por mes, equipo, agente, etapa y prioridad.

**Filtros:**
- Fecha desde / hasta (default: primer día del mes actual → hoy)
- Equipo (opcional)
- Agente (opcional)

**Columnas resultado:**
| Campo | Descripción |
|-------|-------------|
| Mes | Formato `YYYY-MM` |
| Equipo | Nombre del equipo |
| Agente | Usuario asignado |
| Etapa | Etapa del ticket |
| Prioridad | Baja / Media / Alta / Muy Alta |
| Total tickets | Count del grupo |
| Resueltos | Tickets con etapa `closed = True` |
| Pendientes | Tickets con etapa `closed = False` |
| Tiempo prom. resolución (hrs) | Promedio de `closed_date - assigned_date` en horas |

**Exporta a:** Excel + PDF

---

### 2. Reporte por Agente (`Por agente`)

Agrupa tickets por usuario asignado y equipo, calculando métricas de rendimiento.

**Filtros:**
- Fecha desde / hasta
- Equipo (opcional)
- Días para vencido (default: 7) — tickets abiertos más de N días se cuentan como "vencidos"

**Columnas resultado:**
| Campo | Descripción |
|-------|-------------|
| Agente | Usuario asignado |
| Equipo | Equipo del ticket |
| Total asignados | Total tickets en el período |
| Resueltos | Tickets cerrados |
| Pendientes | Tickets abiertos |
| Vencidos | Tickets abiertos hace más de N días |
| Tiempo prom. (hrs) | Promedio de resolución |
| % Resolución | `resueltos / total * 100` |

**Exporta a:** Excel

---

### 3. Reporte por Etapa (`Por etapa`)

Snapshot actual de distribución de tickets en el pipeline.

**Filtros:**
- Equipo (opcional, sin filtro de fechas — muestra estado actual)

**Columnas resultado:**
| Campo | Descripción |
|-------|-------------|
| Etapa | Nombre de la etapa |
| Total tickets | Tickets actualmente en esa etapa |
| % del total | Proporción sobre el total |
| Tiempo prom. en etapa (días) | Promedio de `(now - last_stage_update).days` |

**Exporta a:** Excel

---

### 4. Tickets Sin Resolver (`Sin resolver`)

Lista individual de tickets que llevan demasiado tiempo abiertos.

**Filtros:**
- Días sin resolver / umbral (default: 7)
- Equipo (opcional)
- Agente (opcional)

**Un ticket aparece si:** `stage_id.closed = False` AND `create_date ≤ (now - N días)`

**Columnas resultado:**
| Campo | Descripción |
|-------|-------------|
| N° Ticket | Número secuencial |
| Asunto | Título del ticket |
| Cliente | `partner_id.name` |
| Agente | Usuario asignado |
| Equipo | Equipo del ticket |
| Fecha creación | `create_date` |
| Días sin resolver | `(now - create_date).days` |
| Etapa actual | Etapa del pipeline |

**Exporta a:** Excel + PDF

> **Nota:** El OCA `helpdesk_mgmt` v18 no tiene campo `date_deadline`. Por eso "vencido" se define como tiempo desde creación, no desde una fecha límite.

---

## Estructura de archivos

```
oca_helpdesk_reports/
├── __init__.py                          # Importa models y wizards
├── __manifest__.py                      # Manifest del módulo
│
├── models/
│   ├── __init__.py
│   └── helpdesk_report.py               # TransientModels de resultados (líneas)
│
├── wizards/
│   ├── __init__.py
│   ├── report_monthly_wizard.py         # Wizard reporte mensual
│   ├── report_agent_wizard.py           # Wizard reporte por agente
│   ├── report_stage_wizard.py           # Wizard reporte por etapa
│   └── report_overdue_wizard.py         # Wizard tickets sin resolver
│
├── views/
│   ├── report_monthly_views.xml         # Form + acción wizard mensual
│   ├── report_agent_views.xml           # Form + acción wizard agente
│   ├── report_stage_views.xml           # Form + acción wizard etapa
│   ├── report_overdue_views.xml         # Form + acción wizard vencidos
│   └── menu_views.xml                   # Submenús bajo Reporting (al final del manifest)
│
├── reports/
│   ├── report_monthly_pdf.xml           # ir.actions.report + template QWeb mensual
│   └── report_overdue_pdf.xml           # ir.actions.report + template QWeb vencidos
│
└── security/
    └── ir.model.access.csv              # Acceso solo a group_helpdesk_manager
```

---

## Arquitectura: patrón Wizard + Líneas

Cada reporte usa este patrón:

```
[Wizard TransientModel]  ←──── one2many ────→  [Line TransientModel]
helpdesk.report.*.wizard                        helpdesk.report.*.line
  - campos de filtro                              - campos de datos/resultado
  - action_generate_report()                      - wizard_id (FK al wizard)
  - action_export_xlsx()
  - action_export_pdf()
```

**Flujo de ejecución:**

1. Usuario abre el menú → se crea un nuevo registro `wizard` vacío (TransientModel)
2. Usuario completa filtros y hace clic en "Generar reporte"
3. `action_generate_report()` ejecuta:
   - Borra líneas anteriores (`self.line_ids.unlink()`)
   - Busca tickets con el domain construido desde los filtros
   - Agrupa y calcula métricas en Python
   - Crea registros `line` vinculados al wizard
   - Pone `report_generated = True`
   - Retorna una acción que reabre el mismo wizard con los datos
4. El formulario muestra la tabla de líneas + totales
5. El usuario puede exportar o cerrar

**¿Por qué TransientModel y no un modelo permanente?**  
Los TransientModel son ideales para reportes: no acumulan datos históricos en la BD, Odoo los limpia automáticamente, y permiten que múltiples usuarios generen reportes simultáneamente sin interferencia (cada usuario tiene su propio `wizard_id`).

---

## Modelos de datos

### Modelos de línea (en `models/helpdesk_report.py`)

| Modelo | Descripción |
|--------|-------------|
| `helpdesk.report.monthly.line` | Líneas del reporte mensual |
| `helpdesk.report.agent.line` | Líneas del reporte por agente |
| `helpdesk.report.stage.line` | Líneas del reporte por etapa |
| `helpdesk.report.overdue.line` | Líneas del reporte de vencidos |

### Modelos de wizard (en `wizards/`)

| Modelo | Archivo |
|--------|---------|
| `helpdesk.report.monthly.wizard` | `report_monthly_wizard.py` |
| `helpdesk.report.agent.wizard` | `report_agent_wizard.py` |
| `helpdesk.report.stage.wizard` | `report_stage_wizard.py` |
| `helpdesk.report.overdue.wizard` | `report_overdue_wizard.py` |

---

## Campos clave de `helpdesk.ticket` usados

| Campo | Tipo | Uso en reportes |
|-------|------|-----------------|
| `create_date` | Datetime | Filtro de rango de fechas, cálculo de días abierto |
| `user_id` | Many2one (res.users) | Agrupación por agente |
| `team_id` | Many2one (helpdesk.ticket.team) | Filtro y agrupación por equipo |
| `stage_id` | Many2one (helpdesk.ticket.stage) | Agrupación por etapa |
| `stage_id.closed` | Boolean (related) | Determina si el ticket está resuelto |
| `priority` | Selection 0/1/2/3 | Baja/Media/Alta/Muy Alta |
| `assigned_date` | Datetime | Para calcular tiempo de resolución |
| `closed_date` | Datetime | Para calcular tiempo de resolución |
| `last_stage_update` | Datetime | Para calcular tiempo en etapa |
| `partner_id` | Many2one (res.partner) | Cliente en reporte de vencidos |
| `number` | Char | N° de ticket en reporte de vencidos |

> **Campos que NO existen en esta versión OCA:** `date_opened`, `date_deadline`. El prompt original los mencionaba pero no están en el modelo.

---

## Exportación Excel (xlsxwriter)

Formato del `.xlsx` generado:

- **Hoja 1 — Resumen:** título, período, totales generales
- **Hoja 2 — Detalle:** tabla completa con:
  - Encabezados con fondo `#4B5EA6` (azul) y texto blanco
  - Filas alternas con fondo `#F2F2F2`
  - Fila de totales al final con fondo gris `#D3D3D3`
  - Anchos de columna ajustados al contenido
  - Números con separador de miles
  - Fechas en formato `DD/MM/YYYY`

**Nombre del archivo:**
- Mensual: `reporte_helpdesk_mensual_YYYYMM.xlsx`
- Por agente: `reporte_helpdesk_agente_YYYYMM.xlsx`
- Por etapa: `reporte_helpdesk_etapa_YYYYMM.xlsx`
- Vencidos: `reporte_helpdesk_vencidos_YYYYMM.xlsx`

**Mecanismo de descarga:**  
El xlsx se escribe en memoria (`io.BytesIO`), se codifica en base64, se guarda como `ir.attachment` y se retorna una acción `ir.actions.act_url` apuntando a `/web/content/{id}?download=true`.

---

## Exportación PDF (QWeb)

Los reportes mensual y vencidos tienen PDF. Se define con `ir.actions.report` de tipo `qweb-pdf`.

**Template:** llama a `web.external_layout` (incluye logo y datos de empresa automáticamente) y dibuja una tabla HTML con CSS inline compatible con wkhtmltopdf.

**Orientación:** A4 horizontal via `@page { size: A4 landscape; }` en CSS (el paper format `base.paperformat_a4_landscape` no existe en Odoo 18 — solo existe `base.paperformat_euro`).

---

## Menú y acceso

Los 4 submenús se agregan bajo el menú **Reporting** existente de `helpdesk_mgmt`:

```
Helpdesk
└── Reporting
    ├── Tickets          (nativo OCA — vista pivot)
    ├── Mensual          ← nuevo
    ├── Por agente       ← nuevo
    ├── Por etapa        ← nuevo
    └── Sin resolver     ← nuevo
```

**Grupos de acceso:** solo `helpdesk_mgmt.group_helpdesk_manager` (Helpdesk Manager).

> **Importante para el manifest:** `menu_views.xml` debe cargarse **después** de todos los archivos de vistas que definen las acciones (`action_helpdesk_report_*`). Si se carga primero, Odoo lanza `ValueError: External ID not found`.

---

## Instalación

```bash
docker exec odoo_dev odoo -d odoo -i oca_helpdesk_reports --stop-after-init \
  --db_host=db --db_user=odoo --db_password=odoo
```

Para actualizar después de cambios:

```bash
docker exec odoo_dev odoo -d odoo -u oca_helpdesk_reports --stop-after-init \
  --db_host=db --db_user=odoo --db_password=odoo
```

---

## Límite de registros

Todos los reportes lanzan `UserError` si la consulta retorna más de **10,000 tickets**, para evitar timeouts. El mensaje le pide al usuario reducir el rango de fechas o aplicar más filtros.

---

## Gotchas y decisiones técnicas

| Situación | Decisión |
|-----------|----------|
| `date_deadline` no existe en el modelo | "Vencido" = abierto más de N días desde `create_date` |
| `base.paperformat_a4_landscape` no existe en Odoo 18 | Usar `base.paperformat_euro` + CSS `@page { size: A4 landscape; }` |
| `menu_views.xml` referencia acciones que aún no existen | Cargar `menu_views.xml` al final del array `data` en el manifest |
| `closed` es un campo related no stored | Usar `stage_id.closed` directamente en domains de búsqueda |
| Múltiples usuarios usando reportes simultáneamente | Cada wizard tiene su propio `id` — las líneas se vinculan por `wizard_id`, sin colisión |
