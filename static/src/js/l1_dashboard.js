/** @odoo-module **/
import { registry } from "@web/core/registry";
import { loadJS } from "@web/core/assets";

const CHART_JS_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";

const { Component, useEffect, useState, useRef } = owl;
const _t = require("web.translation")._t;

export class Dashboard extends Component {
    static template = 'custom.l1_dashboard_demo'
    
    setup() {
        super.setup();
        
        this.charts = {};
        
        this.state = useState({
            main_data: {},
            data: {},
            error: false,
            errorMessage: "",
            isLoading: true
        });

        // Chart refs
        this.salesChartRef = useRef("salesChart");
        this.revenueExpensesChartRef = useRef("revenueExpensesChart");
        this.cashflowChartRef = useRef("cashflowChart");
        this.targetBarChartRef = useRef("targetBarChart");

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

                loadJS(CHART_JS_URL)
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
                        this.state.errorMessage = _t("Failed to load Chart.js library.");
                    });
            },
            () => [this.props.record?.data?.dashboard_data]
        );
    }

    _initDashboard() {
        const data = this.state.main_data || {};
        this.state.data = {
            filter_data: data.filter || {},
            sales: data.sales || {},
            revenue_expenses: data.revenue_expenses || {},
            cashflow: data.cashflow || {}
        };
    }

    _renderCharts() {
        if (this.state.error || typeof Chart === 'undefined') {
            console.error('Chart.js not loaded or error state');
            return;
        }

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

    _toNumber(v) {
        if (typeof v === 'number') return v;
        const s = String(v ?? '').replace(/[^\d.-]/g, '');
        const n = Number(s);
        return Number.isFinite(n) ? n : 0;
    }

    _getCanvasContext(element) {
        if (!element) return null;
        
        if (element.tagName === 'CANVAS') {
            const parent = element.parentElement;
            if (parent) {
                element.style.width = '100%';
                element.style.height = '100%';
            }
            return element.getContext('2d');
        }
        
        let canvas = element.querySelector('canvas');
        if (!canvas) {
            canvas = document.createElement('canvas');
            element.innerHTML = '';
            element.appendChild(canvas);
        }
        
        // Set canvas dimensions from parent
        const parentHeight = element.clientHeight || 400;
        const parentWidth = element.clientWidth || element.offsetWidth;
        
        canvas.style.width = '100%';
        canvas.style.height = '100%';
        canvas.style.display = 'block';
        canvas.width = parentWidth;
        canvas.height = parentHeight;
        
        return canvas.getContext('2d');
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

    _navigateToL2Dashboard() {
        window.location.href = "/web#action=my_dashboard.action_l2_dashboard";
    }

    _renderSalesChart() {
        const ctx = this._getCanvasContext(this.salesChartRef.el);
        if (!ctx) return;

        const salesData = this.state.data.sales?.monthly_sales || 
            [12500, 18700, 22300, 19800, 25600, 28900, 31200, 29500, 33800, 36400, 38700, 42100];
        
        const localData = this.state.data.sales?.monthly_local || [];
        const exportData = this.state.data.sales?.monthly_export || [];
        
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const year = this.state.data.filter_data?.year || new Date().getFullYear();
        const length = this._clampArrayLength(salesData, localData, exportData);

        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(99, 102, 241, 0.9)');
        gradient.addColorStop(1, 'rgba(99, 102, 241, 0.3)');

        this.charts.salesChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: months.slice(0, length),
                datasets: [{
                    label: 'Total Sales',
                    data: salesData.slice(0, length),
                    backgroundColor: gradient,
                    borderColor: '#6366f1',
                    borderWidth: 2,
                    borderRadius: 10,
                    hoverBackgroundColor: '#4f46e5',
                    hoverBorderColor: '#4338ca',
                    maxBarThickness: 50,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: () => this._navigateToL2Dashboard(),
                onHover: (evt, elements, chart) => {
                    chart.canvas.style.cursor = elements.length ? 'pointer' : 'default';
                },
                layout: {
                    padding: { top: 10, right: 20, bottom: 10, left: 10 }
                },
                interaction: { intersect: true, mode: 'index' },
                plugins: {
                    legend: { display: false },
                    title: {
                        display: true,
                        text: 'Monthly Sales Performance',
                        font: { size: 18, weight: '700', family: "'Inter', -apple-system, sans-serif" },
                        color: '#1e293b',
                        padding: { top: 5, bottom: 25 }
                    },
                    tooltip: {
                        enabled: true,
                        backgroundColor: 'rgba(30, 41, 59, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: '#6366f1',
                        borderWidth: 2,
                        padding: 14,
                        displayColors: true,
                        callbacks: {
                            title: (ctx) => `${ctx[0].label} ${year}`,
                            label: (ctx) => 'Total: ' + this._formatNumber(ctx.parsed.y),
                            afterBody: (ctx) => {
                                const idx = ctx[0].dataIndex;
                                const local = localData[idx] || 0;
                                const exportVal = exportData[idx] || 0;
                                if (local || exportVal) {
                                    return [
                                        '',
                                        '━━━━━━━━━━━━━━━━━',
                                        'Local: ' + this._formatNumber(local),
                                        'Export: ' + this._formatNumber(exportVal)
                                    ];
                                }
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false, drawBorder: false },
                        ticks: {
                            font: { size: 13, weight: '600', family: "'Inter', sans-serif" },
                            color: '#64748b',
                            padding: 12
                        }
                    },
                    y: {
                        beginAtZero: true,
                        max: this._padMax(Math.max(...salesData)),
                        grid: { color: 'rgba(148, 163, 184, 0.1)', drawBorder: false, lineWidth: 1.5 },
                        border: { display: false },
                        ticks: { display: false }
                    }
                }
            },
            plugins: [{
                id: 'customDataLabels',
                afterDatasetsDraw: (chart) => {
                    const ctx = chart.ctx;
                    const dataset = chart.data.datasets[0];
                    const meta = chart.getDatasetMeta(0);
                    
                    if (!meta.hidden) {
                        meta.data.forEach((bar, index) => {
                            const value = dataset.data[index];
                            const displayValue = this._formatShort(value);
                            const textWidth = ctx.measureText(displayValue).width;

                            ctx.fillStyle = 'rgba(99, 102, 241, 0.95)';
                            ctx.beginPath();
                            ctx.roundRect(bar.x - textWidth / 2 - 8, bar.y - 28, textWidth + 16, 22, 6);
                            ctx.fill();

                            ctx.fillStyle = '#fff';
                            ctx.font = '700 11px Inter, sans-serif';
                            ctx.textAlign = 'center';
                            ctx.textBaseline = 'middle';
                            ctx.fillText(displayValue, bar.x, bar.y - 17);
                        });
                    }
                }
            }]
        });
    }

    _renderRevenueExpensesChart() {
        const ctx = this._getCanvasContext(this.revenueExpensesChartRef.el);
        if (!ctx) return;

        const revenueData = this.state.data.revenue_expenses?.monthly_revenue || 
            [45000, 52000, 48500, 61000, 58000, 67000, 72000, 69500, 78000, 82000, 88000, 95000];
        const expensesData = this.state.data.revenue_expenses?.monthly_expenses || 
            [32000, 35000, 33500, 38000, 36500, 41000, 43000, 42000, 46500, 48000, 51000, 53500];
        
        // EBT (Earnings Before Tax) - kulrang line
        let ebtData = this.state.data.revenue_expenses?.monthly_ebt;
        
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const year = this.state.data.filter_data?.year || new Date().getFullYear();
        const length = this._clampArrayLength(revenueData, expensesData);

        // Agar EBT ma'lumot bo'lmasa yoki noto'g'ri bo'lsa, Revenue - Expenses dan hisoblash
        if (!Array.isArray(ebtData) || ebtData.length !== length) {
            ebtData = Array.from({ length }, (_, i) => {
                const r = Number(revenueData[i] ?? 0);
                const e = Number(expensesData[i] ?? 0);
                return r - e;
            });
        }

        this.charts.revenueExpensesChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: months.slice(0, length),
                datasets: [
                    {
                        label: 'Revenue',
                        data: revenueData.slice(0, length),
                        borderColor: '#22c55e',
                        backgroundColor: 'transparent',
                        borderWidth: 4,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 6,
                        pointHoverRadius: 10,
                        pointBackgroundColor: '#22c55e',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 3,
                    },
                    {
                        label: 'Expenses',
                        data: expensesData.slice(0, length),
                        borderColor: '#ef4444',
                        backgroundColor: 'transparent',
                        borderWidth: 4,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 6,
                        pointHoverRadius: 10,
                        pointBackgroundColor: '#ef4444',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 3,
                    },
                    {
                        label: 'EBT',
                        data: ebtData.slice(0, length),
                        borderColor: '#6b7280',
                        backgroundColor: 'transparent',
                        borderWidth: 4,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 6,
                        pointHoverRadius: 10,
                        pointBackgroundColor: '#6b7280',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 3,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: { top: 10, right: 20, bottom: 10, left: 10 }
                },
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        align: 'end',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'circle',
                            padding: 20,
                            font: { size: 14, weight: '700', family: "'Inter', sans-serif" },
                            color: '#1e293b',
                            boxWidth: 10,
                            boxHeight: 10
                        }
                    },
                    title: {
                        display: true,
                        text: 'Revenue, Expenses and EBT',
                        font: { size: 18, weight: '700', family: "'Inter', -apple-system, sans-serif" },
                        color: '#1e293b',
                        padding: { top: 5, bottom: 10 }
                    },
                    tooltip: {
                        enabled: true,
                        backgroundColor: 'rgba(30, 41, 59, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: 'rgba(148, 163, 184, 0.3)',
                        borderWidth: 2,
                        padding: 18,
                        boxPadding: 8,
                        usePointStyle: true,
                        callbacks: {
                            title: (ctx) => ctx[0].label + ` ${year}`,
                            label: (ctx) => ctx.dataset.label + ': ' + this._formatNumber(ctx.parsed.y),
                            afterBody: (ctx) => {
                                const rev = ctx.find(c => c.dataset.label === 'Revenue')?.parsed.y ?? 0;
                                const exp = ctx.find(c => c.dataset.label === 'Expenses')?.parsed.y ?? 0;
                                
                                if (rev || exp) {
                                    const profit = rev - exp;
                                    const margin = rev ? ((profit / rev) * 100).toFixed(1) : '0.0';
                                    return [
                                        '',
                                        '━━━━━━━━━━━━━━━━━',
                                        'Net Profit: ' + this._formatNumber(profit),
                                        'Profit Margin: ' + margin + '%'
                                    ];
                                }
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false, drawBorder: false },
                        ticks: {
                            font: { size: 13, weight: '600', family: "'Inter', sans-serif" },
                            color: '#64748b',
                            padding: 12
                        }
                    },
                    y: {
                        beginAtZero: true,
                        max: this._padMax(Math.max(...revenueData)),
                        grid: { color: 'rgba(148, 163, 184, 0.1)', drawBorder: false, lineWidth: 1.5 },
                        border: { display: false },
                        ticks: { display: false }
                    }
                }
            },
            plugins: [{
                id: 'customDataLabels',
                afterDatasetsDraw: (chart) => {
                    const ctx = chart.ctx;
                    chart.data.datasets.forEach((dataset, datasetIndex) => {
                        const meta = chart.getDatasetMeta(datasetIndex);
                        if (!meta.hidden) {
                            meta.data.forEach((element, index) => {
                                const value = dataset.data[index];
                                const displayValue = this._formatShort(value);
                                const textWidth = ctx.measureText(displayValue).width;
                                
                                // Position labels: Revenue yuqorida, Expenses pastda, EBT eng yuqorida
                                const y = datasetIndex === 0 ? element.y - 12 
                                        : datasetIndex === 1 ? element.y + 25 
                                        : element.y - 18;
                                
                                const bgColor = datasetIndex === 0 ? 'rgba(34, 197, 94, 0.95)' 
                                              : datasetIndex === 1 ? 'rgba(239, 68, 68, 0.95)' 
                                              : 'rgba(107, 114, 128, 0.95)';

                                ctx.fillStyle = bgColor;
                                ctx.beginPath();
                                ctx.roundRect(element.x - textWidth / 2 - 8, y - 18, textWidth + 16, 22, 6);
                                ctx.fill();

                                ctx.fillStyle = '#fff';
                                ctx.font = '700 11px Inter, sans-serif';
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'bottom';
                                ctx.fillText(displayValue, element.x, y - 3);
                            });
                        }
                    });
                }
            }]
        });
    }

    _renderCashflowChart() {
        const ctx = this._getCanvasContext(this.cashflowChartRef.el);
        if (!ctx) return;

        const inflowsData = this.state.data.cashflow?.monthly_inflows || 
            [55000, 62000, 58500, 71000, 68000, 77000, 82000, 79500, 88000, 92000, 98000, 105000];
        const outflowsData = this.state.data.cashflow?.monthly_outflows || 
            [42000, 45000, 43500, 48000, 46500, 51000, 53000, 52000, 56500, 58000, 61000, 63500];

        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        const year = this.state.data.filter_data?.year || new Date().getFullYear();
        const length = this._clampArrayLength(inflowsData, outflowsData);

        this.charts.cashflowChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: months.slice(0, length),
                datasets: [
                    {
                        label: 'Cash Inflows',
                        data: inflowsData.slice(0, length),
                        borderColor: '#3b82f6',
                        backgroundColor: 'transparent',
                        borderWidth: 4,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 6,
                        pointHoverRadius: 10,
                        pointBackgroundColor: '#3b82f6',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 3,
                    },
                    {
                        label: 'Cash Outflows',
                        data: outflowsData.slice(0, length),
                        borderColor: '#f97316',
                        backgroundColor: 'transparent',
                        borderWidth: 4,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 6,
                        pointHoverRadius: 10,
                        pointBackgroundColor: '#f97316',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 3,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: { top: 10, right: 20, bottom: 10, left: 10 }
                },
                interaction: { intersect: false, mode: 'index' },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        align: 'end',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'circle',
                            padding: 20,
                            font: { size: 14, weight: '700', family: "'Inter', sans-serif" },
                            color: '#1e293b',
                            boxWidth: 10,
                            boxHeight: 10
                        }
                    },
                    title: {
                        display: true,
                        text: 'Cash Flow Analysis',
                        font: { size: 18, weight: '700', family: "'Inter', -apple-system, sans-serif" },
                        color: '#1e293b',
                        padding: { top: 5, bottom: 5 }
                    },
                    tooltip: {
                        enabled: true,
                        backgroundColor: 'rgba(30, 41, 59, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: 'rgba(148, 163, 184, 0.3)',
                        borderWidth: 2,
                        padding: 18,
                        usePointStyle: true,
                        callbacks: {
                            title: (ctx) => ctx[0].label + ` ${year}`,
                            label: (ctx) => ctx.dataset.label + ': ' + this._formatNumber(ctx.parsed.y),
                            afterBody: (ctx) => {
                                if (ctx.length === 2) {
                                    const inflows = ctx[0].parsed.y;
                                    const outflows = ctx[1].parsed.y;
                                    const net = inflows - outflows;
                                    const ratio = inflows ? ((net / inflows) * 100).toFixed(1) : '0.0';
                                    return [
                                        '',
                                        '━━━━━━━━━━━━━━━━━',
                                        'Net Cash Flow: ' + this._formatNumber(net),
                                        'Cash Flow Ratio: ' + ratio + '%'
                                    ];
                                }
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { display: false, drawBorder: false },
                        ticks: {
                            font: { size: 13, weight: '600', family: "'Inter', sans-serif" },
                            color: '#64748b',
                            padding: 12
                        }
                    },
                    y: {
                        beginAtZero: true,
                        max: this._padMax(Math.max(...inflowsData)),
                        grid: { color: 'rgba(148, 163, 184, 0.1)', drawBorder: false, lineWidth: 1.5 },
                        border: { display: false },
                        ticks: { display: false }
                    }
                }
            },
            plugins: [{
                id: 'customDataLabels',
                afterDatasetsDraw: (chart) => {
                    const ctx = chart.ctx;
                    chart.data.datasets.forEach((dataset, datasetIndex) => {
                        const meta = chart.getDatasetMeta(datasetIndex);
                        if (!meta.hidden) {
                            meta.data.forEach((element, index) => {
                                const value = dataset.data[index];
                                const displayValue = this._formatShort(value);
                                const textWidth = ctx.measureText(displayValue).width;
                                
                                const y = datasetIndex === 0 ? element.y - 12 : element.y + 25;
                                const bgColor = datasetIndex === 0 ? 'rgba(59, 130, 246, 0.95)' : 'rgba(249, 115, 22, 0.95)';

                                ctx.fillStyle = bgColor;
                                ctx.beginPath();
                                ctx.roundRect(element.x - textWidth / 2 - 8, y - 18, textWidth + 16, 22, 6);
                                ctx.fill();

                                ctx.fillStyle = '#fff';
                                ctx.font = '700 11px Inter, sans-serif';
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'bottom';
                                ctx.fillText(displayValue, element.x, y - 3);
                            });
                        }
                    });
                }
            }]
        });
    }

    _renderTargetBarChart() {
        const ctx = this._getCanvasContext(this.targetBarChartRef.el);
        if (!ctx) return;

        const ov = this.state.main_data?.overview || {};
        const target = this._toNumber(ov.sales_target);
        const achieved = this._toNumber(ov.total_achieved);
        const safeTarget = Math.max(target, 0);
        const safeAch = Math.min(Math.max(achieved, 0), safeTarget || achieved);
        const remaining = Math.max(safeTarget - safeAch, 0);

        const pctAch = safeTarget ? (safeAch / safeTarget) * 100 : this._toNumber(ov.ratio);
        const pctRem = 100 - pctAch;

        if (this.charts.targetBarChart?.destroy) {
            try { this.charts.targetBarChart.destroy(); } catch {}
        }

        this.charts.targetBarChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Target'],
                datasets: [
                    {
                        label: 'Achieved',
                        data: [safeAch],
                        backgroundColor: '#22c55e',
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
                        backgroundColor: '#ef4444',
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
                        enabled: true,
                        backgroundColor: 'rgba(30, 41, 59, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: 'rgba(148, 163, 184, 0.3)',
                        borderWidth: 2,
                        padding: 14,
                        callbacks: {
                            label: (ctx) => `${ctx.dataset.label}: ${this._formatNumber(ctx.parsed.y)}`,
                            afterBody: () => [
                                '',
                                '━━━━━━━━━━━━━━━━━',
                                `Achieved: ${pctAch.toFixed(2)}%`,
                                `Unachieved: ${pctRem.toFixed(2)}%`,
                            ],
                        },
                    },
                },
                interaction: { intersect: false, mode: 'index' },
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

                    // Achieved label (inside green bar)
                    const achMidY = (barAch.y + barAch.baseY) / 2;
                    ctx.fillStyle = '#ffffff';
                    ctx.fillText(`${pctAch.toFixed(2)}%`, barAch.x, achMidY);

                    // Unachieved label (inside red bar)
                    if (remaining > 0 && Math.abs(barRem.y - barRem.baseY) > 20) {
                        const remMidY = (barRem.y + barRem.baseY) / 2;
                        ctx.fillStyle = '#ffffff';
                        ctx.fillText(`${pctRem.toFixed(2)}%`, barRem.x, remMidY);
                    }

                    // Big center percentage label
                    ctx.font = '700 24px Inter, sans-serif';
                    ctx.fillStyle = '#16a34a';
                    const midY = (chartArea.top + chartArea.bottom) / 2;
                    ctx.fillText(`${pctAch.toFixed(2)}%`, (chartArea.left + chartArea.right) / 2, midY);
                    ctx.restore();
                }
            }]
        });
    }

    _destroyCharts() {
        Object.values(this.charts).forEach((chart) => {
            if (chart?.destroy) {
                try { chart.destroy(); } catch {}
            }
        });
        this.charts = {};
    }

    _formatNumber(value) {
        const n = Number(value);
        if (!isFinite(n)) return "0";
        return new Intl.NumberFormat(undefined, {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0,
        }).format(n);
    }

    _formatShort(value) {
        const abs_value = Math.abs(value);
        if (abs_value >= 1000000) {
            return (value / 1000000).toFixed(1) + 'M';
        } else if (abs_value >= 1000) {
            return (value / 1000).toFixed(1) + 'K';
        }
        return value.toString();
    }

    willUnmount() {
        this._destroyCharts();
    }
}

registry.category("fields").add("l1_dashboard", Dashboard);
