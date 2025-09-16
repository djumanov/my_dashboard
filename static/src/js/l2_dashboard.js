/** @odoo-module **/
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { loadCSS } from "@web/core/assets";

await loadCSS("https://cdn.jsdelivr.net/npm/apexcharts/dist/apexcharts.css");

const { Component, useEffect, useState, useRef } = owl;
const _t = require("web.translation")._t;

export class L2Dashboard extends Component {
  setup() {
    this.charts = {};
    this.state = useState({
      main_data: [],
      data: {},
      error: false,
      errorMessage: "",
      isLoading: false,
    });

    // ---------- external tooltip (outside chart) ----------
    this._extTip = null;
    this._ensureTooltipHost();

    useEffect(() => {
      const dashboardData = this.props.record?.data?.dashboard_data || "{}";
      let parsed;
      try {
        parsed = JSON.parse(dashboardData);
      } catch (e) {
        console.warn("Invalid dashboard JSON", e);
        this.state.error = true;
        this.state.errorMessage = _t("Dashboard data is invalid.");
        return;
      }

      this.state.main_data = parsed;

      loadJS("https://cdn.jsdelivr.net/npm/apexcharts")
        .then(() => {
          this._initDashboard();
          try {
            this._renderCharts();
          } catch (err) {
            console.error("Chart render failed:", err);
            this.state.error = true;
            this.state.errorMessage = _t("Failed to render charts.");
          }
        })
        .catch((err) => {
          console.error("Failed to load ApexCharts", err);
          this.state.error = true;
          this.state.errorMessage = _t("Failed to load chart library.");
        });
    }, () => [this.props.record?.data?.dashboard_data]);

    // refs
    this.totalSalesChart = useRef("totalSalesChart");
    this.localSalesChart = useRef("localSalesChart");
    this.exportSalesChart = useRef("exportSalesChart");

    this.totalRevenueChart = useRef("totalRevenueChart");
    this.localRevenueChart = useRef("localRevenueChart");
    this.exportRevenueChart = useRef("exportRevenueChart");

    this.totalExpensesChart = useRef("totalExpensesChart");
    this.localExpensesChart = useRef("localExpensesChart");
    this.exportExpensesChart = useRef("exportExpensesChart");

    this.totalCashFlowChart = useRef("totalCashFlowChart");
    this.localCashFlowChart = useRef("localCashFlowChart");
    this.exportCashFlowChart = useRef("exportCashFlowChart");
  }

  // ---------------- external tooltip helpers ----------------
  _ensureTooltipHost() {
    if (!document.getElementById("l2-exttip-style")) {
      const css = document.createElement("style");
      css.id = "l2-exttip-style";
      css.textContent = `
        .l2-exttip {
          position: fixed;
          z-index: 999999;
          pointer-events: none;
          background: #fff;
          border: 1px solid rgba(0,0,0,.1);
          box-shadow: 0 6px 24px rgba(0,0,0,.12);
          border-radius: 10px;
          padding: 10px 12px;
          min-width: 220px;
          max-width: 360px;
          opacity: 0;
          transform: translate3d(0, 6px, 0);
          transition: opacity .08s ease, transform .08s ease;
          font-family: Inter, Roboto, sans-serif;
          font-size: 12px;
          color: #222;
        }
        .l2-exttip.show { opacity: 1; transform: translate3d(0, 0, 0); }
        .l2-exttip .l2-head { font-weight: 600; margin-bottom: 6px; }
        .l2-exttip .l2-row { display:flex; justify-content:space-between; gap:12px; margin-top:4px; white-space: nowrap; }
        .l2-exttip .l2-dot { display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px; }
      `;
      document.head.appendChild(css);
    }
    if (!this._extTip) {
      const div = document.createElement("div");
      div.className = "l2-exttip";
      document.body.appendChild(div);
      this._extTip = div;
    }
  }

  _truncateProject(name) {
    if (!name) return "";
    const words = String(name).split(/\s+/).filter(Boolean);
    if (words.length <= 2) return words.join(" ");
    return `${words[0]} ${words[1]} …`;
  }

  _showExtTip(html, clientX = 0, clientY = 0) {
    if (!this._extTip) return;
    this._extTip.innerHTML = html;

    const padding = 12;
    const rect = this._extTip.getBoundingClientRect();
    let x = clientX + 14;
    let y = clientY + 14;

    const vw = window.innerWidth;
    const vh = window.innerHeight;

    if (x + rect.width + padding > vw) x = Math.max(padding, clientX - rect.width - 14);
    if (y + rect.height + padding > vh) y = Math.max(padding, clientY - rect.height - 14);

    this._extTip.style.left = `${x}px`;
    this._extTip.style.top  = `${y}px`;
    this._extTip.classList.add("show");
  }

  _hideExtTip() {
    if (this._extTip) this._extTip.classList.remove("show");
  }
  // ----------------------------------------------------------

  _initDashboard() {
    const data = this.state.main_data || {};
    this.state.data = {
      sales: data.sales,
      revenue: data.revenue,
      expenses: data.expenses,
      cash_flow: data.cash_flow,
      company: data.company,
      global_max: data.global_max || 0,
    };

    this.state.error = !this.state.data;
    this.state.errorMessage = this.state.error ? _t("Error loading dashboard data") : "";
  }

  _renderCharts() {
    if (this.state.error) return;
    this._destroyCharts();

    const { sales, revenue, expenses, cash_flow } = this.state.data;

    const fmt = (v) => this.formatNumber(v);

    const pickNums = (a) => (Array.isArray(a) ? a.map((x) => +x || 0) : []);
    const maxOf = (arrs) => {
      const flat = arrs.flatMap(pickNums);
      return flat.length ? Math.max(...flat) : 1;
    };

    const niceCeil = (val, sig = 2) => {
      if (!isFinite(val) || val <= 0) return 1;
      const power = Math.floor(Math.log10(val)) - (sig - 1);
      const factor = Math.pow(10, power);
      return Math.ceil(val / factor) * factor;
    };
    const SIG = 2;

    const SALES_MAX    = niceCeil(
      maxOf([sales?.total?.amounts, sales?.local_sales?.amounts, sales?.export_sales?.amounts]),
      SIG
    );
    const REVENUE_MAX  = niceCeil(
      maxOf([revenue?.total?.amounts, revenue?.local_revenue?.amounts, revenue?.export_revenue?.amounts]),
      SIG
    );
    const EXPENSES_MAX = niceCeil(
      maxOf([expenses?.total?.amounts, expenses?.local_expenses?.amounts, expenses?.export_expenses?.amounts]),
      SIG
    );
    const CASHFLOW_MAX = niceCeil(
      maxOf([
        cash_flow?.total?.inflow, cash_flow?.total?.outflow,
        cash_flow?.local_cash_flow?.inflow,  cash_flow?.local_cash_flow?.outflow,
        cash_flow?.export_cash_flow?.inflow, cash_flow?.export_cash_flow?.outflow,
      ]),
      SIG
    );

    // add a small headroom so labels above bars are not clipped
    const padMax = (m) => Math.ceil(m * 1.05);

    // ---------- option builders ----------
    const clampLen = (...arrs) => Math.min(...arrs.map(a => Array.isArray(a) ? a.length : 0));

    const totalWithBreakdownOpts = (title, totalData, localData, exportData, color, yMaxRaw) => {
      const yMax = padMax(yMaxRaw);

      const months = Array.isArray(totalData?.months) ? totalData.months : [];
      const L = clampLen(months, totalData?.amounts, localData?.amounts, exportData?.amounts);

      const totalArr  = (totalData?.amounts  || []).slice(0, L).map(n => Number(n) || 0);
      const localArr  = (localData?.amounts  || []).slice(0, L).map(n => Number(n) || 0);
      const exportArr = (exportData?.amounts || []).slice(0, L).map(n => Number(n) || 0);
      const cats      = months.slice(0, L);

      return {
        series: [{ name: title, data: totalArr }],
        chart: {
          type: "bar",
          height: 280,
          toolbar: { show: false },
          fontFamily: "Inter, Roboto, sans-serif",
          animations: { enabled: true, easing: "easeinout", speed: 800 },
          events: { mouseLeave: () => this._hideExtTip() },
        },
        plotOptions: {
          bar: {
            borderRadius: 6,
            columnWidth: "60%",
            distributed: true,
            dataLabels: { position: "top" }, // outside, on top
          },
        },
        dataLabels: {
          enabled: true,
          formatter: (val) => this.formatMillionsShort(val),
          offsetY: -14, // lift above the bar
          style: { fontSize: "11px", fontWeight: 700, colors: ["#111"] },
        },
        stroke: { width: 1, colors: ["#fff"] },
        grid: { borderColor: "#e0e0e0", strokeDashArray: 4 },
        xaxis: {
          categories: cats,
          labels: { rotate: -45, style: { fontSize: "11px", fontWeight: 500, colors: "#333" } },
          axisTicks: { show: false },
          axisBorder: { color: "#ccc" },
        },
        yaxis: {
          min: 0,
          max: yMax,
          tickAmount: 5,
          forceNiceScale: false,
          title: { text: `Amount`, style: { fontSize: "12px", color: "#666" } },
          labels: { formatter: (val) => this.formatNumber(val), style: { fontSize: "11px", color: "#666" } },
        },
        fill: {
          type: "gradient",
          gradient: {
            shade: "light",
            type: "vertical",
            shadeIntensity: 0.3,
            gradientToColors: [color],
            inverseColors: false,
            opacityFrom: 0.6,
            opacityTo: 1,
            stops: [0, 100],
          },
        },
        tooltip: {
          shared: false,
          intersect: true,
          custom: ({ dataPointIndex, w }) => {
            const label = cats[dataPointIndex] ?? "";
            const t = totalArr[dataPointIndex] ?? 0;
            const l = localArr[dataPointIndex] ?? 0;
            const e = exportArr[dataPointIndex] ?? 0;
            const x = w?.globals?.clientX ?? 0;
            const y = w?.globals?.clientY ?? 0;

            const html = `
              <div class="l2-head">${label}</div>
              <div class="l2-row"><span><span class="l2-dot" style="background:${color}"></span>Total</span><b>${fmt(t)}</b></div>
              <div class="l2-row"><span><span class="l2-dot" style="background:#3a86ff"></span>Local</span><b>${fmt(l)}</b></div>
              <div class="l2-row"><span><span class="l2-dot" style="background:#38b000"></span>Export</span><b>${fmt(e)}</b></div>
            `;
            this._showExtTip(html, x, y);
            return '<div></div>';
          },
        },
        legend: { show: false },
      };
    };

    const singleBarOpts = (title, data, color, yMaxRaw) => {
      const yMax = padMax(yMaxRaw);

      const cats = data?.months || [];
      const vals = (data?.amounts || []).map(v => Number(v) || 0);
      const breakdown = Array.isArray(data?.breakdown) ? data.breakdown : null;

      return {
        series: [{ name: title, data: vals }],
        chart: {
          type: "bar",
          height: 280,
          toolbar: { show: false },
          fontFamily: "Inter, Roboto, sans-serif",
          animations: { enabled: true, easing: "easeinout", speed: 800 },
          events: { 
            mouseLeave: () => this._hideExtTip(),
            click: function () {
                window.open("/web#action=my_dashboard.action_l4_dashboard", "_blank");
            }
        },
        },
        plotOptions: {
          bar: {
            borderRadius: 6,
            columnWidth: "60%",
            distributed: true,
            dataLabels: { position: "top" }, // outside, on top
          },
        },
        dataLabels: {
          enabled: true,
          formatter: (val) => this.formatMillionsShort(val),
          offsetY: -14,
          style: { fontSize: "11px", fontWeight: 700, colors: ["#111"] },
        },
        stroke: { width: 1, colors: ["#fff"] },
        grid: { borderColor: "#e0e0e0", strokeDashArray: 4 },
        xaxis: {
          categories: cats,
          labels: { rotate: -45, style: { fontSize: "11px", fontWeight: 500, colors: "#333" } },
          axisTicks: { show: false },
          axisBorder: { color: "#ccc" },
        },
        yaxis: {
          min: 0,
          max: yMax,
          tickAmount: 5,
          forceNiceScale: false,
          title: { text: `Amount`, style: { fontSize: "12px", color: "#666" } },
          labels: { formatter: (val) => this.formatNumber(val), style: { fontSize: "11px", color: "#666" } },
        },
        fill: {
          type: "gradient",
          gradient: {
            shade: "light",
            type: "vertical",
            shadeIntensity: 0.3,
            gradientToColors: [color],
            inverseColors: false,
            opacityFrom: 0.6,
            opacityTo: 1,
            stops: [0, 100],
          },
        },
        tooltip: {
          shared: false,
          intersect: true,
          custom: ({ dataPointIndex, w }) => {
            const label = cats[dataPointIndex] ?? "";
            const totalHere = vals[dataPointIndex] ?? 0;
            const items = (breakdown && breakdown[dataPointIndex]) ? breakdown[dataPointIndex] : [];
            const x = w?.globals?.clientX ?? 0;
            const y = w?.globals?.clientY ?? 0;

            const rows = items.map(it => `
              <div class="l2-row">
                <span>${this._truncateProject(it.project)}</span>
                <b>${this.formatNumber(it.amount)}</b>
              </div>
            `).join("");

            const html = `
              <div class="l2-head">${label}</div>
              <div class="l2-row"><span>Total</span><b>${this.formatNumber(totalHere)}</b></div>
              ${rows || '<div class="l2-row" style="opacity:.7;">No project data</div>'}
            `;
            this._showExtTip(html, x, y);
            return '<div></div>';
          },
        },
        legend: { show: false },
      };
    };

    const areaOpts = (title, data, yMax) => {
      const months = Array.isArray(data?.months) ? data.months.map((m) => m ?? "-") : [];
      const inflow = Array.isArray(data?.inflow) ? data.inflow.map((v) => Number(v) || 0) : [];
      const outflow = Array.isArray(data?.outflow) ? data.outflow.map((v) => Number(v) || 0) : [];
      const len = Math.min(months.length, inflow.length, outflow.length);

      return {
        chart: {
          type: "area",
          height: 300,
          toolbar: { show: true },
          zoom: { enabled: true },
          events: { mouseLeave: () => this._hideExtTip() },
        },
        series: [
          { name: "Inflow", data: inflow.slice(0, len), color: "#1e90ff" },
          { name: "Outflow", data: outflow.slice(0, len), color: "#ff4d4f" },
        ],
        stroke: { curve: "smooth", width: 2 },
        fill: { type: "solid", opacity: 0.4 },
        dataLabels: { enabled: false },
        tooltip: {
          shared: true,
          intersect: false,
          y: { formatter: (val) => this.formatNumber(val) },
          custom: () => {
            this._hideExtTip();
            // IMPORTANT: ApexCharts expects a string; never return undefined.
            return '<div></div>';
          },
        },
        xaxis: {
          categories: months.slice(0, len),
          labels: { rotate: -45, style: { fontSize: "12px", colors: "#333" } },
          axisTicks: { show: false },
          axisBorder: { color: "#ccc" },
        },
        yaxis: {
          min: 0,
          max: yMax,
          tickAmount: 5,
          forceNiceScale: false,
          labels: { formatter: (val) => this.formatNumber(val), style: { fontSize: "12px", colors: "#333" } },
          title: { text: `Amount`, style: { fontSize: "12px", color: "#888" } },
        },
        legend: { position: "top", fontSize: "13px" },
        grid: { borderColor: "#e0e0e0", strokeDashArray: 4 },
      };
    };
    // ---------- /helpers ----------

    // SALES
    this._createChart(
      "totalSales",
      this.totalSalesChart.el,
      totalWithBreakdownOpts("Total Sales", sales?.total, sales?.local_sales, sales?.export_sales, "#4361ee", SALES_MAX)
    );
    this._createChart("localSales",  this.localSalesChart.el,  singleBarOpts("Local Sales",  sales?.local_sales,  "#3a86ff", SALES_MAX));
    this._createChart("exportSales", this.exportSalesChart.el, singleBarOpts("Export Sales", sales?.export_sales, "#38b000", SALES_MAX));

    // REVENUE
    this._createChart(
      "totalRevenue",
      this.totalRevenueChart.el,
      totalWithBreakdownOpts("Total Revenue", revenue?.total, revenue?.local_revenue, revenue?.export_revenue, "#6a4c93", REVENUE_MAX)
    );
    this._createChart("localRevenue",  this.localRevenueChart.el,  singleBarOpts("Local Revenue",  revenue?.local_revenue,  "#9d4edd", REVENUE_MAX));
    this._createChart("exportRevenue", this.exportRevenueChart.el, singleBarOpts("Export Revenue", revenue?.export_revenue, "#ff6b6b", REVENUE_MAX));

    // EXPENSES
    this._createChart(
      "totalExpenses",
      this.totalExpensesChart.el,
      totalWithBreakdownOpts("Total Expenses", expenses?.total, expenses?.local_expenses, expenses?.export_expenses, "#ff9f1c", EXPENSES_MAX)
    );
    this._createChart("localExpenses",  this.localExpensesChart.el,  singleBarOpts("Local Expenses",  expenses?.local_expenses,  "#ffbf69", EXPENSES_MAX));
    this._createChart("exportExpenses", this.exportExpensesChart.el, singleBarOpts("Export Expenses", expenses?.export_expenses, "#cb997e", EXPENSES_MAX));

    // CASH FLOW
    this._createChart("totalCashFlow",  this.totalCashFlowChart.el,  areaOpts("Total Cash Flow",  cash_flow?.total,             padMax(CASHFLOW_MAX)));
    this._createChart("localCashFlow",  this.localCashFlowChart.el,  areaOpts("Local Cash Flow",  cash_flow?.local_cash_flow,   padMax(CASHFLOW_MAX)));
    this._createChart("exportCashFlow", this.exportCashFlowChart.el, areaOpts("Export Cash Flow", cash_flow?.export_cash_flow,  padMax(CASHFLOW_MAX)));
  }

  _createChart(name, element, options) {
    if (!element) return;
    try {
      this.charts[name] = new ApexCharts(element, options);
      this.charts[name].render();
    } catch (error) {
      console.error(`Failed to create chart ${name}:`, error);
      this.state.error = true;
      this.state.errorMessage = _t("Failed to create one of the charts.");
    }
  }

  _destroyCharts() {
    Object.values(this.charts).forEach((chart) => {
      if (chart?.destroy) {
        try { chart.destroy(); } catch (e) { console.warn("Destroy error:", e); }
      }
    });
    this.charts = {};
    this._hideExtTip();
  }

  updateDashboard() {
    this._initDashboard();
    if (!this.state.error) this._renderCharts();
  }

  __destroy() {
    this._destroyCharts();
    if (this._extTip?.parentNode) {
      try { this._extTip.parentNode.removeChild(this._extTip); } catch {}
    }
    super.__destroy();
  }

  // Helpers
  formatCurrency(value) {
    if (value === undefined || value === null) return "0.00";
    return this.formatNumber(value);
  }

  formatNumber(value) {
    const n = Number(value);
    if (!isFinite(n)) return "0";
    return new Intl.NumberFormat(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(n);
  }

  /**
   * Short “millions” label for bar tops, placed OUTSIDE the bars.
   * Truncates to one decimal (no rounding up)
   */
  formatMillionsShort(value) {
    if (value === undefined || value === null) return "";
    const m = value / 1_000_000;
    const truncated = Math.floor(m * 10) / 10;
    const isInt = Math.abs(truncated - Math.round(truncated)) < 1e-9;

    const s = new Intl.NumberFormat(undefined, {
      minimumFractionDigits: isInt ? 0 : 1,
      maximumFractionDigits: isInt ? 0 : 1,
    }).format(truncated);

    return `${s} M`;
  }

  formatDateTime(dateTimeStr) {
    if (!dateTimeStr) return "";
    try {
      const date = new Date(dateTimeStr);
      return new Intl.DateTimeFormat(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      }).format(date);
    } catch (e) {
      return dateTimeStr;
    }
  }
}

L2Dashboard.template = "custom.l2_dashboard";
registry.category("fields").add("l2_dashboard", L2Dashboard);
