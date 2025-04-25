/** @odoo-module **/
import { registry } from "@web/core/registry";

var translation = require('web.translation');
var _t = translation._t;
const { Component, useEffect, useState } = owl;

export class Dashboard extends Component {
    static template = 'custom.l4_dashboard'
    setup() {
        super.setup();

        // Initialize with proper structure to avoid undefined errors
        this.state = useState({
            main_data: {
                projects: [],
                summary: {
                    project_count: 0,
                    total_po_value: 0,
                    total_invoiced: 0,
                    total_collected: 0,
                    total_pending_collection: 0,
                    total_vendor_invoice: 0,
                    total_payment_made: 0,
                    total_payment_to_be_made: 0,
                    total_payroll_cost: 0,
                    total_margin: 0
                }
            },
        })
        
        useEffect(
            () => {
                // Only update if dashboard_data exists and is valid JSON
                if (this.props.record.data.dashboard_data) {
                    try {
                        const parsedData = JSON.parse(this.props.record.data.dashboard_data);
                        // Ensure summary exists to prevent issues
                        if (!parsedData.summary) {
                            parsedData.summary = this.state.main_data.summary;
                        }
                        this.state.main_data = parsedData;
                    } catch (e) {
                        console.error("Error parsing dashboard data:", e);
                    }
                }
            },
            () => [this.props.record.data.dashboard_data]
        );
    }
}

registry.category("fields").add("l4_dashboard", Dashboard);
