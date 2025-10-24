from odoo import models, fields, api, http
from odoo.http import request
import json
import logging
from datetime import date, datetime, timedelta
import io
import xlsxwriter
import base64


_logger = logging.getLogger(__name__)

class L3Dashboard(models.Model):
    _name = 'l3.dashboard'
    _description = 'L3 Project Dashboard'

    project_id = fields.Many2one('project.project', string="Project")
    region = fields.Char(string="Region", readonly=True)
    customer = fields.Char(string="Customer", readonly=True)
    date = fields.Date(string="Project End Date", readonly=True)
    po_value = fields.Float(string="PO Value", readonly=True)
    invoiced = fields.Float(string="Invoiced", readonly=True)
    collected = fields.Float(string="Collected", readonly=True)
    vendor_invoice = fields.Float(string="Vendor Invoice", readonly=True)
    payment_made = fields.Float(string="Payment Made", readonly=True)
    payroll_cost = fields.Float(string="Payroll Cost", readonly=True)
    dashboard_data = fields.Text(string="Dashboard Data", readonly=True)

    @api.model
    def _get_region_projects(self, tag_type=None):
        """Get projects by region tag."""
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)
        
        # Get projects with Local tag
        local_projects = self.env['project.project'].search([
            ('  ', 'in', [local_tag.id]),
            ('active', '=', True)
        ])
        
        # Get projects with Export tag
        export_projects = self.env['project.project'].search([
            ('tag_ids', 'in', [export_tag.id]),
            ('active', '=', True)
        ])
        
        # Get analytic accounts for each set of projects
        local_analytic_ids = local_projects.mapped('analytic_account_id').ids
        export_analytic_ids = export_projects.mapped('analytic_account_id').ids
        
        return local_projects, export_projects, local_analytic_ids, export_analytic_ids

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        project_id = self.env.context.get("default_project_id")
        if not project_id:
            _logger.warning("No project_id in context")
            return res

        project = self.env["project.project"].browse(project_id)
        account = project.analytic_account_id

        if not account:
            _logger.warning("No analytic account found for project %s", project.name)
            return res

        # Calculate PO Value (sum of all confirmed/purchase orders for this project)
        sale_orders = self.env['sale.order'].search([
            ('state', 'in', ('sale', 'done')),  # Only confirmed/done SO's
        ])

        company_currency = self.env.company.currency_id

        # Filter orders that have lines with our analytic account
        po_value = 0.0
        for order in sale_orders:
            if hasattr(project, 'sale_order_id') and project.sale_order_id:
                if project.sale_order_id == order:
                    po_value += order.currency_id._convert(order.amount_untaxed, company_currency, self.env.company, order.date_order)
                    # po_value += order.amount_untaxed
        
        # Initialize all variables
        invoiced = collected = vendor_invoice = payment_made = payroll_cost = 0.0
        milestones = []

        # Define date range - assuming we want data for the project duration
        start_date = project.date_start or fields.Date.today() - timedelta(days=365)  # Default to 1 year back if no start date
        end_date = project.date or fields.Date.today()  # Default to today if no end date
        
        # Get customer invoices
        customer_invoice_domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '!=', 'cancel'),
            # ('invoice_date', '>=', start_date),
            # ('invoice_date', '<=', end_date),
            ('company_id', '=', self.env.company.id),
        ]
        customer_invoices = self.env['account.move'].search(customer_invoice_domain)

        # Process customer invoices for invoiced and collected amounts
        for invoice in customer_invoices:
            for line in invoice.invoice_line_ids:
                if line.analytic_distribution:
                    try:
                        distribution = line.analytic_distribution
                        if not isinstance(distribution, dict):
                            distribution = json.loads(distribution) if distribution else {}
                        
                        for account_id_str, percentage in distribution.items():
                            account_id = int(account_id_str)
                            
                            if account_id == account.id:
                                # Calculate the allocated amount based on percentage
                                allocated_amount = line.price_subtotal

                                # convert amount
                                if invoice.currency_id != company_currency:
                                    allocated_amount = invoice.currency_id._convert(allocated_amount, company_currency, self.env.company, invoice.date)
                                
                                # For customer invoices, add to invoiced total
                                invoiced += allocated_amount
                                
                                # Check if invoice is paid
                                if invoice.payment_state != 'not_paid':
                                    collected += allocated_amount

                                milestone_data = {
                                    "id": line.id,
                                    "description": line.name,
                                    "date": invoice.date.strftime('%Y-%m-%d') if invoice.date else "",
                                    "invoiced": allocated_amount,
                                    "collected": allocated_amount if invoice.payment_state != 'not_paid' else 0.0,
                                    "pending_collection": 0.0,
                                    "outstanding_aging": 0,
                                    "vendor_invoice": 0.0,
                                    "payment_made": 0.0,
                                    "payment_to_be_made": 0.0,
                                }
                                milestone_data['pending_collection'] = milestone_data['invoiced'] - milestone_data['collected']
                                milestone_data['outstanding_aging'] = (date.today() - invoice.date).days if invoice.date and milestone_data['pending_collection'] > 0 else 0
                                
                                milestones.append(milestone_data)
                                break

                    except Exception as e:
                        _logger.error("Error processing analytic distribution for invoice %s, line %s: %s", 
                                    invoice.id, line.id, str(e))

        # Get vendor bills for the project's analytic account
        domain = [
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', self.env.company.id), 
        ]
        vendor_bills = self.env['account.move'].search(domain)
        
        processes_lines = set()
        # Process vendor bills
        for bill in vendor_bills:
            for line in bill.invoice_line_ids:
                if line.id not in processes_lines:
                    if line.analytic_distribution and line.name:
                        try:
                            distribution = line.analytic_distribution
                            if not isinstance(distribution, dict):
                                distribution = json.loads(distribution) if distribution else {}
                            
                            for account_id_str, percentage in distribution.items():
                                account_id = int(account_id_str)
                                
                                if account_id == account.id:
                                    # Calculate the allocated amount based on percentage
                                    allocated_amount = line.price_subtotal

                                    # convert amount
                                    if bill.currency_id != company_currency:
                                        allocated_amount = bill.currency_id._convert(allocated_amount, company_currency, self.env.company, bill.date)

                                    vendor_invoice += allocated_amount
                                    
                                    # Check if the bill is paid
                                    if bill.payment_state != 'not_paid':
                                        payment_made += allocated_amount

                                    milestone_data = {
                                        "id": line.id,
                                        "description": line.name,
                                        "date": bill.invoice_date.strftime('%Y-%m-%d') if bill.date else "",
                                        "invoiced": 0.0,
                                        "collected": 0.0,
                                        "pending_collection": 0.0,
                                        "outstanding_aging": 0,
                                        "vendor_invoice": allocated_amount,
                                        "payment_made": allocated_amount if bill.payment_state == 'paid' else 0.0,
                                        "payment_to_be_made": allocated_amount if bill.payment_state == 'not_paid' else 0.0,
                                    }
                                    if line.id not in processes_lines:
                                        milestones.append(milestone_data)
                                    processes_lines.add(line.id)
                                    break

                                break
                        except Exception as e:
                            _logger.error("Error processing analytic distribution for bill %s, line %s: %s", 
                                        bill.id, line.id, str(e))

        # Calculate payroll costs from timesheets
        payroll_cost = self._calculate_project_payroll(project)

        # Calculate total outstanding aging (weighted average)
        total_outstanding_aging = 0
        total_pending_amount = max(0.0, invoiced - collected)
        
        if total_pending_amount > 0:
            weighted_aging_sum = 0
            for milestone in milestones:
                if milestone['pending_collection'] > 0:
                    weight = milestone['pending_collection'] / total_pending_amount
                    weighted_aging_sum += milestone['outstanding_aging'] * weight
            
            total_outstanding_aging = int(weighted_aging_sum)

        dashboard_data = json.dumps({
            "project": {
                "name": project.display_name,
                "customer": project.partner_id.name,
                "po_value": po_value,
                "start_date": str(project.date_start or ""),
                "end_date": str(project.date or ""),
                "milestones": milestones,
                "total_invoiced": invoiced,
                "total_collected": collected,
                "total_pending_collection": max(0.0, invoiced - collected),
                "total_outstanding_aging": total_outstanding_aging,
                "total_vendor_invoice": vendor_invoice,
                "total_payment_made": payment_made,
                "total_payment_to_be_made": max(0.0, vendor_invoice - payment_made),
                "total_payroll_cost": payroll_cost,
            }
        })

        # Get region tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        region = ''
        if local_tag in project.tag_ids:
            region = "Local"
        if export_tag in project.tag_ids:
            region = "Export"
        
        res.update({
            "project_id": project.id,
            "region": region,
            "customer": project.partner_id.name,
            "date": project.date,
            "po_value": po_value,
            "invoiced": invoiced,
            "collected": collected,
            "vendor_invoice": vendor_invoice,
            "payment_made": payment_made,
            "payroll_cost": payroll_cost,
            "dashboard_data": dashboard_data,
        })

        return res

    @api.model
    def get_dashboard_data(self, project_id):
        """API method to get dashboard data for a project"""
        if not project_id:
            return {'error': 'No project ID provided'}
            
        dashboard = self.search([('project_id', '=', project_id)], limit=1)
        if not dashboard:
            # Create a new dashboard record
            dashboard = self.with_context(default_project_id=project_id).create({})
            
        if dashboard.dashboard_data:
            return json.loads(dashboard.dashboard_data)
        else:
            return {'error': 'Failed to generate dashboard data'}

    def _calculate_project_payroll(self, project):
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
            # ('date', '>=', start_date),
            # ('date', '<=', end_date),
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
    
    def export_excel(self):
        """Export dashboard data to Excel file"""
        self.ensure_one()
        
        data = json.loads(self.dashboard_data)
        project_data = data.get('project', {})
        
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet("Project Dashboard")

        # Define formats
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'left',
            'valign': 'vcenter'
        })
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 11,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        section_header_format = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'bg_color': '#D9E1F2',
            'align': 'left',
            'border': 1
        })
        label_format = workbook.add_format({
            'bold': True,
            'font_size': 10,
            'align': 'left'
        })
        currency_format = workbook.add_format({
            'num_format': '#,##0.00',
            'align': 'right'
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
        summary_label_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E7E6E6',
            'border': 1,
            'align': 'left'
        })
        summary_value_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E7E6E6',
            'border': 1,
            'num_format': '#,##0.00',
            'align': 'right'
        })

        # Set column widths
        worksheet.set_column('A:A', 30)  # Description
        worksheet.set_column('B:B', 12)  # Date
        worksheet.set_column('C:H', 18)  # Financial columns

        row = 0

        # Title
        worksheet.write(row, 0, f'Project Dashboard Report', title_format)
        row += 2

        # Project Information
        worksheet.write(row, 0, 'Project Name:', label_format)
        worksheet.write(row, 1, project_data.get('name', ''))
        row += 1
        
        worksheet.write(row, 0, 'Customer:', label_format)
        worksheet.write(row, 1, project_data.get('customer', ''))
        row += 1
        
        worksheet.write(row, 0, 'Region:', label_format)
        worksheet.write(row, 1, self.region or '')
        row += 1
        
        worksheet.write(row, 0, 'Start Date:', label_format)
        worksheet.write(row, 1, project_data.get('start_date', ''))
        row += 1
        
        worksheet.write(row, 0, 'End Date:', label_format)
        worksheet.write(row, 1, project_data.get('end_date', ''))
        row += 1
        
        worksheet.write(row, 0, 'PO Value:', label_format)
        worksheet.write(row, 1, project_data.get('po_value', 0.0), currency_format)
        row += 2

        # Project Summary Section
        worksheet.write(row, 0, 'PROJECT SUMMARY', section_header_format)
        row += 1

        summary_items = [
            ('Total Invoiced', project_data.get('total_invoiced', 0.0)),
            ('Total Collected', project_data.get('total_collected', 0.0)),
            ('Total Pending Collection', project_data.get('total_pending_collection', 0.0)),
            ('Outstanding Aging (Days)', project_data.get('total_outstanding_aging', 0)),
            ('Total Vendor Invoice', project_data.get('total_vendor_invoice', 0.0)),
            ('Total Payment Made', project_data.get('total_payment_made', 0.0)),
            ('Total Payment To Be Made', project_data.get('total_payment_to_be_made', 0.0)),
            ('Total Payroll Cost', project_data.get('total_payroll_cost', 0.0)),
        ]

        for label, value in summary_items:
            worksheet.write(row, 0, label, summary_label_format)
            if 'Days' in label:
                worksheet.write(row, 1, int(value), summary_label_format)
            else:
                worksheet.write(row, 1, value, summary_value_format)
            row += 1

        # Calculate Total Outgoing and Margin
        total_outgoing = project_data.get('total_vendor_invoice', 0.0) + project_data.get('total_payroll_cost', 0.0)
        total_margin = project_data.get('total_invoiced', 0.0) - total_outgoing
        margin_percent = (total_margin / project_data.get('total_invoiced', 1.0)) * 100 if project_data.get('total_invoiced', 0.0) > 0 else 0.0

        row += 1
        worksheet.write(row, 0, 'Total Outgoing', summary_label_format)
        worksheet.write(row, 1, total_outgoing, summary_value_format)
        row += 1
        
        worksheet.write(row, 0, 'Total Margin', summary_label_format)
        worksheet.write(row, 1, total_margin, summary_value_format)
        row += 1
        
        worksheet.write(row, 0, 'Margin %', summary_label_format)
        margin_format = workbook.add_format({
            'bold': True,
            'bg_color': '#E7E6E6',
            'border': 1,
            'num_format': '0.00%',
            'align': 'right'
        })
        worksheet.write(row, 1, margin_percent / 100, margin_format)
        row += 2

        # Milestone Details Section
        milestones = project_data.get('milestones', [])
        
        if milestones:
            worksheet.write(row, 0, 'MILESTONE DETAILS', section_header_format)
            row += 1

            # Headers for milestones
            milestone_headers = [
                'Description',
                'Date',
                'Invoiced',
                'Collected',
                'Pending Collection',
                'Outstanding Aging (Days)',
                'Vendor Invoice',
                'Payment Made',
                'Payment To Be Made'
            ]

            for col, header in enumerate(milestone_headers):
                worksheet.write(row, col, header, header_format)
            
            row += 1

            # Milestone data rows
            for milestone in milestones:
                worksheet.write(row, 0, milestone.get('description', ''), cell_format)
                worksheet.write(row, 1, milestone.get('date', ''), cell_format)
                worksheet.write(row, 2, milestone.get('invoiced', 0.0), number_cell_format)
                worksheet.write(row, 3, milestone.get('collected', 0.0), number_cell_format)
                worksheet.write(row, 4, milestone.get('pending_collection', 0.0), number_cell_format)
                worksheet.write(row, 5, milestone.get('outstanding_aging', 0), cell_format)
                worksheet.write(row, 6, milestone.get('vendor_invoice', 0.0), number_cell_format)
                worksheet.write(row, 7, milestone.get('payment_made', 0.0), number_cell_format)
                worksheet.write(row, 8, milestone.get('payment_to_be_made', 0.0), number_cell_format)
                row += 1

        workbook.close()
        output.seek(0)
        file_data = output.read()

        # Generate filename
        project_name = self.project_id.name.replace('/', '_').replace(' ', '_') if self.project_id else 'project'
        filename = f'dashboard_{project_name}_{fields.Date.today()}.xlsx'

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

    
    def action_go_back(self):
        """Go to L4 Dashboard in the same tab."""
        return {
            'type': 'ir.actions.act_url',
            'url': '/web#cids=1&menu_id=632&action=934&model=l4.dashboard&view_type=form',
            'target': 'self',
        }
    
    
class L3DashboardController(http.Controller):

    @http.route('/l3_dashboard/data', type='json', auth='user')
    def get_dashboard_data(self, region='', year=None, month=None, project_id=None):
        domain = []

        if region:
            domain.append(('region', '=', region))
        if year:
            domain.append(('date', '>=', f'{year}-01-01'))
            domain.append(('date', '<=', f'{year}-12-31'))
        if month:
            domain.append(('date', 'like', f'-{int(month):02d}-'))
        if project_id:
            domain.append(('project_id', '=', int(project_id)))

        record = request.env['l3.dashboard'].search(domain, limit=1)

        return {
            'dashboard_data': json.loads(record.dashboard_data) if record and record.dashboard_data else {}
        }

    @http.route('/custom/l3_dashboard/projects', type='json', auth='user')
    def get_all_projects(self):
        projects = request.env['project.project'].search([])
        return [{'id': p.id, 'name': p.display_name} for p in projects]

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
    

