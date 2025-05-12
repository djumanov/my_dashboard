/** @odoo-module **/
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";

const { Component, useEffect, useState, useRef } = owl;

var translation = require('web.translation');
var _t = translation._t;

export class L2Dashboard extends Component {
    setup() {
        this.charts = {};  // ✅ Initialize charts

        this.state = useState({
            main_data: [],
            data: {},
            error: false,
            errorMessage: "",
        });

        useEffect(() => {
            const dashboardData = this.props.record?.data?.dashboard_data || '{}';

            let parsedData = {};
            try {
                parsedData = JSON.parse(dashboardData);
            } catch (e) {
                console.warn("Invalid dashboard JSON", e);
                this.state.error = true;
                this.state.errorMessage = _t("Dashboard data is invalid.");
                return;
            }

            this.state.main_data = parsedData;
            this._initDashboard();
            this._renderCharts();
        }, () => [this.props.record?.data?.dashboard_data]);

        // ✅ Initialize all refs
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

        loadJS("https://cdn.jsdelivr.net/npm/apexcharts");
    }

    _initDashboard() {
        const data = this.state.main_data;
        this.state.data = {
            sales: data.sales,
            revenue: data.revenue,
            expenses: data.expenses,
            cash_flow: data.cash_flow,
            company: data.company,
        };

        this.state.error = !this.state.data;
        this.state.errorMessage = this.state.error ? _t("Error loading dashboard data") : "";
    }

    _renderCharts() {
        if (this.state.error) return;

        this._destroyCharts();

        const { sales, revenue, expenses, cash_flow } = this.state.data;
        const currency = this.state.data.company?.currency || "$";

        const getChartOptions = (title, data, color) => ({
            series: [{ name: title, data: data?.amounts || [] }],
            chart: {
                type: 'bar',
                height: 280,
                toolbar: { show: false },
                fontFamily: 'Inter, Roboto, sans-serif',
                animations: {
                    enabled: true,
                    easing: 'easeinout',
                    speed: 800,
                },
            },
            plotOptions: {
                bar: {
                    borderRadius: 6,
                    columnWidth: '60%',
                    distributed: true,
                }
            },
            dataLabels: {
                enabled: false // ✅ No labels shown on top of bars
            },
            stroke: {
                width: 1,
                colors: ['#fff']
            },
            grid: {
                borderColor: '#e0e0e0',
                strokeDashArray: 4,
            },
            xaxis: {
                categories: data?.months || [],
                labels: {
                    rotate: -45,
                    style: {
                        fontSize: '11px',
                        fontWeight: 500,
                        colors: '#333',
                    }
                },
                axisTicks: { show: false },
                axisBorder: { color: '#ccc' },
            },
            yaxis: {
                title: {
                    text: `Amount (${currency})`,
                    style: { fontSize: '12px', color: '#666' }
                },
                labels: {
                    formatter: (val) => this.formatNumber(val),
                    style: { fontSize: '11px', color: '#666' }
                },
                tickAmount: 6,           // ✅ Consistent grid steps
                forceNiceScale: true     // ✅ Smooth axis scale
            },
            fill: {
                type: 'gradient',
                gradient: {
                    shade: 'light',
                    type: 'vertical',
                    shadeIntensity: 0.3,
                    gradientToColors: [color],
                    inverseColors: false,
                    opacityFrom: 0.6,
                    opacityTo: 1,
                    stops: [0, 100]
                }
            },
            tooltip: {
                theme: 'light',
                y: {
                    formatter: (val) => `${currency} ${this.formatNumber(val)}`
                }
            },
            legend: {
                show: false
            }
        });

        const getLineChartOptions = (title, data) => {
            const months = Array.isArray(data?.months) ? data.months.map(m => m ?? '-') : [];
            const inflow = Array.isArray(data?.inflow) ? data.inflow.map(v => v ?? 0) : [];
            const outflow = Array.isArray(data?.outflow) ? data.outflow.map(v => v ?? 0) : [];
          
            const length = Math.min(months.length, inflow.length, outflow.length);
          
            const safeMonths = months.slice(0, length);
            const safeInflow = inflow.slice(0, length);
            const safeOutflow = outflow.slice(0, length);
          
            return {
              series: [
                {
                  name: 'Inflow',
                  data: safeInflow
                },
                {
                  name: 'Outflow',
                  data: safeOutflow
                }
              ],
              chart: {
                type: 'line',
                height: 300,
                toolbar: { show: true },
                animations: {
                  enabled: true,
                  easing: 'easeinout',
                  speed: 600
                },
                zoom: { enabled: true }
              },
              stroke: {
                curve: 'smooth',
                width: 2  ,
                colors:['#28a745', '#dc3545']
              },
              markers: {
                size: 4,
                strokeWidth: 2,
                strokeColors: '#fff'
              },
              fill: {
                type: 'solid',
                opacity: 1
              },
              colors: ['#28a745', '#dc3545'],  // ✅ global colors are enough
              xaxis: {
                categories: safeMonths,
                labels: {
                  rotate: -45,
                  style: {
                    fontSize: '12px',
                    colors: '#333'
                  }
                },
                axisTicks: { show: false },
                axisBorder: { color: '#ccc' }
              },
              yaxis: {
                min: 0,
                forceNiceScale: true,
                labels: {
                  formatter: val => val.toLocaleString(),
                  style: {
                    fontSize: '12px',
                    colors: '#333'
                  }
                },
                title: {
                  text: `Amount (Nu.)`,
                  style: { fontSize: '1px', color: '#888' }
                }
              },
              tooltip: {
                shared: true,
                y: {
                  formatter: val => `Nu. ${val?.toLocaleString?.() ?? 0}`
                }
              },
              legend: {
                position: 'top',
                fontSize: '13px'
              },
              grid: {
                borderColor: '#e0e0e0',
                strokeDashArray: 4
              }
            };
        };
        
        this._createChart('totalSales', this.totalSalesChart.el, getChartOptions('Total Sales', sales?.total, '#4361ee'));
        this._createChart('localSales', this.localSalesChart.el, getChartOptions('Local Sales', sales?.local_sales, '#3a86ff'));
        this._createChart('exportSales', this.exportSalesChart.el, getChartOptions('Export Sales', sales?.export_sales, '#38b000'));

        this._createChart('totalRevenue', this.totalRevenueChart.el, getChartOptions('Total Revenue', revenue?.total, '#6a4c93'));
        this._createChart('localRevenue', this.localRevenueChart.el, getChartOptions('Local Revenue', revenue?.local_revenue, '#9d4edd'));
        this._createChart('exportRevenue', this.exportRevenueChart.el, getChartOptions('Export Revenue', revenue?.export_revenue, '#ff6b6b'));

        this._createChart('totalExpenses', this.totalExpensesChart.el, getChartOptions('Total Expenses', expenses?.total, '#ff9f1c'));
        this._createChart('localExpenses', this.localExpensesChart.el, getChartOptions('Local Expenses', expenses?.local_expenses, '#ffbf69'));
        this._createChart('exportExpenses', this.exportExpensesChart.el, getChartOptions('Export Expenses', expenses?.export_expenses, '#cb997e'));

        this._createChart('totalCashFlow', this.totalCashFlowChart.el, getLineChartOptions('Total Cash Flow', cash_flow?.total, '#1982c4', '#ff595e'));
        this._createChart('localCashFlow', this.localCashFlowChart.el, getLineChartOptions('Local Cash Flow', cash_flow?.local_cash_flow, '#8ac926', '#ff595e'));
        this._createChart('exportCashFlow', this.exportCashFlowChart.el, getLineChartOptions('Export Cash Flow', cash_flow?.export_cash_flow, '#00b4d8', '#ff595e'));
    }

    _createChart(name, element, options) {
        if (!element) return;
        try {
            this.charts[name] = new ApexCharts(element, options);
            this.charts[name].render();
        } catch (error) {
            console.error(`Failed to create chart ${name}:`, error);
        }
    }

    _destroyCharts() {
        Object.values(this.charts).forEach(chart => {
            if (chart?.destroy) {
                try { chart.destroy(); } catch (e) { console.warn("Destroy error:", e); }
            }
        });
        this.charts = {};
    }

    updateDashboard() {
        this._initDashboard();
        if (!this.state.error) this._renderCharts();
    }

    __destroy() {
        this._destroyCharts();
        super.__destroy();
    }

    formatCurrency(value) {
        if (value === undefined || value === null) return "0.00";
        const currency = this.state.data?.company?.currency || "$";
        return `${currency} ${this.formatNumber(value)}`;
    }

    formatNumber(value) {
        if (value === undefined || value === null) return "0.00";
        return new Intl.NumberFormat(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value);
    }

    formatDateTime(dateTimeStr) {
        if (!dateTimeStr) return "";
        try {
            const date = new Date(dateTimeStr);
            return new Intl.DateTimeFormat(undefined, {
                year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
            }).format(date);
        } catch (e) {
            return dateTimeStr;
        }
    }
}

L2Dashboard.template = 'custom.l2_dashboard';
L2Dashboard.props = {
    record: { type: Object, optional: true },
    value: { type: String, optional: true },
    readonly: { type: Boolean, optional: true },
    name: { type: String, optional: true },
    update: { type: Function, optional: true },
    decorations: { type: Object, optional: true },
    id: { type: String, optional: true },
    type: { type: String, optional: true },
    setDirty: { type: Function, optional: true },
    fieldDependencies: { type: Array, optional: true },
    required: { type: Boolean, optional: true },
    className: { type: String, optional: true },
    options: { type: Object, optional: true },
    placeholder: { type: String, optional: true },
    formatValue: { type: Function, optional: true }
};

registry.category("fields").add("l2_dashboard", L2Dashboard);
