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
            },
        });
        
        useEffect(
            () => {
                if (this.props.record.data.dashboard_data) {
                    try {
                        const parsedData = JSON.parse(this.props.record.data.dashboard_data);

                        this.state.main_data.sales = parsedData.sales_data.sales || [];
                        this.state.main_data.total_local_untaxed = parsedData.sales_data.total_local_untaxed || 0;
                        this.state.main_data.total_export_untaxed = parsedData.sales_data.total_export_untaxed || 0;

                        this.state.main_data.revenues = parsedData.revenue_data.revenues || [];
                        this.state.main_data.total_local_revenue = parsedData.revenue_data.total_local_revenue || 0;
                        this.state.main_data.total_export_revenue = parsedData.revenue_data.total_export_revenue || 0;

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
