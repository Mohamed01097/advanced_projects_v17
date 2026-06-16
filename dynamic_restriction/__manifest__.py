# -*- coding: utf-8 -*-
{
    'name': 'Dynamic Access Manager',
    'summary': 'Advanced dynamic security, approval, audit, ownership, and access control for Odoo models.',
    'description': """
Dynamic Access Manager is a security and access control framework for Odoo.

Administrators can configure advanced restrictions directly from the user interface without creating custom record rules, access rights, Python code, or model-specific security customizations.

Key capabilities include:
- Dynamic action restrictions for create, edit, delete, duplicate, export, import, archive, and unarchive.
- User, group, company, domain, ownership, time, and IP based restrictions.
- Own Documents Only mode using configurable owner fields.
- UI action hiding while keeping backend validation as the source of truth.
- Readonly field protection.
- Approval workflows for sensitive actions.
- Audit logs for blocked operations.
- Mass action, import, and export protection.
- Restriction templates for fast deployment.

Compatible with Odoo 17, Odoo 18, and Odoo 19.
    """,
    'author': 'DevOdooX',
    'support': 'devodoox06@gmail.com',
    'license': 'OPL-1',
    'category': 'Security',
    'version': '17.0.1.0.0',
    'price': '50.0',
    'currency': 'USD',
    'depends': ['base', 'web'],
    'images': [
        'static/description/banner.png',
        'static/description/overview.png',
        'static/description/features.png',
        'static/description/support.png',
        'static/description/footer.png',
        'static/description/screenshots/screen_01.png',
        'static/description/screenshots/screen_02.png',
        'static/description/screenshots/screen_03.png',
        'static/description/screenshots/screen_04.png',
        'static/description/screenshots/screen_05.png',
        'static/description/screenshots/screen_06.png',
        'static/description/screenshots/screen_07.png',
        'static/description/screenshots/screen_08.png',
        'static/description/demo.gif',
    ],
    'data': [
        'security/ir.model.access.csv',
        'security/dynamic_restriction_security.xml',
        'data/restriction_support_data.xml',
        'data/default_template_data.xml',
        'views/views.xml',
        'views/templates.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'dynamic_restriction/static/src/js/ui_restriction.js',
        ],
    },
    'demo': [
        'demo/demo.xml',
    ],
}
