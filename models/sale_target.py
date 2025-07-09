from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SaleTarget(models.Model):
    """
    Sales Target Model to track and manage sales targets with categorization.
    """
    _name = 'sale.target'
    _description = 'Sales Target'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'year desc, target_amount desc'

    # Categories
    CATEGORY_SELECTION = [
        ('export', 'Export'),
        ('local', 'Local')
    ]

    # Types
    TYPE_SELECTION = [
        ('sap', 'SAP'),
        ('odoo', 'Odoo'),
        ('ites', 'ITES')
    ]
    
    year = fields.Integer(
        string='Year', 
        required=True, 
        default=lambda self: fields.Date.today().year,
        help='Year for which the sales target is set',
        tracking=True,
        group_operator='max',
        widget='integer'
    )

    def _compute_formatted_year(self):
        """
        Ensure year is displayed without formatting
        """
        for record in self:
            record.formatted_year = f"{record.year:d}"
    
    formatted_year = fields.Char(
        string='Year',
        compute='_compute_formatted_year',
        store=False
    )
    
    target_amount = fields.Monetary(
        string='Target Amount', 
        currency_field='company_currency_id',
        required=True,
        help='Total sales target amount for the specified year',
        tracking=True
    )

    def _compute_formatted_target_amount(self):
        """
        Format target amount with thousand separators (xxx,xxx,xxx)
        """
        for record in self:
            # Format with thousand separators and 2 decimal places
            record.formatted_target_amount = f"{record.target_amount:,.2f}"
    
    formatted_target_amount = fields.Char(
        string='Target Amount',
        compute='_compute_formatted_target_amount',
        store=False
    )
    
    category = fields.Selection(
        selection=CATEGORY_SELECTION,
        string='Category',
        required=True,
        help='Sales target category (Export or Local)',
        tracking=True
    )
    
    type = fields.Selection(
        selection=TYPE_SELECTION,
        string='Type',
        required=True,
        help='Sales target type (SAP, Odoo, or ITES)',
        tracking=True
    )
    
    description = fields.Text(
        string='Description',
        help='Additional details about the sales target'
    )
    
    company_currency_id = fields.Many2one(
        'res.currency', 
        related='company_id.currency_id', 
        string='Company Currency',
        readonly=True
    )
    
    company_id = fields.Many2one(
        'res.company', 
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        tracking=True
    )
    
    display_name = fields.Char(
        string='Display Name', 
        compute='_compute_display_name', 
        store=True
    )
    
    @api.depends('year', 'target_amount', 'category', 'type')
    def _compute_display_name(self):
        """
        Generate a readable display name for the sale target record with formatted amount.
        """
        for record in self:
            # Safely handle potential None or False values
            year = record.year or ''
            category = (record.category or '').capitalize()
            type_val = (record.type or '').upper()
            target_amount = record.target_amount or 0.0

            # Construct display name with formatted amount (thousand separators)
            record.display_name = f"{year} ({category} - {type_val}) Target: {target_amount:,.2f}".strip()
    
    @api.constrains('year')
    def _check_year_range(self):
        """
        Validate that the year is within a reasonable range.
        """
        current_year = fields.Date.today().year
        for record in self:
            if record.year < current_year - 10 or record.year > current_year + 10:
                raise ValidationError(f"Year must be between {current_year-10} and {current_year+10}")
    
    @api.constrains('year', 'category', 'type')
    def _check_unique_target(self):
        """
        Ensure only one target exists for a specific year, category, and type combination.
        """
        for record in self:
            existing_targets = self.search([
                ('year', '=', record.year),
                ('category', '=', record.category),
                ('type', '=', record.type),
                ('id', '!=', record.id)
            ])
            if existing_targets:
                raise ValidationError(
                    f"A target already exists for {record.year} "
                    f"with {record.category} - {record.type} category"
                )
