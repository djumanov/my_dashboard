/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
var translation = require('web.translation');
var _t = translation._t;
const { Component, useEffect, useState } = owl;

export class Dashboard extends Component {
    static template = 'custom.druksmart_dashboard_reports'

    setup() {
        this.actionService = useService("action");

        this.state = useState({
            selectedCategory: this.props.record.data.category || "sales",
            openedGroups: {},
            main_data: {
                sales: [],
                total_sales_local_untaxed: 0,
                total_sales_export_untaxed: 0,
                total_sales_other_untaxed: 0,
                total_sales_local_untaxed_not_converted: 0,
                total_sales_export_untaxed_not_converted: 0,
                total_sales_other_untaxed_not_converted: 0,
                total_sales_untaxed: 0,
                grouped_saless: {},

                revenues: [],
                total_local_revenue_untaxed: 0,
                total_export_revenue_untaxed: 0,
                total_other_revenue_untaxed: 0,
                total_local_revenue_untaxed_not_converted: 0,
                total_export_revenue_untaxed_not_converted: 0,
                total_other_revenue_untaxed_not_converted: 0,
                total_revenue_untaxed: 0,
                grouped_revenues: {},

                expenses: [],
                total_local_expense_untaxed: 0,
                total_export_expense_untaxed: 0,
                total_other_expense_untaxed: 0,
                total_local_expense_untaxed_not_converted: 0,
                total_export_expense_untaxed_not_converted: 0,
                total_other_expense_untaxed_not_converted: 0,
                total_expense_untaxed: 0,
                grouped_expenses: {},

                cashflows: {
                    inflows: {
                        locals: [],
                        exports: []
                    },
                    outflows: {
                        locals: [],
                        exports: []
                    }
                },
                total_local_cashflow_inflow: 0,
                total_export_cashflow_inflow: 0,
                total_local_cashflow_outflow: 0,
                total_export_cashflow_outflow: 0,
                net_local_cashflow: 0,
                net_export_cashflow: 0,
                total_net_cashflow: 0,
            },
        });

        this.setCategory = (category) => {
            console.log("Setting category to:", category);
            this.state.selectedCategory = category;
            // this.props.record.data.category = category;
            this.props.record.update({ category: category });
            this.state.openedGroups = {}; // reset opened groups on category switch
        };

        this.toggleGroup = (groupKey) => {
            this.state.openedGroups[groupKey] = !this.state.openedGroups[groupKey];
        };

        this.isGroupOpened = (key) => {
            return !!this.state.openedGroups[key];
        }

        useEffect(() => {
            console.log(this.props.record.data.category);

            if (this.props.record.data.category && this.props.record.data.category !== this.state.selectedCategory) {
                this.state.selectedCategory = this.props.record.data.category;
            }
        }, () => [this.props.record.data.category]);

        useEffect(() => {
            if (this.props.record.data.dashboard_data) {
                try {
                    const parsedData = JSON.parse(this.props.record.data.dashboard_data);
                    const groupByLE = (records) => {
                        return (records || []).reduce((acc, cur) => {
                            const key = cur.local_export || "Unknown";
                            acc[key] = acc[key] || [];
                            acc[key].push(cur);
                            return acc;
                        }, {});
                    };

                    console.log(this.state.main_data)

                    Object.assign(this.state.main_data, {
                        sales: parsedData.sales_data?.sales || [],
                        total_sales_local_untaxed: parsedData.sales_data?.total_sales_local_untaxed || 0,
                        total_sales_export_untaxed: parsedData.sales_data?.total_sales_export_untaxed || 0,
                        total_sales_other_untaxed: parsedData.sales_data?.total_sales_other_untaxed || 0,
                        total_sales_local_untaxed_not_converted: parsedData.sales_data?.total_sales_local_untaxed_not_converted || 0,
                        total_sales_export_untaxed_not_converted: parsedData.sales_data?.total_sales_export_untaxed_not_converted || 0,
                        total_sales_other_untaxed_not_converted: parsedData.sales_data?.total_sales_other_untaxed_not_converted || 0,
                        total_sales_untaxed: parsedData.sales_data?.total_sales_untaxed || 0,
                        grouped_saless: groupByLE(parsedData.sales_data?.sales),

                        revenues: parsedData.revenue_data?.revenues || [],
                        total_revenue_local_untaxed: parsedData.revenue_data?.total_local_revenue_untaxed || 0,
                        total_revenue_export_untaxed: parsedData.revenue_data?.total_export_revenue_untaxed || 0,                        
                        total_revenue_other_untaxed: parsedData.revenue_data?.total_other_revenue_untaxed || 0,                        
                        total_revenue_local_untaxed_not_converted: parsedData.revenue_data?.total_local_revenue_untaxed_not_converted || 0,
                        total_revenue_export_untaxed_not_converted: parsedData.revenue_data?.total_export_revenue_untaxed_not_converted || 0,                        
                        total_revenue_other_untaxed_not_converted: parsedData.revenue_data?.total_other_revenue_untaxed_not_converted || 0,                        
                        total_revenue_untaxed: parsedData.revenue_data?.total_revenue_untaxed || 0,                        
                        grouped_revenues: groupByLE(parsedData.revenue_data?.revenues),

                        expenses: parsedData.expense_data?.expenses || [],
                        total_expense_local_untaxed: parsedData.expense_data?.total_expenses_local_untaxed || 0,
                        total_expense_export_untaxed: parsedData.expense_data?.total_expenses_export_untaxed || 0,                        
                        total_expense_other_untaxed: parsedData.expense_data?.total_expenses_other_untaxed || 0,                        
                        total_expense_local_untaxed_not_converted: parsedData.expense_data?.total_expenses_local_untaxed_not_converted || 0,
                        total_expense_export_untaxed_not_converted: parsedData.expense_data?.total_expenses_export_untaxed_not_converted || 0,                        
                        total_expense_other_untaxed_not_converted: parsedData.expense_data?.total_expenses_other_untaxed_not_converted || 0,                        
                        total_expense_untaxed: parsedData.expense_data?.total_expense_untaxed || 0,                        
                        grouped_expenses: groupByLE(parsedData.expense_data?.expenses),

                        cashflows: {
                            inflows: {
                                locals: parsedData.cashflow_data?.cashflows?.inflows?.locals || [],
                                exports: parsedData.cashflow_data?.cashflows?.inflows?.exports || []
                            },
                            outflows: {
                                locals: parsedData.cashflow_data?.cashflows?.outflows?.locals || [],
                                exports: parsedData.cashflow_data?.cashflows?.outflows?.exports || []
                            }
                        },
                        total_local_cashflow_inflow: parsedData.cashflow_data?.total_local_cashflow_inflow || 0,
                        total_export_cashflow_inflow: parsedData.cashflow_data?.total_export_cashflow_inflow || 0,
                        total_local_cashflow_outflow: parsedData.cashflow_data?.total_local_cashflow_outflow || 0,
                        total_export_cashflow_outflow: parsedData.cashflow_data?.total_export_cashflow_outflow || 0,
                        net_local_cashflow: parsedData.cashflow_data?.net_local_cashflow || 0,
                        net_export_cashflow: parsedData.cashflow_data?.net_export_cashflow || 0,
                        total_net_cashflow: parsedData.cashflow_data?.total_net_cashflow || 0,
                        // grouped_cashflows: groupByInflowAndLE(parsedData.cashflow_data?.cashflows),
                    });

                } catch (e) {
                    console.error("Error parsing dashboard data:", e);
                }
            }
        }, () => [this.props.record.data.dashboard_data]);
    }
}

registry.category("fields").add("druksmart_dashboard_reports", Dashboard);
