import json
import logging
from datetime import datetime
import io
import base64

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
        revenue_expenses_data = self._compute_revenue_expenses_dashboard_metrics(start_date, end_date)
        cashflow_data = self._compute_cashflow_dashboard_metrics(start_date, end_date)

        return {
            'filter': {
                'year': sel_year
            },
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
            'revenue_expenses': revenue_expenses_data,
            'cashflow': cashflow_data,
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

        target_achievement_ratio = 0
        if yearly_sales_target:
            target_achievement_ratio = round(total_sales_amount / yearly_sales_target, 2)

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
            ('account_id.account_type', 'in', ['income', 'income_other']),
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

    def _compute_revenue_expenses_dashboard_metrics(self, start_date, end_date):
        """Compute monthly revenue and expenses for the dashboard within a given date range."""
        
        # Initialize monthly data with zeros for all 12 months
        monthly_revenue = [0] * 12
        monthly_expenses = [0] * 12
        
        # Fetch all invoices in the date range for the company
        domain = [
            ('company_id', '=', self.company_id.id),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('state', '=', 'posted'),  # Only posted invoices
        ]
        
        # Get customer invoices (revenue) - out_invoice and out_refund
        customer_invoices = self.env['account.move'].search(
            domain + [('move_type', 'in', ['out_invoice', 'out_refund'])]
        )
        
        # Get vendor bills (expenses) - in_invoice and in_refund
        vendor_bills = self.env['account.move'].search(
            domain + [('move_type', 'in', ['in_invoice', 'in_refund'])]
        )
        
        # Process customer invoices (Revenue)
        for invoice in customer_invoices:
            month_index = invoice.invoice_date.month - 1  # 0-based index
            
            # Handle invoices vs credit notes
            if invoice.move_type == 'out_invoice':
                monthly_revenue[month_index] += invoice.amount_untaxed_signed
            elif invoice.move_type == 'out_refund':
                monthly_revenue[month_index] -= invoice.amount_untaxed_signed
        
        # Process vendor bills (Expenses)
        for bill in vendor_bills:
            month_index = bill.invoice_date.month - 1  # 0-based index
            
            # Handle bills vs refunds
            if bill.move_type == 'in_invoice':
                monthly_expenses[month_index] += abs(bill.amount_untaxed_signed)
            elif bill.move_type == 'in_refund':
                monthly_expenses[month_index] -= abs(bill.amount_untaxed_signed)
        
        # Round values to 2 decimal places
        monthly_revenue = [round(amount, 2) for amount in monthly_revenue]
        monthly_expenses = [round(amount, 2) for amount in monthly_expenses]
        monthly_ebt = [round(r - e, 2) for r, e in zip(monthly_revenue, monthly_expenses)]
        
        return {
            'monthly_revenue': monthly_revenue,
            'monthly_expenses': monthly_expenses,
            'monthly_ebt': monthly_ebt,
        }

    def _compute_cashflow_dashboard_metrics(self, start_date, end_date):
        """Compute monthly cash inflows and outflows for the dashboard within a given date range."""
        
        # Initialize monthly data
        monthly_inflows = [0] * 12
        monthly_outflows = [0] * 12
        
        # Get cash and bank accounts
        cash_accounts = self.env['account.account'].search([
            ('company_id', '=', self.company_id.id),
            ('account_type', 'in', ['asset_cash', 'asset_current']),
            ('internal_group', '=', 'asset')
        ])
        
        if not cash_accounts:
            _logger.warning('No cash/bank accounts found for company %s', self.company_id.name)
            return {
                'monthly_inflows': monthly_inflows,
                'monthly_outflows': monthly_outflows,
            }
        
        # SQL query for cash movements
        query = """
            SELECT 
                EXTRACT(MONTH FROM aml.date) as month,
                SUM(CASE WHEN aml.debit > 0 THEN aml.debit ELSE 0 END) as inflow,
                SUM(CASE WHEN aml.credit > 0 THEN aml.credit ELSE 0 END) as outflow
            FROM 
                account_move_line aml
            INNER JOIN 
                account_move am ON aml.move_id = am.id
            WHERE 
                aml.company_id = %s
                AND aml.date >= %s
                AND aml.date <= %s
                AND am.state = 'posted'
                AND aml.account_id IN %s
                AND aml.parent_state = 'posted'
            GROUP BY 
                EXTRACT(MONTH FROM aml.date)
            ORDER BY 
                month
        """
        
        self.env.cr.execute(query, (
            self.company_id.id,
            start_date,
            end_date,
            tuple(cash_accounts.ids)
        ))
        
        results = self.env.cr.dictfetchall()
        
        # Process results
        for row in results:
            month_index = int(row['month']) - 1
            monthly_inflows[month_index] = round(row['inflow'] or 0, 2)
            monthly_outflows[month_index] = round(row['outflow'] or 0, 2)
        
        return {
            'monthly_inflows': monthly_inflows,
            'monthly_outflows': monthly_outflows,
        }

    def action_export_excel(self):
        self.ensure_one()
        data = self._get_dashboard_data()

        import xlsxwriter, io, base64
        from xlsxwriter.utility import xl_rowcol_to_cell
        buf = io.BytesIO()
        wb = xlsxwriter.Workbook(buf, {'in_memory': True})

        # ========= Formats =========
        F_TITLE = wb.add_format({'bold': True, 'font_size': 16})
        F_SUB   = wb.add_format({'bold': True, 'font_size': 12, 'font_color': '#666666'})
        F_KPI_T = wb.add_format({'bold': True, 'font_size': 11})
        F_KPI_V = wb.add_format({'bold': True, 'font_size': 12, 'align': 'right'})
        F_MONEY = wb.add_format({'num_format': '#,##0.00', 'align': 'right'})
        F_PCT   = wb.add_format({'num_format': '0.0%', 'align': 'right'})
        F_BOX   = wb.add_format({'border': 1, 'bg_color': '#FFFFFF'})
        F_HEAD  = wb.add_format({'bold': True, 'bg_color': '#F2F2F2', 'border': 1})
        F_GOOD  = wb.add_format({'font_color': '#1E7E34', 'bold': True, 'align': 'right'})
        F_BAD   = wb.add_format({'font_color': '#C82333', 'bold': True, 'align': 'right'})

        # ========= Sheets =========
        sh  = wb.add_worksheet('Dashboard')
        dat = wb.add_worksheet('Data'); dat.hide()

        # ========= Helpers =========
        def _to_num(v):
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                s = v.replace(',', '').strip()
                if s.endswith('%'):
                    try:
                        return float(s[:-1]) / 100.0
                    except Exception:
                        return None
                try:
                    return float(s)
                except Exception:
                    return None
            return None

        def paint_box(ws, r1, c1, r2, c2):
            """Fill a rectangle with bordered blank cells (no merge)."""
            for r in range(r1, r2 + 1):
                for c in range(c1, c2 + 1):
                    ws.write_blank(r, c, None, F_BOX)

        # ========= Data prep =========
        months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
        sales = (data.get('sales', {}) or {}).get('monthly_sales', [0]*12)
        rexp  = data.get('revenue_expenses', {}) or {}
        rev   = rexp.get('monthly_revenue', [0]*12)
        exp   = rexp.get('monthly_expenses', [0]*12)
        cf    = data.get('cashflow', {}) or {}
        infl  = cf.get('monthly_inflows', [0]*12)
        outf  = cf.get('monthly_outflows', [0]*12)
        ov    = data.get('overview', {}) or {}

        # Data sheet rows
        dat.write(0, 0, 'Months', F_HEAD); dat.write_row(0, 1, months, F_HEAD)
        dat.write(1, 0, 'Sales', F_HEAD);  dat.write_row(1, 1, sales)
        dat.write(3, 0, 'Revenue', F_HEAD); dat.write_row(3, 1, rev)
        dat.write(4, 0, 'Expenses', F_HEAD); dat.write_row(4, 1, exp)
        dat.write(6, 0, 'Inflows', F_HEAD);  dat.write_row(6, 1, infl)
        dat.write(7, 0, 'Outflows', F_HEAD); dat.write_row(7, 1, outf)

        # ========= Layout =========
        sh.set_column('A:A', 2)          # gutter
        sh.set_column('B:I', 13)
        sh.set_column('J:J', 2)          # spacer
        sh.set_column('K:R', 13)

        # Header
        sh.merge_range('B2:I2', 'L1 Dashboard', F_TITLE)
        sh.write('Q2', 'Year:', F_SUB); sh.write('R2', self.year or '')
        sh.merge_range('B4:R4', 'Company Financial Overview', F_SUB)

        # --- Card grids (no big merges) ---
        # Coordinates are 0-indexed here: row, col
        # Card 1 area: B6:I16  -> rows 5..15, cols 1..8
        paint_box(sh, 5, 1, 15, 8)
        sh.write(6, 2, 'Sales', F_KPI_T)
        sh.write(9,  2, 'Sales Target');   sh.write_number(9,  7, _to_num(ov.get('sales_target')) or 0.0, F_MONEY)
        sh.write(11, 2, 'Total Achieved'); sh.write_number(11, 7, _to_num(ov.get('total_achieved')) or 0.0, F_MONEY)
        sh.write(13, 2, 'Sales Order');    sh.write_number(13, 7, _to_num(ov.get('sales_order')) or 0.0, F_KPI_V)

        # Card 2 area: K6:R16 -> rows 5..15, cols 10..17
        paint_box(sh, 5, 10, 15, 17)
        sh.write(6, 11, 'Target Achievement', F_KPI_T)
        sh.write(9,  11, 'Achieved'); sh.write_number(9,  16, _to_num(ov.get('achieved')) or 0.0, F_MONEY)
        sh.write(11, 11, 'Target');   sh.write_number(11, 16, _to_num(ov.get('target')) or 0.0, F_MONEY)
        ratio_num = _to_num(f"{ov.get('ratio', 0)}%") if isinstance(ov.get('ratio'), (int, float)) else _to_num(ov.get('ratio') or '')
        sh.write(13, 11, 'Achievement Ratio')
        if ratio_num is not None:
            sh.write_number(13, 16, ratio_num, F_PCT)
        else:
            sh.write(13, 16, ov.get('ratio') or '', F_KPI_V)

        # Card 3 area: B18:I30 -> rows 17..29, cols 1..8
        paint_box(sh, 17, 1, 29, 8)
        sh.write(18, 2, 'Revenue & Profit', F_KPI_T)
        sh.write(21, 2, 'Revenue');         sh.write_number(21, 7, _to_num(ov.get('total_revenue')) or 0.0, F_MONEY)
        cor = _to_num(ov.get('cost_of_revenue'))
        sh.write(23, 2, 'Cost of Revenue'); sh.write_number(23, 7, cor if cor is not None else 0.0, F_BAD if (cor or 0) > 0 else F_MONEY)
        sh.write(25, 2, 'Gross Profit');    sh.write_number(25, 7, _to_num(ov.get('gross_profit')) or 0.0, F_GOOD)
        gm = _to_num(ov.get('gross_margin') or '')
        sh.write(27, 2, 'Gross Margin')
        if gm is not None:
            sh.write_number(27, 7, gm, F_PCT)
        else:
            sh.write(27, 7, ov.get('gross_margin') or '', F_KPI_V)

        # Card 4 area: K18:R30 -> rows 17..29, cols 10..17
        paint_box(sh, 17, 10, 29, 17)
        sh.write(18, 11, 'Expenses & Net Profit', F_KPI_T)
        sh.write(21, 11, 'Expenses');   sh.write_number(21, 16, _to_num(ov.get('total_expenses')) or 0.0, F_BAD)
        npf = _to_num(ov.get('net_profit'))
        sh.write(23, 11, 'Net Profit'); sh.write_number(23, 16, npf if npf is not None else 0.0, F_GOOD if (npf or 0) >= 0 else F_BAD)
        nm = _to_num(ov.get('net_margin') or '')
        sh.write(25, 11, 'Net Margin')
        if nm is not None:
            sh.write_number(25, 16, nm, F_PCT)
        else:
            sh.write(25, 16, ov.get('net_margin') or '', F_KPI_V)

        # Row 3.5: Receivable & Payable (B32:R42 -> rows 31..41, cols 1..17)
        paint_box(sh, 31, 1, 41, 17)
        sh.write(32, 2, 'Receivable & Payable', F_KPI_T)
        sh.write(35, 2,  'Accounts Receivable'); sh.write_number(35, 7,  _to_num(ov.get('accounts_receivable')) or 0.0, F_MONEY)
        sh.write(35, 12, 'Accounts Payable');    sh.write_number(35, 16, _to_num(ov.get('accounts_payable')) or 0.0, F_MONEY)
        net_pos = _to_num(ov.get('net_postion'))
        sh.write(37, 2, 'Net Position')
        if net_pos is not None:
            sh.write_number(37, 7, net_pos, F_GOOD if net_pos >= 0 else F_BAD)
        else:
            sh.write(37, 7, ov.get('net_postion') or '', F_KPI_V)

        # ========= Charts =========
        ch_sales = wb.add_chart({'type': 'column'})
        ch_sales.set_title({'name': 'Sales Performance'})
        ch_sales.set_legend({'position': 'top'})
        ch_sales.add_series({
            'name': 'Sales',
            'categories': "=Data!$B$1:$M$1",
            'values':     "=Data!$B$2:$M$2",
            'gap': 30,
        })
        ch_sales.set_y_axis({'major_gridlines': {'visible': False}})
        sh.insert_chart('B44', ch_sales, {'x_scale': 1.45, 'y_scale': 1.2})

        ch_re = wb.add_chart({'type': 'line'})
        ch_re.set_title({'name': 'Revenue, Expenses and EBT'})
        ch_re.set_legend({'position': 'top'})
        ch_re.add_series({'name': 'Revenue',  'categories': "=Data!$B$1:$M$1", 'values': "=Data!$B$4:$M$4", 'marker': {'type': 'circle'}})
        ch_re.add_series({'name': 'Expenses', 'categories': "=Data!$B$1:$M$1", 'values': "=Data!$B$5:$M$5", 'marker': {'type': 'circle'}})
        ch_re.set_y_axis({'major_gridlines': {'visible': False}})
        sh.insert_chart('B70', ch_re, {'x_scale': 1.45, 'y_scale': 1.2})

        ch_cf = wb.add_chart({'type': 'area'})
        ch_cf.set_title({'name': 'Cash Flow (Incoming and Outgoing)'})
        ch_cf.set_legend({'position': 'top'})
        ch_cf.add_series({'name': 'Cash Inflows',  'categories': "=Data!$B$1:$M$1", 'values': "=Data!$B$7:$M$7"})
        ch_cf.add_series({'name': 'Cash Outflows', 'categories': "=Data!$B$1:$M$1", 'values': "=Data!$B$8:$M$8"})
        ch_cf.set_y_axis({'major_gridlines': {'visible': False}})
        sh.insert_chart('B96', ch_cf, {'x_scale': 1.45, 'y_scale': 1.2})

        wb.close()
        buf.seek(0)
        datas = base64.b64encode(buf.read())

        att = self.env['ir.attachment'].create({
            'name': f"L1_Dashboard_{self.year or fields.Date.today().year}.xlsx",
            'type': 'binary',
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'datas': datas,
            'res_model': self._name,
            'res_id': self.id,
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/{att.id}?download=1",
            'target': 'self',
        }

        
        
    @api.onchange('year')
    def _onchange_year(self):
        # live-refresh the JSON used by the widget when Year changes
        for rec in self:
            rec.dashboard_data = json.dumps(rec._get_dashboard_data())
            rec.last_update = fields.Datetime.now()