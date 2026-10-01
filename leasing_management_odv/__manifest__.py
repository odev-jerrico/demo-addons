# -*- coding: utf-8 -*-
{
    'name': 'Leasing Management Prototype',
    'version': '19.0.1.0',
    'depends': [
        'base',
        'mail',
        'account',
        'portal',
        'website',
    ],
    'category': 'Sales/Leasing',
    'author': 'Odev Solutions',
    'website': 'https://www.odevsolutions.com',
    'summary': 'Mall leasing lifecycle, automated SOA, utility billing, and tenant maintenance portal',
    'description': """
        Prototype module for mall leasing operations:
        - Unit and tenant lifecycle management
        - Lease contracts and deposit tracking
        - Automated monthly SOA / billing
        - Utility consumption billing
        - Tenant maintenance portal requests
    """,
    'data': [
        'security/leasing_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'data/statement_of_account_server_action.xml',
        'views/leasing_unit_views.xml',
        'views/leasing_contract_views.xml',
        'views/leasing_utility_views.xml',
        'views/leasing_maintenance_request_views.xml',
        'wizard/statement_of_account_wizard_views.xml',
        'reports/statement_of_account_report.xml',
        'views/leasing_menu.xml',
        'views/portal_templates.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
}
