import json
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import date_utils, float_round
import base64
from io import BytesIO
from odoo.tools.misc import xlsxwriter

_logger = logging.getLogger(__name__)


class L1Dashboard(models.Model):
    _name = 'l1.dashboard_demo'
    _description = 'L1 Dashboard Data'

    name = fields.Char(string='Dashboard Name', default='L1 Dashboard')
    
    dashboard_data = fields.Text(string='Dashboard Data', compute='_compute_dashboard_data')
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

    @api.depends('year', 'company_id')
    def _compute_dashboard_data(self):
        for record in self:
            record.dashboard_data = json.dumps(record._get_dashboard_data())
            record.last_update = fields.Datetime.now()

    @api.model
    def get_dashboard_data_json(self, year=None):
        """API method to get dashboard data in JSON format"""
        if not year:
            year = fields.Date.today().year
            
        dashboard = self.search([
            ('year', '=', year),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not dashboard:
            dashboard = self.create({
                'year': year,
            })
        
        dashboard._compute_dashboard_data()
        return dashboard.dashboard_data

    def _get_dashboard_data(self):
        """Compute dashboard data **without** mutating year/month/quarter selections."""
        self.ensure_one()

        sel_year = int(self.year) if self.year else datetime.now().year

        start_date = fields.Date.to_string(datetime(sel_year, 1, 1))
        end_date   = fields.Date.to_string(datetime(sel_year, 12, 31))

        sales_data      = self._get_sales_data(start_date, end_date)
        financial_data  = self._get_financial_data(start_date, end_date)
        cash_flow_data  = self._get_cash_flow_data(start_date, end_date)

        return {
            'filters': {
                'year': sel_year,
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
                        {'name': 'Local',  'value': sales_data['local_sales']},
                    ],
                    'total': sales_data['sales_amount'],
                    'colors': ['#1e88e5', '#ff8f00'],
                },
            },
            'revenue': {
                'amount': self._format_amount(financial_data['revenue']),
                'cost_of_revenue': self._format_amount(financial_data['cost_of_revenue']),
                'gross_profit': self._format_amount(financial_data['gross_profit']),
                'gross_profit_margin': f"{self._format_amount(financial_data['gross_profit_margin'])}%",
                'expenses': self._format_amount(financial_data['expenses']),
                'net_profit': self._format_amount(financial_data['net_profit']),
                'net_profit_margin': f"{self._format_amount(financial_data['net_profit_margin'])}%",
                'accounts_receivable': self._format_amount(financial_data['accounts_receivable']),
                'accounts_payable': self._format_amount(financial_data['accounts_payable']),
                'region_wise': {
                    'data': [
                        {'name': 'Export', 'value': financial_data['export_revenue']},
                        {'name': 'Local',  'value': financial_data['local_revenue']},
                    ],
                    'total': financial_data['export_revenue'] + financial_data['local_revenue'],
                    'colors': ['#1e88e5', '#ff8f00'],
                },
            },
            'expenses': {
                'total': self._format_amount(financial_data['expenses']),
                'region_wise': {
                    'data': [
                        {'name': 'Export', 'value': financial_data['export_expenses']},
                        {'name': 'Local',  'value': financial_data['local_expenses']},
                    ],
                    'total': financial_data['expenses'],
                    'colors': ['#1e88e5', '#ff8f00'],
                },
            },
            'cash_flow': {
                'inflows': self._format_amount(cash_flow_data['inflows']),
                'outflows': self._format_amount(cash_flow_data['outflows']),
                'region_wise': {
                    'inflow':  [{'name': 'Export', 'value': cash_flow_data['export_inflow']},
                                {'name': 'Local',  'value': cash_flow_data['local_inflow']}],
                    'outflow': [{'name': 'Export', 'value': cash_flow_data['export_outflow']},
                                {'name': 'Local',  'value': cash_flow_data['local_outflow']}],
                    'total_inflow': cash_flow_data['inflows'],
                    'total_outflow': cash_flow_data['outflows'],
                    'colors': ['#ff8f00', '#1e88e5'],
                },
            },
        }

    def _format_amount(self, amount):
        """Format amount to match the dashboard display format"""
        return f"{float_round(round(amount, 2), 2):,.2f}"
    
    def _get_sales_data(self, start_date, end_date):
        """Get sales related data for dashboard"""
        # Get company currency
        company_currency = self.env.company.currency_id

        sales_orders = self.env['sale.order'].search([
            ('date_order', '>=', start_date),
            ('date_order', '<=', end_date),
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ['sale', 'done']),
        ])
        
        sales_order_count = len(sales_orders)
        sales_amount = 0.0
        for order in sales_orders:
            sale_currency = order.currency_id
            amount_in_company_currency = sale_currency._convert(
                order.amount_untaxed,
                company_currency,
                self.env.company,
                order.date_order
            )
            sales_amount += amount_in_company_currency

        # sales_amount = sum(order.amount_total for order in sales_orders)
        sales_target = self._get_yearly_sales_target()  # Ensure this returns a valid value
        
        target_achievement = (sales_amount / sales_target) * 100 if sales_target else 0
        
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])

        local_analytic_account_ids = local_projects.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_projects.mapped('analytic_account_id').ids

        local_sales_amount = export_sales_amount = 0.0
        
        for sales_order in sales_orders:
            sale_currency = sales_order.currency_id
            sale_date = sales_order.date_order or sales_order.create_date
            if sales_order.project_ids:
                if sales_order.project_ids[0] in local_projects:
                    amount_in_company_currency = sale_currency._convert(
                        sales_order.amount_untaxed,
                        company_currency,
                        self.env.company,
                        sale_date
                    )
                    local_sales_amount += amount_in_company_currency
            else:
                order_lines = sales_order.order_line
                for line in order_lines:
                    if line.analytic_distribution:
                        try:
                            distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                                else eval(line.analytic_distribution)
                            
                            for account_id, percentage in distribution.items():
                                account_id = int(account_id)
                                
                                if account_id in local_analytic_account_ids:
                                    amount_in_company_currency = sale_currency._convert(
                                        line.price_subtotal,
                                        company_currency,
                                        self.env.company,
                                        sale_date
                                    )
                                    local_sales_amount += amount_in_company_currency

                        except Exception as e:
                            _logger.error(f"Error processing analytic distribution for order {sales_order.id}: {e}")


        for sales_order in sales_orders:
            sale_currency = sales_order.currency_id
            sale_date = sales_order.date_order or sales_order.create_date
            if sales_order.project_ids:
                if sales_order.project_ids[0] in export_projects:
                    amount_in_company_currency = sale_currency._convert(
                        sales_order.amount_untaxed,
                        company_currency,
                        self.env.company,
                        sale_date
                    )
                    export_sales_amount += amount_in_company_currency
            else:
                order_lines = sales_order.order_line
                for line in order_lines:
                    if line.analytic_distribution:
                        try:
                            distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                                else eval(line.analytic_distribution)
                            
                            for account_id, percentage in distribution.items():
                                account_id = int(account_id)
                                
                                if account_id in export_analytic_account_ids:
                                    amount_in_company_currency = sale_currency._convert(
                                        line.price_subtotal,
                                        company_currency,
                                        self.env.company,
                                        sale_date
                                    )
                                    export_sales_amount += amount_in_company_currency

                        except Exception as e:
                            _logger.error(f"Error processing analytic distribution for order {sales_order.id}: {e}")

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
        self.ensure_one()
        
        domain = [
            ('account_id.account_type', '=', 'income'),
            ('parent_state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('company_id', '=', self.company_id.id),
        ]
        
        # Use read_group for better performance with large datasets
        result = self.env['account.move.line'].read_group(
            domain=domain,
            fields=['balance:sum'],
            groupby=[]
        )
        
        # Return negative sum of balance (income accounts have credit balance)
        return -result[0]['balance'] if result else 0.0

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
        # Find project tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        if not local_tag or not export_tag:
            return {'local_revenue': 0.0, 'export_revenue': 0.0}

        # Find projects with respective tags
        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])

        # Get analytic account IDs
        local_analytic_account_ids = local_projects.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_projects.mapped('analytic_account_id').ids
        
        # Get posted customer invoices in the date range
        invoice_domain = [
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]
        customer_invoices = self.env['account.move'].search(invoice_domain)
                
        # Initialize revenue counters
        total_local_revenue = 0.0
        total_export_revenue = 0.0

        for invoice in customer_invoices:
            found = False
            
            for line in invoice.invoice_line_ids:
                # Skip lines with zero or negative amounts
                if line.price_subtotal <= 0:
                    continue
                    
                if line.analytic_distribution:
                    try:
                        distribution = line.analytic_distribution
                        if isinstance(distribution, str):
                            distribution = json.loads(distribution)
                        elif not isinstance(distribution, dict):
                            continue
                        
                        for account_id_str, percentage in distribution.items():
                            account_id = int(account_id_str)
                            
                            if account_id in local_analytic_account_ids:
                                total_local_revenue += invoice.amount_untaxed_signed
                                found = True
                                
                            if account_id in export_analytic_account_ids:
                                total_export_revenue += invoice.amount_untaxed_signed
                                found = True

                    except Exception as e:
                        _logger.error("Error processing analytic distribution for invoice %s, line %s: %s", 
                                    invoice.id, line.id, str(e))
                
                if found:
                    break
        
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

        # Get company currency
        company_currency = self.env.company.currency_id

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
            # Get bill currency
            bill_currency = bill.currency_id
            bill_date = bill.invoice_date or bill.date

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
                            
                            if bill_currency != company_currency:
                                # Convert line amount to company currency
                                amount_in_company_currency = bill_currency._convert(
                                    line.price_subtotal,
                                    company_currency,
                                    self.env.company,
                                    bill_date
                                )
                            else:
                                amount_in_company_currency = line.price_subtotal

                            # Check if the account is in local or export project accounts
                            if account_id in local_analytic_account_ids:
                                total_local_expense += amount_in_company_currency
                            if account_id in export_analytic_account_ids:
                                total_export_expense += amount_in_company_currency                     
                            
                            # # Calculate proportional expense based on distribution percentage
                            # proportional_expense = line.price_subtotal * (percentage / 100)
                            
                            # # Check if the account is in local or export project accounts
                            # if account_id in local_analytic_account_ids:
                            #     total_local_expense += proportional_expense
                            # if account_id in export_analytic_account_ids:
                            #     total_export_expense += proportional_expense
                    
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
        """
        Get cash flow data for the period, filtered by customer/vendor payments
        and categorized by Local and Export projects based on analytic accounts.
        All amounts are converted to the company currency.
        
        Args:
            start_date: Start date of the period
            end_date: End date of the period
            
        Returns:
            dict: Cash flow data categorized by local and export in company currency
        """
        # Initialize result values
        result = {
            'local_inflow': 0.0,
            'export_inflow': 0.0,
            'local_outflow': 0.0,
            'export_outflow': 0.0,
            'inflows': 0.0,
            'outflows': 0.0,
            'net_cash_flow': 0.0
        }
        
        # Get company currency
        company_currency = self.env.company.currency_id
        
        # Get project tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)
        
        # Get projects by tags
        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])
        
        # Get analytic accounts
        local_analytic_account_ids = local_projects.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_projects.mapped('analytic_account_id').ids
        
        # INFLOW: Customer Payments
        customer_payments = self.env['account.payment'].search([
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ])
        
        for payment in customer_payments:
            # Get related invoice
            invoices = payment.reconciled_invoice_ids
            
            for invoice in invoices:
                # Get invoice currency
                invoice_currency = invoice.currency_id
                invoice_date = invoice.invoice_date or invoice.date
                
                for line in invoice.invoice_line_ids:
                    if line.analytic_distribution:
                        try:
                            distribution = line.analytic_distribution
                            if not isinstance(distribution, dict):
                                distribution = json.loads(distribution) if distribution else {}
                            
                            for account_id_str, percentage in distribution.items():
                                account_id = int(account_id_str)
                                
                                # Convert line amount to company currency
                                amount_in_company_currency = invoice_currency._convert(
                                    line.price_subtotal,
                                    company_currency,
                                    self.env.company,
                                    invoice_date
                                )
                                
                                if account_id in local_analytic_account_ids:
                                    result['local_inflow'] += amount_in_company_currency
                                    break
                                elif account_id in export_analytic_account_ids:
                                    result['export_inflow'] += amount_in_company_currency
                                    break

                        except Exception as e:
                            _logger.error("Error processing analytic distribution for invoice %s, line %s: %s", 
                                        invoice.id, line.id, str(e))
            
        # OUTFLOW: Vendor Payments
        vendor_payments = self.env['account.payment'].search([
            ('payment_type', '=', 'outbound'),
            ('state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ])
        
        for payment in vendor_payments:
            # Get related bill
            bills = payment.reconciled_bill_ids

            for bill in bills:
                # Get bill currency
                bill_currency = bill.currency_id
                bill_date = bill.invoice_date or bill.date
                
                for line in bill.invoice_line_ids:
                    if line.analytic_distribution:
                        try:
                            distribution = line.analytic_distribution
                            if not isinstance(distribution, dict):
                                distribution = json.loads(distribution) if distribution else {}
                            
                            for account_id_str, percentage in distribution.items():
                                account_id = int(account_id_str)
                                
                                # Convert line amount to company currency
                                amount_in_company_currency = bill_currency._convert(
                                    line.price_subtotal,
                                    company_currency,
                                    self.env.company,
                                    bill_date
                                )
                                
                                if account_id in local_analytic_account_ids:
                                    result['local_outflow'] += amount_in_company_currency
                                    break
                                elif account_id in export_analytic_account_ids:
                                    result['export_outflow'] += amount_in_company_currency
                                    break
                                                    
                        except Exception as e:
                            _logger.error("Error processing analytic distribution for bill %s, line %s: %s", 
                                        bill.id, line.id, str(e))
            
        # Calculate totals
        result['inflows'] = result['local_inflow'] + result['export_inflow']
        result['outflows'] = result['local_outflow'] + result['export_outflow']
        result['net_cash_flow'] = result['inflows'] - result['outflows']
        
        return result
    
    def action_export_excel(self):
        """Export dashboard data to Excel with charts in a single sheet."""
        self.ensure_one()

        def _to_num(s):
            """Convert formatted string to numeric value."""
            if s is None:
                return 0.0
            if isinstance(s, (int, float)):
                return float(s)
            s = str(s).strip()
            if s in ('-', ''):
                return 0.0
            s = s.replace(',', '')
            if s.endswith('%'):
                try:
                    return float(s[:-1]) / 100.0
                except Exception:
                    return s
            try:
                return float(s)
            except Exception:
                return s

        data = self._get_dashboard_data()
        
        from io import BytesIO
        import base64
        from odoo.tools.misc import xlsxwriter

        output = BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})

        # Define formats
        f_title = wb.add_format({'bold': True, 'font_size': 14, 'font_color': '#1a1a1a'})
        f_subtitle = wb.add_format({'bold': True, 'font_size': 12, 'font_color': '#444444'})
        f_hdr = wb.add_format({'bold': True, 'bg_color': '#DDDDDD', 'border': 1, 'align': 'center'})
        f_txt = wb.add_format({'border': 1})
        f_num = wb.add_format({'num_format': '#,##0.00', 'border': 1})
        f_int = wb.add_format({'num_format': '0', 'border': 1})
        f_pct = wb.add_format({'num_format': '0.00%', 'border': 1})

        # Create single worksheet
        ws = wb.add_worksheet('Dashboard')
        ws.set_column('A:A', 25)
        ws.set_column('B:D', 16)

        row = 0

        # ========== HEADER SECTION ==========
        ws.write(row, 0, f"{data['company']['name']} - Dashboard Report", f_title)
        row += 1
        ws.write(row, 0, f"Period: {data['filters']['month_name'] or data['filters']['quarter'] or 'Full Year'} {data['filters']['year']}", f_txt)
        ws.write(row, 1, f"Currency: {data['company']['currency']}", f_txt)
        row += 2

        # ========== SALES METRICS ==========
        ws.write(row, 0, 'SALES OVERVIEW', f_subtitle)
        row += 1
        ws.write_row(row, 0, ['Metric', 'Value'], f_hdr)
        row += 1

        ws.write(row, 0, 'Sales Orders', f_txt)
        ws.write(row, 1, _to_num(data['sales']['order_count']), f_int)
        row += 1

        ws.write(row, 0, 'Sales Amount', f_txt)
        ws.write(row, 1, _to_num(data['sales']['amount']), f_num)
        row += 1

        ws.write(row, 0, 'Sales Target', f_txt)
        ws.write(row, 1, _to_num(data['sales']['target']), f_num)
        row += 1

        ws.write(row, 0, 'Target Achievement', f_txt)
        ta = _to_num(data['sales']['target_achievement'])
        ws.write(row, 1, ta if isinstance(ta, float) else data['sales']['target_achievement'],
                f_pct if isinstance(ta, float) else f_txt)
        row += 2

        # ========== SALES BY REGION (Data + Chart) ==========
        ws.write(row, 0, 'Sales by Region', f_subtitle)
        row += 1
        
        chart_data_start = row
        ws.write_row(row, 0, ['Region', 'Amount'], f_hdr)
        row += 1

        sales_region_data_start = row
        for item in data['sales']['region_wise']['data']:
            ws.write(row, 0, item['name'], f_txt)
            ws.write(row, 1, _to_num(item['value']), f_num)
            row += 1
        sales_region_data_end = row - 1

        # Sales Pie Chart - positioned at D5
        sales_chart = wb.add_chart({'type': 'pie'})
        sales_chart.add_series({
            'name': 'Sales Distribution',
            'categories': ['Dashboard', sales_region_data_start, 0, sales_region_data_end, 0],
            'values': ['Dashboard', sales_region_data_start, 1, sales_region_data_end, 1],
            'points': [{'fill': {'color': color}} for color in data['sales']['region_wise']['colors']],
            'data_labels': {'percentage': True, 'position': 'best_fit'},
        })
        sales_chart.set_title({'name': 'Sales by Region'})
        sales_chart.set_size({'width': 400, 'height': 300})
        ws.insert_chart('F5', sales_chart)
        
        row += 1

        # ========== FINANCIAL METRICS ==========
        ws.write(row, 0, 'FINANCIAL OVERVIEW', f_subtitle)
        row += 1
        ws.write_row(row, 0, ['Metric', 'Value'], f_hdr)
        row += 1

        financial_metrics = [
            ('Revenue', data['revenue']['amount']),
            ('Cost of Revenue', data['revenue']['cost_of_revenue']),
            ('Gross Profit', data['revenue']['gross_profit']),
            ('Gross Profit Margin', data['revenue']['gross_profit_margin']),
            ('Expenses', data['revenue']['expenses']),
            ('Net Profit', data['revenue']['net_profit']),
            ('Net Profit Margin', data['revenue']['net_profit_margin']),
            ('Accounts Receivable', data['revenue']['accounts_receivable']),
            ('Accounts Payable', data['revenue']['accounts_payable']),
        ]

        for label, value in financial_metrics:
            ws.write(row, 0, label, f_txt)
            num_val = _to_num(value)
            if 'Margin' in label:
                ws.write(row, 1, num_val if isinstance(num_val, float) else value,
                        f_pct if isinstance(num_val, float) else f_txt)
            else:
                ws.write(row, 1, num_val, f_num)
            row += 1
        
        row += 1

        # ========== REVENUE BY REGION (Data + Chart) ==========
        ws.write(row, 0, 'Revenue by Region', f_subtitle)
        row += 1
        
        revenue_chart_start = row
        ws.write_row(row, 0, ['Region', 'Amount'], f_hdr)
        row += 1

        revenue_region_data_start = row
        for item in data['revenue']['region_wise']['data']:
            ws.write(row, 0, item['name'], f_txt)
            ws.write(row, 1, _to_num(item['value']), f_num)
            row += 1
        revenue_region_data_end = row - 1

        # Revenue Pie Chart - positioned at D22
        revenue_chart = wb.add_chart({'type': 'pie'})
        revenue_chart.add_series({
            'name': 'Revenue Distribution',
            'categories': ['Dashboard', revenue_region_data_start, 0, revenue_region_data_end, 0],
            'values': ['Dashboard', revenue_region_data_start, 1, revenue_region_data_end, 1],
            'points': [{'fill': {'color': color}} for color in data['revenue']['region_wise']['colors']],
            'data_labels': {'percentage': True, 'position': 'best_fit'},
        })
        revenue_chart.set_title({'name': 'Revenue by Region'})
        revenue_chart.set_size({'width': 400, 'height': 300})
        ws.insert_chart('F25', revenue_chart)
        
        row += 1

        # ========== EXPENSES BY REGION (Data + Chart) ==========
        ws.write(row, 0, 'Expenses by Region', f_subtitle)
        row += 1
        
        expenses_chart_start = row
        ws.write_row(row, 0, ['Region', 'Amount'], f_hdr)
        row += 1

        expenses_region_data_start = row
        for item in data['expenses']['region_wise']['data']:
            ws.write(row, 0, item['name'], f_txt)
            ws.write(row, 1, _to_num(item['value']), f_num)
            row += 1
        expenses_region_data_end = row - 1

        # Expenses Pie Chart - positioned at J22
        expenses_chart = wb.add_chart({'type': 'pie'})
        expenses_chart.add_series({
            'name': 'Expenses Distribution',
            'categories': ['Dashboard', expenses_region_data_start, 0, expenses_region_data_end, 0],
            'values': ['Dashboard', expenses_region_data_start, 1, expenses_region_data_end, 1],
            'points': [{'fill': {'color': color}} for color in data['expenses']['region_wise']['colors']],
            'data_labels': {'percentage': True, 'position': 'best_fit'},
        })
        expenses_chart.set_title({'name': 'Expenses by Region'})
        expenses_chart.set_size({'width': 400, 'height': 300})
        ws.insert_chart('M25', expenses_chart)
        
        row += 1

        # ========== CASH FLOW SECTION ==========
        ws.write(row, 0, 'CASH FLOW ANALYSIS', f_subtitle)
        row += 1
        
        cashflow_chart_start = row
        ws.write_row(row, 0, ['Type', 'Export', 'Local', 'Total'], f_hdr)
        row += 1

        cashflow_data_start = row
        
        # Inflow
        export_in = next((x['value'] for x in data['cash_flow']['region_wise']['inflow'] if x['name'] == 'Export'), 0.0)
        local_in = next((x['value'] for x in data['cash_flow']['region_wise']['inflow'] if x['name'] == 'Local'), 0.0)
        
        ws.write(row, 0, 'Inflow', f_txt)
        ws.write(row, 1, _to_num(export_in), f_num)
        ws.write(row, 2, _to_num(local_in), f_num)
        ws.write(row, 3, _to_num(export_in) + _to_num(local_in), f_num)
        row += 1

        # Outflow
        export_out = next((x['value'] for x in data['cash_flow']['region_wise']['outflow'] if x['name'] == 'Export'), 0.0)
        local_out = next((x['value'] for x in data['cash_flow']['region_wise']['outflow'] if x['name'] == 'Local'), 0.0)
        
        ws.write(row, 0, 'Outflow', f_txt)
        ws.write(row, 1, _to_num(export_out), f_num)
        ws.write(row, 2, _to_num(local_out), f_num)
        ws.write(row, 3, _to_num(export_out) + _to_num(local_out), f_num)
        row += 1
        
        cashflow_data_end = row - 1

        # Net Cash Flow
        ws.write(row, 0, 'Net Cash Flow', f_txt)
        ws.write(row, 1, _to_num(export_in) - _to_num(export_out), f_num)
        ws.write(row, 2, _to_num(local_in) - _to_num(local_out), f_num)
        ws.write(row, 3, (_to_num(export_in) + _to_num(local_in)) - (_to_num(export_out) + _to_num(local_out)), f_num)

        # Cash Flow Column Chart
        cashflow_chart = wb.add_chart({'type': 'column'})
        
        # Add Export series
        cashflow_chart.add_series({
            'name': 'Export',
            'categories': ['Dashboard', cashflow_data_start, 0, cashflow_data_end, 0],
            'values': ['Dashboard', cashflow_data_start, 1, cashflow_data_end, 1],
            'fill': {'color': '#1e88e5'},
        })
        
        # Add Local series
        cashflow_chart.add_series({
            'name': 'Local',
            'categories': ['Dashboard', cashflow_data_start, 0, cashflow_data_end, 0],
            'values': ['Dashboard', cashflow_data_start, 2, cashflow_data_end, 2],
            'fill': {'color': '#ff8f00'},
        })
        
        cashflow_chart.set_title({'name': 'Cash Flow: Inflow vs Outflow'})
        cashflow_chart.set_x_axis({'name': 'Type'})
        cashflow_chart.set_y_axis({'name': 'Amount', 'num_format': '#,##0'})
        cashflow_chart.set_size({'width': 500, 'height': 350})
        cashflow_chart.set_legend({'position': 'bottom'})
        
        # ws.insert_chart(cashflow_chart_start, 5, cashflow_chart)
        ws.insert_chart('M5', cashflow_chart)

        # Close workbook and prepare download
        wb.close()
        output.seek(0)

        # Generate filename
        period = data['filters']['month_name'] or data['filters']['quarter'] or 'FullYear'
        filename = f"Dashboard_{data['filters']['year']}_{period}.xlsx"

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }

