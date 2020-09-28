# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Bloopark Accounting Migration',
    'version': '1.0',
    'category': 'Tools',
    'summary': 'Blookpark Accounting Migration',
    'depends': ['web','product','account'],
    'data': [
        'views/account_view.xml',
        ],
    'demo': [
        ],
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
