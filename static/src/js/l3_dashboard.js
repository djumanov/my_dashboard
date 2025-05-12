/** @odoo-module **/

import { useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

export class L3Dashboard extends Component {
    static template = "custom.l3_dashboard";
    static props = {
        ...standardFieldProps,
    };

    setup() {
        const currentYear = new Date().getFullYear();

        this.state = useState({
            project: {},
            filters: {
                region: "",
                year: currentYear,
                month: "",
                project: "",
            },
            months: [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ],
            years: Array.from({ length: 10 }, (_, i) => currentYear - i),
            projects: [],
        });

        // Add a formatter function for float numbers
        this.formatNumber = (value) => {
            if (value === undefined || value === null || isNaN(value)) {
                return "";
            }
            
            // Format as XX,XXX.XX
            return parseFloat(value).toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        };

        onWillStart(async () => {
            const rpc = this.env.services.rpc;

            try {
                const result = await rpc("/custom/l3_dashboard/projects");
                this.state.projects = result || [];
                
            } catch (e) {
                console.warn("Failed to load projects:", e);
            }

            if (this.props.value) {
                try {
                    const parsed = JSON.parse(this.props.value);
                    this.state.project = parsed.project || {};
                } catch (e) {
                    console.error("Failed to parse dashboard_data:", e);
                }
            }
        });
    }
}

registry.category("fields").add("l3_dashboard", L3Dashboard);