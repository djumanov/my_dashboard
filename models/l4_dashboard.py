import json
import logging
from datetime import datetime
from odoo import api, fields, models, _
from odoo.tools import date_utils, float_round

_logger = logging.getLogger(__name__)

class L4Dashboard(models.Model):
    _name = 'l4.dashboard'
    _description = 'L4 Dashboard Data'
    _rec_name = 'name'

    name = fields.Char(string='L4 Dashboard', default=lambda self: _('L4 Dashboard - %s') % fields.Date.today().strftime('%Y'))
    dashboard_data = fields.Text(string='Dashboard Data', compute='_compute_dashboard_data')
    last_update = fields.Datetime(string='Last Update', readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    active = fields.Boolean(default=True)

    def _get_year_selection(self):
        current_year = datetime.now().year
        return [(str(year), str(year)) for year in range(2023, current_year + 1)]

    year = fields.Selection(selection=lambda self: self._get_year_selection(), string='Year', default=lambda self: str(fields.Date.today().year))
    tag_type = fields.Selection([
        ('local', 'Local'),
        ('export', 'Export'),
        ('all', 'All')
    ], string='Region', default='all')
    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
        ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
        ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ])
    quarter = fields.Selection(
        [('Q1', 'Quarter 1'), ('Q2', 'Quarter 2'), ('Q3', 'Quarter 3'), ('Q4', 'Quarter 4')]
    )

    @api.depends('year', 'company_id', 'tag_type', 'month', 'quarter')
    def _compute_dashboard_data(self):
        for record in self:
            record.dashboard_data = json.dumps(record._get_dashboard_data())
            record.last_update = fields.Datetime.now()

    @api.model
    def get_dashboard_data_json(self, year=None, tag_type=None, month=None, quarter=None):
        """API method to get dashboard data in JSON format"""
        if not year:
            year = str(fields.Date.today().year)

        dashboard = self.search([
            ('year', '=', year),
            ('month', '=', month),
            ('quarter', '=', quarter),
            ('tag_type', '=', tag_type or 'all'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not dashboard:
            dashboard = self.create({
                'year': year,
                'month': month,
                'quarter': quarter,
                'tag_type': tag_type or 'all',
                'company_id': self.env.company.id
            })
        
        dashboard._compute_dashboard_data()
        return dashboard.dashboard_data

    def _get_dashboard_data(self):
        """Compute all dashboard data and return as a structured dictionary"""
        self.ensure_one()
        
        year = int(self.year) if self.year else datetime.now().year
        
        # Initialize start and end dates - will be modified based on filters
        start_date = None
        end_date = None
        
        # Handle quarter filter (takes precedence over month)
        if self.quarter:
            if self.quarter == 'Q1':
                start_date = datetime(year, 1, 1)
                end_date = datetime(year, 3, 31)
            elif self.quarter == 'Q2':
                start_date = datetime(year, 4, 1)
                end_date = datetime(year, 6, 30)
            elif self.quarter == 'Q3':
                start_date = datetime(year, 7, 1)
                end_date = datetime(year, 9, 30)
            elif self.quarter == 'Q4':
                start_date = datetime(year, 10, 1)
                end_date = datetime(year, 12, 31)
            
            # When quarter is set, month filter is ignored
            month_name = None
            month = 0
            # Explicitly set month to None to ensure consistency
            self.month = None
        # Handle month filter
        elif self.month:
            month = int(self.month)
            # Use date_utils to correctly calculate start and end of month
            start_date = datetime(year, month, 1)
            # End date should be the last day of the month
            start_date = date_utils.start_of(start_date, 'month')
            end_date = date_utils.end_of(start_date, 'month')
            month_name = dict(self._fields['month'].selection).get(self.month)
            # Explicitly set quarter to None to ensure consistency
            self.quarter = None
        # Default to full year if neither quarter nor month is specified
        else:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31)
            month = 0
            month_name = None
        
        # Convert datetime objects to string format for Odoo's ORM
        start_date_str = fields.Date.to_string(start_date)
        end_date_str = fields.Date.to_string(end_date)
        
        tag_type = self.tag_type if self.tag_type else 'all'
        
        return {
            'filters': {
                'year': year,
                'month': month,
                'month_name': month_name,
                'quarter': self.quarter,
                'tag_type': tag_type,
                'date_range': f"{start_date_str} to {end_date_str}",
            },
            'company': {
                'name': self.company_id.name,
                'currency': self.currency_id.symbol,
                'country': self.company_id.country_id.name or _('Not Set')
            },
            'projects': self._get_project_rows(start_date_str, end_date_str, tag_type),
        }

    def _get_project_rows(self, start_date, end_date, tag_type=None):
        """
        Get project data rows for reporting based on date range and tag type.
        
        Args:
            start_date (str): The start date to filter projects
            end_date (str): The end date to filter projects
            tag_type (str, optional): Filter by tag name
        
        Returns:
            list: List of dictionaries with project financial data
        """
        # Search for sales orders within the date range
        # Note: Using create_date instead of date_order for more accurate filtering
        domain = [
            ('company_id', '=', self.company_id.id),
            ('state', '!=', 'cancel'),
            ('date_order', '>=', start_date), 
            ('date_order', '<=', end_date)
        ]
        
        sales_orders = self.env['sale.order'].search(domain)
        
        # Get local and export tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)
        
        # Define project domain with date range
        project_domain =  [
            ('company_id', '=', self.company_id.id),
            # ('date_start', '<=', end_date)
        ]
        
        # Filter by tag type if specified
        if tag_type:
            if tag_type.lower() == 'local' and local_tag:
                project_domain.append(('tag_ids', 'in', [local_tag.id]))
            elif tag_type.lower() == 'export' and export_tag:
                project_domain.append(('tag_ids', 'in', [export_tag.id]))
            elif tag_type.lower() == 'all' and (local_tag or export_tag):
                # Filter for projects with either local or export tag
                tag_ids = []
                if local_tag:
                    tag_ids.append(local_tag.id)
                if export_tag:
                    tag_ids.append(export_tag.id)
                if tag_ids:
                    project_domain.append(('tag_ids', 'in', tag_ids))

        # Search for projects
        projects = self.env['project.project'].search(project_domain)
        
        results = []
        
        for proj in projects:
            # Determine if project is local or export
            is_local = local_tag and local_tag.id in proj.tag_ids.ids
            is_export = export_tag and export_tag.id in proj.tag_ids.ids
            
            region = 'Local' if is_local else 'Export' if is_export else 'Unknown'
            
            data = {
                "region": region,
                "project": proj.name,
                "customer": proj.partner_id.name if proj.partner_id else _('No Customer'),
                "date": '',
                "po_value": 0,
                "invoiced": 0,
                "collected": 0,
                "pending_collection": 0,
                "outstanding_aging": 0,
                "vendor_invoice": 0,
                "payment_made": 0,
                "payment_to_be_made": 0,
                "payroll_cost": 0,
                "total_outgoing": 0,
                "total_margin": 0,
                "margin_percent": 0
            }
            
            # Filter sales orders for this project
            # In Odoo 16, the relationship might be through a many2many field
            project_sales_orders = sales_orders.filtered(
                lambda so: hasattr(so, 'project_ids') and proj.id in so.project_ids.ids
            )
            
            # Calculate PO value (total of sales orders)
            data["po_value"] = sum(project_sales_orders.mapped('amount_untaxed'))
            
            # Calculate invoiced amount - use invoice_date for filtering
            invoices = self.env['account.move'].search([
                ('move_type', '=', 'out_invoice'),
                ('state', 'not in', ['draft', 'cancel']),
                ('invoice_date', '>=', start_date),
                ('invoice_date', '<=', end_date),
            ])
            
            # Link invoices to this project through sales orders
            project_invoices = invoices.filtered(
                lambda inv: any(
                    line.sale_line_ids and line.sale_line_ids.order_id in project_sales_orders 
                    for line in inv.invoice_line_ids 
                    if hasattr(line, 'sale_line_ids') and line.sale_line_ids
                )
            )
            
            data["invoiced"] = sum(project_invoices.mapped('amount_untaxed'))
            
            # Calculate collected amount (paid invoices)
            collected_invoices = project_invoices.filtered(
                lambda inv: inv.payment_state in ['paid', 'in_payment']
            )
            data["collected"] = sum(collected_invoices.mapped('amount_untaxed'))
            
            # Calculate pending collection
            data["pending_collection"] = data["invoiced"] - data["collected"]
            
            # Calculate outstanding aging from first sale order date to today
            domain = [
                ('company_id', '=', self.company_id.id),
                ('state', '!=', 'cancel')
            ]
            
            all_sales_orders = self.env['sale.order'].search(domain)
            project_all_sales_orders = all_sales_orders.filtered(
                lambda so: hasattr(so, 'project_ids') and proj.id in so.project_ids.ids
            )
            if project_all_sales_orders:
                # Get the date of the first sale order for this project
                first_order_dates = sorted([
                    fields.Date.from_string(order.date_order) 
                    for order in project_all_sales_orders 
                    if order.date_order
                ])
                
                if first_order_dates:
                    first_order_date = first_order_dates[0]
                    today = fields.Date.today()
                    data["outstanding_aging"] = (today - first_order_date).days
                    data["date"] = first_order_date.strftime('%Y-%m-%d')
                else:
                    data["outstanding_aging"] = 0
            else:
                data["outstanding_aging"] = 0

            # Calculate vendor invoices (supplier bills)
            vendor_bills = self.env['account.move'].search([
                ('move_type', '=', 'in_invoice'),
                ('state', 'not in', ['draft', 'cancel']),
                ('invoice_date', '>=', start_date),
                ('invoice_date', '<=', end_date),
            ])
            
            # Find project's analytic account
            project_analytic_account = proj.analytic_account_id
            project_vendor_bills = self.env['account.move']
            
            if project_analytic_account:
                # Try different methods to link vendor bills to this project
                
                # Method 1: Direct link through analytic_account_id field on bill
                try:
                    project_vendor_bills_direct = vendor_bills.filtered(
                        lambda bill: hasattr(bill, 'analytic_account_id') and 
                                    bill.analytic_account_id and 
                                    bill.analytic_account_id.id == project_analytic_account.id
                    )
                    project_vendor_bills |= project_vendor_bills_direct
                except Exception as e:
                    _logger.warning(f"Error finding vendor bills by direct analytic account: {e}")
                
                # Method 2: Through analytic distribution on invoice lines (Odoo 15+)
                try:
                    project_vendor_bills_dist = vendor_bills.filtered(
                        lambda bill: any(
                            hasattr(line, 'analytic_distribution') and
                            line.analytic_distribution and 
                            str(project_analytic_account.id) in line.analytic_distribution
                            for line in bill.invoice_line_ids
                        )
                    )
                    project_vendor_bills |= project_vendor_bills_dist
                except Exception as e:
                    _logger.warning(f"Error finding vendor bills by analytic distribution: {e}")
                
                # Method 3: Through analytic_account_id on invoice lines (older versions)
                try:
                    project_vendor_bills_lines = vendor_bills.filtered(
                        lambda bill: any(
                            hasattr(line, 'analytic_account_id') and 
                            line.analytic_account_id and 
                            line.analytic_account_id.id == project_analytic_account.id
                            for line in bill.invoice_line_ids
                        )
                    )
                    project_vendor_bills |= project_vendor_bills_lines
                except Exception as e:
                    _logger.warning(f"Error finding vendor bills by line analytic account: {e}")
            
            data["vendor_invoice"] = sum(project_vendor_bills.mapped('amount_untaxed'))
            
            # Calculate payment made to vendors
            paid_vendor_bills = project_vendor_bills.filtered(
                lambda bill: bill.payment_state in ['paid', 'in_payment']
            )
            data["payment_made"] = sum(paid_vendor_bills.mapped('amount_untaxed'))
            
            # Calculate payment to be made
            data["payment_to_be_made"] = data["vendor_invoice"] - data["payment_made"]
            
            # Calculate payroll cost for Odoo 16
            payroll_cost = 0
            
            # Get timesheets for this project
            timesheet_domain = [
                ('project_id', '=', proj.id),
                ('date', '>=', start_date),
                ('date', '<=', end_date),
            ]
            
            timesheets = self.env['account.analytic.line'].search(timesheet_domain)
            
            for timesheet in timesheets:
                employee = timesheet.employee_id
                if employee and hasattr(employee, 'hourly_cost'):
                    cost = employee.hourly_cost * timesheet.unit_amount
                    payroll_cost += cost
                # Fallback for if hourly_cost isn't available
                elif hasattr(timesheet, 'amount') and timesheet.amount:
                    payroll_cost -= timesheet.amount  # Amount is negative in analytic lines
            
            data["payroll_cost"] = payroll_cost
            
            # Calculate total outgoing
            data["total_outgoing"] = data["vendor_invoice"] + data["payroll_cost"]
            
            # Calculate total margin
            data["total_margin"] = data["po_value"] - data["total_outgoing"]
            
            # Calculate margin percentage
            if data["po_value"] > 0:
                data["margin_percent"] = (data["total_margin"] / data["po_value"]) * 100
            else:
                data["margin_percent"] = 0

            # Format values
            data["po_value"] = self._format_value(data["po_value"])
            data["invoiced"] = self._format_value(data["invoiced"])
            data["collected"] = self._format_value(data["collected"])
            data["pending_collection"] = self._format_value(data["pending_collection"])
            data["vendor_invoice"] = self._format_value(data["vendor_invoice"])
            data["payment_made"] = self._format_value(data["payment_made"])
            data["payment_to_be_made"] = self._format_value(data["payment_to_be_made"])
            data["payroll_cost"] = self._format_value(data["payroll_cost"])
            data["total_outgoing"] = self._format_value(data["total_outgoing"])
            data["total_margin"] = self._format_value(data["total_margin"])
            data["margin_percent"] = self._format_value(data["margin_percent"])
            
            # Append the data to results
            results.append(data)
        
        return results

    def _format_value(self, value):
        """Format a value to the currency format"""
        if not value:
            return 0.0
            
        if isinstance(value, float):
            return round(value, 2)
        return value
