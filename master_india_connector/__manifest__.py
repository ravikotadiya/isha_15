{
    'name': 'Master India Connector',
    'version': '15.0',
    'category': 'API',
    'author': '',
    'website': '',
    'maintainer': '',
    'depends': ['base', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/master_india_instance_view.xml',
        'wizard/upload_file_wizard_view.xml',
        'views/master_india_log_view.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
    'images': ['static/description/main_screen.jpeg'],
    'license': 'LGPL-3',
}
