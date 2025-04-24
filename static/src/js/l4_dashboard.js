/** @odoo-module **/
import { registry } from "@web/core/registry";

var translation = require('web.translation');
var _t = translation._t;
const { Component, useEffect, useState } = owl;

export class Dashboard extends Component {
    static template = 'custom.l4_dashboard'
    setup() {
        super.setup();

        this.state = useState({
            main_data: [],
        })
        useEffect(
            () => {
                this.state.main_data = JSON.parse(this.props.record.data.dashboard_data);
            },
            () => [this.props.record.data.dashboard_data]
        );
    }
}

registry.category("fields").add("l4_dashboard", Dashboard);
