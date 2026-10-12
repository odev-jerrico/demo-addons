# -*- coding: utf-8 -*-
{
    'name': 'FDA Product Accreditation & Permit Management',
    'version': '19.0.1.0',
    'depends': [
        'base',
        'mail',
        'product',
        'stock',
        'account',
        'sale_management',
    ],
    'category': 'Inventory/Traceability',
    'author': 'Odev Solutions',
    'website': 'https://www.odevsolutions.com',
    'summary': 'Track product permits, accreditation, registration dates, and expiry alerts.',
    'description': """
FDA Product Accreditation and Permit Management System

- Manage and track accreditation and permit lots across products
- Early warning alerts for near-expiry permits
- Expose permit registration and expiry dates on products for logistics and sales
- Highlight expired permits in red for faster action
    """,
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/ir_cron_data.xml',
        'views/product_permit_views.xml',
        'views/product_views.xml',
        'views/stock_lot_views.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
}
