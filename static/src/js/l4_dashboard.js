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
            sort: {
                primary: {
                    field: 'region', // Changed default sort field to region
                    direction: 'asc'  // 'asc' or 'desc'
                },
                secondary: {
                    field: 'date', // Added secondary sort field for date
                    direction: 'asc'
                }
            },
        });
        
        // Format number to XXX,XXX,XXX.XX format
        this.formatNumber = (value) => {
            if (value === null || value === undefined) return '';
            
            // Convert to number if it's a string
            const numValue = typeof value === 'string' ? parseFloat(value) : value;
            
            // Check if it's a valid number
            if (isNaN(numValue)) return value;
            
            // Format with commas and 2 decimal places
            return numValue.toLocaleString('en-US', {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            });
        };
        
        // Sort projects based on current sort fields and directions
        this.sortProjects = (projects) => {
            if (!projects || !projects.length) return [];
            
            const primaryField = this.state.sort.primary.field;
            const primaryDirection = this.state.sort.primary.direction;
            const secondaryField = this.state.sort.secondary.field;
            const secondaryDirection = this.state.sort.secondary.direction;
            
            return [...projects].sort((a, b) => {
                // Access raw values for primary field
                const valueA_primary = a[`_raw_${primaryField}`] !== undefined ? a[`_raw_${primaryField}`] : a[primaryField];
                const valueB_primary = b[`_raw_${primaryField}`] !== undefined ? b[`_raw_${primaryField}`] : b[primaryField];
                
                // Handle null/undefined values for primary field
                if (valueA_primary === undefined || valueA_primary === null) return primaryDirection === 'asc' ? -1 : 1;
                if (valueB_primary === undefined || valueB_primary === null) return primaryDirection === 'asc' ? 1 : -1;
                
                // Compare based on data type for primary field
                let primaryCompare = 0;
                if (typeof valueA_primary === 'number' && typeof valueB_primary === 'number') {
                    primaryCompare = primaryDirection === 'asc' ? valueA_primary - valueB_primary : valueB_primary - valueA_primary;
                } else {
                    // Convert to string for string comparison
                    const strA = String(valueA_primary).toLowerCase();
                    const strB = String(valueB_primary).toLowerCase();
                    primaryCompare = primaryDirection === 'asc' ? strA.localeCompare(strB) : strB.localeCompare(strA);
                }
                
                // If primary fields are equal, use secondary field
                if (primaryCompare === 0) {
                    // Access raw values for secondary field
                    const valueA_secondary = a[`_raw_${secondaryField}`] !== undefined ? a[`_raw_${secondaryField}`] : a[secondaryField];
                    const valueB_secondary = b[`_raw_${secondaryField}`] !== undefined ? b[`_raw_${secondaryField}`] : b[secondaryField];
                    
                    // Handle null/undefined values for secondary field
                    if (valueA_secondary === undefined || valueA_secondary === null) return secondaryDirection === 'asc' ? -1 : 1;
                    if (valueB_secondary === undefined || valueB_secondary === null) return secondaryDirection === 'asc' ? 1 : -1;
                    
                    // Compare based on data type for secondary field
                    if (typeof valueA_secondary === 'number' && typeof valueB_secondary === 'number') {
                        return secondaryDirection === 'asc' ? valueA_secondary - valueB_secondary : valueB_secondary - valueA_secondary;
                    } else {
                        // Convert to string for string comparison
                        const strA = String(valueA_secondary).toLowerCase();
                        const strB = String(valueB_secondary).toLowerCase();
                        return secondaryDirection === 'asc' ? strA.localeCompare(strB) : strB.localeCompare(strA);
                    }
                }
                
                return primaryCompare;
            });
        };
        
        // Handler for column header clicks
        this.handleSort = (field) => {
            if (this.state.sort.primary.field === field) {
                // Toggle direction if already sorting by this field
                this.state.sort.primary.direction = this.state.sort.primary.direction === 'asc' ? 'desc' : 'asc';
            } else if (this.state.sort.secondary.field === field) {
                // Toggle secondary direction if clicking on secondary field
                this.state.sort.secondary.direction = this.state.sort.secondary.direction === 'asc' ? 'desc' : 'asc';
            } else {
                // Make the current primary sort the secondary sort
                this.state.sort.secondary.field = this.state.sort.primary.field;
                this.state.sort.secondary.direction = this.state.sort.primary.direction;
                
                // Set new primary sort
                this.state.sort.primary.field = field;
                this.state.sort.primary.direction = 'asc';
            }
            
            // Apply sorting to the projects array
            if (this.state.main_data.projects && this.state.main_data.projects.length > 0) {
                this.state.main_data.projects = this.sortProjects(this.state.main_data.projects);
            }
        };
        
        // Get sort indicator (arrow) for column header
        this.getSortIndicator = (field) => {
            if (this.state.sort.primary.field === field) {
                return this.state.sort.primary.direction === 'asc' ? '▲' : '▼';
            } else if (this.state.sort.secondary.field === field) {
                return this.state.sort.secondary.direction === 'asc' ? '▲ (2)' : '▼ (2)';
            }
            return '';
        };
        
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
                        
                        // Format all numeric fields in projects
                        if (parsedData.projects && parsedData.projects.length > 0) {
                            parsedData.projects = parsedData.projects.map(project => {
                                const formattedProject = {...project};
                                // Format all numeric fields except id, region, project, customer, date
                                const numericFields = [
                                    'po_value', 'invoiced', 'collected', 'pending_collection',
                                    'vendor_invoice', 'payment_made', 'payment_to_be_made', 
                                    'payroll_cost', 'total_outgoing',
                                    'total_margin'
                                ];
                                
                                numericFields.forEach(field => {
                                    if (formattedProject[field] !== undefined) {
                                        // Store original value for calculations
                                        formattedProject[`_raw_${field}`] = formattedProject[field];
                                        // Format for display
                                        formattedProject[field] = this.formatNumber(formattedProject[field]);
                                    }
                                });
                                
                                // Handle percentage separately
                                if (formattedProject.margin_percent !== undefined) {
                                    formattedProject._raw_margin_percent = formattedProject.margin_percent;
                                    formattedProject.margin_percent = this.formatNumber(formattedProject.margin_percent) + '%';
                                }
                                
                                return formattedProject;
                            });
                            
                            // Apply initial sorting
                            parsedData.projects = this.sortProjects(parsedData.projects);
                        }
                        
                        // Format summary values
                        if (parsedData.summary) {
                            const formattedSummary = {...parsedData.summary};
                            const numericSummaryFields = [
                                'total_po_value', 'total_invoiced', 'total_collected',
                                'total_pending_collection', 'total_vendor_invoice',
                                'total_payment_made', 'total_payment_to_be_made',
                                'total_payroll_cost', 'total_margin'
                            ];
                            
                            numericSummaryFields.forEach(field => {
                                if (formattedSummary[field] !== undefined) {
                                    // Store original for calculations
                                    formattedSummary[`_raw_${field}`] = formattedSummary[field];
                                    // Format for display
                                    formattedSummary[field] = this.formatNumber(formattedSummary[field]);
                                }
                            });
                            
                            parsedData.summary = formattedSummary;
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
