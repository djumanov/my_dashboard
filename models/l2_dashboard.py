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
        """Compute and store dashboard data as JSON"""
        for record in self:
            try:
                record.dashboard_data = json.dumps(record._get_dashboard_data())
                record.last_update = fields.Datetime.now()
            except Exception as e:
                record.dashboard_data = json.dumps({
                    'error': _('Error generating dashboard data: %s') % str(e)
                })
                # Log error without crashing
                self.env.cr.rollback()
                self.env.cr.execute('SAVEPOINT dashboard_error')
                self.env.logger.error("Dashboard data computation error: %s", str(e))

    @api.model
    def get_dashboard_data_json(self, year=None, company_id=None):
        """API method to fetch dashboard data in JSON format"""
        year = str(year or fields.Date.today().year)
        company_id = company_id or self.env.company.id
        
        # Find or create dashboard
        dashboard = self.search([
            ('year', '=', year),
            ('company_id', '=', company_id),
            ('active', '=', True)
        ], limit=1)
        
        if not dashboard:
            dashboard = self.create({
                'year': year,
                'company_id': company_id,
                'name': _('L2 Dashboard - %s') % year
            })
        
        # Force recomputation
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
        """Calculate monthly sales data split between local and export"""
        # Get month abbreviations (Jan, Feb, etc.)
        months = [datetime(2000, i+1, 1).strftime('%b') for i in range(12)]
        
        sales_orders = self.env['sale.order'].search([
            ('company_id', '=', self.company_id.id),
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', f'{year}-01-01'),
            ('date_order', '<=', f'{year}-12-31')
        ])
        # This is just placeholder data for demonstration
        total_monthly = [0.0] * 12
        local_monthly = [0.0] * 12
        export_monthly = [0.0] * 12

        for order in sales_orders:
            month = order.date_order.month - 1
            total_monthly[month] += order.amount_total

        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])

        for month in range(12):
            for local_project in local_projects:
                for sales_order in sales_orders:
                    if sales_order.date_order.month - 1 == month and local_project in sales_order.project_ids:
                        local_sales_amount = sales_order.amount_untaxed
                        local_monthly[month] += local_sales_amount

            for export_project in export_projects:
                for sales_order in sales_orders:
                    if sales_order.date_order.month - 1 == month and export_project in sales_order.project_ids:
                        export_sales_amount = sales_order.amount_untaxed
                        export_monthly[month] += export_sales_amount
        
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
        total_monthly = [1000.0] * 12
        local_monthly = [600.0] * 12
        export_monthly = [400.0] * 12

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

        months = [datetime(2000, i + 1, 1).strftime('%b') for i in range(12)]

        # 🎯 Simulate dynamic values instead of flat copies
        inflow_total = [10000 + i * 500 for i in range(12)]         # e.g. 10000, 10500, ..., 15500
        outflow_total = [3000 + (i % 3) * 1000 for i in range(12)]   # e.g. 3000, 4000, 5000, ...

        inflow_local = [inflow_total[i] * 0.6 for i in range(12)]    # 60% of total inflow
        outflow_local = [outflow_total[i] * 0.5 for i in range(12)]  # 50% of total outflow

        inflow_export = [inflow_total[i] * 0.4 for i in range(12)]   # 40% of total inflow
        outflow_export = [outflow_total[i] * 0.5 for i in range(12)] # remaining 50%

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
