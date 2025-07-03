/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
var translation = require('web.translation');
var _t = translation._t;
const { Component, useEffect, useState } = owl;

export class Dashboard extends Component {
    static template = 'custom.druksmart_dashboard_reports'
    setup() {
        super.setup();

        this.actionService = useService("action");

        this.state = useState({
            main_data: {
                sales: [],
                total_local_untaxed: 0,
                total_export_untaxed: 0,

                revenues: [],
                total_local_revenue: 0,
                total_export_revenue: 0,

                expenses: [],
                total_local_expense_untaxed: 0,
                total_export_expense_untaxed: 0,

                cashflows: [],
                total_local_cashflow_inflow: 0,
                total_export_cashflow_inflow: 0,
                total_local_cashflow_outflow: 0,
                total_export_cashflow_outflow: 0,
                net_local_cashflow: 0,
                net_export_cashflow: 0,
                total_net_cashflow: 0,
            },
        });
        
        useEffect(
            () => {
                if (this.props.record.data.dashboard_data) {
                    try {
                        const parsedData = JSON.parse(this.props.record.data.dashboard_data);

                        this.state.main_data.sales = parsedData.sales_data.sales || [];
                        this.state.main_data.total_sales_local_untaxed = parsedData.sales_data.total_sales_local_untaxed || 0;
                        this.state.main_data.total_sales_export_untaxed = parsedData.sales_data.total_sales_export_untaxed || 0;

                        this.state.main_data.revenues = parsedData.revenue_data.revenues || [];
                        this.state.main_data.total_local_revenue_untaxed = parsedData.revenue_data.total_local_revenue_untaxed || 0;
                        this.state.main_data.total_export_revenue_untaxed = parsedData.revenue_data.total_export_revenue_untaxed || 0;

                        this.state.main_data.expenses = parsedData.expense_data.expenses || [];
                        this.state.main_data.total_local_expense_untaxed = parsedData.expense_data.total_local_expense_untaxed || 0;
                        this.state.main_data.total_export_expense_untaxed = parsedData.expense_data.total_export_expense_untaxed || 0;

                        this.state.main_data.cashflows = parsedData.cashflow_data.cashflows || [];
                        this.state.main_data.total_local_cashflow_inflow = parsedData.cashflow_data.total_local_cashflow_inflow || 0;
                        this.state.main_data.total_export_cashflow_inflow = parsedData.cashflow_data.total_export_cashflow_inflow || 0;
                        this.state.main_data.total_local_cashflow_outflow = parsedData.cashflow_data.total_local_cashflow_outflow || 0;
                        this.state.main_data.total_export_cashflow_outflow = parsedData.cashflow_data.total_export_cashflow_outflow || 0;
                        this.state.main_data.net_local_cashflow = parsedData.cashflow_data.net_local_cashflow || 0;
                        this.state.main_data.net_export_cashflow = parsedData.cashflow_data.net_export_cashflow || 0;
                        this.state.main_data.total_net_cashflow = parsedData.cashflow_data.total_net_cashflow || 0;

                    } catch (e) {
                        console.error("Error parsing dashboard data:", e);
                    }
                }
            },
            () => [this.props.record.data.dashboard_data]
        );
    }
}

registry.category("fields").add("druksmart_dashboard_reports", Dashboard);
