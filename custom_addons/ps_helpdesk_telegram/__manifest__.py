{
    "name": "PS Helpdesk Telegram",
    "summary": "Notificaciones de tickets Helpdesk sin tecnico por Telegram",
    "version": "18.0.1.0.0",
    "author": "Punto Singular",
    "license": "LGPL-3",
    "category": "Helpdesk",
    "depends": ["helpdesk_mgmt"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron.xml",
        "views/helpdesk_ticket_team_views.xml",
    ],
    "installable": True,
    "application": False,
}
