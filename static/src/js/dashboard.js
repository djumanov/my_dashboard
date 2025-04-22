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
                this.drawPie('gender', this.pieData(this.state.main_data.hr?.gender_data));
                this.drawPie('expenses', this.pieData(this.state.main_data.expenses?.region_wise));
                this.drawPie('revenue', this.pieData(this.state.main_data.revenue?.region_wise));
                this.drawPie('sales', this.pieData(this.state.main_data.sales?.region_wise));
                this.drawBar();
                this.drawBarHorizontal();
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
                height: 350
            },
            title: { text: '' },
            legend: {
                layout: 'vertical',
                align: 'right',
                verticalAlign: 'middle'
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
                        distance: -40,  // 🔴 Raqamlarni pie bo‘lagi ichiga joylashtirish
                        verticalAlign: 'middle', // 🔴 O‘rtada ushlab turish
                        crop: false, overflow: 'none',
                        formatter: function () {
                            let formattedValue = Highcharts.numberFormat(this.y, 0, '.', ','); // Format number
                            let bgColor = this.point.color === '#1e88e5' ? '#ff8f00' : '#1e88e5'; // 🔀 Ranglarni almashtirish
                            return `<div style="
                                background-color: ${bgColor};  
                                    color: #fff; 
                                    padding: 5px 10px; 
                                    border-radius: 5px;
                                    border: 1px solid black;
                                    font-weight: bold;
                                    font-size: 16px;
                                ">${formattedValue}</div>`;
                        },
                        align: 'center'
                    }
                }
            },
            series: [{
                type: 'pie',
                name: 'Count',
                colors: ['#1e88e5', '#ff8f00'],
                data: data
            }]
        });
    }

    drawBar() {
        const categories = this.state.main_data.hr?.categories.map(item => item.name);
        const data = this.state.main_data.hr?.categories.map(item => item.count);
        Highcharts.chart('category', {
            chart: {
                type: 'column',
                options3d: {
                    enabled: true,
                    alpha: 15,
                    beta: 0,
                }
            },
            title: {
                text: 'Employee Count by Category',
                style: {
                    fontSize: '14px',
                    fontWeight: 'bold',
                    color: '#fff'
                },
                align: 'center',
                verticalAlign: 'top',
                backgroundColor: '#1e88e5',
                borderRadius: 5,
                padding: 10
            },
            xAxis: {
                categories: categories,
                labels: {
                    style: {
                        fontSize: '13px',
                    }
                }
            },
            yAxis: {
                title: { text: '' },
                allowDecimals: false
            },
            plotOptions: {
                column: {
                    depth: 25,
                    beta: 15,
                }
            },
            series: [{
                name: 'Count',
                data: data,
                colorByPoint: true,
                colors: ['#1e88e5'],
                dataLabels: {   
                    enabled: true,
                    format: '{y}',
                }
            }]
        });        
    }

    drawBarHorizontal() {        
        const categories = this.state.main_data.hr?.departments.map(item => item.name);
        const data = this.state.main_data.hr?.departments.map(item => item.count);
        
        Highcharts.chart('department', {
            chart: {
                type: 'bar',
                options3d: {
                    enabled: true,
                    alpha: 10,
                    beta: 0,
                    depth: 50,
                    viewDistance: 25
                }
            },
            title: {
                text: '',
            },
            xAxis: {
                categories: categories,
                title: { text: null },
                labels: {
                    style: {
                        fontSize: '12px',
                        fontWeight: 'bold'
                    }
                }
            },
            yAxis: {
                title: { text: null },
                allowDecimals: false
            },
            plotOptions: {
                bar: {
                    depth: 25
                }
            },
            series: [{
                name: 'Count',
                data: data,
                colorByPoint: true,
                colors: ['#1e88e5'],
                dataLabels: {   
                    enabled: true,
                    format: '{y}',
                }
            }]
        });
    }

    drawChartIncome(){
        const categories = this.state.main_data.cash_flow.region_wise.inflow.map(item => item.name);

        // Inflow va Outflow qiymatlarini olish
        const inflowData = this.state.main_data.cash_flow.region_wise.inflow.map(item => item.value);
        const outflowData = this.state.main_data.cash_flow.region_wise.outflow.map(item => item.value);
            

        // Highcharts
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
                labels: { enabled: false }, // Y-o'q raqamlarini yashirish
                gridLineWidth: 0, // Orqa fon chiziqlarini olib tashlash
                lineWidth: 0 // Y-o'qning o'zini ham o'chirish
            },
            tooltip: {
                pointFormat: '{series.name}: <b>${point.y:,.0f}</b>'
            },
            plotOptions: {
                column: {
                    depth: 25,
                    grouping: true, // Yonma-yon chiqishi uchun
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
