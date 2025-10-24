import json
from odoo import api, fields, models, _
import base64
from io import BytesIO
from odoo.tools.misc import xlsxwriter

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

    def action_export_excel(self):
        """Export summary + stats (dept, gender, category) and then an Employees table (stacked below)."""
        self.ensure_one()

        # ---- Data ----
        company = self.company_id or self.env.company
        Employee = self.env['hr.employee']

        employees = Employee.search([
            ('company_id', '=', company.id),
            ('active', '=', True),
        ])

        total_employees = len(employees)
        male   = len(employees.filtered(lambda e: e.gender == 'male'))
        female = len(employees.filtered(lambda e: e.gender == 'female'))
        other  = total_employees - male - female

        # Departments
        dept_counts = {}
        for emp in employees:
            dname = emp.department_id.name or 'Undefined'
            dept_counts[dname] = dept_counts.get(dname, 0) + 1

        # Categories (tags) – count active employees tagged with each category
        categories = self.env['hr.employee.category'].search([])
        category_counts = {}
        for cat in categories:
            # skip “Male/Female” categories if you use those as tags (optional)
            if cat.name and cat.name.lower() in ('male', 'female'):
                continue
            cnt = Employee.search_count([
                ('category_ids', 'in', cat.id),
                ('company_id', '=', company.id),
                ('active', '=', True),
            ])
            if cnt:
                category_counts[cat.name] = cnt

        # ---- Workbook ----
        from io import BytesIO
        import base64
        from odoo.tools.misc import xlsxwriter

        output = BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = wb.add_worksheet('HR Report')

        # Column widths so nothing shows as "#####"
        ws.set_column('A:A', 5)        # padding
        ws.set_column('B:B', 36)       # labels / names
        ws.set_column('C:C', 18)       # counts
        ws.set_column('D:H', 4)        # spacing
        ws.set_column('I:N', 24)       # employees table (we'll place it in B later; this is just safety)

        title_fmt = wb.add_format({'bold': True, 'font_size': 16})
        hdr_fmt   = wb.add_format({'bold': True, 'bg_color': '#F2F2F2', 'border': 1, 'align': 'left'})
        cell_txt  = wb.add_format({'border': 1})
        cell_int  = wb.add_format({'border': 1, 'num_format': '#,##0'})
        date_fmt  = wb.add_format({'border': 1, 'num_format': 'yyyy-mm-dd'})

        r = 1

        # Title
        ws.write(r, 1, 'HR Dashboard Export', title_fmt); r += 2

        # Summary
        ws.write(r, 1, 'Summary', hdr_fmt); r += 1
        ws.write(r, 1, 'Total Employees', cell_txt)
        ws.write(r, 2, total_employees, cell_int)
        r += 2

        # Departments – Headcount
        ws.write(r, 1, 'Departments – Headcount', hdr_fmt); r += 1
        ws.write(r, 1, 'Department', hdr_fmt)
        ws.write(r, 2, 'Count', hdr_fmt)
        for dname, cnt in sorted(dept_counts.items()):
            r += 1
            ws.write(r, 1, dname, cell_txt)
            ws.write(r, 2, cnt, cell_int)
        r += 2

        # Gender – Headcount
        ws.write(r, 1, 'Gender – Headcount', hdr_fmt); r += 1
        ws.write(r, 1, 'Male',   cell_txt); ws.write(r, 2, male,   cell_int); r += 1
        ws.write(r, 1, 'Female', cell_txt); ws.write(r, 2, female, cell_int); r += 1
        ws.write(r, 1, 'Other',  cell_txt); ws.write(r, 2, other,  cell_int); r += 2

        # NEW: Employee Count by Category
        ws.write(r, 1, 'Employee Count – By Category', hdr_fmt); r += 1
        ws.write(r, 1, 'Category', hdr_fmt)
        ws.write(r, 2, 'Count',    hdr_fmt)
        if category_counts:
            for cname, cnt in sorted(category_counts.items()):
                r += 1
                ws.write(r, 1, cname, cell_txt)
                ws.write(r, 2, cnt,   cell_int)
        else:
            r += 1
            ws.write(r, 1, '— No categories found —', cell_txt)
            ws.write(r, 2, 0, cell_int)
        r += 2

        # Employees table (placed AFTER the stats, stacked vertically)
        start_row = r
        start_col = 1  # column B
        headers = ['Full Name', 'Date of Birth', 'Gender', 'Phone Number', 'Role', 'Department']
        for i, h in enumerate(headers):
            ws.write(start_row, start_col + i, h, hdr_fmt)
        ws.set_column(start_col + 0, start_col + 0, 32)  # Full Name
        ws.set_column(start_col + 1, start_col + 1, 16)  # Date of Birth
        ws.set_column(start_col + 2, start_col + 2, 12)  # Gender
        ws.set_column(start_col + 3, start_col + 3, 24)  # Phone
        ws.set_column(start_col + 4, start_col + 4, 28)  # Role
        ws.set_column(start_col + 5, start_col + 5, 36)  # Department

        r = start_row + 1
        for emp in employees:
            phone = emp.mobile_phone or emp.work_phone or ''
            role  = emp.job_title or ''
            dept  = emp.department_id.name or ''
            ws.write(r, start_col + 0, emp.name or '', cell_txt)

            # birthday to python date for xlsxwriter
            py_date = None
            if emp.birthday:
                try:
                    py_date = fields.Date.to_date(emp.birthday)
                except Exception:
                    py_date = None
            if py_date:
                ws.write_datetime(r, start_col + 1, py_date, date_fmt)
            else:
                ws.write(r, start_col + 1, '', cell_txt)

            ws.write(r, start_col + 2, (emp.gender or '').capitalize(), cell_txt)
            ws.write(r, start_col + 3, phone, cell_txt)
            ws.write(r, start_col + 4, role,  cell_txt)
            ws.write(r, start_col + 5, dept,  cell_txt)
            r += 1

        # Freeze header row of Employees table & add autofilter
        ws.freeze_panes(start_row + 1, start_col)
        ws.autofilter(start_row, start_col, max(start_row, r - 1), start_col + len(headers) - 1)

        wb.close()
        output.seek(0)

        filename = f"HR_Report_{fields.Date.today()}.xlsx"
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': base64.b64encode(output.read()),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
