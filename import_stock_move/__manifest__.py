# -*- coding: utf-8 -*-
{
    'name': 'Import sale order(operations) from Excel or CSV File in odooV14',
    'version': '14.0.0.2',
    'summary': 'Import sale order(operations) Data App',
    'category': 'Inventory/Inventory',
    'description': """
    This module use for importImport sale order(operations) from Excel file.
    """,
    'depends': ['base', 'stock'],
    'data': [
                'security/ir.model.access.csv',
                'views/import_stock_move_view.xml',
                'data/attachment_sample.xml',
            ],
    'installable':True,
    'auto_install':False,
    'application':True,
    "images": ['static/description/Banner.png'],
}

