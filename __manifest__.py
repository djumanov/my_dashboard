{
    'name': 'L1 Dashboard',
    'version': '1.0',
    'summary': 'Advanced L1 Dashboard',
    'description': """
        Comprehensive L1 Dashboard
        ==========================
        * Sales and Cash Flow tracking
        * Financial KPIs visualization
        * Employee statistics
        * Advanced filtering capabilities
    """,
    'author': 'Odoo team',
    'website': '',
    'category': 'Productivity',
    'depends': [
        'base',
        'sale_management',
        'account',
        'hr',
        'web',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/dashboard.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            "https://cdnjs.cloudflare.com/ajax/libs/highcharts/12.1.2/highcharts.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/highcharts/12.1.2/highcharts-3d.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/highcharts/12.1.2/css/highcharts.min.css",
            'my_dashboard/static/src/*.js',
            'my_dashboard/static/src/*.scss',
            'my_dashboard/static/src/*.xml',
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}