import json
import logging
from datetime import datetime
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.tools import float_round

import base64
from io import BytesIO
from odoo.tools.misc import xlsxwriter

_logger = logging.getLogger(__name__)


class L2Dashboard(models.Model):
    _name = 'l2.dashboard'
    _description = 'L2 Dashboard Data'
    _rec_name = 'name'

    name = fields.Char(
        string='Dashboard Name',
        default=lambda self: _('L2 Dashboard - %s') % fields.Date.today().strftime('%Y')
    )

    dashboard_data = fields.Text(
    string="Dashboard Data",
    compute="_compute_dashboard_data",
    readonly=True,
    store=False,
    )

    last_update = fields.Datetime(string='Last Update', readonly=True)

    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(related='company_id.currency_id')

    year = fields.Selection(
        selection='_get_year_selection',
        string='Year',
        default=lambda self: str(fields.Date.today().year),
        required=True,
    )
    active = fields.Boolean(default=True)

    # ---------------- helpers ----------------
    @api.model
    def _get_year_selection(self):
        current_year = datetime.now().year
        return [(str(year), str(year)) for year in range(2023, current_year + 1)]

    @staticmethod
    def _month_names():
        return [datetime(2000, i + 1, 1).strftime('%b') for i in range(12)]

    @staticmethod
    def _zeros():
        return [0.0] * 12

    @staticmethod
    def _empty_breakdown():
        return [[] for _ in range(12)]

    @staticmethod
    def _to_dict(dist):
        """Analytic distribution -> dict[int, float]"""
        if not dist:
            return {}
        if isinstance(dist, dict):
            return dist
        try:
            return json.loads(dist)
        except Exception:
            return {}

    @staticmethod
    def _month_buckets():
        return [defaultdict(float) for _ in range(12)]

    @staticmethod
    def _mk_breakdown(month_buckets, id_to_name):
        out = []
        for b in month_buckets:
            arr = [
                {
                    "project_id": pid,
                    "project": id_to_name.get(pid, str(pid)),
                    "amount": round(val, 2),
                }
                for pid, val in b.items() if val
            ]
            arr.sort(key=lambda x: -x["amount"])
            out.append(arr)
        return out

    def _format_amount(self, amount):
        return float_round(amount, precision_digits=2)
    # -----------------------------------------

    @api.depends('year', 'company_id')
    def _compute_dashboard_data(self):
        for record in self:
            record.dashboard_data = json.dumps(record._get_dashboard_data(), default=float)
            record.last_update = fields.Datetime.now()

    @api.model
    def get_dashboard_data_json(self, year=None):
        if not year:
            year = fields.Date.today().year

        dashboard = self.search([
            ('year', '=', year),
            ('company_id', '=', self.env.company.id)
        ], limit=1)

        if not dashboard:
            dashboard = self.create({'year': year, 'company_id': self.env.company.id})

        dashboard._compute_dashboard_data()
        return dashboard.dashboard_data

    def _get_dashboard_data(self):
        self.ensure_one()
        year = int(self.year)

        sales_data = self._get_sales_data(year)
        revenue_data = self._get_revenue_data(year)
        expenses_data = self._get_expenses_data(year)
        cash_flow_data = self._get_cashflow_data(year)

        global_max = self._get_global_max(sales_data, revenue_data, expenses_data, cash_flow_data)

        return {
            'filters': {'year': year},
            'company': {
                'name': self.company_id.name,
                'currency': self.currency_id.symbol,
                'country': self.company_id.country_id.name or _('Not Set'),
            },
            'sales': sales_data,
            'revenue': revenue_data,
            'expenses': expenses_data,
            'cash_flow': cash_flow_data,
            'global_max': global_max,
            'last_update': fields.Datetime.to_string(fields.Datetime.now())
        }

    def _get_global_max(self, sales, revenue, expenses, cash_flow):
        def flatten(values):
            flat = []
            for v in values or []:
                if isinstance(v, (list, tuple)):
                    flat.extend(flatten(v))
                else:
                    try:
                        flat.append(float(v))
                    except Exception:
                        pass
            return flat

        all_numbers = []
        for dataset in [sales, revenue, expenses]:
            for entry in dataset.values():
                all_numbers.extend(flatten(entry.get("amounts")))

        for entry in cash_flow.values():
            all_numbers.extend(flatten(entry.get("inflow")))
            all_numbers.extend(flatten(entry.get("outflow")))

        return max(all_numbers) if all_numbers else 0

    # ---------------- data builders ----------------
    def _get_sales_data(self, year):
        months = self._month_names()
        total_monthly = self._zeros()
        local_monthly = self._zeros()
        export_monthly = self._zeros()

        local_m_buckets = self._month_buckets()
        export_m_buckets = self._month_buckets()

        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"

        company_currency = self.env.company.currency_id

        orders = self.env['sale.order'].search([
            ('date_order', '>=', start_date),
            ('date_order', '<=', end_date),
            ('company_id', '=', self.env.company.id),
            ('state', 'in', ['sale', 'done']),
        ])

        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)

        if not local_tag or not export_tag:
            # return zeros instead of raising to keep frontend stable
            return {
                'total': {'months': months, 'amounts': total_monthly, 'sum': 0.0},
                'local_sales':  {'months': months, 'amounts': local_monthly,  'sum': 0.0, 'breakdown': self._empty_breakdown()},
                'export_sales': {'months': months, 'amounts': export_monthly, 'sum': 0.0, 'breakdown': self._empty_breakdown()},
            }

        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])

        local_project_ids = set(local_projects.ids)
        export_project_ids = set(export_projects.ids)

        aa_to_project_id = {}
        for pr in (local_projects | export_projects):
            if pr.analytic_account_id:
                aa_to_project_id[pr.analytic_account_id.id] = pr.id

        project_id_to_name = {p.id: p.name for p in (local_projects | export_projects)}

        for order in orders:
            m = order.date_order.month - 1
            cur = order.currency_id
            dt = order.date_order

            categorized = False
            if hasattr(order, 'project_ids') and order.project_ids:
                linked = order.project_ids
                amt_total_ccy = cur._convert(order.amount_untaxed, company_currency, self.env.company, dt)
                per = amt_total_ccy / max(len(linked), 1)

                for pr in linked:
                    if pr.id in local_project_ids:
                        local_monthly[m] += per
                        local_m_buckets[m][pr.id] += per
                        categorized = True
                    elif pr.id in export_project_ids:
                        export_monthly[m] += per
                        export_m_buckets[m][pr.id] += per
                        categorized = True

                if categorized:
                    total_monthly[m] += amt_total_ccy

            if not categorized:
                for line in order.order_line:
                    dist = self._to_dict(line.analytic_distribution)
                    if not dist:
                        continue

                    line_amt_ccy = cur._convert(line.price_subtotal, company_currency, self.env.company, dt)
                    pushed = False
                    for aa_id_str, percent in dist.items():
                        try:
                            aa_id = int(aa_id_str)
                        except Exception:
                            continue
                        pr_id = aa_to_project_id.get(aa_id)
                        if not pr_id:
                            continue
                        share = line_amt_ccy * (float(percent) / 100.0 if percent else 1.0)

                        if pr_id in local_project_ids:
                            local_monthly[m] += share
                            local_m_buckets[m][pr_id] += share
                            total_monthly[m] += share
                            pushed = True
                        elif pr_id in export_project_ids:
                            export_monthly[m] += share
                            export_m_buckets[m][pr_id] += share
                            total_monthly[m] += share
                            pushed = True

                    if not pushed and line_amt_ccy:
                        total_monthly[m] += line_amt_ccy

        for i in range(12):
            total_monthly[i] = round(total_monthly[i], 2)
            local_monthly[i] = round(local_monthly[i], 2)
            export_monthly[i] = round(export_monthly[i], 2)

        local_breakdown = self._mk_breakdown(local_m_buckets, project_id_to_name)
        export_breakdown = self._mk_breakdown(export_m_buckets, project_id_to_name)

        return {
            'total': {'months': months, 'amounts': total_monthly, 'sum': self._format_amount(sum(total_monthly))},
            'local_sales':  {'months': months, 'amounts': local_monthly,  'sum': self._format_amount(sum(local_monthly)),  'breakdown': local_breakdown},
            'export_sales': {'months': months, 'amounts': export_monthly, 'sum': self._format_amount(sum(export_monthly)), 'breakdown': export_breakdown},
        }

    def _get_revenue_data(self, year):
        months = self._month_names()
        total_monthly = self._zeros()
        local_monthly = self._zeros()
        export_monthly = self._zeros()

        local_m_buckets = self._month_buckets()
        export_m_buckets = self._month_buckets()

        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"

        company = self.env.company
        company_currency = company.currency_id

        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)
        if not local_tag or not export_tag:
            return {
                'total': {'months': months, 'amounts': total_monthly, 'sum': 0.0},
                'local_revenue':  {'months': months, 'amounts': local_monthly,  'sum': 0.0, 'breakdown': self._empty_breakdown()},
                'export_revenue': {'months': months, 'amounts': export_monthly, 'sum': 0.0, 'breakdown': self._empty_breakdown()},
            }

        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])

        local_project_ids = set(local_projects.ids)
        export_project_ids = set(export_projects.ids)

        aa_to_project_id = {}
        for pr in (local_projects | export_projects):
            if pr.analytic_account_id:
                aa_to_project_id[pr.analytic_account_id.id] = pr.id

        project_id_to_name = {p.id: p.name for p in (local_projects | export_projects)}

        invoice_domain = [
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('company_id', '=', company.id),
        ]
        customer_invoices = self.env['account.move'].search(invoice_domain)

        for inv in customer_invoices:
            inv_currency = inv.currency_id
            inv_date = inv.invoice_date or inv.date
            month_idx = (inv_date.month - 1) if inv_date else 0

            for line in inv.invoice_line_ids:
                dist = self._to_dict(line.analytic_distribution)
                if not dist:
                    amount_ccy = inv_currency._convert(line.price_subtotal, company_currency, company, inv_date)
                    total_monthly[month_idx] += amount_ccy
                    continue

                vals = list(dist.values())
                sum_vals = sum(float(v) for v in vals) if vals else 0.0
                percent_mode = sum_vals > 1.01

                pushed_any = False
                for aa_id_str, share in dist.items():
                    try:
                        aa_id = int(aa_id_str)
                    except Exception:
                        continue

                    pr_id = aa_to_project_id.get(aa_id)
                    if not pr_id:
                        continue

                    amount_ccy = inv_currency._convert(line.price_subtotal, company_currency, company, inv_date)
                    part = amount_ccy * (float(share) / 100.0 if percent_mode else float(share or 1.0))

                    if pr_id in local_project_ids:
                        local_monthly[month_idx] += part
                        local_m_buckets[month_idx][pr_id] += part
                        total_monthly[month_idx] += part
                        pushed_any = True
                    elif pr_id in export_project_ids:
                        export_monthly[month_idx] += part
                        export_m_buckets[month_idx][pr_id] += part
                        total_monthly[month_idx] += part
                        pushed_any = True

                if not pushed_any:
                    amount_ccy = inv_currency._convert(line.price_subtotal, company_currency, company, inv_date)
                    total_monthly[month_idx] += amount_ccy

        for i in range(12):
            total_monthly[i] = round(total_monthly[i], 2)
            local_monthly[i] = round(local_monthly[i], 2)
            export_monthly[i] = round(export_monthly[i], 2)

        local_breakdown = self._mk_breakdown(local_m_buckets, project_id_to_name)
        export_breakdown = self._mk_breakdown(export_m_buckets, project_id_to_name)

        return {
            'total': {'months': months, 'amounts': total_monthly, 'sum': self._format_amount(sum(total_monthly))},
            'local_revenue':  {'months': months, 'amounts': local_monthly,  'sum': self._format_amount(sum(local_monthly)),  'breakdown': local_breakdown},
            'export_revenue': {'months': months, 'amounts': export_monthly, 'sum': self._format_amount(sum(export_monthly)), 'breakdown': export_breakdown},
        }

    def _get_expenses_data(self, year):
        months = self._month_names()
        total_monthly = self._zeros()
        local_monthly = self._zeros()
        export_monthly = self._zeros()

        # NEW: per-month, per-project buckets for the tooltip
        local_m_buckets = self._month_buckets()
        export_m_buckets = self._month_buckets()

        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"

        company = self.env.company
        company_currency = company.currency_id

        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)
        if not local_tag or not export_tag:
            return {
                'total': {'months': months, 'amounts': total_monthly, 'sum': 0.0},
                'local_expenses':  {'months': months, 'amounts': local_monthly,  'sum': 0.0, 'breakdown': self._empty_breakdown()},
                'export_expenses': {'months': months, 'amounts': export_monthly, 'sum': 0.0, 'breakdown': self._empty_breakdown()},
            }

        # Find projects by tag (Local / Export)
        local_projects = self.env['project.project'].search([('tag_ids', 'in', [local_tag.id])])
        export_projects = self.env['project.project'].search([('tag_ids', 'in', [export_tag.id])])

        local_project_ids = set(local_projects.ids)
        export_project_ids = set(export_projects.ids)

        # Map analytic account -> project, and project -> name (for tooltip rows)
        aa_to_project_id = {}
        for pr in (local_projects | export_projects):
            if pr.analytic_account_id:
                aa_to_project_id[pr.analytic_account_id.id] = pr.id
        project_id_to_name = {p.id: p.name for p in (local_projects | export_projects)}

        vendor_bills = self.env['account.move'].search([
            ('move_type', '=', 'in_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', start_date),
            ('invoice_date', '<=', end_date),
            ('company_id', '=', company.id),
        ])

        for bill in vendor_bills:
            bill_currency = bill.currency_id
            bill_date = bill.invoice_date or bill.date
            m = (bill_date.month - 1) if bill_date else 0

            # Use invoice lines (vendor bill product lines)
            for line in bill.invoice_line_ids:
                dist = self._to_dict(line.analytic_distribution)
                amount_ccy = bill_currency._convert(line.price_subtotal, company_currency, company, bill_date)

                # If no distribution → not classifiable; still count towards TOTAL
                if not dist:
                    if amount_ccy:
                        total_monthly[m] += amount_ccy
                    continue

                vals = list(dist.values())
                sum_vals = sum(float(v) for v in vals) if vals else 0.0
                percent_mode = sum_vals > 1.01  # same heuristic as revenue

                pushed_any = False
                for aa_id_str, share in dist.items():
                    try:
                        aa_id = int(aa_id_str)
                    except Exception:
                        continue

                    pr_id = aa_to_project_id.get(aa_id)
                    # If AA isn’t tied to a project we know, skip (but still add to TOTAL later)
                    if not pr_id:
                        continue

                    part = amount_ccy * (float(share) / 100.0 if percent_mode else float(share or 1.0))

                    if pr_id in local_project_ids:
                        local_monthly[m] += part
                        local_m_buckets[m][pr_id] += part  # <- for tooltip
                        total_monthly[m] += part
                        pushed_any = True
                    elif pr_id in export_project_ids:
                        export_monthly[m] += part
                        export_m_buckets[m][pr_id] += part  # <- for tooltip
                        total_monthly[m] += part
                        pushed_any = True

                # If distribution existed but none of its AAs mapped to our Local/Export projects,
                # still count the whole line to TOTAL to avoid losing amounts.
                if not pushed_any and amount_ccy:
                    total_monthly[m] += amount_ccy

        # Round month sums
        for i in range(12):
            total_monthly[i] = round(total_monthly[i], 2)
            local_monthly[i] = round(local_monthly[i], 2)
            export_monthly[i] = round(export_monthly[i], 2)

        # Build per-month project arrays for the tooltip
        local_breakdown = self._mk_breakdown(local_m_buckets, project_id_to_name)
        export_breakdown = self._mk_breakdown(export_m_buckets, project_id_to_name)

        return {
            'total': {'months': months, 'amounts': total_monthly, 'sum': self._format_amount(sum(total_monthly))},
            'local_expenses':  {
                'months': months,
                'amounts': local_monthly,
                'sum': self._format_amount(sum(local_monthly)),
                'breakdown': local_breakdown,        # <-- NEW
            },
            'export_expenses': {
                'months': months,
                'amounts': export_monthly,
                'sum': self._format_amount(sum(export_monthly)),
                'breakdown': export_breakdown,       # <-- NEW
            }
        }

    def _get_cashflow_data(self, year):
        months = self._month_names()

        inflow_total = self._zeros()
        outflow_total = self._zeros()
        inflow_local = self._zeros()
        outflow_local = self._zeros()
        inflow_export = self._zeros()
        outflow_export = self._zeros()

        start_date = f'{year}-01-01'
        end_date = f'{year}-12-31'

        company_currency = self.env.company.currency_id

        local_tag = self.env['project.tags'].search([('name', '=', 'Local')], limit=1)
        export_tag = self.env['project.tags'].search([('name', '=', 'Export')], limit=1)
        if not local_tag or not export_tag:
            return {
                'total': {'months': months, 'inflow': inflow_total, 'outflow': outflow_total,
                          'sum': self._format_amount(0.0)},
                'local_cash_flow':  {'months': months, 'inflow': inflow_local,  'outflow': outflow_local,
                                     'sum': self._format_amount(0.0)},
                'export_cash_flow': {'months': months, 'inflow': inflow_export, 'outflow': outflow_export,
                                     'sum': self._format_amount(0.0)},
            }

        local_analytic_account_ids = set(self.env['project.project']
                                         .search([('tag_ids', 'in', [local_tag.id])])
                                         .mapped('analytic_account_id').ids)
        export_analytic_account_ids = set(self.env['project.project']
                                          .search([('tag_ids', 'in', [export_tag.id])])
                                          .mapped('analytic_account_id').ids)

        # Inflow: inbound payments reconciled with invoices
        customer_payments = self.env['account.payment'].search([
            ('payment_type', '=', 'inbound'),
            ('state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ])
        for payment in customer_payments:
            payment_month = payment.date.month - 1
            for invoice in payment.reconciled_invoice_ids:
                inv_currency = invoice.currency_id
                inv_date = invoice.invoice_date or invoice.date
                for line in invoice.invoice_line_ids:
                    dist = self._to_dict(line.analytic_distribution)
                    if not dist:
                        continue
                    amount_ccy = inv_currency._convert(line.price_subtotal, company_currency, self.env.company, inv_date)
                    for account_id_str in dist.keys():
                        try:
                            account_id = int(account_id_str)
                        except Exception:
                            continue
                        if account_id in local_analytic_account_ids:
                            inflow_local[payment_month] += amount_ccy
                            inflow_total[payment_month] += amount_ccy
                            break
                        if account_id in export_analytic_account_ids:
                            inflow_export[payment_month] += amount_ccy
                            inflow_total[payment_month] += amount_ccy
                            break

        # Outflow: outbound payments reconciled with bills
        vendor_payments = self.env['account.payment'].search([
            ('payment_type', '=', 'outbound'),
            ('state', '=', 'posted'),
            ('date', '>=', start_date),
            ('date', '<=', end_date)
        ])
        for payment in vendor_payments:
            payment_month = payment.date.month - 1
            for bill in payment.reconciled_bill_ids:
                bill_currency = bill.currency_id
                bill_date = bill.invoice_date or bill.date
                for line in bill.invoice_line_ids:
                    dist = self._to_dict(line.analytic_distribution)
                    if not dist:
                        continue
                    amount_ccy = bill_currency._convert(line.price_subtotal, company_currency, self.env.company, bill_date)
                    for account_id_str in dist.keys():
                        try:
                            account_id = int(account_id_str)
                        except Exception:
                            continue
                        if account_id in local_analytic_account_ids:
                            outflow_local[payment_month] += amount_ccy
                            outflow_total[payment_month] += amount_ccy
                            break
                        if account_id in export_analytic_account_ids:
                            outflow_export[payment_month] += amount_ccy
                            outflow_total[payment_month] += amount_ccy
                            break

        return {
            'total': {
                'months': months, 'inflow': inflow_total, 'outflow': outflow_total,
                'sum': self._format_amount(sum(inflow_total) - sum(outflow_total)),
            },
            'local_cash_flow': {
                'months': months, 'inflow': inflow_local, 'outflow': outflow_local,
                'sum': self._format_amount(sum(inflow_local) - sum(outflow_local)),
            },
            'export_cash_flow': {
                'months': months, 'inflow': inflow_export, 'outflow': outflow_export,
                'sum': self._format_amount(sum(inflow_export) - sum(outflow_export)),
            },
        }

    def action_export_excel(self):
        """Export L2 dashboard as a presentation-ready 4-sheet workbook
        (Sales / Revenue / Expenses / CashFlow). Each sheet contains 3
        stacked tables and ONLY numbers (no charts)."""
        self.ensure_one()

        # ---- Pull computed data once ----
        data = self._get_dashboard_data()
        months = data['sales']['total']['months']  # ["Jan","Feb",..., "Dec"]

        # Convenience handles
        s_total  = data['sales']['total']['amounts']
        s_local  = data['sales']['local_sales']['amounts']
        s_export = data['sales']['export_sales']['amounts']

        r_total  = data['revenue']['total']['amounts']
        r_local  = data['revenue']['local_revenue']['amounts']
        r_export = data['revenue']['export_revenue']['amounts']

        e_total  = data['expenses']['total']['amounts']
        e_local  = data['expenses']['local_expenses']['amounts']
        e_export = data['expenses']['export_expenses']['amounts']

        cf_total_in  = data['cash_flow']['total']['inflow']
        cf_total_out = data['cash_flow']['total']['outflow']
        cf_loc_in    = data['cash_flow']['local_cash_flow']['inflow']
        cf_loc_out   = data['cash_flow']['local_cash_flow']['outflow']
        cf_exp_in    = data['cash_flow']['export_cash_flow']['inflow']
        cf_exp_out   = data['cash_flow']['export_cash_flow']['outflow']
        cf_net_total  = [cf_total_in[i] - cf_total_out[i] for i in range(12)]
        cf_net_local  = [cf_loc_in[i]   - cf_loc_out[i]   for i in range(12)]
        cf_net_export = [cf_exp_in[i]   - cf_exp_out[i]   for i in range(12)]

        # ---- Workbook boilerplate ----
        from io import BytesIO
        import base64
        from odoo.tools.misc import xlsxwriter

        output = BytesIO()
        wb = xlsxwriter.Workbook(output, {'in_memory': True})

        # ---- Formats ----
        title_fmt = wb.add_format({
            'bold': True, 'font_size': 16, 'align': 'left', 'valign': 'vcenter'
        })
        meta_fmt = wb.add_format({'align': 'right', 'italic': True, 'font_color': '#666666'})
        section_fmt = wb.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
        hdr_fmt = wb.add_format({'bold': True, 'bg_color': '#F2F2F2', 'border': 1, 'align': 'center'})
        cell_num = wb.add_format({'border': 1, 'num_format': '#,##0.00'})
        cell_txt = wb.add_format({'border': 1})
        total_fmt = wb.add_format({'border': 1, 'num_format': '#,##0.00', 'bold': True, 'bg_color': '#FFF2CC'})
        zebra = wb.add_format({'border': 1, 'num_format': '#,##0.00', 'bg_color': '#FAFAFA'})

        def setup_sheet(name):
            ws = wb.add_worksheet(name)
            # Column widths to avoid "#####"
            ws.set_column('A:A', 16)    # Month
            ws.set_column('B:Z', 18)    # Amount columns
            # Header row (title + meta)
            ws.merge_range(0, 0, 0, 5, f"{name} – {self.company_id.name}", title_fmt)
            ws.write(0, 6, f"Year: {self.year}   |   Generated: {fields.Datetime.now().strftime('%Y-%m-%d %H:%M')}", meta_fmt)
            # Print settings (looks nice if printed)
            ws.set_landscape()
            ws.fit_to_pages(1, 0)
            ws.repeat_rows(0, 0)
            return ws

        def write_table(ws, top_row, caption, months_list, cols_dict):
            """
            Write a section caption and a table underneath.
            cols_dict = Ordered mapping: {'Label1': [12 floats], 'Label2': [...]}
            Returns last row index used (0-based).
            """
            # Section caption (full-width merge)
            width = 1 + len(cols_dict)  # month + n columns
            ws.merge_range(top_row, 0, top_row, width, caption, section_fmt)
            r = top_row + 1

            # Header
            ws.write(r, 0, "Month", hdr_fmt)
            c = 1
            for lbl in cols_dict.keys():
                ws.write(r, c, lbl, hdr_fmt); c += 1
            r += 1

            # Body: months
            for i, m in enumerate(months_list):
                ws.write(r, 0, m, cell_txt)
                c = 1
                for j, (_, vals) in enumerate(cols_dict.items()):
                    val = float(vals[i]) if i < len(vals) else 0.0
                    # zebra banded rows
                    ws.write(r, c, val, zebra if i % 2 else cell_num)
                    c += 1
                r += 1

            # Totals
            ws.write(r, 0, "Total", hdr_fmt)
            for idx in range(len(cols_dict)):
                col = 1 + idx
                first_data = r - len(months_list)
                last_data = r - 1
                cell_from = xlsxwriter.utility.xl_rowcol_to_cell(first_data, col)
                cell_to = xlsxwriter.utility.xl_rowcol_to_cell(last_data, col)
                ws.write_formula(r, col, f"=SUM({cell_from}:{cell_to})", total_fmt)
            # Freeze panes at header
            ws.freeze_panes(top_row + 2, 1)
            # Autofilter the table
            ws.autofilter(top_row + 1, 0, r, len(cols_dict))
            return r  # last row with totals

        # ---- Sheet 1: Sales Overview (3 tables) ----
        ws = setup_sheet('Sales Overview')
        r = 2
        r = write_table(ws, r, "Total Sales (Monthly)", months, {"Total Sales": s_total})
        r = write_table(ws, r + 2, "Local Sales (Monthly)", months, {"Local Sales": s_local})
        r = write_table(ws, r + 2, "Export Sales (Monthly)", months, {"Export Sales": s_export})

        # ---- Sheet 2: Revenue Overview (3 tables) ----
        ws = setup_sheet('Revenue Overview')
        r = 2
        r = write_table(ws, r, "Total Revenue (Monthly)", months, {"Total Revenue": r_total})
        r = write_table(ws, r + 2, "Local Revenue (Monthly)", months, {"Local Revenue": r_local})
        r = write_table(ws, r + 2, "Export Revenue (Monthly)", months, {"Export Revenue": r_export})

        # ---- Sheet 3: Expenses Overview (3 tables) ----
        ws = setup_sheet('Expenses Overview')
        r = 2
        r = write_table(ws, r, "Total Expenses (Monthly)", months, {"Total Expenses": e_total})
        r = write_table(ws, r + 2, "Local Expenses (Monthly)", months, {"Local Expenses": e_local})
        r = write_table(ws, r + 2, "Export Expenses (Monthly)", months, {"Export Expenses": e_export})

        # ---- Sheet 4: CashFlow Overview (3 tables: Total / Local / Export) ----
        ws = setup_sheet('CashFlow Overview')
        r = 2
        r = write_table(ws, r, "Cash Flow – Total (Monthly)", months, {
            "Inflow (Total)":  cf_total_in,
            "Outflow (Total)": cf_total_out,
            "Net (Total)":     cf_net_total,
        })
        r = write_table(ws, r + 2, "Cash Flow – Local (Monthly)", months, {
            "Inflow (Local)":  cf_loc_in,
            "Outflow (Local)": cf_loc_out,
            "Net (Local)":     cf_net_local,
        })
        r = write_table(ws, r + 2, "Cash Flow – Export (Monthly)", months, {
            "Inflow (Export)":  cf_exp_in,
            "Outflow (Export)": cf_exp_out,
            "Net (Export)":     cf_net_export,
        })

        # ---- Save to attachment ----
        wb.close()
        output.seek(0)

        filename = f"L2_Financial_{self.year}.xlsx"
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

    def action_back_to_l1(self):
        """Go back to L1 dashboard (L1 demo)."""
        self.ensure_one()
        # Prefer XML-ID if available, else fall back to the exact URL you provided.
        try:
            action = self.env.ref("my_dashboard.action_l1_dashboard_demo").read()[0]
            return action
        except Exception:
            return {
                "type": "ir.actions.act_url",
                "url": "http://194.233.83.117:8069/web#cids=1&action=953&model=l1.dashboard_demo&view_type=form&menu_id=632",
                "target": "self",
            }
