{
    "name": "OCA Helpdesk Reports",
    "version": "18.0.1.0.0",
    "summary": "Reporte mensual PDF para helpdesk_mgmt",
    "author": "Kevin",
    "depends": ["helpdesk_mgmt", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/report_monthly_views.xml",
        "reports/report_monthly_pdf.xml",
        "views/menu_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
