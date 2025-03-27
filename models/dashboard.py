import json
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import date_utils, float_round

_logger = logging.getLogger(__name__)

class L1Dashboard(models.Model):
    _name = 'l1.dashboard'
    _description = 'L1 Dashboard Data'

    name = fields.Char(string='Dashboard Name', default='L1 Dashboard')
    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
        ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
        ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ])
    quarter = fields.Selection(
        [('Q1', 'Quarter 1'), ('Q2', 'Quarter 2'), ('Q3', 'Quarter 3'), ('Q4', 'Quarter 4')]
    )
    
    dashboard_data = fields.Text(string='Dashboard Data', compute='_compute_dashboard_data')
    dashboard_data_array = fields.Text(string='D')
    last_update = fields.Datetime(string='Last Update')
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    
    def _get_year_selection(self):
        current_year = datetime.now().year
        return [(str(year), str(year)) for year in range(2023, current_year + 1)]

    year = fields.Selection(
        selection=lambda self: self._get_year_selection(),
        string='Year',
        default=lambda self: str(fields.Date.today().year)
    )

    @api.depends('year', 'month', 'company_id', "quarter")
    def _compute_dashboard_data(self):
        for record in self:
            record.dashboard_data = json.dumps(record._get_dashboard_data())
            record.last_update = fields.Datetime.now()

    @api.model
    def get_dashboard_data_json(self, year=None, month=None, quarter=None):
        """API method to get dashboard data in JSON format"""
        if not year:
            year = fields.Date.today().year
            
        dashboard = self.search([
            ('year', '=', year),
            ('month', '=', month),
            ('quarter', '=', quarter),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not dashboard:
            dashboard = self.create({
                'year': year,
                'month': month,
                'quarter': quarter,
            })
        
        dashboard._compute_dashboard_data()
        return dashboard.dashboard_data

    def _get_dashboard_data(self):
        """Compute all dashboard data and return as a structured dictionary"""
        self.ensure_one()
        
        month = int(self.month) if self.month else 0
        year = int(self.year) if self.year else datetime.now().year
        quarter = self.quarter
        
        if quarter == 'Q1':
            start_date = fields.Date.to_string(datetime(year, 1, 1))
            end_date = fields.Date.to_string(datetime(year, 3, 31))
            self.month = None
        elif quarter == 'Q2':
            start_date = fields.Date.to_string(datetime(year, 4, 1))
            end_date = fields.Date.to_string(datetime(year, 6, 30))
            self.month = None
        elif quarter == 'Q3':
            start_date = fields.Date.to_string(datetime(year, 7, 1))
            end_date = fields.Date.to_string(datetime(year, 9, 30))
            self.month = None
        elif quarter == 'Q4':
            start_date = fields.Date.to_string(datetime(year, 10, 1))
            end_date = fields.Date.to_string(datetime(year, 12, 31))
        elif month == 0:
            start_date = fields.Date.to_string(datetime(year, 1, 1))
            end_date = fields.Date.to_string(datetime(year, 12, 31))
            self.quarter = None
        else:
            start_date = fields.Date.to_string(date_utils.start_of(datetime(year, month, 1), 'month'))
            end_date = fields.Date.to_string(date_utils.end_of(datetime(year, month, 1), 'month'))
            self.quarter = None
           
        sales_data = self._get_sales_data(start_date, end_date)
        financial_data = self._get_financial_data(start_date, end_date)
        employee_data = self._get_employee_data()
        cash_flow_data = self._get_cash_flow_data(start_date, end_date)
        
        return {
            'filters': {
                'year': year,
                'month': month,
                'month_name': dict(self._fields['month'].selection).get(self.month),
            },
            'company': {
                'name': self.company_id.name,
                'currency': self.currency_id.symbol,
                'country': self.company_id.country_id.name,
            },
            'sales': {
                'order_count': sales_data['sales_order_count'],
                'amount': self._format_amount(sales_data['sales_amount']),
                'target': self._format_amount(sales_data['sales_target']),
                'target_achievement': f"{float_round(sales_data['target_achievement'], 0)}%",
                'region_wise': {
                    'data': [
                        {'name': 'Export', 'value': sales_data['export_sales']},
                        {'name': 'Local', 'value': sales_data['local_sales']}
                    ],
                    'total': sales_data['sales_amount'],
                    'colors': ['#1e88e5', '#ff8f00'],
                }
            },
            'revenue': {
                'amount': self._format_amount(financial_data['revenue']),
                'cost_of_revenue': self._format_amount(financial_data['cost_of_revenue']),
                'gross_profit': self._format_amount(financial_data['gross_profit']),
                'gross_profit_margin': f"{float_round(financial_data['gross_profit_margin'], 2)}%",
                'expenses': self._format_amount(financial_data['expenses']),
                'net_profit': self._format_amount(financial_data['net_profit']),
                'net_profit_margin': f"{float_round(financial_data['net_profit_margin'], 2)}%",
                'accounts_receivable': self._format_amount(financial_data['accounts_receivable']),
                'accounts_payable': self._format_amount(financial_data['accounts_payable']),
                'region_wise': {
                    'data': [
                        {'name': 'Export', 'value': financial_data['export_revenue']},
                        {'name': 'Local', 'value': financial_data['local_revenue']}
                    ],
                    'total': financial_data['export_revenue'] + financial_data['local_revenue'],
                    'colors': ['#1e88e5', '#ff8f00'],
                }
            },
            'expenses': {
                'total': self._format_amount(financial_data['expenses']),
                'region_wise': {
                    'data': [
                        {'name': 'Export', 'value': financial_data['export_expenses']},
                        {'name': 'Local', 'value': financial_data['local_expenses']}
                    ],
                    'total': financial_data['expenses'],
                    'colors': ['#1e88e5', '#ff8f00'],
                }
            },
            'cash_flow': {
                'inflows': self._format_amount(cash_flow_data['inflows']),
                'outflows': self._format_amount(cash_flow_data['outflows']),
                'region_wise': {
                    'inflow': [
                        {'name': 'Export', 'value': cash_flow_data['export_inflow']},
                        {'name': 'Local', 'value': cash_flow_data['local_inflow']}
                    ],
                    'outflow': [
                        {'name': 'Export', 'value': cash_flow_data['export_outflow']},
                        {'name': 'Local', 'value': cash_flow_data['local_outflow']}
                    ],
                    'total_inflow': cash_flow_data['inflows'],
                    'total_outflow': cash_flow_data['outflows'],
                    'colors': ['#ff8f00', '#1e88e5'],
                },
            },
            'hr': {
                'total_employees': employee_data['total_employees'],
                'gender_data': {
                    'data': [
                        {'name': 'Male', 'value': employee_data['gender_data']['male']},
                        {'name': 'Female', 'value': employee_data['gender_data']['female']}
                    ],
                    'total': employee_data['gender_data']['male'] + employee_data['gender_data']['female'] + 
                             employee_data['gender_data']['other'],
                    'colors': ['#1e88e5', '#ff8f00'],
                },
                'departments': [
                    {'name': dept, 'count': count} 
                    for dept, count in employee_data['departments'].items()
                ],
                'categories': [
                    {'name': cat, 'count': count} 
                    for cat, count in employee_data['categories'].items()
                ]
            },
        }
    
    def _format_amount(self, amount):
        """Format amount to match the dashboard display format"""
        return f"{float_round(round(amount, 2), 2):,.2f}"
    
    def _get_sales_data(self, start_date, end_date):
        """Get sales related data for dashboard"""
        sales_orders = self.env['sale.order'].search([
            ('date_order', '>=', start_date),
            ('date_order', '<=', end_date),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ['sale', 'done']),
        ])
        
        sales_order_count = len(sales_orders)
        sales_amount = sum(order.amount_untaxed for order in sales_orders)
        sales_target = self._get_yearly_sales_target()  # Ensure this returns a valid value
        
        target_achievement = (sales_amount / sales_target) * 100 if sales_target else 0
        
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])

        local_sales_amount = export_sales_amount = 0.0

        for local_project in local_projects:
            for sales_order in sales_orders:
                if local_project in sales_order.project_ids:
                    local_sales_amount += sales_order.amount_untaxed

        for export_project in export_projects:
            for sales_order in sales_orders:
                if export_project in sales_order.project_ids:
                    export_sales_amount += sales_order.amount_untaxed

        return {
            'sales_order_count': sales_order_count,
            'sales_amount': sales_amount,
            'sales_target': sales_target,
            'target_achievement': target_achievement,
            'local_sales': local_sales_amount,
            'export_sales': export_sales_amount,
        }
    
    def _get_yearly_sales_target(self):
        """Get the yearly sales target from configuration"""
        sale_targets = self.env['sale.target'].search([
            ('year', '=', self.year),
            ('company_id', '=', self.company_id.id)
        ])
        if sale_targets:
            return sum(sale_targets.mapped('target_amount'))
        return 0.0
    
    def _get_financial_data(self, start_date, end_date):
        """Get financial data for the dashboard"""
        total_revenue = self.compute_untaxed_revenue(start_date, end_date)
        
        total_expenses = self.compute_untaxed_expenses(start_date, end_date)

        cost_of_revenue = self.calculate_cost_of_revenue(start_date, end_date)
        
        gross_profit = total_revenue - cost_of_revenue

        # Calculate gross profit margin
        if total_revenue != 0:
            gross_profit_margin = round((gross_profit / total_revenue) * 100, 2)
        else:
            gross_profit_margin = 0.0
        # Calculate net profit and net profit margin
        net_profit = gross_profit - total_expenses
        if total_revenue != 0:
            net_profit_margin = net_profit / total_revenue * 100
        else:
            net_profit_margin = 0.0

        # Calculate accounts receivable and payable
        accounts_receivable = self.calculate_accounts_receivable(start_date, end_date)
        accounts_payable = self.calculate_accounts_payable(start_date, end_date)

        # Calculate revenue and expenses region-wise
        revenue_region_wise = self.calculate_revenue_region_wise(start_date, end_date)
        expenses_region_wise = self.calculate_expenses_region_wise(start_date, end_date)

        return {
            'revenue': total_revenue,
            'cost_of_revenue': cost_of_revenue,
            'gross_profit': gross_profit,
            'gross_profit_margin': gross_profit_margin,
            'net_profit': net_profit,
            'net_profit_margin': net_profit_margin,
            'expenses': abs(total_expenses),
            'net_profit_margin': net_profit_margin,
            'accounts_receivable': accounts_receivable,
            'accounts_payable': accounts_payable,
            'local_revenue': revenue_region_wise['local_revenue'],
            'export_revenue': revenue_region_wise['export_revenue'],
            'local_expenses': expenses_region_wise['local_expense'],
            'export_expenses': expenses_region_wise['export_expense'],
        }

    def _get_employee_data(self):
        """Get employee related data for the dashboard"""
        employees = self.env['hr.employee'].search([
            ('company_id', '=', self.company_id.id),
            ('active', '=', True),
        ])
        
        total_employees = len(employees)
        
        gender_data = {
            'male': len(employees.filtered(lambda e: e.gender == 'male')),
            'female': len(employees.filtered(lambda e: e.gender == 'female')),
            'other': len(employees.filtered(lambda e: e.gender not in ['male', 'female'] or not e.gender)),
        }
        
        departments = {}
        for employee in employees:
            department_name = employee.department_id.name or 'Undefined'
            departments[department_name] = departments.get(department_name, 0) + 1
        
        categories = self.env['hr.employee.category'].search([
            ('name', 'not in', ['Male', 'Female'])
        ])
    
        categories_count = {}
        
        for category in categories:
            # Count employees in this category
            employee_count = self.env['hr.employee'].search_count([
                ('category_ids', 'in', category.id),
                ('active', '=', True)  # Only count active employees
            ])
            
            categories_count[category.name] = employee_count
            
        return {
            'total_employees': total_employees,
            'gender_data': gender_data,
            'departments': departments,
            'categories': categories_count,
        }

    def compute_untaxed_expenses(self, start_date, end_date):
        """
        Calculate total expenses using amount_untaxed_signed from account.move
        
        Args:
            start_date (str): Start date in 'YYYY-MM-DD' format
            end_date (str): End date in 'YYYY-MM-DD' format
            
        Returns:
            float: Total expenses for the period
        """
        # Convert string dates to datetime objects if needed
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)
        
        # Company id
        company_id = self.env.company.id
        
        # Build domain for expense accounts
        domain = [
            ('account_id.account_type', '=', 'expense'),  # Expense accounts in Odoo 16
            ('move_id.state', '=', 'posted'),  # Only posted entries
            ('date', '<=', end_date),  # All entries up to end_date
            ('date', '>=', start_date),  # Start date
            ('company_id', '=', company_id)
        ]
        
        # Get the sum of all expense account balances
        expense_data = self.env['account.move.line'].read_group(
            domain=domain,
            fields=['balance'],
            groupby=[]
        )
        
        # Calculate total expenses (typically positive for expense)
        if expense_data:
            total_expenses = expense_data[0].get('balance', 0.0)

            # check if total_expenses is not None
            if total_expenses is None:
                total_expenses = 0.0
            return total_expenses if total_expenses > 0 else 0.0
        
        return 0.0

    def compute_untaxed_revenue(self, start_date, end_date):
        """
        Calculate total revunue using amount_untaxed_signed from account.move
        
        Args:
            start_date (str): Start date in 'YYYY-MM-DD' format
            end_date (str): End date in 'YYYY-MM-DD' format
            
        Returns:
            float: Total revenue for the period
        """
        customer_invoices = self.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('company_id', '=', self.company_id.id),
        ])
        
        # Get revenue from customer invoices
        total_revenue = sum(invoice.amount_untaxed_signed for invoice in customer_invoices)
        
        return total_revenue

    def calculate_cost_of_revenue(self, start_date, end_date):
        """
        Calculate total cost of revenue based on vendor bills and actual purchase prices.
        
        Args:
            start_date (str): Start date in 'YYYY-MM-DD' format
            end_date (str): End date in 'YYYY-MM-DD' format

        Returns:
            float: Total cost of revenue for the period
        """
        # Convert string dates to datetime objects if needed
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)
        
        # Company id
        company_id = self.env.company.id
        
        # Build domain for direct cost accounts
        domain = [
            ('account_id.account_type', '=', 'expense_direct_cost'),  # Direct cost accounts in Odoo 16
            ('move_id.state', '=', 'posted'),  # Only posted entries
            ('date', '>=', start_date),  # Start date
            ('date', '<=', end_date),  # End date
            ('company_id', '=', company_id)
        ]
        
        # Get the sum of all direct cost account entries
        cost_data = self.env['account.move.line'].read_group(
            domain=domain,
            fields=['debit', 'credit'],
            groupby=[]
        )
        
        # Calculate total cost (debit - credit for expense accounts)
        if cost_data:
            total_debit = cost_data[0].get('debit', 0.0)
            total_credit = cost_data[0].get('credit', 0.0)

            # check if total_debit and total_credit is not None
            if total_debit is None:
                total_debit = 0.0
            if total_credit is None:
                total_credit = 0.0
            # Calculate total cost
            total_cost = total_debit - total_credit
            return total_cost
        
        return 0.0

    def calculate_accounts_receivable(self, start_date, end_date):
        """
        Calculate accounts receivable within a specific date range
        
        Args:
            start_date (str): Start date in 'YYYY-MM-DD' format
            end_date (str): End date in 'YYYY-MM-DD' format
            
        Returns:
            float: Total accounts receivable created within the date range
        """
        # Convert string dates to datetime objects if needed
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)
        
        # Company id
        company_id = self.env.company.id
        
        # Build domain for receivable accounts
        domain = [
            ('account_id.account_type', '=', 'asset_receivable'),  # Receivable accounts in Odoo 16
            ('account_id.non_trade', '=', False),  # Exclude non-trade receivables
            ('move_id.state', '=', 'posted'),  # Only posted entries
            ('date', '<=', end_date),  # All entries up to end_date
            # ('date', '>=', start_date),  # Start date
            # ('company_id', '=', company_id)
        ]
        
        # Get the sum of all receivable account balances
        receivable_data = self.env['account.move.line'].read_group(
            domain=domain,
            fields=['balance'],
            groupby=[]
        )
        
        # Calculate total receivables (typically positive for receivables)
        if receivable_data:
            total_receivables = receivable_data[0].get('balance', 0.0)
            if total_receivables is None:
                total_receivables = 0.0
            # check if total_receivables is not None
            return total_receivables if total_receivables > 0 else 0.0
        
        return 0.0

    def calculate_accounts_payable(self, start_date, end_date):
        """
        Calculate accounts payable within a specific date range
        
        Args:
            start_date (str): Start date in 'YYYY-MM-DD' format
            end_date (str): End date in 'YYYY-MM-DD' format
            
        Returns:
            float: Total accounts payable created within the date range
        """
        # Convert string dates to datetime objects if needed
        if isinstance(start_date, str):
            start_date = fields.Date.from_string(start_date)
        if isinstance(end_date, str):
            end_date = fields.Date.from_string(end_date)
        
        # Company id
        company_id = self.env.company.id
        
        # Build domain for payable accounts only
        domain = [
            ('account_id.account_type', '=', 'liability_payable'),  # Only payable accounts
            ('move_id.state', '=', 'posted'),  # Only posted entries
            ('date', '<=', end_date),  # All entries up to end_date
            ('company_id', '=', company_id)
        ]
        
        # Get the sum of all payable account balances
        payable_data = self.env['account.move.line'].read_group(
            domain=domain,
            fields=['balance'],
            groupby=[]
        )
        
        # Calculate total payables (typically negative, so take absolute value)
        total_payables = 0.0
        if payable_data:
            total_payables = payable_data[0].get('balance', 0.0)
            if total_payables is None:
                total_payables = 0.0
            else:
                total_payables = abs(total_payables)

        # # Build domain for liability accounts only
        # domain = [
        #     '|', 
        #     ('account_id.account_type', 'in', ('liability_current', 'liability_credit_card')), 
        #     '&', 
        #     ('account_id.account_type', '=', 'liability_payable'), 
        #     ('account_id.non_trade', '=', True),
        #     ('move_id.state', '=', 'posted'),  # Only posted entries
        #     ('date', '<=', end_date),  # All entries up to end_date
        #     ('company_id', '=', company_id)
        # ]
        
        # # Get the sum of all liability account balances
        # liability_data = self.env['account.move.line'].read_group(
        #     domain=domain,
        #     fields=['balance'],
        #     groupby=[]
        # )
        
        # # Calculate total liabilities (typically negative, so take absolute value)
        # total_liabilities = 0.0
        # if liability_data:
        #     total_liabilities = abs(liability_data[0].get('balance', 0.0))
        
        # return total_payables + total_liabilities
        return total_payables

    def calculate_revenue_region_wise(self, start_date, end_date):
        """
        Calculate revenue based on project tags (Local and Export) from posted invoices
        
        This implementation efficiently tracks revenue by:
        1. Finding all relevant projects tagged as Local or Export
        2. Identifying all sales orders linked to these projects
        3. Calculating revenue from posted invoices related to these sales orders
        
        Args:
            start_date (str): Start date in 'YYYY-MM-DD' format
            end_date (str): End date in 'YYYY-MM-DD' format
            
        Returns:
            dict: Dictionary containing local and export revenue
        """
        # Performance optimization: Use search_read to get only needed fields
        local_tag_id = self.env['project.tags'].search([('name', '=', 'Local')], limit=1).id
        export_tag_id = self.env['project.tags'].search([('name', '=', 'Export')], limit=1).id
        
        if not (local_tag_id or export_tag_id):
            return {'local_revenue': 0.0, 'export_revenue': 0.0}
        
        # Get projects with their tags in one query
        projects = self.env['project.project'].search_read(
            [('tag_ids', 'in', [local_tag_id, export_tag_id])],
            ['id', 'tag_ids']
        )
        
        # Classify projects by tag
        local_project_ids = []
        export_project_ids = []
        
        for project in projects:
            if local_tag_id in project['tag_ids']:
                local_project_ids.append(project['id'])
            if export_tag_id in project['tag_ids']:
                export_project_ids.append(project['id'])
        
        if not (local_project_ids or export_project_ids):
            return {'local_revenue': 0.0, 'export_revenue': 0.0}
        
        # Find all sale orders related to these projects
        domain = [
            ('project_ids', 'in', local_project_ids + export_project_ids),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ['sale', 'done'])
        ]
        
        sale_orders = self.env['sale.order'].search_read(domain, ['id', 'project_ids'])
        
        # Classify sale orders by project type
        local_sale_order_ids = set()
        export_sale_order_ids = set()
        
        for order in sale_orders:
            order_projects = set(order['project_ids'])
            if any(project_id in order_projects for project_id in local_project_ids):
                local_sale_order_ids.add(order['id'])
            if any(project_id in order_projects for project_id in export_project_ids):
                export_sale_order_ids.add(order['id'])
        
        if not (local_sale_order_ids or export_sale_order_ids):
            return {'local_revenue': 0.0, 'export_revenue': 0.0}
        
        # Get posted customer invoices in the date range related to these sale orders
        invoice_domain = [
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('sale_id', 'in', list(local_sale_order_ids | export_sale_order_ids)),
            ('company_id', '=', self.company_id.id),
        ]
        
        invoices = self.env['account.move'].search_read(
            invoice_domain, 
            ['id', 'sale_id', 'amount_untaxed_signed']
        )
        
        # Calculate revenue
        total_local_revenue = total_export_revenue = 0.0
        
        for invoice in invoices:
            sale_id = invoice['sale_id'] and invoice['sale_id'][0]
            if sale_id in local_sale_order_ids:
                total_local_revenue += invoice['amount_untaxed_signed']
            if sale_id in export_sale_order_ids:
                total_export_revenue += invoice['amount_untaxed_signed']
        
        return {
            'local_revenue': total_local_revenue,
            'export_revenue': total_export_revenue,
        }

    def calculate_expenses_region_wise(self, start_date, end_date):  
        # Get Local and Export tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        # Ensure tags exist
        if not local_tag or not export_tag:
            raise ValueError("Local or Export tags not found")

        # Local Projects
        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        
        # Export Projects
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])
        
        # Get analytic accounts from projects
        local_analytic_account_ids = local_projects.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_projects.mapped('analytic_account_id').ids
        
        total_local_expense = 0.0
        total_export_expense = 0.0

        # Get confirmed vendor bills within the date range
        domain = [
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('company_id', '=', self.env.company.id),
        ]
        vendor_bills = self.env['account.move'].search(domain)
        
        for bill in vendor_bills:
            for line in bill.line_ids:
                # Ensure analytic distribution exists and is processed correctly
                if line.analytic_distribution:
                    # Handle different analytic distribution formats
                    try:
                        # Convert to dictionary if it's a string
                        distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                            else eval(line.analytic_distribution)
                        
                        # Check each analytic account in the distribution
                        for account_id, percentage in distribution.items():
                            account_id = int(account_id)  # Ensure integer
                            
                            # Calculate proportional expense based on distribution percentage
                            proportional_expense = line.price_subtotal * (percentage / 100)
                            
                            # Check if the account is in local or export project accounts
                            if account_id in local_analytic_account_ids:
                                total_local_expense += proportional_expense
                            if account_id in export_analytic_account_ids:
                                total_export_expense += proportional_expense
                    
                    except Exception as e:
                        # Log any errors in processing analytic distribution
                        print(f"Error processing analytic distribution for bill {bill.id}, line {line.id}: {e}")

        # Round to 2 decimal places for currency amounts
        total_local_expense = round(total_local_expense, 2)
        total_export_expense = round(total_export_expense, 2)

        return {
            'local_expense': total_local_expense,
            'export_expense': total_export_expense,
            'local_projects_count': len(local_projects),
            'export_projects_count': len(export_projects),
        }

    def _get_cash_flow_data(self, start_date, end_date):
        """Get cash flow data for the period, filtered by customer invoices and projects."""
        inflows = outflows = local_inflow = export_inflow = local_outflow = export_outflow = 0.0
        
        local_tag_id = self.env['project.tags'].search([('name', '=', 'Local')], limit=1).id
        export_tag_id = self.env['project.tags'].search([('name', '=', 'Export')], limit=1).id

        customer_payments = self.env['account.payment'].search([
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('company_id', '=', self.company_id.id),
        ])

        for payment in customer_payments:
            # Try different methods to get related invoices
            invoices = (
                payment.reconciled_invoice_ids or  # Try reconciled invoices first
                payment.invoice_line_ids.move_id or  # Alternative method
                self.env['account.move'].search([('payment_id', '=', payment.id)])  # Fallback search
            )

            for invoice in invoices:
                # Try multiple methods to find the sale order
                sale_order = False
                
                # Method 1: Try direct sale_id if it exists
                if hasattr(invoice, 'sale_id'):
                    sale_order = invoice.sale_id
                
                # Method 2: Search using invoice reference
                if not sale_order and invoice.ref:
                    sale_order = self.env['sale.order'].search([('name', '=', invoice.ref)], limit=1)
                
                # Method 3: Search using invoice name
                if not sale_order and invoice.name:
                    sale_order = self.env['sale.order'].search([('name', '=', invoice.name)], limit=1)

                if sale_order:
                    for project in sale_order.project_ids:
                        if local_tag_id in project.tag_ids.ids:
                            local_inflow += payment.amount
                            break
                        elif export_tag_id in project.tag_ids.ids:
                            export_inflow += payment.amount
                            break

        # Outbound Payments (Vendor Payments)
        vendor_payments = self.env['account.payment'].search([
            ('payment_type', '=', 'outbound'),
            ('state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('company_id', '=', self.company_id.id),
        ])

        local_project_ids = self.env['project.project'].search([('tag_ids', 'in', [local_tag_id])])
        export_project_ids = self.env['project.project'].search([('tag_ids', 'in', [export_tag_id])])
        local_analytic_account_ids = local_project_ids.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_project_ids.mapped('analytic_account_id').ids

        # Process Outbound Payments
        for payment in vendor_payments:
            if not payment.reconciled_bill_ids:
                continue
            # Try different methods to get related bills
            try:
                bill = payment.reconciled_bill_ids or payment.bill_line_ids.move_id
            except Exception as e:
                print(f"Error retrieving reconciled bill for payment {payment.id}: {e}")
                bill = False
            if bill:
                for line in bill.line_ids:
                    if line.analytic_distribution:
                        try:
                            distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                                else eval(line.analytic_distribution)
                            
                            for account_id, percentage in distribution.items():
                                account_id = int(account_id)
                                
                                # Check if the account is in local or export project accounts
                                if account_id in local_analytic_account_ids:
                                    local_outflow += payment.amount
                                    break
                                if account_id in export_analytic_account_ids:
                                    export_outflow += payment.amount
                                    break
                        except Exception as e:
                            print(f"Error processing analytic distribution for bill {bill.id}, line {line.id}: {e}")

        return {
            'inflows': inflows,
            'outflows': outflows,
            'local_inflow': local_inflow,
            'export_inflow': export_inflow,
            'local_outflow': local_outflow,
            'export_outflow': export_outflow,
        }