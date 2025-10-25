import json
import logging
from datetime import datetime

from odoo import api, fields, models, _
from odoo.tools import float_round

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
        
        sales_data = self._compute_sales_dashboard_metrics(start_date, end_date)
        financial_data = self._compute_financial_dashboard_metrics(start_date, end_date)

        return {
            'overview': {
                'sales_target': self._format_amount(sales_data['sales_target']),
                'total_achieved': self._format_amount(sales_data['total_sales']),
                'sales_order': sales_data['order_count'],
                'target': self._format_amount(sales_data['sales_target']),
                'achieved': self._format_amount(sales_data['total_sales']),
                'ratio': sales_data['target_achievement_ratio'],
                'total_revenue': self._format_amount(financial_data['total_revenue']),
                'cost_of_revenue': self._format_amount(financial_data['cost_of_revenue']),
                'gross_profit': self._format_amount(financial_data['gross_profit']),
                'gross_margin': f"{financial_data['gross_profit_margin']}%",
                'total_expenses': self._format_amount(financial_data['total_expenses']),
                'net_profit': self._format_amount(financial_data['net_profit']),
                'net_margin': f"{financial_data['net_profit_margin']}%",
                'accounts_receivable': self._format_amount(financial_data['accounts_receivable']),
                'accounts_payable': self._format_amount(financial_data['accounts_payable']),
                'net_postion': self._format_amount(
                    financial_data['accounts_receivable'] - financial_data['accounts_payable']
                ),
            },
            'sales': {
                'monthly_sales': sales_data['monthly_sales'],
            },
            'revenue_expenses': {
                'monthly_revenue': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],  # Placeholder for monthly revenue data
                'monthly_expenses': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],  # Placeholder for monthly expenses data
            },
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

    def _format_amount(self, amount):
        """Format amount to match the dashboard display format"""
        return f"{float_round(round(amount, 2), 2):,.2f}"
    
    def _compute_sales_dashboard_metrics(self, start_date, end_date):
        """Compute key sales metrics (count, total, target) for the dashboard within a given date range."""
        
        company = self.env.company
        company_currency = company.currency_id

        # Fetch confirmed or done sales orders for the specified period and company
        sale_orders = self.env['sale.order'].search([
            ('date_order', '>=', start_date),
            ('date_order', '<=', end_date),
            ('company_id', '=', company.id),
            ('state', 'in', ['sale', 'done']),
        ])

        total_orders = len(sale_orders)
        total_sales_amount = 0.0
        monthly_sales_distribution = [0.0] * 12  # index 0 => January, ..., 11 => December

        for order in sale_orders:
            converted_amount = order.currency_id._convert(
                order.amount_untaxed,
                company_currency,
                company,
                order.date_order
            )
            total_sales_amount += converted_amount
            monthly_sales_distribution[order.date_order.month - 1] += converted_amount

        yearly_sales_target = self._get_yearly_sales_target() or 0.0

        if total_sales_amount >= 10_000_000.00:
            target_achievement_ratio = 100
        elif total_sales_amount >= 8_000_000.00:
            target_achievement_ratio = 80
        elif total_sales_amount >= 6_000_000.00:
            target_achievement_ratio = 60
        elif total_sales_amount >= 4_000_000.00:
            target_achievement_ratio = 40
        elif total_sales_amount >= 2_000_000.00:
            target_achievement_ratio = 20
        else:
            target_achievement_ratio = 0

        return {
            'order_count': total_orders,
            'total_sales': total_sales_amount,
            'sales_target': yearly_sales_target,
            'target_achievement_ratio': target_achievement_ratio,
            'monthly_sales': monthly_sales_distribution,
        }
    
    def _compute_financial_dashboard_metrics(self, start_date, end_date):
        """Compute key financial metrics (revenue, profit, margins, receivables, payables) for the dashboard."""

        # === Core financial figures ===
        total_revenue = self._compute_untaxed_revenue(start_date, end_date)
        total_expenses = self._compute_untaxed_expenses(start_date, end_date)
        cost_of_revenue = self._calculate_cost_of_revenue(start_date, end_date)

        # === Profit Calculations ===
        gross_profit = total_revenue - cost_of_revenue
        net_profit = gross_profit - total_expenses

        # === Profit Margin Calculations (safe division) ===
        gross_profit_margin = round((gross_profit / total_revenue) * 100, 2) if total_revenue else 0.0
        net_profit_margin = round((net_profit / total_revenue) * 100, 2) if total_revenue else 0.0

        # === Balance Sheet Components ===
        accounts_receivable = self._calculate_accounts_receivable(start_date, end_date)
        accounts_payable = self._calculate_accounts_payable(start_date, end_date)

        # === Structured Response ===
        return {
            'total_revenue': total_revenue,
            'total_expenses': abs(total_expenses),
            'cost_of_revenue': cost_of_revenue,
            'gross_profit': gross_profit,
            'gross_profit_margin': gross_profit_margin,
            'net_profit': net_profit,
            'net_profit_margin': net_profit_margin,
            'accounts_receivable': accounts_receivable,
            'accounts_payable': accounts_payable,
        }

    def _compute_untaxed_expenses(self, start_date, end_date):
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

    def _compute_untaxed_revenue(self, start_date, end_date):
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

    def _calculate_cost_of_revenue(self, start_date, end_date):
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

    def _calculate_accounts_receivable(self, start_date, end_date):
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

    def _calculate_accounts_payable(self, start_date, end_date):
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
