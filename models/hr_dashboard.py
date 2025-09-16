import json
from odoo import api, fields, models, _


class HRDashboard(models.Model):
    _name = 'hr.dashboard'
    _description = 'HR Dashboard Data'

    name = fields.Char(string='Dashboard Name', default='HR Dashboard')
    
    dashboard_data = fields.Text(string='Dashboard Data', compute='_compute_dashboard_data')
    dashboard_data_array = fields.Text(string='D')
    last_update = fields.Datetime(string='Last Update')

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    

    @api.depends('company_id')
    def _compute_dashboard_data(self):
        for record in self:
            record.dashboard_data = json.dumps(record._get_dashboard_data())
            record.last_update = fields.Datetime.now()

    @api.model
    def get_dashboard_data_json(self):
        """API method to get dashboard data in JSON format"""
            
        dashboard = self.search([
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        
        if not dashboard:
            dashboard = self.create({
                'company_id': self.env.company.id,
            })
        
        dashboard._compute_dashboard_data()
        return dashboard.dashboard_data

    def _get_dashboard_data(self):
        """Compute all dashboard data and return as a structured dictionary"""
        self.ensure_one()
        
        employee_data = self._get_employee_data()
        
        return {
            'hr': {
                'total_employees': employee_data['total_employees'],
                'gender_data': {
                    'data': [
                        {'name': 'Male', 'value': employee_data['gender_data']['male']},
                        {'name': 'Female', 'value': employee_data['gender_data']['female']}
                    ],
                    'total': employee_data['gender_data']['male'] + employee_data['gender_data']['female'] + 
                             employee_data['gender_data']['other'],
                    'colors': ['#1e88e5', '#ff8f00'],
                },
                'departments': [
                    {'name': dept, 'count': count} 
                    for dept, count in employee_data['departments'].items()
                ],
                'categories': [
                    {'name': cat, 'count': count} 
                    for cat, count in employee_data['categories'].items()
                ]
            },
        }
    
    def _get_employee_data(self):
        """Get employee related data for the dashboard"""
        employees = self.env['hr.employee'].search([
            ('company_id', '=', self.company_id.id),
            ('active', '=', True),
        ])
        
        total_employees = len(employees)
        
        gender_data = {
            'male': len(employees.filtered(lambda e: e.gender == 'male')),
            'female': len(employees.filtered(lambda e: e.gender == 'female')),
            'other': len(employees.filtered(lambda e: e.gender not in ['male', 'female'] or not e.gender)),
        }
        
        departments = {}
        for employee in employees:
            department_name = employee.department_id.name or 'Undefined'
            departments[department_name] = departments.get(department_name, 0) + 1
        
        categories = self.env['hr.employee.category'].search([
            ('name', 'not in', ['Male', 'Female'])
        ])
    
        categories_count = {}
        
        for category in categories:
            # Count employees in this category
            employee_count = self.env['hr.employee'].search_count([
                ('category_ids', 'in', category.id),
                ('active', '=', True)  # Only count active employees
            ])
            
            categories_count[category.name] = employee_count
            
        return {
            'total_employees': total_employees,
            'gender_data': gender_data,
            'departments': departments,
            'categories': categories_count,
        }

   