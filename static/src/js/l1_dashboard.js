/** @odoo-module **/
import { registry } from "@web/core/registry";

var translation = require('web.translation');
var _t = translation._t;
const { Component, useEffect, useState } = owl;


export class Dashboard extends Component {
    static template = 'custom.l1_dashboard_demo'
    setup() {
        super.setup();

        this.state = useState({
            main_data: [],
        })
        useEffect(
            () => {
                this.state.main_data = JSON.parse(this.props.record.data.dashboard_data);
                this._renderSalesChart();
            },
            () => [this.props.record.data.dashboard_data]
        );
    }

    _renderSalesChart() {
        const ctx = document.getElementById("salesLineChart");
        if (!ctx || !this.state.main_data?.sales?.monthly_sales) return;

        const monthlySales = this.state.main_data.sales.monthly_sales;
        const months = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ];

        // Destroy old chart if exists
        if (this.chart) {
            this.chart.destroy();
        }

        this.chart = new Chart(ctx, {
            type: "line",
            data: {
                labels: months,
                datasets: [
                    {
                        label: "Monthly Sales",
                        data: monthlySales,
                        fill: false,
                        borderColor: "#0d6efd",
                        backgroundColor: "#0d6efd",
                        tension: 0.3,
                        pointRadius: 5,
                        pointHoverRadius: 7,
                    },
                ],
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        display: true,
                        position: "top",
                    },
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function (value) {
                                return "$" + value.toLocaleString();
                            },
                        },
                    },
                },
            },
        });
    }
}

registry.category("fields").add("l1_dashboard", Dashboard);
