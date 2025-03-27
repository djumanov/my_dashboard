from odoo import models, fields, api
from odoo.exceptions import ValidationError

class SaleTarget(models.Model):
    """
    Sales Target Model to track and manage sales targets by project tag and year.
    """
    _name = 'sale.target'
    _description = 'Sales Target'
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Add mail tracking
    _rec_name = 'display_name'
    _order = 'year desc, target_amount desc'

    # Existing fields remain the same
    project_tag_id = fields.Many2one(
        'project.tags', 
        string='Project Tag', 
        required=True, 
        help='Project tag for which the sales target is defined',
        tracking=True  # Enable tracking for this field
    )
    
    year = fields.Integer(
        string='Year', 
        required=True, 
        default=lambda self: fields.Date.today().year,
        help='Year for which the sales target is set',
        tracking=True
    )
    
    target_amount = fields.Monetary(
        string='Target Amount', 
        currency_field='company_currency_id',
        required=True,
        help='Total sales target amount for the specified project tag and year',
        tracking=True
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
    
    # Existing methods remain the same
    @api.depends('project_tag_id', 'year', 'target_amount')
    def _compute_display_name(self):
        """
        Generate a readable display name for the sale target record.
        """
        for record in self:
            record.display_name = f"{record.project_tag_id.name} - {record.year} (Target: {record.target_amount:,.2f})"
    
    @api.constrains('year')
    def _check_year_range(self):
        """
        Validate that the year is within a reasonable range.
        """
        current_year = fields.Date.today().year
        for record in self:
            if record.year < current_year - 10 or record.year > current_year + 10:
                raise ValidationError(f"Year must be between {current_year-10} and {current_year+10}")
    
    @api.constrains('project_tag_id', 'year')
    def _check_unique_target(self):
        """
        Ensure only one target exists for a specific project tag and year combination.
        """
        for record in self:
            existing_targets = self.search([
                ('project_tag_id', '=', record.project_tag_id.id),
                ('year', '=', record.year),
                ('id', '!=', record.id)
            ])
            if existing_targets:
                raise ValidationError(f"A target already exists for {record.project_tag_id.name} in {record.year}")