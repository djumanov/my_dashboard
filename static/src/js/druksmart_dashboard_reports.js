/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
var translation = require("web.translation");
var _t = translation._t;

const { Component, useEffect, useState } = owl;

export class Dashboard extends Component {
    static template = "custom.druksmart_dashboard_reports";

    setup() {
        this.actionService = useService("action");

        this.state = useState({
            filters: {
                year: "",
                month: "",
                quarter: "",
            },
            years: [2023, 2024, 2025],
            months: [
                { value: "01", label: "January" },
                { value: "02", label: "February" },
                { value: "03", label: "March" },
                { value: "04", label: "April" },
                { value: "05", label: "May" },
                { value: "06", label: "June" },
                { value: "07", label: "July" },
                { value: "08", label: "August" },
                { value: "09", label: "September" },
                { value: "10", label: "October" },
                { value: "11", label: "November" },
                { value: "12", label: "December" },
            ],
            main_data: {
                sales: [],
                total_sales_local_untaxed: 0,
                total_sales_export_untaxed: 0,

                revenues: [],
                total_local_revenue_untaxed: 0,
                total_export_revenue_untaxed: 0,

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
                const data = this.props.record?.data?.dashboard_data;
                if (data) {
                    try {
                        const parsed = JSON.parse(data);

                        // Reset first to avoid ghost data on update
                        this.state.main_data.sales = parsed.sales_data?.sales || [];
                        this.state.main_data.total_sales_local_untaxed = parsed.sales_data?.total_sales_local_untaxed || 0;
                        this.state.main_data.total_sales_export_untaxed = parsed.sales_data?.total_sales_export_untaxed || 0;

                        this.state.main_data.revenues = parsed.revenue_data?.revenues || [];
                        this.state.main_data.total_local_revenue_untaxed = parsed.revenue_data?.total_local_revenue_untaxed || 0;
                        this.state.main_data.total_export_revenue_untaxed = parsed.revenue_data?.total_export_revenue_untaxed || 0;

                        this.state.main_data.expenses = parsed.expense_data?.expenses || [];
                        this.state.main_data.total_local_expense_untaxed = parsed.expense_data?.total_local_expense_untaxed || 0;
                        this.state.main_data.total_export_expense_untaxed = parsed.expense_data?.total_export_expense_untaxed || 0;

                        this.state.main_data.cashflows = parsed.cashflow_data?.cashflows || [];
                        this.state.main_data.total_local_cashflow_inflow = parsed.cashflow_data?.total_local_cashflow_inflow || 0;
                        this.state.main_data.total_export_cashflow_inflow = parsed.cashflow_data?.total_export_cashflow_inflow || 0;
                        this.state.main_data.total_local_cashflow_outflow = parsed.cashflow_data?.total_local_cashflow_outflow || 0;
                        this.state.main_data.total_export_cashflow_outflow = parsed.cashflow_data?.total_export_cashflow_outflow || 0;
                        this.state.main_data.net_local_cashflow = parsed.cashflow_data?.net_local_cashflow || 0;
                        this.state.main_data.net_export_cashflow = parsed.cashflow_data?.net_export_cashflow || 0;
                        this.state.main_data.total_net_cashflow = parsed.cashflow_data?.total_net_cashflow || 0;
                    } catch (error) {
                        console.error("Dashboard JSON parse error:", error);
                    }
                }
            },
            () => [this.props.record?.data?.dashboard_data]
        );
    }

    setCategory(category) {
        this.props.record.update({ category });
    }

    setFilter(key, ev) {
        this.state.filters[key] = ev.target.value;
    }
}

registry.category("fields").add("druksmart_dashboard_reports", Dashboard);
