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
        return [(str(year), str(year)) for year in range(2023, current_year + 1)]

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
        
        # Define date range for the year
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        
        # Get company currency
        company_currency = self.env.company.currency_id
        
        # Get confirmed sales orders for the year
        sales_orders = self.env['sale.order'].search([
            ('date_order', '>=', start_date),
            ('date_order', '<=', end_date),
            ('company_id', '=', self.env.company.id),
            ('state', 'in', ['sale', 'done']),
        ])
        
        # Get Local and Export tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)
        
        # Ensure tags exist
        if not local_tag or not export_tag:
            raise ValueError("Local or Export tags not found")
        
        # Get projects by tags
        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])
        
        # Get analytic accounts from projects
        local_analytic_account_ids = local_projects.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_projects.mapped('analytic_account_id').ids
        
        for order in sales_orders:
            # Get order month index (0-11)
            order_month = order.date_order.month - 1
            
            # Get order currency
            order_currency = order.currency_id
            order_date = order.date_order
            
            # Flag to track if the order has been categorized
            order_categorized = False
            
            # First check if the order is directly linked to any local projects
            for local_project in local_projects:
                if hasattr(order, 'project_ids') and local_project in order.project_ids:
                    # Convert to company currency
                    amount_in_company_currency = order_currency._convert(
                        order.amount_untaxed,
                        company_currency,
                        self.env.company,
                        order_date
                    )
                    
                    local_monthly[order_month] += amount_in_company_currency
                    total_monthly[order_month] += amount_in_company_currency
                    order_categorized = True
                    break
            
            # If not categorized yet, check export projects
            if not order_categorized:
                for export_project in export_projects:
                    if hasattr(order, 'project_ids') and export_project in order.project_ids:
                        # Convert to company currency
                        amount_in_company_currency = order_currency._convert(
                            order.amount_untaxed,
                            company_currency,
                            self.env.company,
                            order_date
                        )
                        
                        export_monthly[order_month] += amount_in_company_currency
                        total_monthly[order_month] += amount_in_company_currency
                        order_categorized = True
                        break
            
            # If still not categorized, check analytic distribution on order lines
            if not order_categorized:
                for line in order.order_line:
                    if line.analytic_distribution:
                        try:
                            distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                                else eval(line.analytic_distribution) if isinstance(line.analytic_distribution, str) \
                                else json.loads(line.analytic_distribution) if line.analytic_distribution else {}
                            
                            # Convert line amount to company currency
                            amount_in_company_currency = order_currency._convert(
                                line.price_subtotal,
                                company_currency,
                                self.env.company,
                                order_date
                            )
                            
                            line_categorized = False
                            
                            for account_id_str, percentage in distribution.items():
                                account_id = int(account_id_str) if isinstance(account_id_str, str) else int(account_id_str)
                                
                                if account_id in local_analytic_account_ids:
                                    local_monthly[order_month] += amount_in_company_currency
                                    total_monthly[order_month] += amount_in_company_currency
                                    line_categorized = True
                                    break
                                
                                if not line_categorized and account_id in export_analytic_account_ids:
                                    export_monthly[order_month] += amount_in_company_currency
                                    total_monthly[order_month] += amount_in_company_currency
                                    line_categorized = True
                                    break
                        
                        except Exception as e:
                            _logger.error(f"Error processing analytic distribution for order {order.id}, line {line.id}: {e}")
        
        # Round to 2 decimal places for currency amounts
        for i in range(12):
            total_monthly[i] = round(total_monthly[i], 2)
            local_monthly[i] = round(local_monthly[i], 2)
            export_monthly[i] = round(export_monthly[i], 2)
        
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
        
        # Initialize monthly arrays
        total_monthly = [0.0] * 12
        local_monthly = [0.0] * 12
        export_monthly = [0.0] * 12
        
        # Define date range for the year
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        
        # Get Local and Export tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)
        
        # Ensure tags exist
        if not local_tag or not export_tag:
            raise ValueError("Local or Export tags not found")
        
        # Get projects by tags
        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])
        
        # Get analytic accounts from projects
        local_analytic_account_ids = local_projects.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_projects.mapped('analytic_account_id').ids
        
        # Get company currency
        company_currency = self.env.company.currency_id
        
        # Get posted customer invoices in the date range
        invoice_domain = [
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', self.env.company.id),
        ]
        customer_invoices = self.env['account.move'].search(invoice_domain)
        
        for invoice in customer_invoices:
            # Get invoice currency
            invoice_currency = invoice.currency_id
            invoice_date = invoice.invoice_date or invoice.date
            
            # Get invoice month index (0-11)
            invoice_month = invoice_date.month - 1
            
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
                            
                            if account_id in local_analytic_account_ids:
                                local_monthly[invoice_month] += amount_in_company_currency
                                total_monthly[invoice_month] += amount_in_company_currency
                                break
                                
                            if account_id in export_analytic_account_ids:
                                export_monthly[invoice_month] += amount_in_company_currency
                                total_monthly[invoice_month] += amount_in_company_currency
                                break
                    
                    except Exception as e:
                        _logger.error("Error processing analytic distribution for invoice %s, line %s: %s", 
                                    invoice.id, line.id, str(e))
        
        # Round to 2 decimal places for currency amounts
        for i in range(12):
            total_monthly[i] = round(total_monthly[i], 2)
            local_monthly[i] = round(local_monthly[i], 2)
            export_monthly[i] = round(export_monthly[i], 2)
        
        return {
            'total': {
                'months': months,
                'amounts': total_monthly,
                'sum': self._format_amount(sum(total_monthly)),
            },
            'local_revenue': {
                'months': months,
                'amounts': local_monthly,
                'sum': self._format_amount(sum(local_monthly)),
            },
            'export_revenue': {
                'months': months,
                'amounts': export_monthly,
                'sum': self._format_amount(sum(export_monthly)),
            },
        }
        
    def _get_expenses_data(self, year):
        """Calculate expenses data"""
        # Get month abbreviations (Jan, Feb, etc.)
        months = [datetime(2000, i+1, 1).strftime('%b') for i in range(12)]

        # Initialize monthly arrays
        total_monthly = [0.0] * 12
        local_monthly = [0.0] * 12
        export_monthly = [0.0] * 12

        # Define date range for the year
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"

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

        # Get company currency
        company_currency = self.env.company.currency_id

        # Get confirmed vendor bills within the date range
        domain = [
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('company_id', '=', self.env.company.id),
        ]
        vendor_bills = self.env['account.move'].search(domain)
        
        for bill in vendor_bills:
            # Get bill currency
            bill_currency = bill.currency_id
            bill_date = bill.invoice_date or bill.date
            
            # Get bill month index (0-11)
            bill_month = bill_date.month - 1
            
            for line in bill.line_ids:
                # Ensure analytic distribution exists and is processed correctly
                if line.analytic_distribution:
                    # Handle different analytic distribution formats
                    try:
                        # Convert to dictionary if it's a string
                        distribution = line.analytic_distribution if isinstance(line.analytic_distribution, dict) \
                            else eval(line.analytic_distribution)
                        
                        # Check each analytic account in the distribution
                        for account_id_str, percentage in distribution.items():
                            account_id = int(account_id_str)  # Ensure integer

                            # Convert line amount to company currency
                            amount_in_company_currency = bill_currency._convert(
                                line.price_subtotal,
                                company_currency,
                                self.env.company,
                                bill_date
                            )

                            # Check if the account is in local or export project accounts
                            if account_id in local_analytic_account_ids:
                                local_monthly[bill_month] += amount_in_company_currency
                                total_monthly[bill_month] += amount_in_company_currency
                            
                            if account_id in export_analytic_account_ids:
                                export_monthly[bill_month] += amount_in_company_currency
                                total_monthly[bill_month] += amount_in_company_currency
                    
                    except Exception as e:
                        # Log any errors in processing analytic distribution
                        _logger.error(f"Error processing analytic distribution for bill {bill.id}, line {line.id}: {e}")

        # Round to 2 decimal places for currency amounts
        for i in range(12):
            total_monthly[i] = round(total_monthly[i], 2)
            local_monthly[i] = round(local_monthly[i], 2)
            export_monthly[i] = round(export_monthly[i], 2)

        return {
            'total': {
                'months': months,
                'amounts': total_monthly,
                'sum': self._format_amount(sum(total_monthly)),
            },
            'local_expenses': {  # Fixed the typo in 'local_exenses'
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
        
        # Get company currency
        company_currency = self.env.company.currency_id
        
        # Get project tags
        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)
        
        # Get projects by tags
        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])
        
        # Get analytic accounts
        local_analytic_account_ids = local_projects.mapped('analytic_account_id').ids
        export_analytic_account_ids = export_projects.mapped('analytic_account_id').ids
        
        # INFLOW: Customer Payments
        customer_payments = self.env['account.payment'].search([
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ])
        
        for payment in customer_payments:
            # Get payment month index (0-11)
            payment_month = payment.date.month - 1
            
            # Get related invoice
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
                                
                                if account_id in local_analytic_account_ids:
                                    inflow_local[payment_month] += amount_in_company_currency
                                    inflow_total[payment_month] += amount_in_company_currency
                                    break
                                elif account_id in export_analytic_account_ids:
                                    inflow_export[payment_month] += amount_in_company_currency
                                    inflow_total[payment_month] += amount_in_company_currency
                                    break

                        except Exception as e:
                            _logger.error("Error processing analytic distribution for invoice %s, line %s: %s", 
                                        invoice.id, line.id, str(e))
            
        # OUTFLOW: Vendor Payments
        vendor_payments = self.env['account.payment'].search([
            ('payment_type', '=', 'outbound'),
            ('state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ])
        
        for payment in vendor_payments:
            # Get payment month index (0-11)
            payment_month = payment.date.month - 1
            
            # Get related bill
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
                                    line.price_subtotal,
                                    company_currency,
                                    self.env.company,
                                    bill_date
                                )
                                
                                if account_id in local_analytic_account_ids:
                                    outflow_local[payment_month] += amount_in_company_currency
                                    outflow_total[payment_month] += amount_in_company_currency
                                    break
                                elif account_id in export_analytic_account_ids:
                                    outflow_export[payment_month] += amount_in_company_currency
                                    outflow_total[payment_month] += amount_in_company_currency
                                    break
                                                    
                        except Exception as e:
                            _logger.error("Error processing analytic distribution for bill %s, line %s: %s", 
                                        bill.id, line.id, str(e))

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
