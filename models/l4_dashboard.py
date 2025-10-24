import json
import io
import xlsxwriter
import base64
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
        """API method to get dashboard data in JSON format"""
        if not year:
            year = fields.Date.today().year
            
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
        
        tag_type = self.tag_type or 'all'

        project_rows = self._get_project_rows(start_date, end_date, tag_type)
        
        return {
            'filters': {
                'year': year,
                'month': int(self.month) if self.month else 0,
                'month_name': month,
                'quarter': self.quarter,
                'tag_type': tag_type,
                'date_range': f"{start_date} to {end_date}",
            },
            'company': {
                'name': self.company_id.name,
                'currency': self.currency_id.symbol,
                'country': self.company_id.country_id.name or _('Not Set')
            },
            'projects': project_rows,
            'summary': self._get_dashboard_summary(project_rows),
        }
        
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
        ]
        sales_orders = self.env['sale.order'].search(domain)

        # Find projects within date range
        domain = [
            ('company_id', '=', self.company_id.id),
            ('date_start', '>=', start_date), 
            ('date_start', '<=', end_date)
        ]
        projects = self.env['project.project'].search(domain)

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
                        if project in projects:
                            data = self._get_project_data(project, order, start_date, end_date, 
                                                        local_analytic_ids if project_region == 'Local' else export_analytic_ids)
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
                            
                            try:
                                if project in projects:
                                    data = self._get_project_data(project, order, start_date, end_date,
                                                                local_analytic_ids if project_region == 'Local' else export_analytic_ids)
                                    data['region'] = project_region
                                    results.append(data)
                            except Exception as e:
                                _logger.error(f"Error processing project {project.name} with analytic distribution: {e}")
                            
                    except Exception as e:
                        _logger.error(f"Error processing analytic distribution for order {order.id}: {e}")
        
        return results

    def _get_project_data(self, project, sale_order, start_date, end_date, analytic_ids):
        """Calculate financial data for a project
        
        Args:
            project: project.project record
            sale_order: sale.order record
            start_date: Start date string
            end_date: End date string
            analytic_ids: List of analytic account IDs
            
        Returns:
            dict: Project financial data
        """
        data = {
            "project_id": project.id,
            "project": project.name,
            "customer": project.partner_id.name if project.partner_id else _('No Customer'),
            "date": project.date_start.strftime('%Y-%m-%d') if hasattr(project, "date_start") else "",
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
        company_currency = self.env.company.currency_id

        for so in project_sales_orders:
            if so.currency_id != company_currency:
                data["po_value"] += so.currency_id._convert(so.amount_untaxed, company_currency, self.env.company, so.date_order)
            else:
                data["po_value"] += so.amount_untaxed
        
        data["invoiced"] = 0.0
        for so in project_sales_orders:
            data["invoiced"] += sum(so.invoice_ids.mapped('amount_untaxed_signed'))
        
        data["collected"] = 0.0
        for so in project_sales_orders:
            invoices = so.invoice_ids.filtered(lambda inv: inv.state not in ['draft', 'cancel'])
            collected_invoices = invoices.filtered(
                lambda inv: inv.payment_state in ['paid', 'in_payment']
            )
            data["collected"] += sum(collected_invoices.mapped('amount_untaxed_signed'))

        # Calculate pending collection
        data["pending_collection"] = data["invoiced"] - data["collected"]
        
        if data['pending_collection'] > 0:
            # Calculate outstanding aging from first sale order date to today
            today = fields.Date.today()
            data["outstanding_aging"] = (today - sale_order.date_order.date()).days
        else:
            data["outstanding_aging"] = 0

        # Calculate vendor bills and payments
        vendor_bills_data = self._get_project_vendor_bills_data(project, start_date, end_date)
        
        data["vendor_invoice"] = vendor_bills_data['total_amount']
        data["payment_made"] = vendor_bills_data['paid_amount']
        data["payment_to_be_made"] = data["vendor_invoice"] - data["payment_made"]
        
        # Calculate payroll cost using timesheets
        data["payroll_cost"] = self._calculate_project_payroll(project, start_date, end_date)
        
        # Calculate total outgoing
        data["total_outgoing"] = data["vendor_invoice"] + data["payroll_cost"]
        
        # Calculate total margin based on Invoice value instead of PO value
        data["total_margin"] = data["invoiced"] - data["total_outgoing"]

        # Calculate margin percentage based on Invoice value instead of PO value
        if data["invoiced"] > 0:
            data["margin_percent"] = (data["total_margin"] / data["invoiced"]) * 100
        else:
            data["margin_percent"] = 0.0
        
        return self._format_project_data(data)

    def _get_project_vendor_bills_data(self, project, start_date, end_date):
        """Get comprehensive vendor bills data related to a project
        
        Args:
            project: project.project record
            start_date: Start date string
            end_date: End date string
            
        Returns:
            dict: Contains total_amount and paid_amount for vendor bills
        """
        # Get project analytic account ids
        analytic_ids = project.analytic_account_id.ids if project.analytic_account_id else []
        
        if not analytic_ids:
            return {'total_amount': 0.0, 'paid_amount': 0.0}
        
        total_amount = 0.0
        paid_amount = 0.0
        
        # Get confirmed vendor bills within the date range
        domain = [
            ('move_type', '=', 'in_invoice'),
            ('state', 'not in', ['draft', 'cancel']),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('company_id', '=', self.env.company.id),
        ]
        vendor_bills = self.env['account.move'].search(domain)

        company_currency = self.env.company.currency_id
        
        for bill in vendor_bills:
            for line in bill.invoice_line_ids:
                if line.analytic_distribution:
                    try:
                        distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                            else eval(line.analytic_distribution)
                        
                        for account_id_str, percentage in distribution.items():
                            account_id = int(account_id_str)
                            
                            if account_id in analytic_ids:
                                # Apply the percentage from the distribution
                                line_amount = line.price_subtotal * (percentage / 100.0)

                                # Convert to company currency if needed
                                if bill.currency_id != company_currency:
                                    line_amount = bill.currency_id._convert(line_amount, company_currency, self.env.company, bill.date)
                                    
                                total_amount += line_amount
                                
                                # Check if the bill is actually paid
                                if bill.payment_state in ['paid', 'in_payment']:
                                    paid_amount += line_amount
                    
                    except Exception as e:
                        _logger.error(f"Error processing analytic distribution for bill {bill.id}, line {line.id}: {e}")
        
        return {
            'total_amount': total_amount,
            'paid_amount': paid_amount
        }

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
        
    def _get_dashboard_summary(self, project_rows):
        """Get summary data for dashboard
        
        Args:
            project_rows: a list of project data
            
        Returns:
            dict: Summary data
        """
        # Initialize summary data
        summary = {
            'total_po_value': 0.0,
            'total_invoiced': 0.0,
            'total_collected': 0.0,
            'total_pending_collection': 0.0,
            'total_vendor_invoice': 0.0,
            'total_payment_made': 0.0,
            'total_payment_to_be_made': 0.0,
            'total_payroll_cost': 0.0,
            'total_margin': 0.0,
            'avg_margin_percent': 0.0,
            'project_count': 0,
        }
            
        # Sum values from all projects
        for row in project_rows:
            summary['total_po_value'] += row['po_value']
            summary['total_invoiced'] += row['invoiced']
            summary['total_collected'] += row['collected']
            summary['total_pending_collection'] += row['pending_collection']
            summary['total_vendor_invoice'] += row['vendor_invoice']
            summary['total_payment_made'] += row['payment_made']
            summary['total_payment_to_be_made'] += row['payment_to_be_made']
            summary['total_payroll_cost'] += row['payroll_cost']
            summary['total_margin'] += row['total_margin']
            
        summary['project_count'] = len(project_rows)
        
        # Calculate average margin percentage
        if summary['total_invoiced'] > 0:
            summary['avg_margin_percent'] = (summary['total_margin'] / summary['total_invoiced']) * 100
            
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

    def export_excel(self):
        self.ensure_one()
        data = self._get_dashboard_data()

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet("L3 Dashboard Report")

        # Define formats
        bold = workbook.add_format({'bold': True, 'font_size': 11})
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'left'
        })
        info_label_format = workbook.add_format({
            'bold': True,
            'font_size': 10
        })
        currency_format = workbook.add_format({
            'num_format': '#,##0.00',
            'align': 'right'
        })
        percent_format = workbook.add_format({
            'num_format': '0.00%',
            'align': 'right'
        })
        date_format = workbook.add_format({
            'num_format': 'yyyy-mm-dd',
            'align': 'center'
        })
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter'
        })
        number_cell_format = workbook.add_format({
            'border': 1,
            'num_format': '#,##0.00',
            'align': 'right',
            'valign': 'vcenter'
        })
        percent_cell_format = workbook.add_format({
            'border': 1,
            'num_format': '0.00%',
            'align': 'right',
            'valign': 'vcenter'
        })
        summary_label_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
            'align': 'left'
        })
        summary_value_format = workbook.add_format({
            'bold': True,
            'bg_color': '#D9E1F2',
            'border': 1,
            'num_format': '#,##0.00',
            'align': 'right'
        })

        # Set column widths
        worksheet.set_column('A:A', 25)  # Project
        worksheet.set_column('B:B', 20)  # Customer
        worksheet.set_column('C:C', 12)  # Region
        worksheet.set_column('D:D', 12)  # Date
        worksheet.set_column('E:N', 15)  # Financial columns

        row = 0

        # Title
        worksheet.write(row, 0, 'L3 Dashboard Report', title_format)
        row += 2

        # Company Information
        worksheet.write(row, 0, 'Company:', info_label_format)
        worksheet.write(row, 1, data['company']['name'])
        row += 1
        worksheet.write(row, 0, 'Currency:', info_label_format)
        worksheet.write(row, 1, data['company']['currency'])
        row += 1
        worksheet.write(row, 0, 'Country:', info_label_format)
        worksheet.write(row, 1, data['company']['country'])
        row += 2

        # Filter Information
        worksheet.write(row, 0, 'Report Filters:', info_label_format)
        row += 1
        worksheet.write(row, 0, 'Year:', info_label_format)
        worksheet.write(row, 1, str(data['filters']['year']))
        row += 1
        
        if data['filters']['quarter']:
            worksheet.write(row, 0, 'Quarter:', info_label_format)
            worksheet.write(row, 1, data['filters']['quarter'])
            row += 1
        elif data['filters']['month']:
            worksheet.write(row, 0, 'Month:', info_label_format)
            worksheet.write(row, 1, str(data['filters']['month']))
            row += 1
        
        worksheet.write(row, 0, 'Region:', info_label_format)
        worksheet.write(row, 1, data['filters']['tag_type'].title())
        row += 1
        worksheet.write(row, 0, 'Date Range:', info_label_format)
        worksheet.write(row, 1, data['filters']['date_range'])
        row += 2

        # Project Data Headers
        headers = [
            'Project',
            'Customer',
            'Region',
            'Date',
            'PO Value',
            'Invoiced',
            'Collected',
            'Pending Collection',
            'Outstanding Aging (Days)',
            'Vendor Invoice',
            'Payment Made',
            'Payment To Be Made',
            'Payroll Cost',
            'Total Outgoing',
            'Total Margin',
            'Margin %'
        ]

        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)
        
        row += 1

        # Project Data Rows
        for project in data['projects']:
            worksheet.write(row, 0, project['project'], cell_format)
            worksheet.write(row, 1, project['customer'], cell_format)
            worksheet.write(row, 2, project.get('region', ''), cell_format)
            worksheet.write(row, 3, project['date'], cell_format)
            worksheet.write(row, 4, project['po_value'], number_cell_format)
            worksheet.write(row, 5, project['invoiced'], number_cell_format)
            worksheet.write(row, 6, project['collected'], number_cell_format)
            worksheet.write(row, 7, project['pending_collection'], number_cell_format)
            worksheet.write(row, 8, project['outstanding_aging'], cell_format)
            worksheet.write(row, 9, project['vendor_invoice'], number_cell_format)
            worksheet.write(row, 10, project['payment_made'], number_cell_format)
            worksheet.write(row, 11, project['payment_to_be_made'], number_cell_format)
            worksheet.write(row, 12, project['payroll_cost'], number_cell_format)
            worksheet.write(row, 13, project['total_outgoing'], number_cell_format)
            worksheet.write(row, 14, project['total_margin'], number_cell_format)
            worksheet.write(row, 15, project['margin_percent'] / 100, percent_cell_format)
            row += 1

        # Summary Section
        row += 1
        summary = data['summary']
        
        worksheet.write(row, 0, 'SUMMARY', title_format)
        row += 2

        # Summary data
        summary_items = [
            ('Total Projects', summary['project_count']),
            ('Total PO Value', summary['total_po_value']),
            ('Total Invoiced', summary['total_invoiced']),
            ('Total Collected', summary['total_collected']),
            ('Total Pending Collection', summary['total_pending_collection']),
            ('Total Vendor Invoice', summary['total_vendor_invoice']),
            ('Total Payment Made', summary['total_payment_made']),
            ('Total Payment To Be Made', summary['total_payment_to_be_made']),
            ('Total Payroll Cost', summary['total_payroll_cost']),
            ('Total Margin', summary['total_margin']),
            ('Average Margin %', summary['avg_margin_percent']),
        ]

        for label, value in summary_items:
            worksheet.write(row, 0, label, summary_label_format)
            if label == 'Total Projects':
                worksheet.write(row, 1, int(value), summary_label_format)
            elif label == 'Average Margin %':
                worksheet.write(row, 1, value / 100, percent_cell_format)
            else:
                worksheet.write(row, 1, value, summary_value_format)
            row += 1

        workbook.close()
        output.seek(0)
        file_data = output.read()

        # Generate filename with date
        filename = f'l3_dashboard_report_{data["filters"]["year"]}'
        if data['filters']['quarter']:
            filename += f'_{data["filters"]["quarter"]}'
        elif data['filters']['month']:
            filename += f'_M{data["filters"]["month"]:02d}'
        filename += '.xlsx'

        attachment = self.env['ir.attachment'].create({
            'name': filename,
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
        
        
        
        
    def action_back_to_l2(self):
        """Go back to L2 dashboard."""
        self.ensure_one()
        # Preferred: use the XML-ID of the L2 action if available.
        # Replace 'my_dashboard.action_l2_dashboard' with the real module XML-ID.
        try:
            action = self.env.ref('my_dashboard.action_l2_dashboard').read()[0]
            return action
        except Exception:
            # Fallback to the URL you provided (action=947).
            return {
                'type': 'ir.actions.act_url',
                'url': '/web#action=947&model=l2.dashboard&view_type=form',
                'target': 'self',
            }