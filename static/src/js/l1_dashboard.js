/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

const { Component, onWillStart, onMounted, useRef, useState } = owl;

export class Dashboard extends Component {
    static template = 'custom.l1_dashboard_demo'
    
    setup() {
        super.setup();
        this.orm = useService("orm");
        
        this.salesChartRef = useRef("salesChart");
        this.revenueExpensesChartRef = useRef("revenueExpensesChart");
        
        this.salesChartInstance = null;
        this.revenueExpensesChartInstance = null;
        
        this.state = useState({
            main_data: {},
            isLoading: true
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });

        onMounted(() => {
            setTimeout(() => {
                this.initializeCharts();
            }, 300);
        });
    }

    async loadDashboardData() {
        try {
            if (this.props.record.data.dashboard_data) {
                this.state.main_data = JSON.parse(this.props.record.data.dashboard_data);
            }
            this.state.isLoading = false;
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.state.isLoading = false;
        }
    }

    initializeCharts() {
        if (typeof Chart === 'undefined') {
            console.error('Chart.js is not loaded!');
            return;
        }

        // Register datalabels plugin if available
        if (Chart.registry && Chart.registry.plugins && Chart.registry.plugins.get('datalabels')) {
            Chart.register(ChartDataLabels);
        }

        if (this.salesChartRef.el) {
            this.renderSalesChart();
        }

        if (this.revenueExpensesChartRef.el) {
            this.renderRevenueExpensesChart();
        }
    }

    renderSalesChart() {
        if (this.salesChartInstance) {
            this.salesChartInstance.destroy();
        }

        const canvas = this.salesChartRef.el;
        const ctx = canvas.getContext('2d');
        
        const salesData = this.state.main_data.sales?.monthly_sales || [12500, 18700, 22300, 19800, 25600, 28900, 31200, 29500, 33800, 36400, 38700, 42100];
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

        // Create gradient
        const gradient = ctx.createLinearGradient(0, 0, 0, 400);
        gradient.addColorStop(0, 'rgba(99, 102, 241, 0.5)');
        gradient.addColorStop(0.5, 'rgba(99, 102, 241, 0.25)');
        gradient.addColorStop(1, 'rgba(99, 102, 241, 0.0)');

        this.salesChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: months,
                datasets: [{
                    label: 'Sales',
                    data: salesData,
                    borderColor: '#6366f1',
                    backgroundColor: gradient,
                    borderWidth: 4,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 6,
                    pointHoverRadius: 10,
                    pointBackgroundColor: '#6366f1',
                    pointBorderColor: '#fff',
                    pointBorderWidth: 3,
                    pointHoverBackgroundColor: '#fff',
                    pointHoverBorderColor: '#6366f1',
                    pointHoverBorderWidth: 4,
                    // Data labels on points
                    datalabels: {
                        align: 'top',
                        anchor: 'end',
                        backgroundColor: 'rgba(99, 102, 241, 0.9)',
                        borderRadius: 6,
                        color: '#fff',
                        font: {
                            weight: '700',
                            size: 11
                        },
                        padding: {
                            top: 4,
                            bottom: 4,
                            left: 8,
                            right: 8
                        },
                        formatter: function(value) {
                            if (value >= 1000000) {
                                return '$' + (value / 1000000).toFixed(1) + 'M';
                            } else if (value >= 1000) {
                                return '$' + (value / 1000).toFixed(1) + 'K';
                            }
                            return '$' + value;
                        }
                    }
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                layout: {
                    padding: {
                        top: 40,
                        right: 20,
                        bottom: 10,
                        left: 10
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
                plugins: {
                    legend: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: 'Monthly Sales Performance',
                        font: {
                            size: 18,
                            weight: '700',
                            family: "'Inter', -apple-system, sans-serif"
                        },
                        color: '#1e293b',
                        padding: {
                            top: 5,
                            bottom: 25
                        }
                    },
                    tooltip: {
                        enabled: true,
                        backgroundColor: 'rgba(30, 41, 59, 0.95)',
                        titleColor: '#fff',
                        bodyColor: '#fff',
                        borderColor: '#6366f1',
                        borderWidth: 2,
                        padding: 16,
                        boxPadding: 8,
                        usePointStyle: true,
                        titleFont: {
                            size: 14,
                            weight: '600'
                        },
                        bodyFont: {
                            size: 16,
                            weight: '700'
                        },
                        displayColors: false,
                        callbacks: {
                            title: function(context) {
                                return context[0].label + ' 2025';
                            },
                            label: function(context) {
                                return '$' + context.parsed.y.toLocaleString('en-US', {
                                    minimumFractionDigits: 0,
                                    maximumFractionDigits: 0
                                });
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false,
                            drawBorder: false
                        },
                        ticks: {
                            font: {
                                size: 13,
                                weight: '600',
                                family: "'Inter', sans-serif"
                            },
                            color: '#64748b',
                            padding: 12
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)',
                            drawBorder: false,
                            lineWidth: 1.5
                        },
                        border: {
                            display: false
                        },
                        ticks: {
                            font: {
                                size: 13,
                                weight: '600',
                                family: "'Inter', sans-serif"
                            },
                            color: '#64748b',
                            padding: 15,
                            callback: function(value) {
                                if (value >= 1000000) {
                                    return '$' + (value / 1000000).toFixed(1) + 'M';
                                } else if (value >= 1000) {
                                    return '$' + (value / 1000).toFixed(0) + 'K';
                                }
                                return '$' + value;
                            }
                        }
                    }
                }
            },
            plugins: [{
                // Custom plugin to show values on points
                id: 'customDataLabels',
                afterDatasetsDraw: function(chart) {
                    const ctx = chart.ctx;
                    chart.data.datasets.forEach((dataset, i) => {
                        const meta = chart.getDatasetMeta(i);
                        if (!meta.hidden) {
                            meta.data.forEach((element, index) => {
                                // Draw value above point
                                ctx.fillStyle = '#6366f1';
                                ctx.font = '700 11px Inter, sans-serif';
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'bottom';
                                
                                const value = dataset.data[index];
                                let displayValue;
                                if (value >= 1000000) {
                                    displayValue = '$' + (value / 1000000).toFixed(1) + 'M';
                                } else if (value >= 1000) {
                                    displayValue = '$' + (value / 1000).toFixed(1) + 'K';
                                } else {
                                    displayValue = '$' + value;
                                }
                                
                                // Background for label
                                const textWidth = ctx.measureText(displayValue).width;
                                const x = element.x;
                                const y = element.y - 12;
                                
                                ctx.fillStyle = 'rgba(99, 102, 241, 0.95)';
                                ctx.beginPath();
                                ctx.roundRect(x - textWidth / 2 - 8, y - 18, textWidth + 16, 22, 6);
                                ctx.fill();
                                
                                // Text
                                ctx.fillStyle = '#fff';
                                ctx.fillText(displayValue, x, y - 3);
                            });
                        }
                    });
                }
            }]
        });
    }

    renderRevenueExpensesChart() {
        if (this.revenueExpensesChartInstance) {
            this.revenueExpensesChartInstance.destroy();
        }

        const canvas = this.revenueExpensesChartRef.el;
        const ctx = canvas.getContext('2d');
        
        const revenueData = this.state.main_data.revenue_expenses?.monthly_revenue || [45000, 52000, 48500, 61000, 58000, 67000, 72000, 69500, 78000, 82000, 88000, 95000];
        const expensesData = this.state.main_data.revenue_expenses?.monthly_expenses || [32000, 35000, 33500, 38000, 36500, 41000, 43000, 42000, 46500, 48000, 51000, 53500];
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

        // Create gradients
        const revenueGradient = ctx.createLinearGradient(0, 0, 0, 400);
        revenueGradient.addColorStop(0, 'rgba(34, 197, 94, 0.4)');
        revenueGradient.addColorStop(0.5, 'rgba(34, 197, 94, 0.2)');
        revenueGradient.addColorStop(1, 'rgba(34, 197, 94, 0.0)');

        const expensesGradient = ctx.createLinearGradient(0, 0, 0, 400);
        expensesGradient.addColorStop(0, 'rgba(239, 68, 68, 0.4)');
        expensesGradient.addColorStop(0.5, 'rgba(239, 68, 68, 0.2)');
        expensesGradient.addColorStop(1, 'rgba(239, 68, 68, 0.0)');

        this.revenueExpensesChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: months,
                datasets: [
                    {
                        label: 'Revenue',
                        data: revenueData,
                        borderColor: '#22c55e',
                        backgroundColor: revenueGradient,
                        borderWidth: 4,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 6,
                        pointHoverRadius: 10,
                        pointBackgroundColor: '#22c55e',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 3,
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: '#22c55e',
                        pointHoverBorderWidth: 4,
                    },
                    {
                        label: 'Expenses',
                        data: expensesData,
                        borderColor: '#ef4444',
                        backgroundColor: expensesGradient,
                        borderWidth: 4,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 6,
                        pointHoverRadius: 10,
                        pointBackgroundColor: '#ef4444',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 3,
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: '#ef4444',
                        pointHoverBorderWidth: 4,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                layout: {
                    padding: {
                        top: 50,
                        right: 20,
                        bottom: 10,
                        left: 10
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        align: 'end',
                        labels: {
                            usePointStyle: true,
                            pointStyle: 'circle',
                            padding: 20,
                            font: {
                                size: 14,
                                weight: '700',
                                family: "'Inter', sans-serif"
                            },
                            color: '#1e293b',
                            boxWidth: 10,
                            boxHeight: 10
                        }
                    },
                    title: {
                        display: true,
                        text: 'Revenue vs Expenses Analysis',
                        font: {
                            size: 18,
                            weight: '700',
                            family: "'Inter', -apple-system, sans-serif"
                        },
                        color: '#1e293b',
                        padding: {
                            top: 5,
                            bottom: 25
                        }
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
                        titleFont: {
                            size: 14,
                            weight: '600'
                        },
                        bodyFont: {
                            size: 15,
                            weight: '700'
                        },
                        displayColors: true,
                        callbacks: {
                            title: function(context) {
                                return context[0].label + ' 2025';
                            },
                            label: function(context) {
                                let label = context.dataset.label || '';
                                if (label) {
                                    label += ': ';
                                }
                                label += '$' + context.parsed.y.toLocaleString('en-US');
                                return label;
                            },
                            afterBody: function(context) {
                                if (context.length === 2) {
                                    const revenue = context[0].parsed.y;
                                    const expenses = context[1].parsed.y;
                                    const profit = revenue - expenses;
                                    const margin = ((profit / revenue) * 100).toFixed(1);
                                    return [
                                        '',
                                        '━━━━━━━━━━━━━━━━━',
                                        'Net Profit: $' + profit.toLocaleString(),
                                        'Profit Margin: ' + margin + '%'
                                    ];
                                }
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false,
                            drawBorder: false
                        },
                        ticks: {
                            font: {
                                size: 13,
                                weight: '600',
                                family: "'Inter', sans-serif"
                            },
                            color: '#64748b',
                            padding: 12
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(148, 163, 184, 0.1)',
                            drawBorder: false,
                            lineWidth: 1.5
                        },
                        border: {
                            display: false
                        },
                        ticks: {
                            font: {
                                size: 13,
                                weight: '600',
                                family: "'Inter', sans-serif"
                            },
                            color: '#64748b',
                            padding: 15,
                            callback: function(value) {
                                if (value >= 1000000) {
                                    return '$' + (value / 1000000).toFixed(1) + 'M';
                                } else if (value >= 1000) {
                                    return '$' + (value / 1000).toFixed(0) + 'K';
                                }
                                return '$' + value;
                            }
                        }
                    }
                }
            },
            plugins: [{
                id: 'customDataLabels',
                afterDatasetsDraw: function(chart) {
                    const ctx = chart.ctx;
                    chart.data.datasets.forEach((dataset, datasetIndex) => {
                        const meta = chart.getDatasetMeta(datasetIndex);
                        if (!meta.hidden) {
                            meta.data.forEach((element, index) => {
                                const value = dataset.data[index];
                                let displayValue;
                                if (value >= 1000000) {
                                    displayValue = '$' + (value / 1000000).toFixed(1) + 'M';
                                } else if (value >= 1000) {
                                    displayValue = '$' + (value / 1000).toFixed(1) + 'K';
                                } else {
                                    displayValue = '$' + value;
                                }
                                
                                const textWidth = ctx.measureText(displayValue).width;
                                const x = element.x;
                                const y = datasetIndex === 0 ? element.y - 12 : element.y + 25;
                                
                                const bgColor = datasetIndex === 0 ? 'rgba(34, 197, 94, 0.95)' : 'rgba(239, 68, 68, 0.95)';
                                
                                ctx.fillStyle = bgColor;
                                ctx.beginPath();
                                ctx.roundRect(x - textWidth / 2 - 8, y - 18, textWidth + 16, 22, 6);
                                ctx.fill();
                                
                                ctx.fillStyle = '#fff';
                                ctx.font = '700 11px Inter, sans-serif';
                                ctx.textAlign = 'center';
                                ctx.textBaseline = 'bottom';
                                ctx.fillText(displayValue, x, y - 3);
                            });
                        }
                    });
                }
            }]
        });
    }

    willUnmount() {
        if (this.salesChartInstance) {
            this.salesChartInstance.destroy();
        }
        if (this.revenueExpensesChartInstance) {
            this.revenueExpensesChartInstance.destroy();
        }
    }
}

registry.category("fields").add("l1_dashboard", Dashboard);
