/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";

export class L2Dashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.rpc = useService("rpc");
        this.notification = useService("notification");

        // Chart references
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

        this.charts = {};

        this.state = useState({
            isLoading: true,
            error: null,
            data: {
                sales: {
                    total: { months: [], amounts: [], sum: 0 },
                    local_sales: { months: [], amounts: [], sum: 0 },
                    export_sales: { months: [], amounts: [], sum: 0 }
                },
                revenue: {
                    total: { months: [], amounts: [], sum: 0 },
                    local_revenue: { months: [], amounts: [], sum: 0 },
                    export_revenue: { months: [], amounts: [], sum: 0 }
                },
                expenses: {
                    total: { months: [], amounts: [], sum: 0 },
                    local_expenses: { months: [], amounts: [], sum: 0 },
                    export_expenses: { months: [], amounts: [], sum: 0 }
                },
                cash_flow: {
                    total: { months: [], inflow: [], outflow: [], sum: 0 },
                    local_cash_flow: { months: [], inflow: [], outflow: [], sum: 0 },
                    export_cash_flow: { months: [], inflow: [], outflow: [], sum: 0 }
                },
                company: { currency: "$", name: "" },
                last_update: null
            },
            selectedYear: new Date().getFullYear().toString()
        });

        onWillStart(async () => {
            try {
                await loadJS("https://cdn.jsdelivr.net/npm/apexcharts");
                await this._initDashboard();
            } catch (error) {
                this._handleError(error);
            }
        });

        onMounted(() => {
            if (!this.state.isLoading && !this.state.error) {
                setTimeout(() => this._renderCharts(), 100);
            }
        });
    }

    async _initDashboard() {
        this.state.isLoading = true;
        this.state.error = null;

        try {
            let dashboardData = null;

            if (this.props.value) {
                try {
                    dashboardData = JSON.parse(this.props.value);
                } catch (e) {
                    console.warn("Failed to parse dashboard data from record", e);
                }
            }

            if (!dashboardData) {
                const recordYear = this.props.record?.data?.year || new Date().getFullYear().toString();
                const result = await this.orm.call('l2.dashboard', 'get_dashboard_data_json', [recordYear]);

                try {
                    dashboardData = JSON.parse(result);
                } catch (e) {
                    throw new Error("Invalid data received from server: " + e.message);
                }
            }

            if (!dashboardData || typeof dashboardData !== 'object') {
                throw new Error("Invalid dashboard data format");
            }

            this._validateAndSanitizeData(dashboardData);
            this.state.data = dashboardData;
            this.state.selectedYear = dashboardData.filters?.year?.toString() || new Date().getFullYear().toString();
            this.state.isLoading = false;
        } catch (error) {
            this._handleError(error);
        }
    }

    _validateAndSanitizeData(data) {
        if (!data.sales) data.sales = {};
        if (!data.sales.total) data.sales.total = { months: [], amounts: [], sum: 0 };
        if (!data.sales.local_sales) data.sales.local_sales = { months: [], amounts: [], sum: 0 };
        if (!data.sales.export_sales) data.sales.export_sales = { months: [], amounts: [], sum: 0 };

        if (!data.revenue) data.revenue = {};
        if (!data.revenue.total) data.revenue.total = { months: [], amounts: [], sum: 0 };
        if (!data.revenue.local_revenue) data.revenue.local_revenue = { months: [], amounts: [], sum: 0 };
        if (!data.revenue.export_revenue) data.revenue.export_revenue = { months: [], amounts: [], sum: 0 };

        if (!data.expenses) data.expenses = {};
        if (!data.expenses.total) data.expenses.total = { months: [], amounts: [], sum: 0 };
        if (!data.expenses.local_expenses) data.expenses.local_expenses = { months: [], amounts: [], sum: 0 };
        if (!data.expenses.export_expenses) data.expenses.export_expenses = { months: [], amounts: [], sum: 0 };

        if (!data.cash_flow) data.cash_flow = {};
        if (!data.cash_flow.total) data.cash_flow.total = { months: [], inflow: [], outflow: [], sum: 0 };
        if (!data.cash_flow.local_cash_flow) data.cash_flow.local_cash_flow = { months: [], inflow: [], outflow: [], sum: 0 };
        if (!data.cash_flow.export_cash_flow) data.cash_flow.export_cash_flow = { months: [], inflow: [], outflow: [], sum: 0 };

        if (!data.company) data.company = { currency: "$", name: "" };

        return data;
    }

    _handleError(error) {
        console.error("Dashboard error:", error);
        this.state.isLoading = false;
        this.state.error = error.message || "Failed to load dashboard data";
        this.notification.add(this.state.error, {
            type: "danger",
            title: "Dashboard Error",
            sticky: true
        });
    }

    _renderCharts() {
        if (!window.ApexCharts) {
            console.error("ApexCharts library not loaded");
            this.state.error = "Chart library not loaded";
            return;
        }

        this._destroyCharts();

        const { sales, revenue, expenses, cash_flow } = this.state.data;
        const currency = this.state.data.company?.currency || "$";

        const getChartOptions = (title, data, color) => ({
            series: [{ name: title, data: data?.amounts || [] }],
            chart: { type: 'bar', height: 300, toolbar: { show: false }, fontFamily: 'Roboto' },
            plotOptions: { bar: { borderRadius: 4, columnWidth: '70%' } },
            dataLabels: { enabled: false },
            stroke: { width: 2 },
            grid: { row: { colors: ['#f3f3f3', 'transparent'], opacity: 0.2 } },
            xaxis: { categories: data?.months || [], labels: { rotate: -45, style: { fontSize: '10px' } } },
            yaxis: { title: { text: `Amount (${currency})` }, labels: { formatter: value => this.formatNumber(value) } },
            fill: { colors: [color] },
            tooltip: { y: { formatter: value => `${currency} ${this.formatNumber(value)}` } }
        });

        const getLineChartOptions = (title, data, color1, color2) => ({
            series: [
                { name: "Inflow", data: data?.inflow || [] },
                { name: "Outflow", data: data?.outflow || [] }
            ],
            chart: { type: 'line', height: 300, toolbar: { show: false }, fontFamily: 'Roboto' },
            stroke: { width: 3, curve: 'smooth' },
            markers: { size: 4 },
            xaxis: { categories: data?.months || [], labels: { rotate: -45, style: { fontSize: '10px' } } },
            yaxis: { title: { text: `Amount (${currency})` }, labels: { formatter: val => this.formatNumber(val) } },
            colors: [color1, color2],
            tooltip: { y: { formatter: val => `${currency} ${this.formatNumber(val)}` } },
            legend: { position: 'top', horizontalAlign: 'center' }
        });

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

    async updateDashboard() {
        await this._initDashboard();
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
    // Original props
    record: { type: Object, optional: true },
    value: { type: String, optional: true },
    readonly: { type: Boolean, optional: true },
    name: { type: String, optional: true },
    
    // Additional required field props from standard Odoo fields
    update: { type: Function, optional: true },
    decorations: { type: Object, optional: true },
    id: { type: String, optional: true },
    type: { type: String, optional: true },
    setDirty: { type: Function, optional: true },
    
    // Additional standard Odoo field props that might be passed
    fieldDependencies: { type: Array, optional: true },
    required: { type: Boolean, optional: true },
    className: { type: String, optional: true },
    options: { type: Object, optional: true },
    placeholder: { type: String, optional: true },
    formatValue: { type: Function, optional: true }
};

registry.category("fields").add("l2_dashboard", L2Dashboard);