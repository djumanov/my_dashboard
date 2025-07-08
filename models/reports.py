import json
import logging
from datetime import datetime

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
            'cashflows': [],
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
                
                # Determine if it's Local or Export
                if project in local_projects:
                    local_export = "Local"
                elif project in export_projects:
                    local_export = "Export"
                else:
                    local_export = "Other"  # Project exists but not tagged as Local/Export
                
                sales_data.append({
                    "sale_id": sale_id_counter,
                    "date": sale_order.date_order.strftime('%Y-%m-%d'),
                    "sales_order_no": sale_order.name,
                    "local_export": local_export,
                    "tags": tags,
                    "customer": sale_order.partner_id.name,
                    "sale_person": sale_order.user_id.name,
                    "untaxed_amount": self._format_amount(untaxed_amount),
                })
                sale_id_counter += 1
                # Update totals
                if local_export == "Local":
                    total_local_untaxed += untaxed_amount
                elif local_export == "Export":
                    total_export_untaxed += untaxed_amount
            
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
                    region = "Mixed"  # Has both Local and Export
                elif has_analytic_distribution:
                    region = "Other"  # Has analytic distribution but not Local/Export
                else:
                    region = "Unclassified"  # No analytic distribution at all
                
                tags = ", ".join(sorted(all_tags))
                
                # Use calculated amount or fallback to sale order amount
                if total_untaxed_amount == 0.0:
                    total_untaxed_amount = sale_order.amount_untaxed
                
                if region == "Unclassified":
                    # Skip unclassified sales
                    continue
                sales_data.append({
                    "sale_id": sale_id_counter,
                    "date": sale_order.date_order.strftime('%Y-%m-%d'),
                    "sales_order_no": sale_order.name,
                    "local_export": region,
                    "tags": tags,
                    "customer": sale_order.partner_id.name,
                    "sale_person": sale_order.user_id.name,
                    "untaxed_amount": self._format_amount(total_untaxed_amount),
                })
                sale_id_counter += 1
                # Update totals
                if region == "Local":
                    total_local_untaxed += total_untaxed_amount
                elif region == "Export":
                    total_export_untaxed += total_untaxed_amount
        
        return {
            'sales': sales_data,
            'total_sales_local_untaxed': self._format_amount(total_local_untaxed),
            'total_sales_export_untaxed': self._format_amount(total_export_untaxed)
        }
    
    def _get_revenue_data(self, start_date, end_date):
        """Get revenue data for the dashboard"""
        # Find project tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        if not local_tag or not export_tag:
            return {
                'revenues': [],
                'total_sales_local_untaxed': self._format_amount(0.0),
                'total_sales_export_untaxed': self._format_amount(0.0)
            }

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

        revenues = []
        total_local_revenue_untaxed = 0.0
        total_export_revenue_untaxed = 0.0

        revenue_id_counter = 1

        for invoice in customer_invoices:
            # if hasattr(invoice, 'sale_orders') and invoice.sale_orders:
            #     sale_order = invoice.sale_orders[0]
            #     if sale_order.project_ids:
            #         project = sale_order.project_ids[0]
            #         tags = ", ".join(project.tag_ids.mapped('name')) if project.tag_ids else ""

            #         if project in local_projects:
            #             revenues.append({
            #                 "revenue_id": invoice.id,
            #                 "date": invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '',
            #                 "invoice_no": invoice.name,
            #                 "sales_order_no": sale_order.name,
            #                 "local_export": "Local",
            #                 "tags": tags,
            #                 "customer": invoice.partner_id.name or '',
            #                 "untaxed_amount": self._format_amount(invoice.amount_untaxed),
            #                 "payment_status": invoice.payment_state or '',
            #             })
            #             total_local_revenue += invoice.amount_untaxed
            #         elif project in export_projects:
            #             revenues.append({
            #                 "revenue_id": invoice.id,
            #                 "date": invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '',
            #                 "invoice_no": invoice.name,
            #                 "sales_order_no": sale_order.name,
            #                 "local_export": "Export",
            #                 "tags": tags,
            #                 "customer": invoice.partner_id.name or '',
            #                 "untaxed_amount": self._format_amount(invoice.amount_untaxed),
            #                 "payment_status": invoice.payment_state or '',
            #             })
            #             total_export_revenue += invoice.amount_untaxed
            #     else:
            #         regions_found = set()
            #         all_tags = set()
            #         if sale_order.analytic_distribution:
            #             try:
            #                 distribution = sale_order.analytic_distribution if isinstance(sale_order.analytic_distribution, dict) \
            #                     else eval(sale_order.analytic_distribution)
                            
            #                 for account_id, percentage in distribution.items():
            #                     account_id = int(account_id)
                                
            #                     if account_id in local_analytic_account_ids:
            #                         regions_found.add("Local")
            #                         project = self.env['project.project'].search([
            #                             ('analytic_account_id', '=', account_id)
            #                         ], limit=1)
            #                         if project and project.tag_ids:
            #                             all_tags.update(project.tag_ids.mapped('name'))
            #                     elif account_id in export_analytic_account_ids:
            #                         regions_found.add("Export")
            #                         project = self.env['project.project'].search([
            #                             ('analytic_account_id', '=', account_id)
            #                         ], limit=1)
            #                         if project and project.tag_ids:
            #                             all_tags.update(project.tag_ids.mapped('name'))
            #             except Exception as e:
            #                 _logger.error(f"Error processing analytic distribution for invoice {invoice.id}: {e}")

            #         if regions_found:
            #             local_export_label = "Local" if "Local" in regions_found else "Export"
            #             tag_string = ", ".join(all_tags)
            #             revenues.append({
            #                 "revenue_id": invoice.id,
            #                 "date": invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '',
            #                 "invoice_no": invoice.name,
            #                 "sales_order_no": sale_order.name,
            #                 "local_export": local_export_label,
            #                 "tags": tag_string,
            #                 "customer": invoice.partner_id.name or '',
            #                 "untaxed_amount": self._format_amount(invoice.amount_untaxed),
            #                 "payment_status": invoice.payment_state or '',
            #             })

            #         if local_export_label == "Local":
            #             total_local_revenue += invoice.amount_untaxed
            #         else:
            #             total_export_revenue += invoice.amount_untaxed

            # else:
                for line in invoice.invoice_line_ids:
                    regions_found = set()
                    all_tags = set()
                    total_untaxed_amount = 0.0
                    has_analytic_distribution = False
                    if line.analytic_distribution:
                        has_analytic_distribution = True
                        try:
                            distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                                else eval(line.analytic_distribution)
                            
                            for account_id, percentage in distribution.items():
                                account_id = int(account_id)
                                
                                if account_id in local_analytic_account_ids:
                                    regions_found.add("Local")
                                    project = self.env['project.project'].search([
                                        ('analytic_account_id', '=', account_id)
                                    ], limit=1)
                                    if project and project.tag_ids:
                                        all_tags.update(project.tag_ids.mapped('name'))
                                elif account_id in export_analytic_account_ids:
                                    regions_found.add("Export")
                                    project = self.env['project.project'].search([
                                        ('analytic_account_id', '=', account_id)
                                    ], limit=1)
                                    if project and project.tag_ids:
                                        all_tags.update(project.tag_ids.mapped('name'))
                                
                                total_untaxed_amount += line.price_subtotal * (percentage / 100)
                        
                        except Exception as e:
                            _logger.error(f"Error processing analytic distribution for invoice {invoice.id}: {e}")
                    
                    if regions_found:
                        local_export_label = "Local" if "Local" in regions_found else "Export"
                        tag_string = ", ".join(sorted(all_tags))
                        
                        # Use calculated amount or fallback to invoice line amount
                        if total_untaxed_amount == 0.0:
                            total_untaxed_amount = line.price_subtotal
                        
                        revenues.append({
                            "revenue_id": revenue_id_counter,
                            "date": invoice.invoice_date.strftime('%Y-%m-%d') if invoice.invoice_date else '',
                            "invoice_no": invoice.name,
                            "sales_order_no": invoice.invoice_origin or '',
                            "local_export": local_export_label,
                            "tags": tag_string,
                            "customer": invoice.partner_id.name or '',
                            "untaxed_amount": self._format_amount(total_untaxed_amount),
                            "payment_status": invoice.payment_state or '',
                        })
                        revenue_id_counter += 1
                        
                        if local_export_label == "Local":
                            total_local_revenue_untaxed += total_untaxed_amount
                        else:
                            total_export_revenue_untaxed += total_untaxed_amount

        return {
            'revenues': revenues,
            'total_local_revenue_untaxed': self._format_amount(total_local_revenue_untaxed),
            'total_export_revenue_untaxed': self._format_amount(total_export_revenue_untaxed)
        }

    def get_expense_data(self, start_date, end_date):
        """Get expense data for the dashboard"""
        # Find project tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        if not local_tag or not export_tag:
            return {
                'expenses': [],
                'total_expenses_local_untaxed': self._format_amount(0.0),
                'total_expenses_export_untaxed': self._format_amount(0.0)
            }

        # Find projects with respective tags
        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])

        # Get analytic account IDs
        local_analytic_account_ids = local_projects.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_projects.mapped('analytic_account_id').ids

        # Get posted vendor bills in the date range
        bill_domain = [
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]
        vendor_bills = self.env['account.move'].search(bill_domain)

        expenses = [] # expense_id, date, bill_no, vendor, local_export, tags, source_document, tax_excluded, payment_status
        total_local_expense_untaxed = 0.0
        total_export_expense_untaxed = 0.0

        expense_id_counter = 1

        for bill in vendor_bills:
            # if bill.project_ids:
            #     project = bill.project_ids[0]
            #     tags = ", ".join(project.tag_ids.mapped('name')) if project.tag_ids else ""

            #     if project in local_projects:
            #         local_export = "Local"
            #     elif project in export_projects:
            #         local_export = "Export"
            #     else:
            #         local_export = "Other"
            #     expenses.append({
            #         "expense_id": expense_id_counter,
            #         "date": bill.date.strftime('%Y-%m-%d') if bill.date else '',
            #         "bill_no": bill.name,
            #         "vendor": bill.partner_id.name,
            #         "local_export": local_export,
            #         "tags": tags,
            #         "source_document": bill.invoice_origin or '',
            #         "tax_excluded": self._format_amount(bill.amount_untaxed),
            #         "payment_status": bill.payment_state or '',
            #     })
            #     expense_id_counter += 1
            #     # Update totals
            #     if local_export == "Local":
            #         total_local_expense_untaxed += bill.amount_untaxed
            #     elif local_export == "Export":
            #         total_export_expense_untaxed += bill.amount_untaxed

            # else:
                regions_found = set()
                all_tags = set()
                total_untaxed_amount = 0.0
                has_analytic_distribution = False
                
                for line in bill.invoice_line_ids:
                    if line.analytic_distribution:
                        has_analytic_distribution = True
                        try:
                            distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                                else eval(line.analytic_distribution)
                            
                            for account_id, percentage in distribution.items():
                                account_id = int(account_id)
                                
                                if account_id in local_analytic_account_ids:
                                    regions_found.add("Local")
                                    project = self.env['project.project'].search([
                                        ('analytic_account_id', '=', account_id)
                                    ], limit=1)
                                    if project and project.tag_ids:
                                        all_tags.update(project.tag_ids.mapped('name'))
                                elif account_id in export_analytic_account_ids:
                                    regions_found.add("Export")
                                    project = self.env['project.project'].search([
                                        ('analytic_account_id', '=', account_id)
                                    ], limit=1)
                                    if project and project.tag_ids:
                                        all_tags.update(project.tag_ids.mapped('name'))
                                
                                total_untaxed_amount += line.price_subtotal * (percentage / 100)
                        
                        except Exception as e:
                            _logger.error(f"Error processing analytic distribution for bill {bill.id}: {e}")
                    
                    else:
                        # Line has no analytic distribution, add its amount
                        total_untaxed_amount += line.price_subtotal
                
                # Determine final region and tags
                if len(regions_found) == 1:
                    region = list(regions_found)[0]
                elif len(regions_found) > 1:
                    region = "Mixed"
                elif has_analytic_distribution:
                    region = "Other"
                else:
                    region = "Unclassified"

                tags = ", ".join(sorted(all_tags))
                # Use calculated amount or fallback to bill amount
                if total_untaxed_amount == 0.0:
                    total_untaxed_amount = bill.amount_untaxed
                if region == "Unclassified":
                    # Skip unclassified expenses
                    continue
                expenses.append({
                    "expense_id": expense_id_counter,
                    "date": bill.date.strftime('%Y-%m-%d') if bill.date else '',
                    "bill_no": bill.name,
                    "vendor": bill.partner_id.name,
                    "local_export": region,
                    "tags": tags,
                    "source_document": bill.invoice_origin or '',
                    "tax_excluded": self._format_amount(total_untaxed_amount),
                    "payment_status": bill.payment_state or '',
                })
                expense_id_counter += 1
                # Update totals
                if region == "Local":
                    total_local_expense_untaxed += total_untaxed_amount
                elif region == "Export":
                    total_export_expense_untaxed += total_untaxed_amount
            
        return {
            'expenses': expenses,
            'total_local_expense_untaxed': self._format_amount(total_local_expense_untaxed),
            'total_export_expense_untaxed': self._format_amount(total_export_expense_untaxed)
        }

    def get_cashflow_data(self, start_date, end_date):
        """Get cashflow data for the dashboard"""
        # Find project tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        if not local_tag or not export_tag:
            return {
                'cashflows': [],
                'total_local_cashflow_inflow': self._format_amount(0.0),
                'total_export_cashflow_inflow': self._format_amount(0.0),
                'total_local_cashflow_outflow': self._format_amount(0.0),
                'total_export_cashflow_outflow': self._format_amount(0.0),
                'net_local_cashflow': self._format_amount(0.0),
                'net_export_cashflow': self._format_amount(0.0)
            }

        # Find projects with respective tags
        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])

        # Get analytic account IDs
        local_analytic_account_ids = local_projects.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_projects.mapped('analytic_account_id').ids

        cashflows = []
        total_local_inflow = 0.0
        total_export_inflow = 0.0
        total_local_outflow = 0.0
        total_export_outflow = 0.0
        
        cashflow_id_counter = 1

        # Get payment records (both inbound and outbound)
        payment_domain = [
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('state', '=', 'posted'),
            ('company_id', '=', self.company_id.id),
        ]
        payments = self.env['account.payment'].search(payment_domain, order='date desc')

        for payment in payments:
            regions_found = set()
            all_tags = set()
            payment_amount = 0.0
            has_analytic_distribution = False
            
            # Determine payment type
            if payment.payment_type == 'inbound':
                flow_type = 'Inflow'
                partner_type = 'Customer'
            else:
                flow_type = 'Outflow'
                partner_type = 'Vendor'

            # Check if payment has reconciled moves with analytic distribution
            reconciled_moves = payment.reconciled_invoice_ids
            
            if reconciled_moves:
                # Process reconciled invoices/bills
                for move in reconciled_moves:
                    for line in move.invoice_line_ids:
                        if line.analytic_distribution:
                            has_analytic_distribution = True
                            try:
                                distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                                    else eval(line.analytic_distribution)
                                
                                for account_id, percentage in distribution.items():
                                    account_id = int(account_id)
                                    
                                    if account_id in local_analytic_account_ids:
                                        regions_found.add("Local")
                                        project = self.env['project.project'].search([
                                            ('analytic_account_id', '=', account_id)
                                        ], limit=1)
                                        if project and project.tag_ids:
                                            all_tags.update(project.tag_ids.mapped('name'))
                                    elif account_id in export_analytic_account_ids:
                                        regions_found.add("Export")
                                        project = self.env['project.project'].search([
                                            ('analytic_account_id', '=', account_id)
                                        ], limit=1)
                                        if project and project.tag_ids:
                                            all_tags.update(project.tag_ids.mapped('name'))
                                    
                                    # Calculate proportional payment amount
                                    line_amount = line.price_subtotal * (percentage / 100)
                                    # Get the proportion of this line's amount in the total invoice
                                    if move.amount_untaxed > 0:
                                        line_proportion = line_amount / move.amount_untaxed
                                        payment_amount += payment.amount * line_proportion
                            
                            except Exception as e:
                                _logger.error(f"Error processing analytic distribution for payment {payment.id}: {e}")
            
            else:
                # If no reconciled moves, check if payment itself has analytic distribution
                # (This might be the case for manual payments or advance payments)
                if hasattr(payment, 'analytic_distribution') and payment.analytic_distribution:
                    has_analytic_distribution = True
                    try:
                        distribution = payment.analytic_distribution if isinstance(payment.analytic_distribution, dict) \
                            else eval(payment.analytic_distribution)
                        
                        for account_id, percentage in distribution.items():
                            account_id = int(account_id)
                            
                            if account_id in local_analytic_account_ids:
                                regions_found.add("Local")
                                project = self.env['project.project'].search([
                                    ('analytic_account_id', '=', account_id)
                                ], limit=1)
                                if project and project.tag_ids:
                                    all_tags.update(project.tag_ids.mapped('name'))
                            elif account_id in export_analytic_account_ids:
                                regions_found.add("Export")
                                project = self.env['project.project'].search([
                                    ('analytic_account_id', '=', account_id)
                                ], limit=1)
                                if project and project.tag_ids:
                                    all_tags.update(project.tag_ids.mapped('name'))
                            
                            payment_amount += payment.amount * (percentage / 100)
                    
                    except Exception as e:
                        _logger.error(f"Error processing payment analytic distribution for payment {payment.id}: {e}")

            # Determine final region and tags
            if len(regions_found) == 1:
                region = list(regions_found)[0]
            elif len(regions_found) > 1:
                region = "Mixed"
            elif has_analytic_distribution:
                region = "Other"
            else:
                region = "Unclassified"

            tags = ", ".join(sorted(all_tags))
            
            # Use calculated amount or fallback to payment amount
            if payment_amount == 0.0:
                payment_amount = payment.amount

            # Skip unclassified payments
            if region == "Unclassified":
                continue

            # Get reference document
            reference_doc = ""
            if payment.reconciled_invoice_ids:
                reference_doc = ", ".join(payment.reconciled_invoice_ids.mapped('name'))
            elif payment.communication:
                reference_doc = payment.communication

            # Get project name from analytic account
            project_name = ""
            if regions_found:
                # Find the first project that matches the region by checking analytic distribution
                for move in reconciled_moves:
                    for line in move.invoice_line_ids:
                        if line.analytic_distribution:
                            try:
                                distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                                    else eval(line.analytic_distribution)
                                
                                for account_id_str in distribution.keys():
                                    account_id = int(account_id_str)
                                    if region == "Local":
                                        matching_project = local_projects.filtered(lambda p: p.analytic_account_id.id == account_id)
                                        if matching_project:
                                            project_name = matching_project[0].name
                                            break
                                    elif region == "Export":
                                        matching_project = export_projects.filtered(lambda p: p.analytic_account_id.id == account_id)
                                        if matching_project:
                                            project_name = matching_project[0].name
                                            break
                            except Exception:
                                continue
                        if project_name:
                            break
                    if project_name:
                        break

            cashflows.append({
                "cashflow_id": cashflow_id_counter,
                "date": payment.date.strftime('%Y-%m-%d') if payment.date else '',
                "inflow_outflow": flow_type,
                "project": project_name,
                "local_export": region,
                "tags": tags,
                "source_document": reference_doc,
                "payment_amount": self._format_amount(payment_amount),
                "payment_status": payment.state or '',
            })
            cashflow_id_counter += 1

            # Update totals
            if flow_type == 'Inflow':
                if region == "Local":
                    total_local_inflow += payment_amount
                elif region == "Export":
                    total_export_inflow += payment_amount
            else:  # Outflow
                if region == "Local":
                    total_local_outflow += payment_amount
                elif region == "Export":
                    total_export_outflow += payment_amount

        # Alternative approach: Get cash flows from account moves if payments don't have enough data
        if not cashflows:
            # Get account moves for cash/bank accounts
            cash_bank_accounts = self.env['account.account'].search([
                ('account_type', 'in', ['asset_cash', 'liability_current']),
                ('company_id', '=', self.company_id.id)
            ])
            
            move_line_domain = [
                ('date', '>=', start_date),
                ('date', '<=', end_date),
                ('account_id', 'in', cash_bank_accounts.ids),
                ('parent_state', '=', 'posted'),
                ('company_id', '=', self.company_id.id),
            ]
            
            cash_move_lines = self.env['account.move.line'].search(move_line_domain, order='date desc')
            
            for line in cash_move_lines:
                regions_found = set()
                all_tags = set()
                line_amount = abs(line.debit - line.credit)
                
                if line.analytic_distribution:
                    try:
                        distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                            else eval(line.analytic_distribution)
                        
                        for account_id, percentage in distribution.items():
                            account_id = int(account_id)
                            
                            if account_id in local_analytic_account_ids:
                                regions_found.add("Local")
                                project = self.env['project.project'].search([
                                    ('analytic_account_id', '=', account_id)
                                ], limit=1)
                                if project and project.tag_ids:
                                    all_tags.update(project.tag_ids.mapped('name'))
                            elif account_id in export_analytic_account_ids:
                                regions_found.add("Export")
                                project = self.env['project.project'].search([
                                    ('analytic_account_id', '=', account_id)
                                ], limit=1)
                                if project and project.tag_ids:
                                    all_tags.update(project.tag_ids.mapped('name'))
                    
                    except Exception as e:
                        _logger.error(f"Error processing analytic distribution for move line {line.id}: {e}")
                
                if not regions_found:
                    continue
                    
                region = list(regions_found)[0] if len(regions_found) == 1 else "Mixed"
                tags = ", ".join(sorted(all_tags))
                
                # Determine flow type based on debit/credit
                if line.debit > 0:
                    flow_type = 'Inflow'
                    partner_type = 'Customer'
                else:
                    flow_type = 'Outflow'
                    partner_type = 'Vendor'
                
                # Get project name from analytic account
                project_name = ""
                if regions_found:
                    if region == "Local" and local_projects:
                        # Find project that matches the analytic account
                        for account_id_str in distribution.keys():
                            account_id = int(account_id_str)
                            matching_project = local_projects.filtered(lambda p: p.analytic_account_id.id == account_id)
                            if matching_project:
                                project_name = matching_project[0].name
                                break
                    elif region == "Export" and export_projects:
                        # Find project that matches the analytic account
                        for account_id_str in distribution.keys():
                            account_id = int(account_id_str)
                            matching_project = export_projects.filtered(lambda p: p.analytic_account_id.id == account_id)
                            if matching_project:
                                project_name = matching_project[0].name
                                break
                
                cashflows.append({
                    "cashflow_id": cashflow_id_counter,
                    "date": line.date.strftime('%Y-%m-%d') if line.date else '',
                    "inflow_outflow": flow_type,
                    "project": project_name,
                    "local_export": region,
                    "tags": tags,
                    "source_document": line.ref or line.name or '',
                    "payment_amount": self._format_amount(line_amount),
                    "payment_status": line.move_id.state or '',
                })
                cashflow_id_counter += 1
                
                # Update totals
                if flow_type == 'Inflow':
                    if region == "Local":
                        total_local_inflow += line_amount
                    elif region == "Export":
                        total_export_inflow += line_amount
                else:  # Outflow
                    if region == "Local":
                        total_local_outflow += line_amount
                    elif region == "Export":
                        total_export_outflow += line_amount

        # Calculate net cashflows
        net_local_cashflow = total_local_inflow - total_local_outflow
        net_export_cashflow = total_export_inflow - total_export_outflow

        return {
            'cashflows': cashflows,
            'total_local_cashflow_inflow': self._format_amount(total_local_inflow),
            'total_export_cashflow_inflow': self._format_amount(total_export_inflow),
            'total_local_cashflow_outflow': self._format_amount(total_local_outflow),
            'total_export_cashflow_outflow': self._format_amount(total_export_outflow),
            'net_local_cashflow': self._format_amount(net_local_cashflow),
            'net_export_cashflow': self._format_amount(net_export_cashflow),
            'total_net_cashflow': self._format_amount(net_local_cashflow + net_export_cashflow)
        }
