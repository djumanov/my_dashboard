from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import date_utils, float_round

_logger = logging.getLogger(__name__)

class L1Dashboard(models.Model):
    _name = 'l1.dashboard'
    _description = 'L1 Dashboard Data'

    name = fields.Char(string='Dashboard Name', default='L1 Dashboard')
    # year = fields.Integer(string='Year', default=lambda self: fields.Date.today().year)
    month = fields.Selection([
        ('0', 'All'), 
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
        ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
        ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='Month', default='0')
    
    dashboard_data = fields.Text(string='Dashboard Data', compute='_compute_dashboard_data')
    dashboard_data_array = fields.Text(string='D')
    last_update = fields.Datetime(string='Last Update')
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    
    def _get_year_selection(self):
        current_year = datetime.now().year
        return [(str(year), str(year)) for year in range(1990, current_year + 1)]

    year = fields.Selection(
        selection=lambda self: self._get_year_selection(),
        string='Year',
        default=lambda self: str(fields.Date.today().year)
    )

    @api.depends('year', 'month', 'company_id')
    def _compute_dashboard_data(self):
        for record in self:
            record.dashboard_data = json.dumps(record._get_dashboard_data())
            record.last_update = fields.Datetime.now()
    
    def _get_dashboard_data(self):
        """Compute all dashboard data and return as a structured dictionary"""
        self.ensure_one()
        
        month = int(self.month)
        year = int(self.year)
        
        if month == 0:
            start_date = fields.Date.to_string(datetime(year, 1, 1))
            end_date = fields.Date.to_string(datetime(year, 12, 31))
        else:
            start_date = fields.Date.to_string(date_utils.start_of(datetime(year, month, 1), 'month'))
            end_date = fields.Date.to_string(date_utils.end_of(datetime(year, month, 1), 'month'))
           
        sales_data = self._get_sales_data(start_date, end_date)
        financial_data = self._get_financial_data(start_date, end_date)
        employee_data = self._get_employee_data()
        cash_flow_data = self._get_cash_flow_data(start_date, end_date)
        historical_data = self._get_historical_data(year, month)
        
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
                    'total': financial_data['revenue'],
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
                'net_cash_flow': self._format_amount(cash_flow_data['net_cash_flow']),
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
                'months_data': cash_flow_data['months_data']
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
            'historical': historical_data
        }
    
    def _format_amount(self, amount):
        """Format amount to match the dashboard display format"""
        return f"{float_round(amount, 2):,.2f}"
    
    def _get_sales_data(self, start_date, end_date):
        """Get sales related data for dashboard"""
        sales_orders = self.env['sale.order'].search([
            ('date_order', '>=', start_date),
            ('date_order', '<=', end_date),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ['sale', 'done']),
        ])
        
        sales_order_count = len(sales_orders)
        sales_amount = sum(order.amount_total for order in sales_orders)
        sales_target = self._get_yearly_sales_target()
        target_achievement = (sales_amount / sales_target) * 100 if sales_target else 0
        
        local_country_id = self.company_id.country_id.id
        local_sales = sum(order.amount_total for order in sales_orders if order.partner_id.country_id.id == local_country_id)
        export_sales = sales_amount - local_sales
        
        return {
            'sales_order_count': sales_order_count,
            'sales_amount': sales_amount,
            'sales_target': sales_target,
            'target_achievement': target_achievement,
            'local_sales': local_sales,
            'export_sales': export_sales,
        }
    
    def _get_yearly_sales_target(self):
        """Get the yearly sales target from configuration"""
        config_param = self.env['ir.config_parameter'].sudo().get_param('l1_dashboard.yearly_sales_target', '250000000')
        try:
            return float(config_param)
        except (ValueError, TypeError):
            return 250000000
    
    def _get_financial_data(self, start_date, end_date):
        """Get financial data for the dashboard"""
        invoices = self.env['account.move'].search([
            ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ])
        
        revenue_invoices = invoices.filtered(lambda inv: inv.move_type in ['out_invoice', 'out_refund'])
        revenue = sum(invoice.amount_total for invoice in revenue_invoices.filtered(lambda inv: inv.move_type == 'out_invoice'))
        revenue -= sum(invoice.amount_total for invoice in revenue_invoices.filtered(lambda inv: inv.move_type == 'out_refund'))
        
        cost_invoices = invoices.filtered(lambda inv: inv.move_type in ['in_invoice', 'in_refund'])
        cost_of_revenue = sum(invoice.amount_total for invoice in cost_invoices.filtered(lambda inv: inv.move_type == 'in_invoice'))
        cost_of_revenue -= sum(invoice.amount_total for invoice in cost_invoices.filtered(lambda inv: inv.move_type == 'in_refund'))
        
        expense_accounts = self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_id', '=', self.company_id.id),
        ])
        
        expense_moves = self.env['account.move.line'].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('account_id', 'in', expense_accounts.ids),
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ])
        expenses = sum(line.balance for line in expense_moves)
        
        gross_profit = revenue - cost_of_revenue
        gross_profit_margin = (gross_profit / revenue) * 100 if revenue else 0
        net_profit = gross_profit - expenses
        net_profit_margin = (net_profit / revenue) * 100 if revenue else 0
        
        receivable_moves = self.env['account.move.line'].search([
            ('account_id.account_type', '=', 'asset_receivable'),
            ('date', '<=', end_date),
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ])
        accounts_receivable = sum(line.balance for line in receivable_moves)
        
        payable_moves = self.env['account.move.line'].search([
            ('account_id.account_type', '=', 'liability_payable'),
            ('date', '<=', end_date),
            ('parent_state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ])
        accounts_payable = -sum(line.balance for line in payable_moves)
        
        local_country_id = self.company_id.country_id.id
        local_revenue = sum(invoice.amount_total for invoice in revenue_invoices.filtered(
            lambda inv: inv.move_type == 'out_invoice' and inv.partner_id.country_id.id == local_country_id))
        local_revenue -= sum(invoice.amount_total for invoice in revenue_invoices.filtered(
            lambda inv: inv.move_type == 'out_refund' and inv.partner_id.country_id.id == local_country_id))
        export_revenue = revenue - local_revenue
        
        local_expenses = sum(abs(line.balance) for line in expense_moves if line.partner_id.country_id.id == local_country_id)
        export_expenses = expenses - local_expenses
        
        return {
            'revenue': revenue,
            'cost_of_revenue': cost_of_revenue,
            'expenses': expenses,
            'gross_profit': gross_profit,
            'gross_profit_margin': gross_profit_margin,
            'net_profit': net_profit,
            'net_profit_margin': net_profit_margin,
            'accounts_receivable': accounts_receivable,
            'accounts_payable': accounts_payable,
            'local_revenue': local_revenue,
            'export_revenue': export_revenue,
            'local_expenses': local_expenses,
            'export_expenses': export_expenses,
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
        
        categories = {}
        for employee in employees:
            for category in employee.category_ids:
                if category.name not in ['Male', 'Female']:
                    categories[category.name] = categories.get(category.name, 0) + 1
        
        return {
            'total_employees': total_employees,
            'gender_data': gender_data,
            'departments': departments,
            'categories': categories,
        }
    
    def _get_cash_flow_data(self, start_date, end_date):
        """Get cash flow data for the period"""
        cash_accounts = self.env['account.account'].search([
            '|', ('account_type', '=', 'asset_cash'),
            ('account_type', '=', 'asset_current'),
            ('company_id', '=', self.company_id.id),
        ])
        
        cash_moves = self.env['account.move.line'].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('account_id', 'in', cash_accounts.ids),
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ])
        
        inflows = sum(line.balance for line in cash_moves if line.balance > 0)
        outflows = sum(abs(line.balance) for line in cash_moves if line.balance < 0)
        
        local_country_id = self.company_id.country_id.id
        local_inflow = sum(line.balance for line in cash_moves if 
                          line.balance > 0 and line.partner_id.country_id.id == local_country_id)
        export_inflow = inflows - local_inflow
        
        local_outflow = sum(abs(line.balance) for line in cash_moves if 
                           line.balance < 0 and line.partner_id.country_id.id == local_country_id)
        export_outflow = outflows - local_outflow
        
        months_data = []
        for i in range(3):
            month_date = fields.Date.from_string(start_date) - relativedelta(months=i)
            month_start = fields.Date.to_string(date_utils.start_of(month_date, 'month'))
            month_end = fields.Date.to_string(date_utils.end_of(month_date, 'month'))
            
            month_moves = self.env['account.move.line'].search([
                ('date', '>=', month_start),
                ('date', '<=', month_end),
                ('account_id', 'in', cash_accounts.ids),
                ('move_id.state', '=', 'posted'),
                ('company_id', '=', self.company_id.id),
            ])
            
            month_inflow = sum(line.balance for line in month_moves if line.balance > 0)
            month_outflow = sum(abs(line.balance) for line in month_moves if line.balance < 0)
            
            months_data.append({
                'month': month_date.strftime('%b'),
                'inflow': month_inflow,
                'outflow': month_outflow,
                'net': month_inflow - month_outflow,
            })
        
        return {
            'inflows': inflows,
            'outflows': outflows,
            'net_cash_flow': inflows - outflows,
            'local_inflow': local_inflow,
            'export_inflow': export_inflow,
            'local_outflow': local_outflow,
            'export_outflow': export_outflow,
            'months_data': months_data,
        }
    
    def _get_historical_data(self, year, month):
        """Get historical trends for key metrics"""
        result = {
            'sales': [],
            'revenue': [],
            'profit': [],
            'cash_flow': []
        }
        
        if month == 0:
            month = 12
        
        # Get data for the last 6 months
        for i in range(5, -1, -1):
            target_date = datetime(year, month, 1) - relativedelta(months=i)
            start_date = fields.Date.to_string(date_utils.start_of(target_date, 'month'))
            end_date = fields.Date.to_string(date_utils.end_of(target_date, 'month'))
            
            # Sales data
            sales_orders = self.env['sale.order'].search([
                ('date_order', '>=', start_date),
                ('date_order', '<=', end_date),
                ('company_id', '=', self.company_id.id),
                ('state', 'in', ['sale', 'done']),
            ])
            sales_amount = sum(order.amount_total for order in sales_orders)
            
            # Revenue data
            invoices = self.env['account.move'].search([
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('invoice_date', '>=', start_date),
                ('invoice_date', '<=', end_date),
                ('state', '=', 'posted'),
                ('company_id', '=', self.company_id.id),
            ])
            revenue = sum(invoice.amount_total for invoice in invoices.filtered(lambda inv: inv.move_type == 'out_invoice'))
            revenue -= sum(invoice.amount_total for invoice in invoices.filtered(lambda inv: inv.move_type == 'out_refund'))
            
            # Get financial data for profit
            financial_data = self._calculate_profit_for_period(start_date, end_date)
            
            # Cash flow
            cash_accounts = self.env['account.account'].search([
                '|', ('account_type', '=', 'asset_cash'),
                ('account_type', '=', 'asset_current'),
                ('company_id', '=', self.company_id.id),
            ])
            cash_moves = self.env['account.move.line'].search([
                ('date', '>=', start_date),
                ('date', '<=', end_date),
                ('account_id', 'in', cash_accounts.ids),
                ('move_id.state', '=', 'posted'),
                ('company_id', '=', self.company_id.id),
            ])
            inflows = sum(line.balance for line in cash_moves if line.balance > 0)
            outflows = sum(abs(line.balance) for line in cash_moves if line.balance < 0)
            net_cash_flow = inflows - outflows
            
            month_name = target_date.strftime('%b %Y')
            
            result['sales'].append({
                'month': month_name,
                'value': sales_amount
            })
            result['revenue'].append({
                'month': month_name,
                'value': revenue
            })
            result['profit'].append({
                'month': month_name,
                'value': financial_data['net_profit']
            })
            result['cash_flow'].append({
                'month': month_name,
                'value': net_cash_flow
            })
        
        return result
    
    def _calculate_profit_for_period(self, start_date, end_date):
        """Calculate profit metrics for a specific period"""
        invoices = self.env['account.move'].search([
            ('move_type', 'in', ['out_invoice', 'out_refund', 'in_invoice', 'in_refund']),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ])
        
        revenue_invoices = invoices.filtered(lambda inv: inv.move_type in ['out_invoice', 'out_refund'])
        revenue = sum(invoice.amount_total for invoice in revenue_invoices.filtered(lambda inv: inv.move_type == 'out_invoice'))
        revenue -= sum(invoice.amount_total for invoice in revenue_invoices.filtered(lambda inv: inv.move_type == 'out_refund'))
        
        cost_invoices = invoices.filtered(lambda inv: inv.move_type in ['in_invoice', 'in_refund'])
        cost_of_revenue = sum(invoice.amount_total for invoice in cost_invoices.filtered(lambda inv: inv.move_type == 'in_invoice'))
        cost_of_revenue -= sum(invoice.amount_total for invoice in cost_invoices.filtered(lambda inv: inv.move_type == 'in_refund'))
        
        expense_accounts = self.env['account.account'].search([
            ('account_type', '=', 'expense'),
            ('company_id', '=', self.company_id.id),
        ])
        
        expense_moves = self.env['account.move.line'].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('account_id', 'in', expense_accounts.ids),
            ('move_id.state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ])
        expenses = sum(line.balance for line in expense_moves)
        
        gross_profit = revenue - cost_of_revenue
        net_profit = gross_profit - expenses
        
        return {
            'revenue': revenue,
            'cost_of_revenue': cost_of_revenue,
            'gross_profit': gross_profit,
            'expenses': expenses,
            'net_profit': net_profit,
        }

    
    @api.model
    def get_dashboard_data_json(self, year=None, month=None):
        """API method to get dashboard data in JSON format"""
        if not year:
            year = fields.Date.today().year
        if not month:
            month = fields.Date.today().month
            
        dashboard = self.search([
            ('year', '=', year),
            ('month', '=', str(month)),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not dashboard:
            dashboard = self.create({
                'year': year,
                'month': str(month),
            })
        
        dashboard._compute_dashboard_data()
        return dashboard.dashboard_data