import json
import logging
from datetime import datetime
import base64
import io
import xlsxwriter

from odoo import api, fields, models, _
from odoo.tools import date_utils, float_round

_logger = logging.getLogger(__name__)


class DashboardReports(models.Model):
    _name = 'druksmart_dashboard.reports'
    _description = 'DrukSmart Dashboard Reports'

    name = fields.Char(string='Dashboard Name', default='Reports')
    category = fields.Selection([
        ('sales', 'Sales'),
        ('revenue', 'Revenue'),
        ('expense', 'Expense'),
        ('cashflow', 'Cashflow'),
    ], string='Category', default='sales', required=True, help="Category of the dashboard report")
    
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

    @api.onchange('category', 'year', 'month', 'quarter')
    def _onchange_dashboard_trigger(self):
        if self:
            self._compute_dashboard_data()

    @api.depends('category', 'year', 'month', 'company_id', "quarter")
    def _compute_dashboard_data(self):
        for record in self:
            record.dashboard_data = json.dumps(record._get_dashboard_data())
            record.last_update = fields.Datetime.now()

    @api.model
    def get_dashboard_data_json(self, category, year=None, month=None, quarter=None):
        """API method to get dashboard data in JSON format"""

        if not year:
            year = str(fields.Date.today().year)
            
        dashboard = self.search([
            ('category', '=', category),
            ('year', '=', str(year)),
            ('month', '=', month),
            ('quarter', '=', quarter),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not dashboard:
            dashboard = self.create({
                'category': category,
                'year': str(year),
                'month': month,
                'quarter': quarter,
            })
        
        dashboard._compute_dashboard_data()
        return dashboard.dashboard_data

    def _get_dashboard_data(self):
        """Compute all dashboard data and return as a structured dictionary"""
        self.ensure_one()
        
        category = self.category
        month = int(self.month) if self.month else 0
        year = int(self.year) if self.year else datetime.now().year
        quarter = self.quarter
        
        # Calculate date ranges
        if quarter == 'Q1':
            start_date = fields.Date.to_string(datetime(year, 1, 1))
            end_date = fields.Date.to_string(datetime(year, 3, 31))
        elif quarter == 'Q2':
            start_date = fields.Date.to_string(datetime(year, 4, 1))
            end_date = fields.Date.to_string(datetime(year, 6, 30))
        elif quarter == 'Q3':
            start_date = fields.Date.to_string(datetime(year, 7, 1))
            end_date = fields.Date.to_string(datetime(year, 9, 30))
        elif quarter == 'Q4':
            start_date = fields.Date.to_string(datetime(year, 10, 1))
            end_date = fields.Date.to_string(datetime(year, 12, 31))
        elif month == 0:
            start_date = fields.Date.to_string(datetime(year, 1, 1))
            end_date = fields.Date.to_string(datetime(year, 12, 31))
        else:
            start_date = fields.Date.to_string(date_utils.start_of(datetime(year, month, 1), 'month'))
            end_date = fields.Date.to_string(date_utils.end_of(datetime(year, month, 1), 'month'))

        response = {
            'filters': {
                'category': category,
                'quarter': quarter,
                'year': year,
                'month': month,
                'month_name': dict(self._fields['month'].selection).get(self.month),
            },
            'company': {
                'name': self.company_id.name,
                'currency': self.currency_id.symbol,
                'country': self.company_id.country_id.name,
            }
        }
        
        # Initialize empty data structures for all categories
        response['sales_data'] = {
            'sales': [],
            'total_sales_local_untaxed': 0,
            'total_sales_export_untaxed': 0,
        }
        response['revenue_data'] = {
            'revenues': [],
            'total_local_revenue_untaxed': 0,
            'total_export_revenue_untaxed': 0,
        }
        response['expense_data'] = {
            'expenses': [],
            'total_local_expense_untaxed': 0,
            'total_export_expense_untaxed': 0,
        }
        response['cashflow_data'] = {
            'cashflows': {},
            'total_local_cashflow_inflow': 0,
            'total_export_cashflow_inflow': 0,
            'total_local_cashflow_outflow': 0,
            'total_export_cashflow_outflow': 0,
            'net_local_cashflow': 0,
            'net_export_cashflow': 0,
            'total_net_cashflow': 0,
        }
        
        # Populate data based on category
        if category == 'sales':
            sales_data = self._get_sales_data(start_date, end_date)
            response['sales_data'] = sales_data
        elif category == 'revenue':
            revenue_data = self._get_revenue_data(start_date, end_date)
            response['revenue_data'] = revenue_data
        elif category == 'expense':
            expense_data = self.get_expense_data(start_date, end_date)
            response['expense_data'] = expense_data
        elif category == 'cashflow':
            cashflow_data = self.get_cashflow_data(start_date, end_date)
            response['cashflow_data'] = cashflow_data

        return response
    
    def _format_amount(self, amount):
        """Format amount to match the dashboard display format"""
        return f"{float_round(round(amount, 2), 2):,.2f}"
    
    def _get_sales_data(self, start_date, end_date):
        """Get sales related data for dashboard reports"""
        # Query sale orders within the date range
        domain = [
            ('date_order', '>=', start_date),
            ('date_order', '<=', end_date),
            ('state', 'in', ['sale', 'done']),  # Only confirmed sales
            ('company_id', '=', self.company_id.id)
        ]
        
        sale_orders = self.env['sale.order'].search(domain, order='date_order desc')

        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])

        local_analytic_account_ids = local_projects.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_projects.mapped('analytic_account_id').ids
        
        sale_id_counter = 1
        sales_data = []

        total_local_untaxed = 0.0
        total_export_untaxed = 0.0
        total_other_untaxed = 0.0  # Added Other category total

        total_local_untaxed_not_converted = 0.0
        total_export_untaxed_not_converted = 0.0
        total_other_untaxed_not_converted = 0.0  # Added Other category total
        
        for sale_order in sale_orders:
            # Case 1: Sale order has project_ids
            if sale_order.project_ids:
                project = sale_order.project_ids[0]
                tags = ", ".join(project.tag_ids.mapped('name')) if project.tag_ids else ""
                
                # Calculate untaxed amount
                untaxed_amount = 0.0
                for line in sale_order.order_line:
                    untaxed_amount += line.price_subtotal
                
                if not untaxed_amount:
                    untaxed_amount = sale_order.amount_untaxed
                
                # Determine if it's Local, Export, or Other
                if project in local_projects:
                    local_export = "Local"
                elif project in export_projects:
                    local_export = "Export"
                else:
                    local_export = "Other"  # Changed from continue to include Other
                
                if self.env.company.currency_id != sale_order.currency_id:
                    converted_amount = sale_order.currency_id._convert(
                        untaxed_amount,
                        self.company_id.currency_id,
                        self.company_id,
                        sale_order.date_order or fields.Date.today()
                    )
                else:
                    converted_amount = untaxed_amount

                comapany_currancy_icon = self.company_id.currency_id.symbol or ''
                sale_currancy_icon = sale_order.currency_id.symbol or ''

                sales_data.append({
                    "id": sale_id_counter,
                    "date": sale_order.date_order.strftime('%Y-%m-%d'),
                    "sales_order_no": sale_order.name,
                    "local_export": local_export,
                    "tags": tags,
                    "customer": sale_order.partner_id.name,
                    "sale_person": sale_order.user_id.name,
                    "untaxed_amount": f"{sale_currancy_icon}{self._format_amount(untaxed_amount)}",
                    "converted_amount": f"{comapany_currancy_icon}{self._format_amount(converted_amount)}",
                })
                sale_id_counter += 1
                # Update totals - now includes Other
                if local_export == "Local":
                    total_local_untaxed += converted_amount
                    total_local_untaxed_not_converted += untaxed_amount
                elif local_export == "Export":
                    total_export_untaxed += converted_amount
                    total_export_untaxed_not_converted += untaxed_amount
                elif local_export == "Other":
                    total_other_untaxed += converted_amount
                    total_other_untaxed_not_converted += untaxed_amount
            
            # Case 2: Sale order has no project_ids - check analytic distribution
            else:
                order_lines = sale_order.order_line
                regions_found = set()
                all_tags = set()
                total_untaxed_amount = 0.0
                has_analytic_distribution = False
                
                for line in order_lines:
                    if line.analytic_distribution:
                        has_analytic_distribution = True
                        try:
                            distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                                else eval(line.analytic_distribution)
                            
                            for account_id, percentage in distribution.items():
                                account_id = int(account_id)
                                
                                if account_id in local_analytic_account_ids:
                                    regions_found.add("Local")
                                    # Find project that has this analytic account
                                    project = self.env['project.project'].search([
                                        ('analytic_account_id', '=', account_id)
                                    ], limit=1)
                                    if project and project.tag_ids:
                                        all_tags.update(project.tag_ids.mapped('name'))
                                elif account_id in export_analytic_account_ids:
                                    regions_found.add("Export")
                                    # Find project that has this analytic account
                                    project = self.env['project.project'].search([
                                        ('analytic_account_id', '=', account_id)
                                    ], limit=1)
                                    if project and project.tag_ids:
                                        all_tags.update(project.tag_ids.mapped('name'))
                                else:
                                    # Analytic account exists but is not Local or Export
                                    regions_found.add("Other")
                                    # Find project that has this analytic account
                                    project = self.env['project.project'].search([
                                        ('analytic_account_id', '=', account_id)
                                    ], limit=1)
                                    if project and project.tag_ids:
                                        all_tags.update(project.tag_ids.mapped('name'))
                                
                                total_untaxed_amount += line.price_subtotal * (percentage / 100)
                        
                        except Exception as e:
                            _logger.error(f"Error processing analytic distribution for order {sale_order.id}: {e}")
                    else:
                        # Line has no analytic distribution, add its amount
                        total_untaxed_amount += line.price_subtotal
                
                # Determine final region and tags
                if len(regions_found) == 1:
                    region = list(regions_found)[0]
                elif len(regions_found) > 1:
                    region = "Mixed"  # Has both Local and Export or other combinations
                elif has_analytic_distribution:
                    region = "Other"  # Has analytic distribution but not Local/Export
                else:
                    region = "Other"  # Changed from "Unclassified" to "Other"
                
                tags = ", ".join(sorted(all_tags))
                
                # Use calculated amount or fallback to sale order amount
                if total_untaxed_amount == 0.0:
                    total_untaxed_amount = sale_order.amount_untaxed
                
                # No longer skip any sales - include all categories
                
                if self.env.company.currency_id != sale_order.currency_id:
                    converted_amount = sale_order.currency_id._convert(
                        total_untaxed_amount,
                        self.company_id.currency_id,
                        self.company_id,
                        sale_order.date_order or fields.Date.today()
                    )
                else:
                    converted_amount = total_untaxed_amount

                comapany_currancy_icon = self.company_id.currency_id.symbol or ''
                sale_currancy_icon = sale_order.currency_id.symbol or ''

                sales_data.append({
                    "id": sale_id_counter,
                    "date": sale_order.date_order.strftime('%Y-%m-%d'),
                    "sales_order_no": sale_order.name,
                    "local_export": region,
                    "tags": tags,
                    "customer": sale_order.partner_id.name,
                    "sale_person": sale_order.user_id.name,
                    "untaxed_amount": f"{sale_currancy_icon}{self._format_amount(total_untaxed_amount)}",
                    "converted_amount": f"{comapany_currancy_icon}{self._format_amount(converted_amount)}",
                })
                sale_id_counter += 1
                # Update totals - now includes Other and Mixed
                if region == "Local":
                    total_local_untaxed += converted_amount
                    total_local_untaxed_not_converted += total_untaxed_amount
                elif region == "Export":
                    total_export_untaxed += converted_amount
                    total_export_untaxed_not_converted += total_untaxed_amount
                else:  # Other, Mixed, or any other category
                    total_other_untaxed += converted_amount
                    total_other_untaxed_not_converted += total_untaxed_amount

        company_currancy_icon = self.company_id.currency_id.symbol or ''
        total_sales_untaxed = total_local_untaxed + total_export_untaxed + total_other_untaxed

        return {
            'sales': sales_data,
            'total_sales_local_untaxed': f"{company_currancy_icon}{self._format_amount(total_local_untaxed)}",
            'total_sales_export_untaxed': f"{company_currancy_icon}{self._format_amount(total_export_untaxed)}",
            'total_sales_other_untaxed': f"{company_currancy_icon}{self._format_amount(total_other_untaxed)}",  # Added Other total
            'total_sales_local_untaxed_not_converted': f"{self._format_amount(total_local_untaxed_not_converted)}",
            'total_sales_export_untaxed_not_converted': f"{self._format_amount(total_export_untaxed_not_converted)}",
            'total_sales_other_untaxed_not_converted': f"{self._format_amount(total_other_untaxed_not_converted)}",  # Added Other total
            'total_sales_untaxed': f"{company_currancy_icon}{self._format_amount(total_sales_untaxed)}"  # Added Other total
        }
    
    def _get_revenue_data(self, start_date, end_date):
        """Get revenue data for the dashboard"""
        # Find project tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        # Get posted customer invoices in the date range
        invoice_domain = [
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]
        customer_invoices = self.env['account.move'].search(invoice_domain)

        revenues = []
        total_local_revenue = 0.0
        total_export_revenue = 0.0
        total_other_revenue = 0.0
        total_local_revenue_signed = 0.0
        total_export_revenue_signed = 0.0
        total_other_revenue_signed = 0.0

        payment_state_mapping = {
            'paid': 'Paid',
            'not_paid': 'Not Paid',
            'in_payment': 'In Payment',
            'partial': 'Partially Paid',
            'reversed': 'Reversed',
        }

        revenue_id_counter = 1

        for invoice in customer_invoices:
            # Skip if no valid date
            if not invoice.invoice_date:
                _logger.warning(f"Invoice {invoice.name} has no valid date, skipping")
                continue

            # Get the invoice's untaxed amount
            invoice_amount = invoice.amount_untaxed_signed
            invoice_amount_signed = invoice.amount_total_signed
            
            # Skip zero or negative amount invoices
            if invoice_amount <= 0:
                continue

            # Find linked project
            linked_project = None
            invoice_category = "Other"
            invoice_tags = []

            # Method 1: Check if invoice has direct project_id field
            if hasattr(invoice, 'project_id') and invoice.project_id:
                linked_project = invoice.project_id
            
            # Method 2: Try to find project from invoice_origin (Sale Order)
            elif invoice.invoice_origin:
                sale_order = self.env['sale.order'].search([
                    ('name', '=', invoice.invoice_origin)
                ], limit=1)
                
                if sale_order and hasattr(sale_order, 'project_id') and sale_order.project_id:
                    linked_project = sale_order.project_id
            
            # Method 3: Check analytic account on invoice lines to find project
            if not linked_project:
                # Get analytic accounts from invoice lines
                analytic_account_ids = set()
                for line in invoice.invoice_line_ids:
                    if line.analytic_distribution:
                        try:
                            distribution = line.analytic_distribution
                            if isinstance(distribution, str):
                                distribution = json.loads(distribution)
                            
                            if isinstance(distribution, dict):
                                analytic_account_ids.update([int(acc_id) for acc_id in distribution.keys()])
                        except Exception as e:
                            _logger.error(f"Error parsing analytic distribution for invoice {invoice.name}: {e}")
                
                # Find project with matching analytic account
                if analytic_account_ids:
                    linked_project = self.env['project.project'].search([
                        ('analytic_account_id', 'in', list(analytic_account_ids))
                    ], limit=1)

            # Determine category based on project tags
            if linked_project and linked_project.tag_ids:
                project_tag_names = linked_project.tag_ids.mapped('name')
                invoice_tags = project_tag_names
                
                if local_tag and local_tag.name in project_tag_names:
                    invoice_category = "Local"
                elif export_tag and export_tag.name in project_tag_names:
                    invoice_category = "Export"
                else:
                    invoice_category = "Other"
            else:
                invoice_category = "Other"
                invoice_tags = []

            # Add revenue entry
            revenues.append({
                "id": revenue_id_counter,
                "date": invoice.invoice_date.strftime('%Y-%m-%d'),
                "invoice_no": invoice.name,
                "sales_order_no": invoice.invoice_origin or '',
                "local_export": invoice_category,
                "tags": ', '.join(sorted(invoice_tags)) if invoice_tags else '',
                "customer": invoice.partner_id.name or '',
                "untaxed_amount": self._format_amount(invoice_amount),
                "payment_status": payment_state_mapping.get(invoice.payment_state, invoice.payment_state or ''),
                "project": linked_project.name if linked_project else '',
            })
            revenue_id_counter += 1

            # Update category totals
            if invoice_category == "Local":
                total_local_revenue += invoice_amount
                total_local_revenue_signed += invoice_amount_signed
            elif invoice_category == "Export":
                total_export_revenue += invoice_amount
                total_export_revenue_signed += invoice_amount_signed
            else:
                total_other_revenue += invoice_amount
                total_other_revenue_signed += invoice_amount_signed

        total_revenue = total_local_revenue + total_export_revenue + total_other_revenue
        total_revenue_signed = total_local_revenue_signed + total_export_revenue_signed + total_other_revenue_signed

        return {
            'revenues': revenues,
            'total_local_revenue_untaxed': self._format_amount(total_local_revenue_signed),
            'total_export_revenue_untaxed': self._format_amount(total_export_revenue_signed),
            'total_other_revenue_untaxed': self._format_amount(total_other_revenue_signed),
            'total_local_revenue_untaxed_not_converted': self._format_amount(total_local_revenue),
            'total_export_revenue_untaxed_not_converted': self._format_amount(total_export_revenue),
            'total_other_revenue_untaxed_not_converted': self._format_amount(total_other_revenue),
            'total_revenue_untaxed': self._format_amount(total_revenue_signed)
        }

    def get_expense_data(self, start_date, end_date):
        """Get expense data for the dashboard"""
        # Find project tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        # Get posted vendor bills in the date range
        bill_domain = [
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]
        vendor_bills = self.env['account.move'].search(bill_domain)

        expenses = []
        total_local_expense = 0.0
        total_export_expense = 0.0
        total_other_expense = 0.0
        total_local_expense_signed = 0.0
        total_export_expense_signed = 0.0
        total_other_expense_signed = 0.0

        payment_state_mapping = {
            'paid': 'Paid',
            'not_paid': 'Not Paid',
            'in_payment': 'In Payment',
            'partial': 'Partially Paid',
            'reversed': 'Reversed',
        }

        expense_id_counter = 1

        for bill in vendor_bills:
            # Skip if no valid date
            if not bill.date:
                _logger.warning(f"Bill {bill.name} has no valid date, skipping")
                continue

            # Get the bill's untaxed amount (use absolute value for vendor bills)
            bill_amount = abs(bill.amount_untaxed_signed)
            bill_amount_signed = abs(bill.amount_total_signed)
            
            # Skip zero amount bills
            if bill_amount <= 0:
                continue

            # Find linked project (assuming there's a project_id field on account.move)
            # If not directly available, we need to check the source document or other relation
            linked_project = None
            bill_category = "Other"
            bill_tags = []

            # Method 1: Check if bill has direct project_id field
            if hasattr(bill, 'project_id') and bill.project_id:
                linked_project = bill.project_id
            
            # Method 2: Try to find project from invoice_origin (like SO001, PO001, etc.)
            elif bill.invoice_origin:
                # Try to find purchase order with this reference
                purchase_order = self.env['purchase.order'].search([
                    ('name', '=', bill.invoice_origin)
                ], limit=1)
                
                if purchase_order and hasattr(purchase_order, 'project_id') and purchase_order.project_id:
                    linked_project = purchase_order.project_id
                else:
                    # Try to find sale order
                    sale_order = self.env['sale.order'].search([
                        ('name', '=', bill.invoice_origin)
                    ], limit=1)
                    if sale_order and hasattr(sale_order, 'project_id') and sale_order.project_id:
                        linked_project = sale_order.project_id
            
            # Method 3: Check analytic account on bill lines to find project
            if not linked_project:
                # Get analytic accounts from bill lines
                analytic_account_ids = set()
                for line in bill.invoice_line_ids:
                    if line.analytic_distribution:
                        try:
                            distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                                else eval(line.analytic_distribution)
                            analytic_account_ids.update([int(acc_id) for acc_id in distribution.keys()])
                        except Exception as e:
                            _logger.error(f"Error parsing analytic distribution for bill {bill.name}: {e}")
                
                # Find project with matching analytic account
                if analytic_account_ids:
                    linked_project = self.env['project.project'].search([
                        ('analytic_account_id', 'in', list(analytic_account_ids))
                    ], limit=1)

            # Determine category based on project tags
            if linked_project and linked_project.tag_ids:
                project_tag_names = linked_project.tag_ids.mapped('name')
                bill_tags = project_tag_names
                
                if local_tag and local_tag.name in project_tag_names:
                    bill_category = "Local"
                elif export_tag and export_tag.name in project_tag_names:
                    bill_category = "Export"
                else:
                    bill_category = "Other"
            else:
                bill_category = "Other"
                bill_tags = []

            # Add expense entry
            expenses.append({
                "id": expense_id_counter,
                "date": bill.date.strftime('%Y-%m-%d'),
                "bill_no": bill.name,
                "vendor": bill.partner_id.name or '',
                "local_export": bill_category,
                "tags": ', '.join(sorted(bill_tags)) if bill_tags else '',
                "source_document": bill.invoice_origin or '',
                "tax_excluded": self._format_amount(bill_amount),
                "payment_status": payment_state_mapping.get(bill.payment_state, bill.payment_state or ''),
                "project": linked_project.name if linked_project else '',
            })
            expense_id_counter += 1

            # Update category totals
            if bill_category == "Local":
                total_local_expense += bill_amount
                total_local_expense_signed += bill_amount_signed
            elif bill_category == "Export":
                total_export_expense += bill_amount
                total_export_expense_signed += bill_amount_signed
            else:
                total_other_expense += bill_amount
                total_other_expense_signed += bill_amount_signed

        # total_expense = total_local_expense + total_export_expense + total_other_expense
        total_expense_signed = total_local_expense_signed + total_export_expense_signed + total_other_expense_signed

        return {
            'expenses': expenses,
            'total_expenses_local_untaxed': self._format_amount(total_local_expense_signed),
            'total_expenses_export_untaxed': self._format_amount(total_export_expense_signed),
            'total_expenses_other_untaxed': self._format_amount(total_other_expense_signed),
            'total_expenses_local_untaxed_not_converted': self._format_amount(total_local_expense),
            'total_expenses_export_untaxed_not_converted': self._format_amount(total_export_expense),
            'total_expenses_other_untaxed_not_converted': self._format_amount(total_other_expense),
            'total_expense_untaxed': self._format_amount(total_expense_signed),
            # 'total_expense_signed': self._format_amount(),
        }

    def get_cashflow_data(self, start_date, end_date):
        """Get cashflow data for the dashboard"""
        # Find project tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        company_currency = self.env.company.currency_id
        company_currency_icon = company_currency.symbol or ''

        if not local_tag or not export_tag:
            return {
                'cashflows': {
                    "inflows": {
                        "locals": [],
                        "exports": [],
                    },
                    "outflows": {
                        "locals": [],
                        "exports": [],
                    },
                },
                'company_currency_icon': company_currency_icon,
                'total_local_cashflow_inflow': f"{self._format_amount(0.0)}",
                'total_export_cashflow_inflow': f"{self._format_amount(0.0)}",
                'total_local_cashflow_outflow': f"{self._format_amount(0.0)}",
                'total_export_cashflow_outflow': f"{self._format_amount(0.0)}",
                'net_local_cashflow': f"{self._format_amount(0.0)}",
                'net_export_cashflow': f"{self._format_amount(0.0)}",
                'total_net_cashflow': f"{self._format_amount(0.0)}",
            }

        # Get project tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)
        
        # Get projects by tags
        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])
        
        # Get analytic accounts
        local_analytic_account_ids = local_projects.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_projects.mapped('analytic_account_id').ids

        cashflows = {
            "inflows": {
                "locals": [],
                "exports": [],
            },
            "outflows": {
                "locals": [],
                "exports": [],
            },
        }
        total_local_inflow = 0.0
        total_export_inflow = 0.0
        total_local_outflow = 0.0
        total_export_outflow = 0.0
        
        cashflow_id_counter = 1
        company_currency = self.env.company.currency_id

        # Helper function to get project info from analytic account
        def get_project_info(account_id):
            project = self.env['project.project'].search([('analytic_account_id', '=', account_id)], limit=1)
            if project:
                project_name = project.name
                project_tags = ', '.join(project.tag_ids.mapped('name'))
                # Determine region based on tags
                if local_tag.id in project.tag_ids.ids:
                    region = 'Local'
                elif export_tag.id in project.tag_ids.ids:
                    region = 'Export'
                else:
                    region = 'Unknown'
                return project_name, project_tags, region
            return 'Unknown Project', '', 'Unknown'

        # INFLOW: Customer Payments
        customer_payments = self.env['account.payment'].search([
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ])
        
        for payment in customer_payments:
            # Get related invoices
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
                                
                                # Get project information
                                project_name, project_tags, region = get_project_info(account_id)
                                
                                if account_id in local_analytic_account_ids:
                                    cashflow_entry = {
                                        "id": cashflow_id_counter,
                                        "date": payment.date.strftime('%Y-%m-%d') if payment.date else '',
                                        "inflow_outflow": "Inflow",
                                        "project": project_name,
                                        "local_export": region,
                                        "tags": project_tags,
                                        "source_document": invoice.name or '',
                                        "payment_amount": f"{self._format_amount(amount_in_company_currency)}",
                                        "payment_status": payment.state or '',
                                    }
                                    
                                    cashflows['inflows']['locals'].append(cashflow_entry)
                                    total_local_inflow += amount_in_company_currency
                                    cashflow_id_counter += 1
                                    break
                                    
                                elif account_id in export_analytic_account_ids:
                                    cashflow_entry = {
                                        "id": cashflow_id_counter,
                                        "date": payment.date.strftime('%Y-%m-%d') if payment.date else '',
                                        "inflow_outflow": "Inflow",
                                        "project": project_name,
                                        "local_export": region,
                                        "tags": project_tags,
                                        "source_document": invoice.name or '',
                                        "payment_amount": f"{self._format_amount(amount_in_company_currency)}",
                                        "payment_status": payment.state or '',
                                    }
                                    cashflows['inflows']['exports'].append(cashflow_entry)
                                    total_export_inflow += amount_in_company_currency
                                    cashflow_id_counter += 1
                                    break

                        except Exception as e:
                            _logger.error("Error processing analytic distribution for invoice %s, line %s: %s", 
                                        invoice.id, line.id, str(e))
        
        # OUTFLOW: Vendor Payments
        vendor_payments = self.env['account.payment'].search([
            ('payment_type', '=', 'outbound'),
            ('state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('company_id', '=', self.company_id.id)
        ], order='date desc')
        
        for payment in vendor_payments:
            # Get related bills
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
                                    line.price_subtotal * (percentage / 100.0),
                                    company_currency,
                                    self.env.company,
                                    bill_date
                                )
                                
                                # Get project information
                                project_name, project_tags, region = get_project_info(account_id)
                                
                                if account_id in local_analytic_account_ids:
                                    cashflow_entry = {
                                        "id": cashflow_id_counter,
                                        "date": payment.date.strftime('%Y-%m-%d') if payment.date else '',
                                        "inflow_outflow": "Outflow",
                                        "project": project_name,
                                        "local_export": region,
                                        "tags": project_tags,
                                        "source_document": bill.name or '',
                                        "payment_amount": f"{self._format_amount(amount_in_company_currency)}",
                                        "payment_status": payment.state or '',
                                    }
                                    cashflows['outflows']['locals'].append(cashflow_entry)
                                    total_local_outflow += amount_in_company_currency
                                    cashflow_id_counter += 1
                                    break
                                    
                                elif account_id in export_analytic_account_ids:
                                    cashflow_entry = {
                                        "id": cashflow_id_counter,
                                        "date": payment.date.strftime('%Y-%m-%d') if payment.date else '',
                                        "inflow_outflow": "Outflow",
                                        "project": project_name,
                                        "local_export": region,
                                        "tags": project_tags,
                                        "source_document": bill.name or '',
                                        "payment_amount": f"{self._format_amount(amount_in_company_currency)}",
                                        "payment_status": payment.state or '',
                                    }
                                    cashflows['outflows']['exports'].append(cashflow_entry)
                                    total_export_outflow += amount_in_company_currency
                                    cashflow_id_counter += 1
                                    break
                                                    
                        except Exception as e:
                            _logger.error("Error processing analytic distribution for bill %s, line %s: %s", 
                                        bill.id, line.id, str(e))

        # Calculate net cashflows
        net_local_cashflow = total_local_inflow - total_local_outflow
        net_export_cashflow = total_export_inflow - total_export_outflow

        return {
            'cashflows': cashflows,
            'company_currency_icon': company_currency_icon,
            'total_local_cashflow_inflow': self._format_amount(total_local_inflow),
            'total_export_cashflow_inflow': self._format_amount(total_export_inflow),
            'total_local_cashflow_outflow': self._format_amount(total_local_outflow),
            'total_export_cashflow_outflow': self._format_amount(total_export_outflow),
            'net_local_cashflow': self._format_amount(net_local_cashflow),
            'net_export_cashflow': self._format_amount(net_export_cashflow),
            'total_net_cashflow': self._format_amount(net_local_cashflow + net_export_cashflow)
        }
    
    def export_excel(self):
        self.ensure_one()
        data = self._get_dashboard_data()
        category = data['filters']['category']

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet(f"{category.capitalize()} Report")

        bold = workbook.add_format({'bold': True})

        def parse_numeric(val):
            if val is None:
                return 0
            if isinstance(val, str):
                val = val.replace(',', '').replace('Nu.', '').replace('₹', '').replace('$', '').strip()
                try:
                    return float(val)
                except ValueError:
                    return 0
            return val

        # Header
        worksheet.write(0, 0, 'Company', bold)
        worksheet.write(0, 1, data['company']['name'])

        worksheet.write(1, 0, 'Currency', bold)
        worksheet.write(1, 1, data['company']['currency'])

        worksheet.write(2, 0, 'Period', bold)
        worksheet.write(2, 1, f"{data['filters']['month_name'] or data['filters']['quarter'] or 'Year'} {data['filters']['year']}")

        row = 4

        if category == 'sales':
            local_sales = [r for r in data['sales_data']['sales'] if 'Local' in (r.get('tags') or '')]
            export_sales = [r for r in data['sales_data']['sales'] if 'Export' in (r.get('tags') or '')]

            # --- Local Sales Section ---
            worksheet.write(row, 0, 'LOCAL SALES', bold)
            row += 1
            worksheet.write_row(row, 0, ['Date', 'Sale Order No', 'Tags', 'Customer', 'Sale Person', 'Untaxed Amount', 'Converted Amount'], bold)
            row += 1
            for record in local_sales:
                worksheet.write(row, 0, record.get('date'))
                worksheet.write(row, 1, record.get('sales_order_no'))
                worksheet.write(row, 2, record.get('tags'))
                worksheet.write(row, 3, record.get('customer'))
                worksheet.write(row, 4, record.get('sale_person'))
                worksheet.write_number(row, 5, parse_numeric(record.get('untaxed_amount')))
                worksheet.write_number(row, 6, parse_numeric(record.get('converted_amount')))
                row += 1

            # row += 1

            # --- Export Sales Section ---
            # row += 2
            worksheet.write(row, 0, 'EXPORT SALES', bold)
            row += 1
            worksheet.write_row(row, 0, ['Date', 'Sale Order No', 'Tags', 'Customer', 'Sale Person', 'Untaxed Amount', 'Converted Amount'], bold)
            row += 1
            for record in export_sales:
                worksheet.write(row, 0, record.get('date'))
                worksheet.write(row, 1, record.get('sales_order_no'))
                worksheet.write(row, 2, record.get('tags'))
                worksheet.write(row, 3, record.get('customer'))
                worksheet.write(row, 4, record.get('sale_person'))
                worksheet.write_number(row, 5, parse_numeric(record.get('untaxed_amount')))
                worksheet.write_number(row, 6, parse_numeric(record.get('converted_amount')))
                row += 1

            row += 1
            worksheet.write(row, 4, "Total Local Untaxed", bold)
            worksheet.write_number(row, 5, parse_numeric(data['sales_data']['total_sales_local_untaxed']))
            row += 1
            worksheet.write(row, 4, "Total Export Untaxed", bold)
            worksheet.write_number(row, 5, parse_numeric(data['sales_data']['total_sales_export_untaxed']))

        elif category == 'revenue':
            worksheet.write_row(row, 0, ['Date', 'Invoice No', 'Tags', 'Customer', 'Untaxed Amount'], bold)
            row += 1
            for record in data['revenue_data']['revenues']:
                worksheet.write(row, 0, record.get('date'))
                worksheet.write(row, 1, record.get('invoice_no'))
                worksheet.write(row, 2, record.get('tags'))
                worksheet.write(row, 3, record.get('customer'))
                worksheet.write_number(row, 4, parse_numeric(record.get('untaxed_amount')))
                row += 1

            row += 1
            worksheet.write(row, 3, "Total Local Revenue", bold)
            worksheet.write_number(row, 4, parse_numeric(data['revenue_data']['total_local_revenue_untaxed']))

            row += 1
            worksheet.write(row, 3, "Total Export Revenue", bold)
            worksheet.write_number(row, 4, parse_numeric(data['revenue_data']['total_export_revenue_untaxed']))

        elif category == 'expense':
            worksheet.write_row(row, 0, ['Date', 'Vendor', 'Tags', 'Tax Excluded'], bold)
            row += 1

            local_total = 0
            export_total = 0

            for record in data['expense_data']['expenses']:
                worksheet.write(row, 0, record.get('date'))
                worksheet.write(row, 1, record.get('vendor'))
                worksheet.write(row, 2, record.get('tags'))
                amount = parse_numeric(record.get('tax_excluded'))
                worksheet.write_number(row, 3, amount)
                if 'Local' in (record.get('tags') or ''):
                    local_total += amount
                elif 'Export' in (record.get('tags') or ''):
                    export_total += amount
                row += 1

            row += 1
            worksheet.write(row, 2, "Total Local Expense", bold)
            worksheet.write_number(row, 3, local_total)

            row += 1
            worksheet.write(row, 2, "Total Export Expense", bold)
            worksheet.write_number(row, 3, export_total)


        elif category == 'cashflow':
            worksheet.write_row(row, 0, ['Inflow - Local'], bold)
            row += 1
            worksheet.write_row(row, 0, ['Date', 'Type', 'Project', 'Local/Export', 'Tags', 'Source Doc', 'Amount', 'Status'], bold)
            row += 1

            inflow_local_total = 0

            for record in data['cashflow_data']['cashflows']['inflows']['locals']:
                worksheet.write(row, 0, record.get('date'))
                worksheet.write(row, 1, record.get('inflow_outflow'))
                worksheet.write(row, 2, record.get('project'))
                worksheet.write(row, 3, record.get('local_export'))
                worksheet.write(row, 4, record.get('tags'))
                worksheet.write(row, 5, record.get('source_document'))
                amount = parse_numeric(record.get('payment_amount'))
                worksheet.write_number(row, 6, amount)
                worksheet.write(row, 7, record.get('payment_status'))
                inflow_local_total += amount
                row += 1

            worksheet.write(row, 5, "Inflow Local Total", bold)
            worksheet.write_number(row, 6, inflow_local_total)
            row += 2

            worksheet.write_row(row, 0, ['Inflow - Export'], bold)
            row += 1
            worksheet.write_row(row, 0, ['Date', 'Type', 'Project', 'Local/Export', 'Tags', 'Source Doc', 'Amount', 'Status'], bold)
            row += 1

            inflow_export_total = 0
            for record in data['cashflow_data']['cashflows']['inflows']['exports']:
                worksheet.write(row, 0, record.get('date'))
                worksheet.write(row, 1, record.get('inflow_outflow'))
                worksheet.write(row, 2, record.get('project'))
                worksheet.write(row, 3, record.get('local_export'))
                worksheet.write(row, 4, record.get('tags'))
                worksheet.write(row, 5, record.get('source_document'))
                amount = parse_numeric(record.get('payment_amount'))
                worksheet.write_number(row, 6, amount)
                worksheet.write(row, 7, record.get('payment_status'))
                inflow_export_total += amount
                row += 1

            worksheet.write(row, 5, "Inflow Export Total", bold)
            worksheet.write_number(row, 6, inflow_export_total)
            row += 2

            worksheet.write_row(row, 0, ['Outflow - Local'], bold)
            row += 1
            worksheet.write_row(row, 0, ['Date', 'Type', 'Project', 'Local/Export', 'Tags', 'Source Doc', 'Amount', 'Status'], bold)
            row += 1

            outflow_local_total = 0
            for record in data['cashflow_data']['cashflows']['outflows']['locals']:
                worksheet.write(row, 0, record.get('date'))
                worksheet.write(row, 1, record.get('inflow_outflow'))
                worksheet.write(row, 2, record.get('project'))
                worksheet.write(row, 3, record.get('local_export'))
                worksheet.write(row, 4, record.get('tags'))
                worksheet.write(row, 5, record.get('source_document'))
                amount = parse_numeric(record.get('payment_amount'))
                worksheet.write_number(row, 6, amount)
                worksheet.write(row, 7, record.get('payment_status'))
                outflow_local_total += amount
                row += 1

            worksheet.write(row, 5, "Outflow Local Total", bold)
            worksheet.write_number(row, 6, outflow_local_total)
            row += 2

            worksheet.write_row(row, 0, ['Outflow - Export'], bold)
            row += 1
            worksheet.write_row(row, 0, ['Date', 'Type', 'Project', 'Local/Export', 'Tags', 'Source Doc', 'Amount', 'Status'], bold)
            row += 1

            outflow_export_total = 0
            for record in data['cashflow_data']['cashflows']['outflows']['exports']:
                worksheet.write(row, 0, record.get('date'))
                worksheet.write(row, 1, record.get('inflow_outflow'))
                worksheet.write(row, 2, record.get('project'))
                worksheet.write(row, 3, record.get('local_export'))
                worksheet.write(row, 4, record.get('tags'))
                worksheet.write(row, 5, record.get('source_document'))
                amount = parse_numeric(record.get('payment_amount'))
                worksheet.write_number(row, 6, amount)
                worksheet.write(row, 7, record.get('payment_status'))
                outflow_export_total += amount
                row += 1

            worksheet.write(row, 5, "Outflow Export Total", bold)
            worksheet.write_number(row, 6, outflow_export_total)
            row += 2

            # Final Summary
            worksheet.write(row, 2, "Net Local Cashflow", bold)
            worksheet.write_number(row, 3, parse_numeric(data['cashflow_data']['net_local_cashflow']))
            row += 1
            worksheet.write(row, 2, "Net Export Cashflow", bold)
            worksheet.write_number(row, 3, parse_numeric(data['cashflow_data']['net_export_cashflow']))
            row += 1
            worksheet.write(row, 2, "Total Net Cashflow", bold)
            worksheet.write_number(row, 3, parse_numeric(data['cashflow_data']['total_net_cashflow']))

        workbook.close()
        output.seek(0)
        file_data = output.read()

        attachment = self.env['ir.attachment'].create({
            'name': f'{category}_report.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(file_data),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }
