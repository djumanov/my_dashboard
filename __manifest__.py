{
    'name': 'DrukSmart Dashboard',
    'version': '1.0',
    'summary': 'Advanced DrukSmart Dashboard',
    'description': """
        Comprehensive L1, L2, L3, L4, L5 Dashboard
        =========================================
        * Sales, Revenue, Expenses, and Cash Flow tracking
        * Employee statistics
        * Advanced filtering capabilities
    """,
    'author': 'Odoo team',
    'website': '',
    'category': 'Productivity',
    'license': 'LGPL-3', 
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
        'views/hr_dashboard_menu.xml',
        'views/l2_dashboard.xml',
        'views/l3_dashboard.xml',
        'views/l4_dashboard.xml',
        'views/sale_target.xml',
        'views/reports.xml',
        'views/menu.xml',
    ],                            
    'images': ['static/description/icon.png'],
    'assets': {
        'web.assets_backend': [
            "https://cdnjs.cloudflare.com/ajax/libs/highcharts/12.1.2/highcharts.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/highcharts/12.1.2/highcharts-3d.min.js",
            "https://cdnjs.cloudflare.com/ajax/libs/highcharts/12.1.2/css/highcharts.min.css",
            'my_dashboard/static/src/js/*.js',
            'my_dashboard/static/src/scss/*.scss',
            'my_dashboard/static/src/xml/*.xml', 
        ],
    },
    'application': True,
    'installable': True,
    'auto_install': False,
}
