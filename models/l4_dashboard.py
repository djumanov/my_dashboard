# import json
# import logging
# from datetime import datetime
# from odoo import api, fields, models, _
# from odoo.tools import date_utils, float_round

# _logger = logging.getLogger(__name__)

# class L4Dashboard(models.Model):
#     _name = 'l4.dashboard'
#     _description = 'L4 Dashboard Data'
#     _rec_name = 'name'

#     name = fields.Char(string='L4 Dashboard', default=lambda self: _('L4 Dashboard - %s') % fields.Date.today().strftime('%Y'))
#     dashboard_data = fields.Text(string='Dashboard Data', compute='_compute_dashboard_data')
#     last_update = fields.Datetime(string='Last Update', readonly=True)
#     company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
#     currency_id = fields.Many2one(related='company_id.currency_id')
#     active = fields.Boolean(default=True)

#     def _get_year_selection(self):
#         current_year = datetime.now().year
#         return [(str(year), str(year)) for year in range(2023, current_year + 1)]

#     year = fields.Selection(selection=lambda self: self._get_year_selection(), string='Year', default=lambda self: str(fields.Date.today().year))
#     tag_type = fields.Selection([
#         ('local', 'Local'),
#         ('export', 'Export'),
#         ('all', 'All')
#     ], string='Region', default='all')
#     month = fields.Selection([
#         ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
#         ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
#         ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December'),
#     ])
#     quarter = fields.Selection(
#         [('Q1', 'Quarter 1'), ('Q2', 'Quarter 2'), ('Q3', 'Quarter 3'), ('Q4', 'Quarter 4')]
#     )

#     @api.depends('year', 'company_id', 'tag_type', 'month', 'quarter')
#     def _compute_dashboard_data(self):
#         for record in self:
#             record.dashboard_data = json.dumps(record._get_dashboard_data())
#             record.last_update = fields.Datetime.now()

#     @api.model
#     def get_dashboard_data_json(self, year=None, tag_type=None, month=None, quarter=None):
#         """API method to get dashboard data in JSON format"""
#         if not year:
#             year = str(fields.Date.today().year)

#         dashboard = self.search([
#             ('year', '=', year),
#             ('month', '=', month),
#             ('quarter', '=', quarter),
#             ('tag_type', '=', tag_type or 'all'),
#             ('company_id', '=', self.env.company.id)
#         ], limit=1)
        
#         if not dashboard:
#             dashboard = self.create({
#                 'year': year,
#                 'month': month,
#                 'quarter': quarter,
#                 'tag_type': tag_type or 'all',
#                 'company_id': self.env.company.id
#             })
        
#         dashboard._compute_dashboard_data()
#         return dashboard.dashboard_data

#     def _get_dashboard_data(self):
#         """Compute all dashboard data and return as a structured dictionary"""
#         self.ensure_one()
        
#         year = int(self.year) if self.year else datetime.now().year
        
#         # Initialize start and end dates - will be modified based on filters
#         start_date = None
#         end_date = None
        
#         # Handle quarter filter (takes precedence over month)
#         if self.quarter:
#             if self.quarter == 'Q1':
#                 start_date = datetime(year, 1, 1)
#                 end_date = datetime(year, 3, 31)
#             elif self.quarter == 'Q2':
#                 start_date = datetime(year, 4, 1)
#                 end_date = datetime(year, 6, 30)
#             elif self.quarter == 'Q3':
#                 start_date = datetime(year, 7, 1)
#                 end_date = datetime(year, 9, 30)
#             elif self.quarter == 'Q4':
#                 start_date = datetime(year, 10, 1)
#                 end_date = datetime(year, 12, 31)
            
#             # When quarter is set, month filter is ignored
#             month_name = None
#             month = 0
#             # Explicitly set month to None to ensure consistency
#             self.month = None
#         # Handle month filter
#         elif self.month:
#             month = int(self.month)
#             # Use date_utils to correctly calculate start and end of month
#             start_date = datetime(year, month, 1)
#             # End date should be the last day of the month
#             start_date = date_utils.start_of(start_date, 'month')
#             end_date = date_utils.end_of(start_date, 'month')
#             month_name = dict(self._fields['month'].selection).get(self.month)
#             # Explicitly set quarter to None to ensure consistency
#             self.quarter = None
#         # Default to full year if neither quarter nor month is specified
#         else:
#             start_date = datetime(year, 1, 1)
#             end_date = datetime(year, 12, 31)
#             month = 0
#             month_name = None
        
#         # Convert datetime objects to string format for Odoo's ORM
#         start_date_str = fields.Date.to_string(start_date)
#         end_date_str = fields.Date.to_string(end_date)
        
#         tag_type = self.tag_type if self.tag_type else 'all'
        
#         return {
#             'filters': {
#                 'year': year,
#                 'month': month,
#                 'month_name': month_name,
#                 'quarter': self.quarter,
#                 'tag_type': tag_type,
#                 'date_range': f"{start_date_str} to {end_date_str}",
#             },
#             'company': {
#                 'name': self.company_id.name,
#                 'currency': self.currency_id.symbol,
#                 'country': self.company_id.country_id.name or _('Not Set')
#             },
#             'projects': self._get_project_rows(start_date_str, end_date_str, tag_type),
#         }

#     def _get_project_rows(self, start_date, end_date, tag_type):
#         """
#         Get project data rows for reporting based on date range and tag type.
        
#         Args:
#             start_date (str): The start date to filter projects
#             end_date (str): The end date to filter projects
#             tag_type (str, optional): Filter by tag name
        
#         Returns:
#             list: List of dictionaries with project financial data
#         """
#         domain = [
#             ('company_id', '=', self.company_id.id),
#             ('state', '!=', 'cancel'),
#             ('date_order', '>=', start_date), 
#             ('date_order', '<=', end_date)
#         ]
#         sales_orders = self.env['sale.order'].search(domain)

#         if not sales_orders:
#             return []
        
#         local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
#         export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

#         local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
#         export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])

#         local_analytic_account_ids = local_projects.mapped('analytic_account_id').ids
#         export_analytic_account_ids = export_projects.mapped('analytic_account_id').ids
        
#         results = []
#         for sales_order in sales_orders:
#             if sales_order.project_ids:
#                 if tag_type == 'local' or tag_type == 'all':
#                     for local_project in local_projects:
#                         if local_project in sales_order.project_ids:
#                             data = self._get_project_data(local_project, sale_order, start_date, end_date)
#                             data['ragion'] = 'Local'
#                             results.append(data)
#                 if tag_type == 'export' or tag_type == 'all':
#                     for export_project in export_projects:
#                         if export_project in sales_order.project_ids:
#                             data = self._get_project_data(local_project, sale_order, start_date, end_date)
#                             data['ragion'] = 'Export'
#                             results.append(data)

#             else:
#                 order_lines = sales_order.order_line
#                 for line in order_lines:
#                     if line.analytic_distribution:
#                         try:
#                             distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
#                                 else eval(line.analytic_distribution)
                            
#                             for account_id, percentage in distribution.items():
#                                 account_id = int(account_id)
                                
#                                 if tag_type == 'local' or tag_type == 'all':
#                                     if account_id in local_analytic_account_ids:
#                                         data = self._get_project_data(local_project, sale_order, start_date, end_date)
#                                         data['ragion'] = 'Local'
#                                         results.append(data)
#                                 if tag_type == 'export' or tag_type == 'all':
#                                     if account_id in export_analytic_account_ids:
#                                         data = self._get_project_data(local_project, sale_order, start_date, end_date)
#                                         data['ragion'] = 'Export'
#                                         results.append(data)
                                    
#                         except Exception as e:
#                             _logger.error(f"Error processing analytic distribution for order {sales_order.id}: {e}")

#         return results

#     def _get_project_sale_date(self, project, sale_order, start_date, end_date):
#         data = {
#             "project": proj.name,
#             "customer": proj.partner_id.name if proj.partner_id else _('No Customer'),
#             "date": sale_order.date_order,
#             "po_value": 0,
#             "invoiced": 0,
#             "collected": 0,
#             "pending_collection": 0,
#             "outstanding_aging": 0,
#             "vendor_invoice": 0,
#             "payment_made": 0,
#             "payment_to_be_made": 0,
#             "payroll_cost": 0,
#             "total_outgoing": 0,
#             "total_margin": 0,
#             "margin_percent": 0
#         }
        
#         data["po_value"] = sale_order.amount_untaxed
        
#         # Calculate invoiced amount - use invoice_date for filtering
#         invoices = self.env['account.move'].search([
#             ('move_type', '=', 'out_invoice'),
#             ('state', 'not in', ['draft', 'cancel']),
#             ('invoice_date', '>=', start_date),
#             ('invoice_date', '<=', end_date),
#         ])
        
#         # Link invoices to this project through sales orders
#         project_invoices = invoices.filtered(
#             lambda inv: any(
#                 line.sale_line_ids and line.sale_line_ids.order_id in project_sales_orders 
#                 for line in inv.invoice_line_ids 
#                 if hasattr(line, 'sale_line_ids') and line.sale_line_ids
#             )
#         )
        
#         data["invoiced"] = sum(project_invoices.mapped('amount_untaxed'))
        
#         # Calculate collected amount (paid invoices)
#         collected_invoices = project_invoices.filtered(
#             lambda inv: inv.payment_state in ['paid', 'in_payment']
#         )
#         data["collected"] = sum(collected_invoices.mapped('amount_untaxed'))
        
#         # Calculate pending collection
#         data["pending_collection"] = data["invoiced"] - data["collected"]
        
#         # Calculate outstanding aging from first sale order date to today
#         domain = [
#             ('company_id', '=', self.company_id.id),
#             ('state', '!=', 'cancel')
#         ]
        
#         today = fields.Date.today()
#         data["outstanding_aging"] = (today - sale_order.date_order).days

#         # Calculate vendor invoices (supplier bills)
#         vendor_bills = self.env['account.move'].search([
#             ('move_type', '=', 'in_invoice'),
#             ('state', 'not in', ['draft', 'cancel']),
#             ('invoice_date', '>=', start_date),
#             ('invoice_date', '<=', end_date),
#         ])
        
#         # Find project's analytic account
#         project_analytic_account = proj.analytic_account_id
#         project_vendor_bills = self.env['account.move']
        
#         if project_analytic_account:
#             # Method 1: Direct link through analytic_account_id field on bill
#             try:
#                 project_vendor_bills_direct = vendor_bills.filtered(
#                     lambda bill: hasattr(bill, 'analytic_account_id') and 
#                                 bill.analytic_account_id and 
#                                 bill.analytic_account_id.id == project_analytic_account.id
#                 )
#                 project_vendor_bills |= project_vendor_bills_direct
#             except Exception as e:
#                 _logger.warning(f"Error finding vendor bills by direct analytic account: {e}")
            
#             # Method 2: Through analytic distribution on invoice lines (Odoo 15+)
#             try:
#                 project_vendor_bills_dist = vendor_bills.filtered(
#                     lambda bill: any(
#                         hasattr(line, 'analytic_distribution') and
#                         line.analytic_distribution and 
#                         str(project_analytic_account.id) in line.analytic_distribution
#                         for line in bill.invoice_line_ids
#                     )
#                 )
#                 project_vendor_bills |= project_vendor_bills_dist
#             except Exception as e:
#                 _logger.warning(f"Error finding vendor bills by analytic distribution: {e}")
            
#             # Method 3: Through analytic_account_id on invoice lines (older versions)
#             try:
#                 project_vendor_bills_lines = vendor_bills.filtered(
#                     lambda bill: any(
#                         hasattr(line, 'analytic_account_id') and 
#                         line.analytic_account_id and 
#                         line.analytic_account_id.id == project_analytic_account.id
#                         for line in bill.invoice_line_ids
#                     )
#                 )
#                 project_vendor_bills |= project_vendor_bills_lines
#             except Exception as e:
#                 _logger.warning(f"Error finding vendor bills by line analytic account: {e}")
        
#         data["vendor_invoice"] = sum(project_vendor_bills.mapped('amount_untaxed'))
        
#         # Calculate payment made to vendors
#         paid_vendor_bills = project_vendor_bills.filtered(
#             lambda bill: bill.payment_state in ['paid', 'in_payment']
#         )
#         data["payment_made"] = sum(paid_vendor_bills.mapped('amount_untaxed'))
        
#         # Calculate payment to be made
#         data["payment_to_be_made"] = data["vendor_invoice"] - data["payment_made"]
        
#         # Calculate payroll cost for Odoo 16
#         payroll_cost = 0
        
#         # Get timesheets for this project
#         timesheet_domain = [
#             ('project_id', '=', proj.id),
#             ('date', '>=', start_date),
#             ('date', '<=', end_date),
#         ]
        
#         timesheets = self.env['account.analytic.line'].search(timesheet_domain)
        
#         for timesheet in timesheets:
#             employee = timesheet.employee_id
#             if employee and hasattr(employee, 'hourly_cost'):
#                 cost = employee.hourly_cost * timesheet.unit_amount
#                 payroll_cost += cost
#             # Fallback for if hourly_cost isn't available
#             elif hasattr(timesheet, 'amount') and timesheet.amount:
#                 payroll_cost -= timesheet.amount  # Amount is negative in analytic lines
        
#         data["payroll_cost"] = payroll_cost
        
#         # Calculate total outgoing
#         data["total_outgoing"] = data["vendor_invoice"] + data["payroll_cost"]
        
#         # Calculate total margin
#         data["total_margin"] = data["po_value"] - data["total_outgoing"]
        
#         # Calculate margin percentage
#         if data["po_value"] > 0:
#             data["margin_percent"] = (data["total_margin"] / data["po_value"]) * 100
#         else:
#             data["margin_percent"] = 0

#         # Format values
#         data["po_value"] = self._format_value(data["po_value"])
#         data["invoiced"] = self._format_value(data["invoiced"])
#         data["collected"] = self._format_value(data["collected"])
#         data["pending_collection"] = self._format_value(data["pending_collection"])
#         data["vendor_invoice"] = self._format_value(data["vendor_invoice"])
#         data["payment_made"] = self._format_value(data["payment_made"])
#         data["payment_to_be_made"] = self._format_value(data["payment_to_be_made"])
#         data["payroll_cost"] = self._format_value(data["payroll_cost"])
#         data["total_outgoing"] = self._format_value(data["total_outgoing"])
#         data["total_margin"] = self._format_value(data["total_margin"])
#         data["margin_percent"] = self._format_value(data["margin_percent"])

#         return data

#     def _format_value(self, value):
#         """Format a value to the currency format"""
#         if not value:
#             return 0.0
            
#         if isinstance(value, float):
#             return round(value, 2)
#         return value


import json
import logging
from datetime import datetime, timedelta
from odoo import api, fields, models, Command, _
from odoo.tools import date_utils, float_round
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class L4Dashboard(models.Model):
    _name = 'l4.dashboard'
    _description = 'L4 Dashboard Data'
    _rec_name = 'name'
    _order = 'create_date desc'

    name = fields.Char(string='L4 Dashboard', default=lambda self: _('L4 Dashboard - %s') % fields.Date.today().strftime('%Y'))
    dashboard_data = fields.Text(string='Dashboard Data', compute='_compute_dashboard_data', store=False)
    last_update = fields.Datetime(string='Last Update', readonly=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    active = fields.Boolean(default=True)

    def _get_year_selection(self):
        """Get available years for selection starting from 2023"""
        current_year = datetime.now().year
        return [(str(year), str(year)) for year in range(2023, current_year + 1)]

    year = fields.Selection(selection=_get_year_selection, string='Year', default=lambda self: str(fields.Date.today().year))
    tag_type = fields.Selection([
        ('local', 'Local'),
        ('export', 'Export'),
        ('all', 'All')
    ], string='Region', default='all')
    month = fields.Selection([
        ('1', 'January'), ('2', 'February'), ('3', 'March'), ('4', 'April'),
        ('5', 'May'), ('6', 'June'), ('7', 'July'), ('8', 'August'),
        ('9', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December'),
    ], string='Month')
    quarter = fields.Selection(
        [('Q1', 'Quarter 1'), ('Q2', 'Quarter 2'), ('Q3', 'Quarter 3'), ('Q4', 'Quarter 4')],
        string='Quarter'
    )

    _sql_constraints = [
        ('unique_dashboard_config', 
         'UNIQUE(year, tag_type, month, quarter, company_id)',
         'Dashboard configuration must be unique!')
    ]

    @api.depends('year', 'company_id', 'tag_type', 'month', 'quarter')
    def _compute_dashboard_data(self):
        """Compute dashboard data based on current filters"""
        for record in self:
            try:
                data = record._get_dashboard_data()
                record.dashboard_data = json.dumps(data)
                record.last_update = fields.Datetime.now()
            except Exception as e:
                _logger.error(f"Error computing dashboard data: {e}")
                record.dashboard_data = json.dumps({
                    'error': str(e),
                    'filters': {
                        'year': record.year,
                        'tag_type': record.tag_type,
                        'month': record.month,
                        'quarter': record.quarter,
                    }
                })

    @api.model
    def get_dashboard_data_json(self, year=None, tag_type=None, month=None, quarter=None):
        """API method to get dashboard data in JSON format
        
        Args:
            year (str): Year to filter by
            tag_type (str): Region filter (local/export/all)
            month (str): Month number to filter by
            quarter (str): Quarter to filter by
            
        Returns:
            str: JSON data for dashboard
        """
        if not year:
            year = str(fields.Date.today().year)

        # Validate parameters
        if month and quarter:
            # Cannot have both month and quarter
            quarter = None
            
        # Avoid creating unnecessary records, search first
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
        
        # Recompute data (don't rely on stored value since data changes frequently)
        dashboard._compute_dashboard_data()
        return dashboard.dashboard_data

    def _get_dashboard_data(self):
        """Compute all dashboard data and return as a structured dictionary
        
        Returns:
            dict: Complete dashboard data structure
        """
        self.ensure_one()
        
        year = int(self.year) if self.year else datetime.now().year
        
        # Initialize start and end dates - will be modified based on filters
        start_date, end_date = self._get_filter_date_range(year)
        
        # Handle quarter filter (takes precedence over month)
        if self.quarter and self.month:
            # Reset month when quarter is set to ensure consistency
            self.write({'month': False})
        
        # Format dates for ORM
        start_date_str = fields.Date.to_string(start_date)
        end_date_str = fields.Date.to_string(end_date)
        
        # Get month name if filtering by month
        month_name = None
        if self.month:
            month_name = dict(self._fields['month'].selection).get(self.month)
        
        tag_type = self.tag_type or 'all'
        
        return {
            'filters': {
                'year': year,
                'month': int(self.month) if self.month else 0,
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
            'summary': self._get_dashboard_summary(start_date_str, end_date_str, tag_type),
        }
        
    def _get_filter_date_range(self, year):
        """Calculate start and end dates based on filters
        
        Args:
            year (int): Year to filter by
            
        Returns:
            tuple: (start_date, end_date) as datetime objects
        """
        # Handle quarter filter
        if self.quarter:
            if self.quarter == 'Q1':
                start_date = datetime(year, 1, 1)
                end_date = datetime(year, 3, 31, 23, 59, 59)
            elif self.quarter == 'Q2':
                start_date = datetime(year, 4, 1)
                end_date = datetime(year, 6, 30, 23, 59, 59)
            elif self.quarter == 'Q3':
                start_date = datetime(year, 7, 1)
                end_date = datetime(year, 9, 30, 23, 59, 59)
            elif self.quarter == 'Q4':
                start_date = datetime(year, 10, 1)
                end_date = datetime(year, 12, 31, 23, 59, 59)
        # Handle month filter
        elif self.month:
            month = int(self.month)
            # Calculate start and end of month
            start_date = datetime(year, month, 1)
            end_date = date_utils.end_of(start_date, 'month')
        # Default to full year
        else:
            start_date = datetime(year, 1, 1)
            end_date = datetime(year, 12, 31, 23, 59, 59)
            
        return start_date, end_date
        
    def _get_region_projects(self, tag_type):
        """Get projects based on region tag
        
        Args:
            tag_type (str): Region filter ('local', 'export' or 'all')
            
        Returns:
            tuple: (local_projects, export_projects, local_analytic_ids, export_analytic_ids)
        """
        # Get region tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)
        
        # Get projects by tag
        local_projects = self.env['project.project']
        export_projects = self.env['project.project']
        local_analytic_ids = []
        export_analytic_ids = []
        
        if tag_type in ('local', 'all') and local_tag:
            local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
            local_analytic_ids = local_projects.mapped('analytic_account_id').ids
            
        if tag_type in ('export', 'all') and export_tag:
            export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])
            export_analytic_ids = export_projects.mapped('analytic_account_id').ids
            
        return local_projects, export_projects, local_analytic_ids, export_analytic_ids

    def _get_project_rows(self, start_date, end_date, tag_type):
        """Get project data rows for reporting based on date range and tag type
        
        Args:
            start_date (str): The start date to filter projects
            end_date (str): The end date to filter projects
            tag_type (str): Filter by region tag ('local', 'export' or 'all')
        
        Returns:
            list: List of dictionaries with project financial data
        """
        # Find sales orders within date range
        domain = [
            ('company_id', '=', self.company_id.id),
            ('state', '!=', 'cancel'),
            ('date_order', '>=', start_date), 
            ('date_order', '<=', end_date)
        ]
        sales_orders = self.env['sale.order'].search(domain)

        if not sales_orders:
            return []
            
        # Get projects by region tag
        local_projects, export_projects, local_analytic_ids, export_analytic_ids = self._get_region_projects(tag_type)
        
        # Process each sales order
        results = []
        processed_project_ids = set()  # Track processed projects to avoid duplicates
        
        for order in sales_orders:
            # Handle projects directly linked to sales orders
            if order.project_ids:
                projects_to_process = []
                
                # Add relevant projects based on tag_type
                if tag_type in ('local', 'all'):
                    projects_to_process.extend(local_projects & order.project_ids)
                    
                if tag_type in ('export', 'all'):
                    projects_to_process.extend(export_projects & order.project_ids)
                    
                # Process each project linked to this sales order
                for project in projects_to_process:
                    if project.id in processed_project_ids:
                        continue
                        
                    processed_project_ids.add(project.id)
                    project_region = 'Local' if project in local_projects else 'Export'
                    
                    try:
                        data = self._get_project_data(project, order, start_date, end_date)
                        data['region'] = project_region
                        results.append(data)
                    except Exception as e:
                        _logger.error(f"Error processing project {project.name}: {e}")
            
            # Handle analytic distribution on order lines
            else:
                for line in order.order_line:
                    if not line.analytic_distribution:
                        continue
                        
                    try:
                        # Ensure we have a dictionary
                        distribution = line.analytic_distribution
                        if isinstance(distribution, str):
                            distribution = json.loads(distribution.replace("'", '"'))
                            
                        # Process each account in the distribution
                        for account_id_str, percentage in distribution.items():
                            account_id = int(account_id_str)
                            
                            # Find associated project
                            project = self.env['project.project'].search([
                                ('analytic_account_id', '=', account_id)
                            ], limit=1)
                            
                            if not project or project.id in processed_project_ids:
                                continue
                                
                            processed_project_ids.add(project.id)
                            
                            # Determine region based on analytic account
                            project_region = None
                            if account_id in local_analytic_ids:
                                if tag_type not in ('local', 'all'):
                                    continue
                                project_region = 'Local'
                            elif account_id in export_analytic_ids:
                                if tag_type not in ('export', 'all'):
                                    continue
                                project_region = 'Export'
                            else:
                                continue  # Skip if not matching our tag filters
                                
                            data = self._get_project_data(project, order, start_date, end_date)
                            data['region'] = project_region
                            results.append(data)
                            
                    except Exception as e:
                        _logger.error(f"Error processing analytic distribution for order {order.id}: {e}")
        
        return results

    def _get_project_data(self, project, sale_order, start_date, end_date):
        """Calculate financial data for a project
        
        Args:
            project: project.project record
            sale_order: sale.order record
            start_date: Start date string
            end_date: End date string
            
        Returns:
            dict: Project financial data
        """
        data = {
            "project": project.name,
            "customer": project.partner_id.name if project.partner_id else _('No Customer'),
            "date": sale_order.date_order.strftime('%Y-%m-%d'),
            "po_value": 0.0,
            "invoiced": 0.0,
            "collected": 0.0,
            "pending_collection": 0.0,
            "outstanding_aging": 0,
            "vendor_invoice": 0.0,
            "payment_made": 0.0,
            "payment_to_be_made": 0.0,
            "payroll_cost": 0.0,
            "total_outgoing": 0.0,
            "total_margin": 0.0,
            "margin_percent": 0.0
        }
        
        # Get project's sales orders
        project_sales_orders = sale_order
        if hasattr(project, 'sale_order_id') and project.sale_order_id:
            project_sales_orders |= project.sale_order_id
        if hasattr(project, 'sale_line_id') and project.sale_line_id:
            project_sales_orders |= project.sale_line_id.order_id
            
        # Total value from sale order
        data["po_value"] = sale_order.amount_untaxed
        
        # Calculate invoiced amount
        invoices = self._get_project_invoices(project, project_sales_orders, start_date, end_date)
        data["invoiced"] = sum(invoices.mapped('amount_untaxed_signed'))
        
        # Calculate collected amount (paid invoices)
        collected_invoices = invoices.filtered(
            lambda inv: inv.payment_state in ['paid', 'in_payment']
        )
        data["collected"] = sum(collected_invoices.mapped('amount_untaxed_signed'))
        
        # Calculate pending collection
        data["pending_collection"] = data["invoiced"] - data["collected"]
        
        if data['pending_collection'] > 0:
            # Calculate outstanding aging from first sale order date to today
            today = fields.Date.today()
            data["outstanding_aging"] = (today - sale_order.date_order.date()).days
        else:
            data["outstanding_aging"] = 0
            
        # Calculate vendor bills and payments
        vendor_bills = self._get_project_vendor_bills(project, start_date, end_date)
        data["vendor_invoice"] = sum(vendor_bills.mapped('amount_untaxed'))
        
        # Calculate payment made to vendors
        paid_vendor_bills = vendor_bills.filtered(
            lambda bill: bill.payment_state in ['paid', 'in_payment']
        )
        data["payment_made"] = sum(paid_vendor_bills.mapped('amount_untaxed'))
        
        # Calculate payment to be made
        data["payment_to_be_made"] = data["vendor_invoice"] - data["payment_made"]
        
        # Calculate payroll cost using timesheets
        data["payroll_cost"] = self._calculate_project_payroll(project, start_date, end_date)
        
        # Calculate total outgoing
        data["total_outgoing"] = data["vendor_invoice"] + data["payroll_cost"]
        
        # Calculate total margin
        data["total_margin"] = data["po_value"] - data["total_outgoing"]
        
        # Calculate margin percentage
        if data["po_value"] > 0:
            data["margin_percent"] = (data["total_margin"] / data["po_value"]) * 100
        
        return self._format_project_data(data)
        
    def _get_project_invoices(self, project, sale_orders, start_date, end_date):
        """Get customer invoices related to a project
        
        Args:
            project: project.project record
            sale_orders: sale.order recordset
            start_date: Start date string
            end_date: End date string
            
        Returns:
            recordset: account.move records
        """
        # Find all invoices in date range
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', 'not in', ['draft', 'cancel']),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('company_id', '=', self.company_id.id),
        ]
        
        invoices = self.env['account.move'].search(domain)
        if not invoices:
            return self.env['account.move']
            
        # Link invoices to project through sale orders
        project_invoices = self.env['account.move']
        
        # Method 1: Through invoice lines linked to sale order lines
        project_invoices |= invoices.filtered(
            lambda inv: any(
                line.sale_line_ids and line.sale_line_ids.order_id in sale_orders
                for line in inv.invoice_line_ids
                if hasattr(line, 'sale_line_ids') and line.sale_line_ids
            )
        )
        
        # Method 2: Through analytic account on invoice lines
        if project.analytic_account_id:
            # Get by analytic distribution (Odoo 16)
            analytic_invoices = invoices.filtered(
                lambda inv: any(
                    line.analytic_distribution and 
                    str(project.analytic_account_id.id) in line.analytic_distribution
                    for line in inv.invoice_line_ids
                    if hasattr(line, 'analytic_distribution')
                )
            )
            project_invoices |= analytic_invoices
            
        return project_invoices
        
    def _get_project_vendor_bills(self, project, start_date, end_date):
        """Get vendor bills related to a project
        
        Args:
            project: project.project record
            start_date: Start date string
            end_date: End date string
            
        Returns:
            recordset: account.move records
        """
        # Find vendor bills in date range
        domain = [
            ('move_type', '=', 'in_invoice'),
            ('state', 'not in', ['draft', 'cancel']),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('company_id', '=', self.company_id.id),
        ]
        
        vendor_bills = self.env['account.move'].search(domain)
        if not vendor_bills or not project.analytic_account_id:
            return self.env['account.move']
            
        project_vendor_bills = self.env['account.move']
        analytic_account_id = project.analytic_account_id.id
        str_analytic_id = str(analytic_account_id)
        
        # Get by analytic distribution (Odoo 16)
        for bill in vendor_bills:
            for line in bill.invoice_line_ids:
                if hasattr(line, 'analytic_distribution') and line.analytic_distribution:
                    dist = line.analytic_distribution
                    if isinstance(dist, str):
                        try:
                            dist = json.loads(dist.replace("'", '"'))
                        except:
                            continue
                            
                    if str_analytic_id in dist:
                        project_vendor_bills |= bill
                        break
                        
        return project_vendor_bills
        
    def _calculate_project_payroll(self, project, start_date, end_date):
        """Calculate payroll cost for project using timesheets
        
        Args:
            project: project.project record
            start_date: Start date string
            end_date: End date string
            
        Returns:
            float: Total payroll cost
        """
        # Get timesheets for this project
        domain = [
            ('project_id', '=', project.id),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
        ]
        
        timesheets = self.env['account.analytic.line'].search(domain)
        if not timesheets:
            return 0.0
            
        # Calculate cost
        payroll_cost = 0.0
        
        for timesheet in timesheets:
            employee = timesheet.employee_id
            if not employee:
                continue
                
            # Get hourly cost with fallbacks
            hourly_cost = 0.0
            
            # Method 1: Direct hourly_cost field (depends on HR modules)
            if hasattr(employee, 'hourly_cost') and employee.hourly_cost:
                hourly_cost = employee.hourly_cost
            # Method 2: From timesheet costs
            elif hasattr(timesheet, 'unit_cost') and timesheet.unit_cost:
                hourly_cost = timesheet.unit_cost
            # Method 3: From timesheet amount (negative in analytic lines)
            elif hasattr(timesheet, 'amount') and timesheet.amount:
                payroll_cost -= timesheet.amount  # Amount is negative in analytic lines
                continue
                
            payroll_cost += hourly_cost * timesheet.unit_amount
            
        return payroll_cost
        
    def _format_project_data(self, data):
        """Format project data values
        
        Args:
            data: Dictionary of project data
            
        Returns:
            dict: Formatted project data
        """
        # Format numeric values
        for key in data:
            if isinstance(data[key], float):
                data[key] = float_round(data[key], precision_digits=2)
                
        return data
        
    def _get_dashboard_summary(self, start_date, end_date, tag_type):
        """Get summary data for dashboard
        
        Args:
            start_date: Start date string
            end_date: End date string
            tag_type: Region filter
            
        Returns:
            dict: Summary data
        """
        # Initialize summary data
        summary = {
            'total_po_value': 0.0,
            'total_invoiced': 0.0,
            'total_collected': 0.0,
            'total_vendor_invoice': 0.0,
            'total_payment_made': 0.0,
            'total_payroll_cost': 0.0,
            'total_margin': 0.0,
            'avg_margin_percent': 0.0,
            'project_count': 0,
        }
        
        # Reuse project rows data
        project_rows = self._get_project_rows(start_date, end_date, tag_type)
        if not project_rows:
            return summary
            
        # Sum values from all projects
        for row in project_rows:
            summary['total_po_value'] += row['po_value']
            summary['total_invoiced'] += row['invoiced']
            summary['total_collected'] += row['collected']
            summary['total_vendor_invoice'] += row['vendor_invoice']
            summary['total_payment_made'] += row['payment_made']
            summary['total_payroll_cost'] += row['payroll_cost']
            summary['total_margin'] += row['total_margin']
            
        summary['project_count'] = len(project_rows)
        
        # Calculate average margin percentage
        if summary['total_po_value'] > 0:
            summary['avg_margin_percent'] = (summary['total_margin'] / summary['total_po_value']) * 100
            
        # Format values
        for key in summary:
            if isinstance(summary[key], float):
                summary[key] = float_round(summary[key], precision_digits=2)
                
        return summary

    def _format_value(self, value):
        """Format a value to the currency format
        
        Args:
            value: Value to format
            
        Returns:
            float: Rounded value
        """
        if not value:
            return 0.0
            
        if isinstance(value, float):
            return float_round(value, precision_digits=2)
        return value