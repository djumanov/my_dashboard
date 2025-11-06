/** @odoo-module **/
import { loadJS } from "@web/core/assets";

import { registry } from "@web/core/registry";
const { Component, useEffect, useState } = owl;

const CHART_JS_URL = "https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js";

export class Dashboard extends Component {
    static template = "custom.hr_dashboard";

    setup() {
        super.setup();
        this.state = useState({ main_data: [] });

        useEffect(() => {
            const parsedData = JSON.parse(this.props.record.data.dashboard_data || "{}");
            this.state.main_data = parsedData;
            loadJS(CHART_JS_URL).then(() => {
                this.renderCharts();
            });
        }, () => [this.props.record.data.dashboard_data]);
    }

    renderCharts() {

        this.renderDepartmentChart();
        this.renderGenderChart();
        this.renderCategoryChart();
    }

    _gradient(ctx, colorStart, colorEnd, vertical = false) {
        const gradient = ctx.createLinearGradient(0, 0, vertical ? 0 : ctx.canvas.width, vertical ? ctx.canvas.height : 0);
        gradient.addColorStop(0, colorStart);
        gradient.addColorStop(1, colorEnd);
        return gradient;
    }

    renderDepartmentChart() {
        const canvas = document.getElementById("department");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");

        const data = this.state.main_data.hr?.departments || [];
        
        // Sort data by count for better visualization
        const sortedData = [...data].sort((a, b) => b.count - a.count);
        const labels = sortedData.map(d => d.name);
        const values = sortedData.map(d => d.count);

        const gradient = this._gradient(ctx, "#6366f1", "#a855f7");

        new Chart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Employees",
                    data: values,
                    borderRadius: 8,
                    backgroundColor: gradient,
                    borderSkipped: false,
                    barPercentage: 0.7,
                    categoryPercentage: 0.8,
                }]
            },
            options: {
                indexAxis: "y", // This makes it horizontal
                maintainAspectRatio: false,
                responsive: true,
                animation: { 
                    duration: 1200, 
                    easing: "easeOutQuart" 
                },
                layout: {
                    padding: {
                        left: 120, // More space for long labels
                        right: 20,
                        top: 10,
                        bottom: 10
                    }
                },
                plugins: {
                    legend: { 
                        display: false 
                    },
                    tooltip: {
                        backgroundColor: "#0f172a",
                        titleColor: "#fff",
                        bodyColor: "#cbd5e1",
                        padding: 12,
                        borderWidth: 0,
                        cornerRadius: 8,
                        displayColors: false,
                        callbacks: {
                            title: function(tooltipItems) {
                                // Show full department name in tooltip
                                return tooltipItems[0].label;
                            },
                            label: function(context) {
                                return `Employees: ${context.parsed.x}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: { 
                            color: "#e5e7eb",
                            drawBorder: false
                        },
                        ticks: { 
                            color: "#475569", 
                            font: { 
                                size: 12,
                                weight: "500" 
                            },
                            stepSize: 1
                        },
                        title: {
                            display: true,
                            text: 'Number of Employees',
                            color: '#64748b',
                            font: {
                                size: 13,
                                weight: '600'
                            }
                        }
                    },
                    y: {
                        grid: { 
                            display: false 
                        },
                        ticks: { 
                            color: "#1e293b", 
                            font: { 
                                size: 12, 
                                weight: "500" 
                            },
                            // Auto-wrap long labels
                            callback: function(value, index) {
                                const label = this.getLabelForValue(index);
                                const maxLength = 30;
                                if (label.length > maxLength) {
                                    const words = label.split(' ');
                                    let lines = [];
                                    let currentLine = '';
                                    
                                    words.forEach(word => {
                                        if ((currentLine + word).length <= maxLength) {
                                            currentLine += (currentLine ? ' ' : '') + word;
                                        } else {
                                            if (currentLine) lines.push(currentLine);
                                            currentLine = word;
                                        }
                                    });
                                    if (currentLine) lines.push(currentLine);
                                    
                                    return lines;
                                }
                                return label;
                            },
                            padding: 8
                        }
                    }
                }
            }
        });
    }

    renderGenderChart() {
        const canvas = document.getElementById("gender");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");

        const data = this.state.main_data.hr?.gender_data?.data || [];
        const labels = data.map(g => g.name);
        const values = data.map(g => g.value);

        new Chart(ctx, {
            type: "doughnut",
            data: {
                labels,
                datasets: [{
                    data: values,
                    backgroundColor: ["#6366f1", "#f472b6", "#10b981"],
                    borderWidth: 0,
                    hoverOffset: 12,
                }]
            },
            options: {
                cutout: "68%",
                maintainAspectRatio: false,
                animation: { duration: 1200, easing: "easeOutCubic" },
                plugins: {
                    legend: {
                        position: "bottom",
                        labels: {
                            color: "#334155",
                            usePointStyle: true,
                            boxWidth: 10,
                            padding: 14,
                            font: { size: 13, weight: "500" },
                        }
                    },
                    tooltip: {
                        backgroundColor: "#0f172a",
                        titleColor: "#fff",
                        bodyColor: "#cbd5e1",
                        cornerRadius: 8,
                        padding: 10,
                    }
                }
            },
            plugins: [{
                id: "centerText",
                afterDraw(chart) {
                    const { ctx, chartArea: { width, height } } = chart;
                    ctx.save();
                    const total = values.reduce((a, b) => a + b, 0);
                    ctx.font = "600 16px 'Inter'";
                    ctx.fillStyle = "#1e293b";
                    ctx.textAlign = "center";
                    ctx.fillText(`${total}`, width / 2, height / 2 + 6);
                    ctx.restore();
                }
            }]
        });
    }

    renderCategoryChart() {
        const canvas = document.getElementById("category");
        if (!canvas) return;
        const ctx = canvas.getContext("2d");

        const data = this.state.main_data.hr?.categories || [];
        const labels = data.map(c => c.name);
        const values = data.map(c => c.count);

        const gradient = this._gradient(ctx, "#10b981", "#06b6d4", true);

        new Chart(ctx, {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Employees",
                    data: values,
                    borderRadius: 14,
                    borderSkipped: false,
                    backgroundColor: gradient,
                }]
            },
            options: {
                maintainAspectRatio: false,
                animation: { duration: 1000, easing: "easeOutBounce" },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: "#0f172a",
                        titleColor: "#fff",
                        bodyColor: "#cbd5e1",
                        padding: 10,
                        borderWidth: 0,
                        cornerRadius: 8,
                    }
                },
                scales: {
                    x: {
                        grid: { color: "#f3f4f6" },
                        ticks: { color: "#334155", font: { weight: "600" } }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: "#e2e8f0" },
                        ticks: { color: "#64748b", stepSize: 1 }
                    }
                }
            }
        });
    }
}

registry.category("fields").add("hr_dashboard", Dashboard);
