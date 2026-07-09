import base64
from pathlib import Path

LOGO_PATH = Path(__file__).parent / 'logos' / 'Punto-Singular-WEB.png'

PRIMARY_COLOR = '#122A59'
SECONDARY_COLOR = '#3B8EDE'


def post_init_hook(env):
    logo_b64 = base64.b64encode(LOGO_PATH.read_bytes())
    report_layout = env.ref('web.external_layout_standard', raise_if_not_found=False)
    companies = env['res.company'].search([])
    companies.write({
        'logo': logo_b64,
        'primary_color': PRIMARY_COLOR,
        'secondary_color': SECONDARY_COLOR,
        **({'external_report_layout_id': report_layout.id} if report_layout else {}),
    })
