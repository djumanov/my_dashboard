/** @odoo-module **/
import { useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class L3Dashboard extends Component {
  static template = "custom.l3_dashboard";
  static props = { ...standardFieldProps };

  setup() {
    const currentYear = new Date().getFullYear();
    this.state = useState({
      project: {},
      filters: { region: "", year: currentYear, month: "", project: "" },
      months: ["January","February","March","April","May","June","July","August","September","October","November","December"],
      years: Array.from({ length: 10 }, (_, i) => currentYear - i),
      projects: [],
    });

    this.formatNumber = (v) => {
      if (v === undefined || v === null || isNaN(v)) return "";
      return parseFloat(v).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    };
    this.formatPercent = (v) => {
      if (v === undefined || v === null || isNaN(v)) return "";
      return `${v.toFixed(2)}%`;
    };

    // ---------- per-row metrics ----------
    this.totalCost = (m) => (Number(m?.vendor_invoice || 0) + Number(m?.payroll_cost || 0));
    this.margin = (m) => (Number(m?.invoiced || 0) - this.totalCost(m));
    this.marginPct = (m) => {
      const inv = Number(m?.invoiced || 0);
      if (inv <= 0) return 0;
      return (this.margin(m) / inv) * 100;
    };

    // ---------- totals ----------
    this.totalCostTotals = (p) => Number(p?.total_vendor_invoice || 0) + Number(p?.total_payroll_cost || 0);
    this.marginTotals = (p) => Number(p?.total_invoiced || 0) - this.totalCostTotals(p);
    this.marginPctTotals = (p) => {
      const inv = Number(p?.total_invoiced || 0);
      if (inv <= 0) return 0;
      return (this.marginTotals(p) / inv) * 100;
    };

    onWillStart(async () => {
      const rpc = this.env.services.rpc;
      try {
        const result = await rpc("/custom/l3_dashboard/projects");
        this.state.projects = result || [];
      } catch (e) { console.warn("Failed to load projects:", e); }

      if (this.props.value) {
        try {
          const parsed = JSON.parse(this.props.value);
          this.state.project = parsed.project || {};
        } catch (e) { console.error("Failed to parse dashboard_data:", e); }
      }
    });
  }
}
registry.category("fields").add("l3_dashboard", L3Dashboard);
