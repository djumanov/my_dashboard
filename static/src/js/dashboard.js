/** @odoo-module **/
import { registry } from "@web/core/registry";

var translation = require('web.translation');
var _t = translation._t;
const { Component, useEffect, useState } = owl;


export class Dashboard extends Component {
    static template = 'custom.dashboard'
    setup() {
        super.setup();

        this.state = useState({
            main_data: [],
        })
        useEffect(
            () => {
                this.state.main_data = JSON.parse(this.props.record.data.dashboard_data);
                this.drawPie('expenses', this.pieData(this.state.main_data.expenses?.region_wise));
                this.drawPie('revenue', this.pieData(this.state.main_data.revenue?.region_wise));
                this.drawPie('sales', this.pieData(this.state.main_data.sales?.region_wise));
                this.drawChartIncome();
            },
            () => [this.props.record.data.dashboard_data]
        );
    }

    drawPie(id, data) {
        Highcharts.chart(id, {
            chart: {
                type: 'pie',
                options3d: {
                    enabled: true,
                    alpha: 60,
                    beta: 0
                },
                width: 400,
                height: 350,
                events: {
                    load: function () {
                        // Grafik yuklangach, barcha data label span’lariga width beramiz
                        const spans = document.querySelectorAll(`#${id} span[style*="position: absolute"]`);
                        spans.forEach(span => {
                            span.style.width = '90px';
                            span.style.whiteSpace = 'nowrap'; // matn o‘ramasin
                            span.style.overflow = 'visible';  // kesilmasin
                            span.style.textOverflow = 'unset'; // ellipsis olib tashlash
                        });
                    }
                }
            },
            title: { text: '' },
            legend: {
                layout: 'vertical',
                align: 'right',
                verticalAlign: 'middle'
            },
            tooltip: {
                useHTML: true,
                backgroundColor: '#000',
                borderRadius: 8,
                borderWidth: 0,
                style: {
                    color: '#fff',
                    fontSize: '16px',
                    padding: 12
                },
                formatter: function () {
                    const formattedValue = Highcharts.numberFormat(this.y, 0, '.', ',');
                    return `<b style="color:${this.point.color}; font-size: 16px;">${this.point.name}</b>: 
                            <span style="font-weight: bold; font-size: 16px;">${formattedValue}</span>`;
                }
            },
            plotOptions: {
                pie: {
                    allowPointSelect: false,
                    cursor: 'pointer',
                    depth: 35,
                    showInLegend: true,
                    size: "90%",
                    dataLabels: {
                        enabled: true,
                        useHTML: true,
                        distance: -40,
                        formatter: function () {
                            let formattedValue = Highcharts.numberFormat(this.y, 0, '.', ',');
                            let bgColor = this.point.color || '#007bff';
                            return `<div style="
                                background-color: ${bgColor}; 
                                color: #fff; 
                                padding: 4px 10px; 
                                border-radius: 8px;
                                font-weight: 600;
                                font-size: 14px;
                                text-align: center;
                                white-space: nowrap;
                                display: inline-block;
                            ">${formattedValue}</div>`;
                        },
                        align: 'center'
                    },
                    point: {
                        events: {
                            click: function () {
                                window.location.href = "/web#action=my_dashboard.action_l2_dashboard";
                            }
                        }
                    }
                }
            },
            series: [{
                type: 'pie',
                name: 'Count',
                colors: ['#4e79a7', '#f28e2c'],
                data: data
            }]
        });
    }
    
    drawChartIncome() {
        const categories = this.state.main_data.cash_flow.region_wise.inflow.map(item => item.name);
        const inflowData = this.state.main_data.cash_flow.region_wise.inflow.map(item => item.value);
        const outflowData = this.state.main_data.cash_flow.region_wise.outflow.map(item => item.value);
    
        Highcharts.chart('cash', {
            chart: {
                type: 'column',
                options3d: {
                    enabled: true,
                    alpha: 10,
                    beta: 5,
                    depth: 25,
                    viewDistance: 25
                }
            },
            title: {
                text: 'Region Wise Cash Flow',
                align: 'center',
                style: {
                    fontSize: '16px',
                    fontWeight: 'bold',
                    color: '#fff'
                },
                backgroundColor: '#3b71ca',
                borderRadius: 5,
                padding: 10
            },
            xAxis: {
                categories: categories,
                labels: {
                    style: {
                        fontSize: '12px',
                        fontWeight: 'bold'
                    }
                }
            },
            yAxis: {
                title: { text: null },
                labels: { enabled: false },
                gridLineWidth: 0,
                lineWidth: 0
            },
            tooltip: {
                useHTML: true,
                backgroundColor: '#000',
                borderRadius: 6,
                borderWidth: 0,
                style: {
                    color: '#fff',
                    fontSize: '14px'
                },
                formatter: function () {
                    const value = Highcharts.numberFormat(this.y, 0, '.', ',');
                    return `<b style="color:${this.color}">${this.series.name}</b>: <b>${value}</b>`;
                }
                
            },
            plotOptions: {
                column: {
                    depth: 25,
                    grouping: true,
                    dataLabels: {
                        enabled: true,
                        formatter: function () {
                            return `${Highcharts.numberFormat(this.y, 0, '.', ',')}`;
                        },
                        style: {
                            fontSize: '12px',
                            fontWeight: 'bold',
                            color: '#000'
                        }
                    },
                    point: {
                        events: {
                            click: function () {
                                window.location.href = "/web#action=my_dashboard.action_l2_dashboard";
                            }
                        }
                    }
                }
            },
            legend: {
                align: 'center',
                verticalAlign: 'bottom',
                layout: 'horizontal',
                backgroundColor: '#FFFFFF'
            },
            series: [
                {
                    name: 'Inflow',
                    data: inflowData,
                    color: '#1e88e5'
                },
                {
                    name: 'Outflow',
                    data: outflowData,
                    color: '#ff8f00'
                }
            ]
        });
    }
    
    pieData(source) {
        return source.data.map(info => ({
            name: info.name,
            y: info.value,
        }));
    }

}

registry.category("fields").add("dashboard", Dashboard);
