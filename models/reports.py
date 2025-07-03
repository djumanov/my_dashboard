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
        revenue_data = self._get_revenue_data(start_date, end_date)
        
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
            'sales_data': sales_data,
            'revenue_data': revenue_data,
        }
    
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
        total_local_revenue = 0.0
        total_export_revenue = 0.0

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
                            total_local_revenue += total_untaxed_amount
                        else:
                            total_export_revenue += total_untaxed_amount

        return {
            'revenues': revenues,
            'total_local_revenue': self._format_amount(total_local_revenue),
            'total_export_revenue': self._format_amount(total_export_revenue)
        }


