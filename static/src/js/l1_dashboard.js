/** @odoo-module **/
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";
import { loadCSS } from "@web/core/assets";

await loadCSS("https://cdn.jsdelivr.net/npm/apexcharts/dist/apexcharts.css");

const CHART_JS_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";

const { Component, useEffect, useState, useRef } = owl;
const _t = require("web.translation")._t;

export class Dashboard extends Component {
  setup() {
    this.charts = {};

    this.state = useState({
      main_data: {},
      data: {},
      error: false,
      errorMessage: "",
      isLoading: true,
    });

    this.palette = {
      sales: "#0077b6",
      revenue: "#22c55e",
      expenses: "#ef4444",
      ebt: "#6b7280",
      inflow: "#3b82f6",
      outflow: "#f97316",
      target_achieved: "#22c55e",
      target_remaining: "#ef4444",
    };

    this._extTip = null;
    this._ensureTooltipHost();

    useEffect(
      () => {
        const dashboardData = this.props.record?.data?.dashboard_data || "{}";
        let parsed;
        try {
          parsed = JSON.parse(dashboardData);
        } catch (e) {
          this.state.error = true;
          this.state.errorMessage = _t("Dashboard data is invalid.");
          return;
        }
        this.state.main_data = parsed;
        this.state.isLoading = false;

        Promise.all([
          loadJS("https://cdn.jsdelivr.net/npm/apexcharts"),
          loadJS(CHART_JS_URL),
        ])
          .then(() => {
            this._initDashboard();
            try {
              this._renderCharts();
            } catch (error) {
              console.error("Chart render error:", error);
              this.state.error = true;
              this.state.errorMessage = _t("Failed to render charts.");
            }
          })
          .catch(() => {
            this.state.error = true;
            this.state.errorMessage = _t("Failed to load chart libraries.");
          });
      },
      () => [this.props.record?.data?.dashboard_data]
    );

    // Chart refs
    this.salesChartRef = useRef("salesChart");
    this.revenueExpensesChartRef = useRef("revenueExpensesChart");
    this.cashflowChartRef = useRef("cashflowChart");
    this.targetBarChartRef = useRef("targetBarChart");
  }

  // ---------- external tooltip host (Apex charts) ----------
  _ensureTooltipHost() {
    if (!document.getElementById("l1-exttip-style")) {
      const css = document.createElement("style");
      css.id = "l1-exttip-style";
      css.textContent = `
        .l1-exttip {
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
        .l1-exttip.show { opacity: 1; transform: translate3d(0, 0, 0); }
        .l1-exttip .l1-head { font-weight: 600; margin-bottom: 6px; }
        .l1-exttip .l1-row { display:flex; justify-content:space-between; gap:12px; margin-top:4px; white-space: nowrap; }
        .l1-exttip .l1-dot { display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px; }
      `;
      document.head.appendChild(css);
    }
    if (!this._extTip) {
      const div = document.createElement("div");
      div.className = "l1-exttip";
      document.body.appendChild(div);
      this._extTip = div;
    }
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
    this._extTip.style.top = `${y}px`;
    this._extTip.classList.add("show");
  }

  _hideExtTip() {
    if (this._extTip) this._extTip.classList.remove("show");
  }
  // ----------------------------------------------------------

  _initDashboard() {
    const data = this.state.main_data || {};
    this.state.data = {
      filter_data: data.filter || {},
      sales: data.sales || {},
      revenue_expenses: data.revenue_expenses || {},
      cashflow: data.cashflow || {},
      overview: data.overview || {},
    };
  }

  _renderCharts() {
    if (this.state.error) return;
    this._destroyCharts();

    if (this.salesChartRef.el) {
      this._renderSalesChart();
    }

    if (this.revenueExpensesChartRef.el) {
      this._renderRevenueExpensesChart();
    }

    if (this.cashflowChartRef.el) {
      this._renderCashflowChart();
    }

    if (this.targetBarChartRef.el) {
      this._renderTargetBarChart();
    }
  }

  _navigateToL2Dashboard() {
    window.location.href = "/web#action=my_dashboard.action_l2_dashboard";
  }

  _renderSalesChart() {
    const element = this.salesChartRef.el;
    if (!element) return;

    const salesData = this.state.data.sales?.monthly_sales || 
      [12500, 18700, 22300, 19800, 25600, 28900, 31200, 29500, 33800, 36400, 38700, 42100];
    
    const localData = this.state.data.sales?.monthly_local || [];
    const exportData = this.state.data.sales?.monthly_export || [];
    
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const year = this.state.data.filter_data?.year || new Date().getFullYear();
    const length = this._clampArrayLength(salesData, localData, exportData);

    const yMax = this._padMax(Math.max(...salesData));

    const options = {
      series: [{ name: 'Total Sales', data: salesData.slice(0, length) }],
      chart: {
        type: 'bar',
        height: 380,
        toolbar: { show: false },
        fontFamily: "Inter, Roboto, sans-serif",
        animations: { enabled: true, easing: "easeinout", speed: 800 },
        events: {
          click: () => this._navigateToL2Dashboard(),
          mouseLeave: () => this._hideExtTip(),
        },
      },
      colors: [this.palette.sales],
      plotOptions: {
        bar: {
          borderRadius: 6,
          columnWidth: "60%",
          distributed: false,
          dataLabels: { position: "top" },
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
        categories: months.slice(0, length),
        labels: { rotate: -45, style: { fontSize: "11px", fontWeight: 500, colors: "#333" } },
        axisTicks: { show: false },
        axisBorder: { color: "#ccc" },
      },
      yaxis: {
        min: 0,
        max: yMax,
        tickAmount: 5,
        labels: { show: false },
        title: { text: undefined },
      },
      fill: { type: "solid", opacity: 0.9 },
      tooltip: {
        shared: false,
        intersect: true,
        custom: ({ dataPointIndex, w }) => {
          const label = months[dataPointIndex] ?? "";
          const total = salesData[dataPointIndex] ?? 0;
          const local = localData[dataPointIndex] || 0;
          const exportVal = exportData[dataPointIndex] || 0;
          const x = w?.globals?.clientX ?? 0;
          const y = w?.globals?.clientY ?? 0;

          const html = `
            <div class="l1-head">${label} ${year}</div>
            <div class="l1-row"><span><span class="l1-dot" style="background:${this.palette.sales}"></span>Total</span><b>${this.formatNumber(total)}</b></div>
            ${(local || exportVal) ? `
              <div style="margin: 6px 0; border-top: 1px solid rgba(0,0,0,.1);"></div>
              <div class="l1-row"><span>Local</span><b>${this.formatNumber(local)}</b></div>
              <div class="l1-row"><span>Export</span><b>${this.formatNumber(exportVal)}</b></div>
            ` : ''}
          `;
          this._showExtTip(html, x, y);
          return '<div></div>';
        },
      },
      legend: { show: false },
    };

    this._createChart("salesChart", element, options);
  }

  _renderRevenueExpensesChart() {
    const element = this.revenueExpensesChartRef.el;
    if (!element) return;

    const revenueData = this.state.data.revenue_expenses?.monthly_revenue || 
      [45000, 52000, 48500, 61000, 58000, 67000, 72000, 69500, 78000, 82000, 88000, 95000];
    const expensesData = this.state.data.revenue_expenses?.monthly_expenses || 
      [32000, 35000, 33500, 38000, 36500, 41000, 43000, 42000, 46500, 48000, 51000, 53500];
    
    let ebtData = this.state.data.revenue_expenses?.monthly_ebt;
    
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const year = this.state.data.filter_data?.year || new Date().getFullYear();
    const length = this._clampArrayLength(revenueData, expensesData);

    if (!Array.isArray(ebtData) || ebtData.length !== length) {
      ebtData = Array.from({ length }, (_, i) => {
        const r = Number(revenueData[i] ?? 0);
        const e = Number(expensesData[i] ?? 0);
        return r - e;
      });
    }

    let canvas = element.tagName === "CANVAS" ? element : element.querySelector("canvas");
    if (!canvas) {
      canvas = document.createElement("canvas");
      element.innerHTML = "";
      element.appendChild(canvas);
    }
    element.style.height = "380px";
    canvas.height = 380;

    if (element._chartjs?.destroy) {
      try { element._chartjs.destroy(); } catch {}
    }

    const ctx = canvas.getContext("2d");

    element._chartjs = new Chart(ctx, {
      type: "line",
      data: {
        labels: months.slice(0, length),
        datasets: [
          {
            label: "Revenue",
            data: revenueData.slice(0, length),
            borderColor: this.palette.revenue,
            borderWidth: 4,
            fill: false,
            tension: 0.4,
            pointRadius: 5,
            pointHoverRadius: 8,
            pointBackgroundColor: this.palette.revenue,
            pointBorderColor: "#fff",
            pointBorderWidth: 2,
          },
          {
            label: "Expenses",
            data: expensesData.slice(0, length),
            borderColor: this.palette.expenses,
            borderWidth: 4,
            fill: false,
            tension: 0.4,
            pointRadius: 5,
            pointHoverRadius: 8,
            pointBackgroundColor: this.palette.expenses,
            pointBorderColor: "#fff",
            pointBorderWidth: 2,
          },
          {
            label: "EBT",
            data: ebtData.slice(0, length),
            borderColor: this.palette.ebt,
            borderWidth: 4,
            fill: false,
            tension: 0.4,
            pointRadius: 5,
            pointHoverRadius: 8,
            pointBackgroundColor: this.palette.ebt,
            pointBorderColor: "#fff",
            pointBorderWidth: 2,
          },
        ],
      },
      options: {
        onClick: () => this._navigateToL2Dashboard(),
        onHover: (evt, elements, chart) => {
          chart.canvas.style.cursor = elements.length ? 'pointer' : 'default';
        },
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 8, right: 12, bottom: 8, left: 12 } },
        interaction: { intersect: false, mode: "index" },
        plugins: {
          title: { display: false },
          legend: {
            display: true,
            position: "top",
            align: "end",
            labels: {
              usePointStyle: true,
              pointStyle: "circle",
              padding: 12,
              font: { size: 13, weight: "700", family: "'Inter', sans-serif" },
              color: "#1e293b",
            },
          },
          tooltip: {
            enabled: true,
            backgroundColor: "rgba(30,41,59,0.95)",
            titleColor: "#fff",
            bodyColor: "#fff",
            padding: 14,
            callbacks: {
              title: (ctx) => `${ctx[0].label} ${year}`,
              label: (ctx) => `${ctx.dataset.label}: ${this.formatNumber(ctx.parsed.y)}`,
              afterBody: (ctx) => {
                const rev = ctx.find(c => c.dataset.label === 'Revenue')?.parsed.y ?? 0;
                const exp = ctx.find(c => c.dataset.label === 'Expenses')?.parsed.y ?? 0;
                
                if (rev || exp) {
                  const profit = rev - exp;
                  const margin = rev ? ((profit / rev) * 100).toFixed(1) : "0.0";
                  return ["", "Net Profit: " + this.formatNumber(profit), "Profit Margin: " + margin + "%"];
                }
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false, drawBorder: false },
            ticks: { font: { size: 12, weight: "600", family: "'Inter', sans-serif" }, color: "#64748b" },
          },
          y: {
            ticks: { display: false },
            grid: { color: "rgba(224,224,224,0.5)", borderDash: [4,4], drawBorder: false },
          },
        },
      },
      plugins: [{
        id: 'customDataLabels',
        afterDatasetsDraw: (chart) => {
          const ctx = chart.ctx;
          chart.data.datasets.forEach((dataset, datasetIndex) => {
            const meta = chart.getDatasetMeta(datasetIndex);
            if (!meta.hidden) {
              meta.data.forEach((bar, index) => {
                const value = dataset.data[index];
                const displayValue = this.formatMillionsShort(value);

                ctx.fillStyle = '#333';
                ctx.font = '700 11px Inter, sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'bottom';
                ctx.fillText(displayValue, bar.x, bar.y - 8);
              });
            }
          });
        }
      }]
    });
  }

  _renderCashflowChart() {
    const element = this.cashflowChartRef.el;
    if (!element) return;

    const inflowsData = this.state.data.cashflow?.monthly_inflows || 
      [55000, 62000, 58500, 71000, 68000, 77000, 82000, 79500, 88000, 92000, 98000, 105000];
    const outflowsData = this.state.data.cashflow?.monthly_outflows || 
      [42000, 45000, 43500, 48000, 46500, 51000, 53000, 52000, 56500, 58000, 61000, 63500];

    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const year = this.state.data.filter_data?.year || new Date().getFullYear();
    const length = this._clampArrayLength(inflowsData, outflowsData);

    let canvas = element.tagName === "CANVAS" ? element : element.querySelector("canvas");
    if (!canvas) {
      canvas = document.createElement("canvas");
      element.innerHTML = "";
      element.appendChild(canvas);
    }
    element.style.height = "380px";
    canvas.height = 380;

    if (element._chartjs?.destroy) {
      try { element._chartjs.destroy(); } catch {}
    }

    const ctx = canvas.getContext("2d");

    element._chartjs = new Chart(ctx, {
      type: "line",
      data: {
        labels: months.slice(0, length),
        datasets: [
          {
            label: "Cash Inflows",
            data: inflowsData.slice(0, length),
            borderColor: this.palette.inflow,
            borderWidth: 4,
            fill: false,
            tension: 0.4,
            pointRadius: 5,
            pointHoverRadius: 8,
            pointBackgroundColor: this.palette.inflow,
            pointBorderColor: "#fff",
            pointBorderWidth: 2,
          },
          {
            label: "Cash Outflows",
            data: outflowsData.slice(0, length),
            borderColor: this.palette.outflow,
            borderWidth: 4,
            fill: false,
            tension: 0.4,
            pointRadius: 5,
            pointHoverRadius: 8,
            pointBackgroundColor: this.palette.outflow,
            pointBorderColor: "#fff",
            pointBorderWidth: 2,
          },
        ],
      },
      options: {
        onClick: () => this._navigateToL2Dashboard(),
        onHover: (evt, elements, chart) => {
          chart.canvas.style.cursor = elements.length ? 'pointer' : 'default';
        },
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 8, right: 12, bottom: 8, left: 12 } },
        interaction: { intersect: false, mode: "index" },
        plugins: {
          title: { display: false },
          legend: {
            display: true,
            position: "top",
            align: "end",
            labels: {
              usePointStyle: true,
              pointStyle: "circle",
              padding: 12,
              font: { size: 13, weight: "700", family: "'Inter', sans-serif" },
              color: "#1e293b",
            },
          },
          tooltip: {
            enabled: true,
            backgroundColor: "rgba(30,41,59,0.95)",
            titleColor: "#fff",
            bodyColor: "#fff",
            padding: 14,
            callbacks: {
              title: (ctx) => `${ctx[0].label} ${year}`,
              label: (ctx) => `${ctx.dataset.label}: ${this.formatNumber(ctx.parsed.y)}`,
              afterBody: (ctx) => {
                if (ctx.length === 2) {
                  const infl = ctx[0].parsed.y || 0;
                  const out = ctx[1].parsed.y || 0;
                  const net = infl - out;
                  const ratio = infl ? ((net / infl) * 100).toFixed(1) : "0.0";
                  return ["", `Net Cash Flow: ${this.formatNumber(net)}`, `Cash Flow Ratio: ${ratio}%`];
                }
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false, drawBorder: false },
            ticks: { font: { size: 12, weight: "600", family: "'Inter', sans-serif" }, color: "#64748b" },
          },
          y: {
            ticks: { display: false },
            grid: { color: "rgba(224,224,224,0.5)", borderDash: [4,4], drawBorder: false },
          },
        },
      },
      plugins: [{
        id: 'customDataLabels',
        afterDatasetsDraw: (chart) => {
          const ctx = chart.ctx;
          chart.data.datasets.forEach((dataset, datasetIndex) => {
            const meta = chart.getDatasetMeta(datasetIndex);
            if (!meta.hidden) {
              meta.data.forEach((bar, index) => {
                const value = dataset.data[index];
                const displayValue = this.formatMillionsShort(value);

                ctx.fillStyle = '#333';
                ctx.font = '700 11px Inter, sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'bottom';
                ctx.fillText(displayValue, bar.x, bar.y - 8);
              });
            }
          });
        }
      }]
    });
  }

  _renderTargetBarChart() {
    const element = this.targetBarChartRef.el;
    if (!element) return;

    let canvas = element.tagName === "CANVAS" ? element : element.querySelector("canvas");
    if (!canvas) {
      canvas = document.createElement("canvas");
      element.innerHTML = "";
      element.appendChild(canvas);
    }
    element.style.height = "380px";
    canvas.height = 380;

    if (element._chartjs?.destroy) {
      try { element._chartjs.destroy(); } catch {}
    }

    const ov = this.state.data.overview || {};
    const target = this._toNumber(ov.sales_target);
    const achieved = this._toNumber(ov.total_achieved);
    const safeTarget = Math.max(target, 0);
    const safeAch = Math.min(Math.max(achieved, 0), safeTarget || achieved);
    const remaining = Math.max(safeTarget - safeAch, 0);

    const pctAch = safeTarget ? (safeAch / safeTarget) * 100 : this._toNumber(ov.ratio);
    const pctRem = 100 - pctAch;

    const ctx = canvas.getContext("2d");

    element._chartjs = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: ['Target'],
        datasets: [
          {
            label: 'Achieved',
            data: [safeAch],
            backgroundColor: this.palette.target_achieved,
            borderColor: '#16a34a',
            borderWidth: 2,
            stack: 'stack1',
            borderSkipped: false,
            barPercentage: 1.0,
            categoryPercentage: 1.0,
          },
          {
            label: 'Unachieved',
            data: [remaining],
            backgroundColor: this.palette.target_remaining,
            borderColor: '#dc2626',
            borderWidth: 2,
            stack: 'stack1',
            borderSkipped: false,
            barPercentage: 1.0,
            categoryPercentage: 1.0,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: { padding: { top: 10, right: 10, bottom: 10, left: 10 } },
        plugins: {
          legend: { display: false },
          title: { display: false },
          tooltip: {
            enabled: false
          },
        },
        interaction: { mode: null },
        hover: {
            mode: null
        },
        scales: {
          x: { 
            stacked: true, 
            grid: { display: false }, 
            ticks: { display: false }, 
            border: { display: false } 
          },
          y: { 
            stacked: true, 
            beginAtZero: true, 
            grid: { color: 'rgba(148,163,184,0.08)' }, 
            ticks: { display: false }, 
            border: { display: false } 
          },
        },
      },
      plugins: [{
        id: 'segmentLabels',
        afterDatasetsDraw: (chart) => {
          const { ctx, chartArea } = chart;
          const metaAch = chart.getDatasetMeta(0);
          const metaRem = chart.getDatasetMeta(1);
          if (!metaAch?.data?.[0] || !metaRem?.data?.[0]) return;

          const barAch = metaAch.data[0];
          const barRem = metaRem.data[0];

          ctx.save();
          ctx.font = '700 13px Inter, sans-serif';
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';

          const achMidY = (barAch.y + barAch.baseY) / 2;
          ctx.fillStyle = '#ffffff';
          ctx.fillText(`${pctAch.toFixed(2)}%`, barAch.x, achMidY);

          if (remaining > 0 && Math.abs(barRem.y - barRem.baseY) > 20) {
            const remMidY = (barRem.y + barRem.baseY) / 2;
            ctx.fillStyle = '#ffffff';
            ctx.fillText(`${pctRem.toFixed(2)}%`, barRem.x, remMidY);
          }

          ctx.font = '700 24px Inter, sans-serif';
          ctx.fillStyle = '#16a34a';
          const midY = (chartArea.top + chartArea.bottom) / 2;
          ctx.fillText(`${pctAch.toFixed(2)}%`, (chartArea.left + chartArea.right) / 2, midY);
          ctx.restore();
        }
      }]
    });
  }

  _createChart(name, element, options) {
    if (!element) return;
    try {
      this.charts[name] = new ApexCharts(element, options);
      this.charts[name].render();
    } catch (error) {
      console.error("Failed to create chart:", error);
      this.state.error = true;
      this.state.errorMessage = _t("Failed to create one of the charts.");
    }
  }

  _destroyCharts() {
    Object.values(this.charts).forEach((chart) => {
      if (chart?.destroy) {
        try { chart.destroy(); } catch {}
      }
    });
    this.charts = {};
    this._hideExtTip();
  }

  _toNumber(v) {
    if (typeof v === 'number') return v;
    const s = String(v ?? '').replace(/[^\d.-]/g, '');
    const n = Number(s);
    return Number.isFinite(n) ? n : 0;
  }

  _clampArrayLength(...arrays) {
    const validLengths = arrays
      .filter(arr => Array.isArray(arr) && arr.length > 0)
      .map(arr => arr.length);
    return validLengths.length > 0 ? Math.max(...validLengths, 12) : 12;
  }

  _padMax(value) {
    const num = Number(value) || 0;
    return num > 0 ? Math.ceil(num * 1.15) : 100;
  }

  formatNumber(value) {
    const n = Number(value);
    if (!isFinite(n)) return "0";
    return new Intl.NumberFormat(undefined, {
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(n);
  }

  formatMillionsShort(value) {
    if (value === undefined || value === null) return "";
    const m = value / 1_000_000;
    const truncated = Math.floor(m * 10) / 10;
    const isInt = Math.abs(truncated - Math.round(truncated)) < 1e-9;
    const s = new Intl.NumberFormat(undefined, {
      minimumFractionDigits: isInt ? 0 : 1,
      maximumFractionDigits: isInt ? 0 : 1,
    }).format(truncated);
    if (!s) return "";
    if (s === "0") return "0";
    return `${s} M`;
  }

  __destroy() {
    this._destroyCharts();
    if (this._extTip?.parentNode) {
      try { this._extTip.parentNode.removeChild(this._extTip); } catch {}
    }
    super.__destroy();
  }

  willUnmount() {
    this.__destroy();
  }
}

Dashboard.template = 'custom.l1_dashboard_demo';
registry.category("fields").add("l1_dashboard", Dashboard);
