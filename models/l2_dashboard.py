import json
from datetime import datetime
from odoo import api, fields, models, _
from odoo.tools import float_round


class L2Dashboard(models.Model):
    _name = 'l2.dashboard'
    _description = 'L2 Dashboard Data'
    _rec_name = 'name'

    name = fields.Char(
        string='Dashboard Name', 
        default=lambda self: _('L2 Dashboard - %s') % fields.Date.today().strftime('%Y')
    )
    
    dashboard_data = fields.Text(string='Dashboard Data', compute='_compute_dashboard_data')
    last_update = fields.Datetime(string='Last Update', readonly=True)
    
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')
    
    # Configuration fields
    year = fields.Selection(
        selection='_get_year_selection',
        string='Year',
        default=lambda self: str(fields.Date.today().year),
        required=True,
    )
    active = fields.Boolean(default=True)
    
    @api.model
    def _get_year_selection(self):
        """Generate year options from 2023 to current year + 1"""
        current_year = datetime.now().year
        return [(str(year), str(year)) for year in range(2023, current_year + 2)]

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
                'company_id': self.env.company.id
            })
        
        dashboard._compute_dashboard_data()
        return dashboard.dashboard_data

    def _get_dashboard_data(self):
        """Compile all dashboard data into a structured dictionary"""
        self.ensure_one()
        year = int(self.year)

        # Get sales data
        sales_data = self._get_sales_data(year)

        # Get revenue data
        revenue_data = self._get_revenue_data(year)

        #Get expenses data
        expenses_data = self._get_expenses_data(year)

        #Get Cash Flow data
        cash_flow_data = self._get_cashflow_data(year)
        
        # Build complete dashboard structure
        return {
            'filters': {
                'year': year,
            },
            'company': {
                'name': self.company_id.name,
                'currency': self.currency_id.symbol,
                'country': self.company_id.country_id.name or _('Not Set'),
            },
            'sales': sales_data,
            'revenue': revenue_data,
            'expenses': expenses_data,
            'cash_flow': cash_flow_data,
            'last_update': fields.Datetime.to_string(fields.Datetime.now())
        }
    
    def _format_amount(self, amount):
        """Format amount with 2 decimal precision"""
        return float_round(amount, precision_digits=2)
    
    def _get_sales_data(self, year):
        """
        Calculate monthly sales data split between local and export
        
        This method retrieves all sales orders for the given year and categorizes
        them as either local or export sales based on project tags or analytic accounts.
        
        Args:
            year (int): The year for which to calculate sales data
            
        Returns:
            dict: A dictionary containing total, local, and export sales data by month
        """
        # Get month abbreviations (Jan, Feb, etc.)
        months = [datetime(2000, i+1, 1).strftime('%b') for i in range(12)]
        
        # Initialize arrays to store monthly sales data
        total_monthly = [0.0] * 12
        local_monthly = [0.0] * 12
        export_monthly = [0.0] * 12
        
        # Get all sales orders for the given year
        sales_orders = self.env['sale.order'].search([
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', f'{year}-01-01'),
            ('date_order', '<=', f'{year}-12-31')
        ])
        
        if not sales_orders:
            return {
                'total': {'months': months, 'amounts': total_monthly, 'sum': self._format_amount(0.0)},
                'local_sales': {'months': months, 'amounts': local_monthly, 'sum': self._format_amount(0.0)},
                'export_sales': {'months': months, 'amounts': export_monthly, 'sum': self._format_amount(0.0)},
            }
        
        # Calculate total monthly sales first
        for order in sales_orders:
            month_idx = order.date_order.month - 1
            total_monthly[month_idx] += order.amount_untaxed
        
        # Get local and export tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)
        
        # Get projects with local and export tags
        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])]) if local_tag else self.env['project.project']
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])]) if export_tag else self.env['project.project']
        
        # Get analytic account IDs for local and export projects
        local_analytic_account_ids = set(local_projects.mapped('analytic_account_id').ids) if local_projects else set()
        export_analytic_account_ids = set(export_projects.mapped('analytic_account_id').ids) if export_projects else set()
        
        # Process each sales order once with better performance
        for order in sales_orders:
            month_idx = order.date_order.month - 1
            order_amount = order.amount_untaxed
            
            # Check if order is related to local or export projects
            order_projects = order.project_ids if hasattr(order, 'project_ids') else self.env['project.project']
            
            # If order directly linked to projects
            if order_projects:
                if any(project in local_projects for project in order_projects):
                    local_monthly[month_idx] += order_amount
                    continue
                elif any(project in export_projects for project in order_projects):
                    export_monthly[month_idx] += order_amount
                    continue
            
            # If not directly linked to projects, check analytic distribution
            is_local = False
            is_export = False
            
            for line in order.order_line:
                if not line.analytic_distribution:
                    continue
                    
                try:
                    # Handle analytic_distribution which could be a string or dict
                    distribution = line.analytic_distribution
                    if not isinstance(distribution, dict):
                        distribution = eval(distribution)
                    
                    line_amount = line.price_subtotal
                    line_percentage = 0.0
                    
                    for account_id_str, percentage in distribution.items():
                        account_id = int(account_id_str)
                        
                        if account_id in local_analytic_account_ids:
                            is_local = True
                            line_percentage += float(percentage)
                        elif account_id in export_analytic_account_ids:
                            is_export = True
                            line_percentage += float(percentage)
                    
                    # Apply proportional amount based on percentage
                    if line_percentage > 0:
                        proportion = line_percentage / 100.0
                        if is_local:
                            local_monthly[month_idx] += line_amount * proportion
                        if is_export:
                            export_monthly[month_idx] += line_amount * proportion
                    
                except Exception as e:
                    _logger.error(f"Error processing analytic distribution for order {order.id}, line {line.id}: {e}")
            
            # If we couldn't determine through analytic accounts and no percentage was applied
            if not is_local and not is_export:
                # Default categorization logic if needed
                pass
        
        # Round values for better display
        total_monthly = [round(amount, 2) for amount in total_monthly]
        local_monthly = [round(amount, 2) for amount in local_monthly]
        export_monthly = [round(amount, 2) for amount in export_monthly]
        
        return {
            'total': {
                'months': months,
                'amounts': total_monthly,
                'sum': self._format_amount(sum(total_monthly)),
            },
            'local_sales': {
                'months': months,
                'amounts': local_monthly,
                'sum': self._format_amount(sum(local_monthly)),
            },
            'export_sales': {
                'months': months,
                'amounts': export_monthly,
                'sum': self._format_amount(sum(export_monthly)),
            },
        }

    def _get_revenue_data(self, year):
        """
        Calculate monthly revenue data by project type (Local vs Export) for the given year.
        
        This optimized implementation efficiently tracks revenue by:
        1. Finding all relevant projects tagged as Local or Export
        2. Identifying all sales orders linked to these projects
        3. Calculating monthly revenue from posted invoices related to these sales orders
        
        Args:
            year (int): The year for which to calculate revenue data
            
        Returns:
            dict: Dictionary containing total, local and export revenue data with monthly breakdown
        """
        # Get month abbreviations (Jan, Feb, etc.)
        months = [datetime(2000, i+1, 1).strftime('%b') for i in range(12)]
        
        # Initialize result structure with zero values
        result = {
            'total': {
                'months': months,
                'amounts': [0.0] * 12,
                'sum': self._format_amount(0.0),
            },
            'local_revenue': {
                'months': months,
                'amounts': [0.0] * 12,
                'sum': self._format_amount(0.0),
            },
            'export_revenue': {
                'months': months,
                'amounts': [0.0] * 12,
                'sum': self._format_amount(0.0),
            },
        }
        
        # Performance optimization: Get tag IDs for Local and Export projects in a single query
        tags = self.env['project.tags'].search_read([('name', 'in', ['Local', 'Export'])], ['id', 'name'])
        tag_map = {tag['name']: tag['id'] for tag in tags}
        
        local_tag_id = tag_map.get('Local')
        export_tag_id = tag_map.get('Export')
        
        if not (local_tag_id and export_tag_id):
            _logger.warning("Missing required project tags: Local and/or Export")
            return result
        
        # Find all projects with relevant tags in a single query
        projects = self.env['project.project'].search_read(
            [('tag_ids', 'in', [local_tag_id, export_tag_id])],
            ['id', 'tag_ids', 'name']
        )
        
        # Early return if no projects found
        if not projects:
            _logger.info("No local or export projects found for revenue calculation")
            return result
        
        # Classify projects by tag type (a project can be both local and export)
        local_project_ids = []
        export_project_ids = []
        
        for project in projects:
            if local_tag_id in project['tag_ids']:
                local_project_ids.append(project['id'])
            if export_tag_id in project['tag_ids']:
                export_project_ids.append(project['id'])
        
        # Early return if no tagged projects found
        if not (local_project_ids or export_project_ids):
            _logger.info("No properly tagged projects found for revenue calculation")
            return result
        
        # Get all relevant sale orders in a single query
        all_project_ids = list(set(local_project_ids + export_project_ids))
        sale_orders = self.env['sale.order'].search_read(
            [
                ('project_ids', 'in', all_project_ids),
                ('company_id', '=', self.company_id.id),
                ('state', 'in', ['sale', 'done'])
            ],
            ['id', 'project_ids', 'name']
        )
        
        # Early return if no sale orders found
        if not sale_orders:
            _logger.info("No sale orders found for revenue calculation")
            return result
        
        # Create efficient lookup maps for sale orders by type
        # A sale order can be linked to both local and export projects
        local_sale_orders = set()
        export_sale_orders = set()
        
        for order in sale_orders:
            order_project_ids = set(order['project_ids'])
            
            # Check if any project in the order is a local project
            if any(pid in local_project_ids for pid in order_project_ids):
                local_sale_orders.add(order['id'])
                
            # Check if any project in the order is an export project
            if any(pid in export_project_ids for pid in order_project_ids):
                export_sale_orders.add(order['id'])
        
        # Early return if no properly classified sale orders
        if not (local_sale_orders or export_sale_orders):
            _logger.info("No properly classified sale orders found for revenue calculation")
            return result
        
        # Get all relevant invoices for the specified year in a single query
        start_date = f'{year}-01-01'
        end_date = f'{year}-12-31'
        
        all_sale_order_ids = list(local_sale_orders | export_sale_orders)
        
        invoice_domain = [
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('sale_id', 'in', all_sale_order_ids),
            ('company_id', '=', self.company_id.id),
        ]
        
        # Only fetch fields we actually need
        invoices = self.env['account.move'].search_read(
            invoice_domain, 
            ['sale_id', 'amount_untaxed_signed', 'invoice_date']
        )
        
        # Initialize arrays for monthly revenue
        total_monthly = [0.0] * 12
        local_monthly = [0.0] * 12
        export_monthly = [0.0] * 12
        
        # Process each invoice to calculate monthly revenue
        for invoice in invoices:
            if not invoice.get('sale_id'):
                continue
                
            sale_id = invoice['sale_id'][0]
            invoice_date = invoice['invoice_date']  # Odoo returns this as datetime.date
            amount = invoice['amount_untaxed_signed']
            
            # Skip invalid dates or amounts
            if not invoice_date or not isinstance(amount, (int, float)):
                continue
                
            # Get month index (0-11)
            month_index = invoice_date.month - 1
            
            # Update total monthly revenue
            total_monthly[month_index] += amount
            
            # Update local revenue if applicable
            if sale_id in local_sale_orders:
                local_monthly[month_index] += amount
                
            # Update export revenue if applicable
            if sale_id in export_sale_orders:
                export_monthly[month_index] += amount
        
        # Calculate totals
        total_sum = sum(total_monthly)
        local_sum = sum(local_monthly)
        export_sum = sum(export_monthly)
        
        # Update and return the result structure
        result['total']['amounts'] = total_monthly
        result['total']['sum'] = self._format_amount(total_sum)
        
        result['local_revenue']['amounts'] = local_monthly
        result['local_revenue']['sum'] = self._format_amount(local_sum)
        
        result['export_revenue']['amounts'] = export_monthly
        result['export_revenue']['sum'] = self._format_amount(export_sum)
        
        return result
    
    def _get_expenses_data(self, year):
        """Calculate expenses data"""
        # Get month abbreviations (Jan, Feb, etc.)
        months = [datetime(2000, i+1, 1).strftime('%b') for i in range(12)]

        # Placeholder data for demonstration
        total_monthly = [0.0] * 12
        local_monthly = [0.0] * 12
        export_monthly = [0.0] * 12

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

        # Get confirmed vendor bills within the date range
        domain = [
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', f'{year}-01-01'),
            ('invoice_date', '<=', f'{year}-12-31'),
            ('company_id', '=', self.env.company.id),
        ]
        vendor_bills = self.env['account.move'].search(domain)
        
        for month in range(12):
            for bill in vendor_bills:
                # Check if the bill's date falls within the current month
                if bill.invoice_date.month - 1 == month:
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
                                    
                                    # Calculate proportional expense based on distribution percentage
                                    proportional_expense = line.price_subtotal * (percentage / 100)
                                    
                                    # Check if the account is in local or export project accounts
                                    if account_id in local_analytic_account_ids:
                                        local_monthly[month] += proportional_expense
                                    if account_id in export_analytic_account_ids:
                                        export_monthly[month] += proportional_expense
                                    
                                    
                            
                            except Exception as e:
                                # Log any errors in processing analytic distribution
                                print(f"Error processing analytic distribution for bill {bill.id}, line {line.id}: {e}")

                    total_monthly[month] += bill.amount_total

        return {
            'total': {
                'months': months,
                'amounts': total_monthly,
                'sum': self._format_amount(sum(total_monthly)),
            },
            'local_exenses': {
                'months': months,
                'amounts': local_monthly,
                'sum': self._format_amount(sum(local_monthly)),
            },
            'export_expenses': {
                'months': months,
                'amounts': export_monthly,
                'sum': self._format_amount(sum(export_monthly)),
            },
        }

    def _get_cashflow_data(self, year):
        """Calculate cash flow data for the given year"""
        months = [datetime(2000, i + 1, 1).strftime('%b') for i in range(12)]

        inflow_total = [0.0] * 12
        outflow_total = [0.0] * 12

        inflow_local = [0.0] * 12
        outflow_local = [0.0] * 12

        inflow_export = [0.0] * 12
        outflow_export = [0.0] * 12

        start_date = f'{year}-01-01'
        end_date = f'{year}-12-31'
        
        local_tag_id = self.env['project.tags'].search([('name', '=', 'Local')], limit=1).id
        export_tag_id = self.env['project.tags'].search([('name', '=', 'Export')], limit=1).id

        customer_payments = self.env['account.payment'].search([
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('company_id', '=', self.company_id.id),
        ])

        for payment in customer_payments:
            month = payment.date.month - 1
            invoices = (
                payment.reconciled_invoice_ids or 
                payment.invoice_line_ids.move_id or
                self.env['account.move'].search([('payment_id', '=', payment.id)])
            )

            for invoice in invoices:
                sale_order = False
                
                if hasattr(invoice, 'sale_id'):
                    sale_order = invoice.sale_id
                
                if not sale_order and invoice.ref:
                    sale_order = self.env['sale.order'].search([('name', '=', invoice.ref)], limit=1)
                
                if not sale_order and invoice.name:
                    sale_order = self.env['sale.order'].search([('name', '=', invoice.name)], limit=1)

                if sale_order:
                    for project in sale_order.project_ids:
                        if local_tag_id in project.tag_ids.ids:
                            inflow_local[month] += payment.amount
                            break
                        elif export_tag_id in project.tag_ids.ids:
                            inflow_export[month] += payment.amount
                            break
            inflow_total[month] += payment.amount

        vendor_payments = self.env['account.payment'].search([
            ('payment_type', '=', 'outbound'),
            ('state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('company_id', '=', self.company_id.id),
        ])

        local_project_ids = self.env['project.project'].search([('tag_ids', 'in', [local_tag_id])])
        export_project_ids = self.env['project.project'].search([('tag_ids', 'in', [export_tag_id])])
        local_analytic_account_ids = local_project_ids.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_project_ids.mapped('analytic_account_id').ids

        for payment in vendor_payments:
            month = payment.date.month - 1
            if not payment.reconciled_bill_ids:
                continue
            try:
                bill = payment.reconciled_bill_ids or payment.bill_line_ids.move_id
            except Exception as e:
                print(f"Error retrieving reconciled bill for payment {payment.id}: {e}")
                bill = False
            if bill:
                for line in bill.line_ids:
                    if line.analytic_distribution:
                        try:
                            distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                                else eval(line.analytic_distribution)
                            
                            for account_id, percentage in distribution.items():
                                account_id = int(account_id)
                                
                                # Check if the account is in local or export project accounts
                                if account_id in local_analytic_account_ids:
                                    outflow_local[month] += payment.amount
                                    break
                                if account_id in export_analytic_account_ids:
                                    outflow_export[month] += payment.amount
                                    break
                        except Exception as e:
                            print(f"Error processing analytic distribution for bill {bill.id}, line {line.id}: {e}")
            outflow_total[month] += payment.amount

        return {
            'total': {
                'months': months,
                'inflow': inflow_total,
                'outflow': outflow_total,
                'sum': self._format_amount(sum(inflow_total) - sum(outflow_total)),
            },
            'local_cash_flow': {
                'months': months,
                'inflow': inflow_local,
                'outflow': outflow_local,
                'sum': self._format_amount(sum(inflow_local) - sum(outflow_local)),
            },
            'export_cash_flow': {
                'months': months,
                'inflow': inflow_export,
                'outflow': outflow_export,
                'sum': self._format_amount(sum(inflow_export) - sum(outflow_export)),
            },
        }
