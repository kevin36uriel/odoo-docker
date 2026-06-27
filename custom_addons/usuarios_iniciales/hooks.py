def post_init_hook(env):
    lang = env['res.lang'].with_context(active_test=False).search([('code', '=', 'es_MX')], limit=1)
    if lang:
        wizard = env['base.language.install'].create({
            'lang_ids': [(4, lang.id)],
            'overwrite': False,
        })
        wizard.lang_install()

    env['res.users'].search([]).write({'lang': 'es_MX'})
    env.ref('base.main_partner').write({'lang': 'es_MX'})
