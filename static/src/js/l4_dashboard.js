/** @odoo-module **/
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// OWL hooks
const { Component, useEffect, useState, onMounted, onPatched, useRef } = owl;

export class Dashboard extends Component {
  static template = "custom.l4_dashboard";

  setup() {
    super.setup();
    this.actionService = useService("action");

    // ---- REFS ----
    this.tableRef = useRef("table");
    this.searchInputRef = useRef("searchInput");

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
          total_margin: 0,
        },
      },
      sort: {
        primary: { field: "region", direction: "asc" },
        secondary: { field: "date", direction: "asc" },
      },
      searchTerm: "",
      originalProjects: [],
    });

    // ---- FORMATTERS ----
    this.formatNumber = (v) => {
      if (v === null || v === undefined || v === "") return "";
      const n = typeof v === "string" ? Number(v.replace(/[,\s]/g, "")) : Number(v);
      if (Number.isNaN(n)) return v;
      const i = Math.trunc(n);
      return i.toLocaleString(undefined, { maximumFractionDigits: 0 });
    };

    this.formatPercent = (v) => {
      if (v === null || v === undefined || v === "") return "";
      const n = Number(String(v).replace("%", "").trim());
      if (Number.isNaN(n)) return v;
      const i = Math.trunc(n);
      return i.toLocaleString(undefined, { maximumFractionDigits: 0 }) + "%";
    };

    this.splitProjectIntoLines = (name) => {
      if (!name) return [""];
      const parts = String(name).trim().split(/\s+/);
      if (parts.length <= 3) return [name]; // no break
      return [parts.slice(0, 3).join(" "), parts.slice(3).join(" ")];
    };

    // Aliases used in template
    this.fmt = this.formatNumber;
    this.fmtPercent = this.formatPercent;

    // ---- SORT ----
    this.sortProjects = (projects) => {
      if (!projects?.length) return [];
      const { field: pField, direction: pDir } = this.state.sort.primary;
      const { field: sField, direction: sDir } = this.state.sort.secondary;
      return [...projects].sort((a, b) => {
        const avp = a[`_raw_${pField}`] ?? a[pField];
        const bvp = b[`_raw_${pField}`] ?? b[pField];
        const cmpP =
          typeof avp === "number" && typeof bvp === "number"
            ? pDir === "asc" ? avp - bvp : bvp - avp
            : pDir === "asc"
              ? String(avp).localeCompare(String(bvp))
              : String(bvp).localeCompare(String(avp));
        if (cmpP) return cmpP;
        const avs = a[`_raw_${sField}`] ?? a[sField];
        const bvs = b[`_raw_${sField}`] ?? b[sField];
        return typeof avs === "number" && typeof bvs === "number"
          ? sDir === "asc" ? avs - bvs : bvs - avs
          : sDir === "asc"
            ? String(avs).localeCompare(String(bvs))
            : String(bvs).localeCompare(String(avs));
      });
    };

    this.handleSort = (field) => {
      if (this.state.sort.primary.field === field) {
        this.state.sort.primary.direction =
          this.state.sort.primary.direction === "asc" ? "desc" : "asc";
      } else if (this.state.sort.secondary.field === field) {
        this.state.sort.secondary.direction =
          this.state.sort.secondary.direction === "asc" ? "desc" : "asc";
      } else {
        this.state.sort.secondary = { ...this.state.sort.primary };
        this.state.sort.primary = { field, direction: "asc" };
      }
      if (this.state.main_data.projects?.length) {
        this.state.main_data.projects = this.sortProjects(this.state.main_data.projects);
        this.wrapHeaderLabels();
        this.autosizeNumericColumns();
      }
    };

    // ---- SEARCH ----
    this.handleSearch = (s) => {
      this.state.searchTerm = s;
      if (!s.trim()) {
        this.state.main_data.projects = [...this.state.originalProjects];
      } else {
        const term = s.toLowerCase().trim();
        this.state.main_data.projects = this.state.originalProjects.filter(
          (p) =>
            (p.project && p.project.toLowerCase().includes(term)) ||
            (p.customer && p.customer.toLowerCase().includes(term))
        );
      }
      this.state.main_data.projects = this.sortProjects(this.state.main_data.projects);
      this.wrapHeaderLabels();
      this.autosizeNumericColumns();
    };

    this.clearSearch = () => {
      this.state.searchTerm = "";
      this.state.main_data.projects = this.sortProjects([...this.state.originalProjects]);
      if (this.searchInputRef.el) this.searchInputRef.el.value = "";
      this.wrapHeaderLabels();
      this.autosizeNumericColumns();
    };

    // ---- DATA LOAD ----
    useEffect(() => {
      if (this.props.record.data.dashboard_data) {
        try {
          const parsed = JSON.parse(this.props.record.data.dashboard_data);
          if (!parsed.summary) parsed.summary = this.state.main_data.summary;

          if (parsed.projects?.length) {
            const seenKeys = new Set();
            parsed.projects = parsed.projects.map((project, i) => {
              const p = { ...project };

              // numeric/percent normalization
              const fields = [
                "po_value",
                "invoiced",
                "collected",
                "pending_collection",
                "vendor_invoice",
                "payment_made",
                "payment_to_be_made",
                "payroll_cost",
                "total_outgoing",
                "total_margin",
              ];
              fields.forEach((f) => {
                if (p[f] !== undefined) {
                  const raw = Number(String(p[f]).replace(/[,\s]/g, ""));
                  p[`_raw_${f}`] = Number.isNaN(raw) ? p[f] : raw;
                  p[f] = this.formatNumber(raw);
                }
              });
              if (p.margin_percent !== undefined) {
                const rawPct = Number(String(p.margin_percent).replace("%", "").trim());
                p._raw_margin_percent = Number.isNaN(rawPct) ? p.margin_percent : rawPct;
                p.margin_percent = this.formatPercent(rawPct);
              }
              if (p.region !== undefined) p._raw_region = p.region;
              if (p.date !== undefined) p._raw_date = p.date;

              // ---- UNIQUE, STABLE KEY ----
              const base = p.id ?? p.project_id ?? p.code ?? p.uuid ?? null;
              let key =
                base != null
                  ? `id:${String(base)}`
                  : `${p.region ?? ""}|${p.project ?? ""}|${p.customer ?? ""}|${p.date ?? ""}` || `idx-${i}`;

              let uniqueKey = String(key);
              let bump = 1;
              while (seenKeys.has(uniqueKey)) {
                uniqueKey = `${key}#${bump++}`;
              }
              seenKeys.add(uniqueKey);
              p.__key = uniqueKey;

              return p;
            });

            this.state.originalProjects = [...parsed.projects];
            parsed.projects = this.sortProjects(parsed.projects);
          }

          if (parsed.summary) {
            const s = { ...parsed.summary };
            const sFields = [
              "total_po_value",
              "total_invoiced",
              "total_collected",
              "total_pending_collection",
              "total_vendor_invoice",
              "total_payment_made",
              "total_payment_to_be_made",
              "total_payroll_cost",
              "total_margin",
            ];
            sFields.forEach((f) => {
              if (s[f] !== undefined) {
                const raw = Number(String(s[f]).replace(/[,\s]/g, ""));
                s[`_raw_${f}`] = Number.isNaN(raw) ? s[f] : raw;
                s[f] = this.formatNumber(raw);
              }
            });
            if (s.avg_margin_percent !== undefined) {
              const rawPct = Number(String(s.avg_margin_percent).replace("%", "").trim());
              s._raw_avg_margin_percent = Number.isNaN(rawPct) ? s.avg_margin_percent : rawPct;
              s.avg_margin_percent = this.formatPercent(rawPct);
            }
            parsed.summary = s;
          }

          this.state.main_data = parsed;

          // DOM ready → wrap headers & autosize cols
          requestAnimationFrame(() => {
            this.wrapHeaderLabels();
            this.autosizeNumericColumns();
          });
        } catch (e) {
          console.error("Error parsing dashboard data:", e);
        }
      }
    }, () => [this.props.record.data.dashboard_data]);

    // Renderdan keyin va har bir patchdan keyin qayta o'lchash va header wrap
    onMounted(() => {
      this.wrapHeaderLabels();
      this.autosizeNumericColumns();
    });
    onPatched(() => {
      this.wrapHeaderLabels();
      this.autosizeNumericColumns();
    });
  }

  // --- Header wrapping: each word on new line for compact headers ---
  wrapHeaderLabels() {
    const table = this.tableRef.el;
    if (!table || !table.tHead) return;
    const ths = table.tHead.querySelectorAll("th");
    ths.forEach((th) => {
      const orig = th.getAttribute("data-original-text") ?? th.textContent.trim();
      th.setAttribute("data-original-text", orig);
      const html = orig.split(/\s+/).join("<br>");
      if (th.innerHTML !== html) th.innerHTML = html;
    });
  }

  // --- Autosize numeric/date/aging columns to content width ---
  autosizeNumericColumns() {
    const table = this.tableRef.el;
    if (!table || !table.tHead || !table.tBodies?.length) return;

    const cols = table.querySelectorAll("colgroup col");
    const headerCells = table.tHead.rows[0]?.cells || [];
    const bodyRows = table.tBodies[0].rows || [];

    const meas = document.createElement("span");
    const cs = getComputedStyle(table);
    meas.style.visibility = "hidden";
    meas.style.position = "absolute";
    meas.style.whiteSpace = "nowrap";
    meas.style.font = `${cs.fontStyle} ${cs.fontVariant} ${cs.fontWeight} ${cs.fontSize} / ${cs.lineHeight} ${cs.fontFamily}`;
    document.body.appendChild(meas);

    for (let i = 0; i < headerCells.length; i++) {
      const th = headerCells[i];
      const isNum = th.classList.contains("num") || cols[i]?.classList.contains("col-num");
      const isAging = th.classList.contains("aging") || cols[i]?.classList.contains("col-aging");
      const isDate = (th.textContent || "").replace(/\s+/g, " ").trim().toLowerCase() === "date"
        || cols[i]?.classList.contains("col-date");

      if (!(isNum || isAging || isDate)) {
        if (cols[i]) {
          cols[i].style.width = "";
          cols[i].style.minWidth = "";
          cols[i].style.maxWidth = "";
        }
        continue;
      }

      let maxPx = 0;

      const headerLines = th.innerText ? th.innerText.split("\n") : [(th.textContent || "").trim()];
      for (const line of headerLines) {
        meas.textContent = line.trim();
        maxPx = Math.max(maxPx, meas.getBoundingClientRect().width);
      }

      for (const row of bodyRows) {
        const cell = row.cells[i];
        if (!cell) continue;
        meas.textContent = (cell.textContent || "").trim();
        maxPx = Math.max(maxPx, meas.getBoundingClientRect().width);
      }

      const finalPx = Math.ceil(maxPx + 24);
      if (cols[i]) {
        cols[i].style.width = `${finalPx}px`;
        cols[i].style.minWidth = `${finalPx}px`;
        cols[i].style.maxWidth = `${finalPx}px`;
      }
    }

    document.body.removeChild(meas);
  }

  openProjectDetails(projectId) {
    this.actionService.doAction({
      type: "ir.actions.act_window",
      res_model: "l3.dashboard",
      view_mode: "form",
      views: [[false, "form"]],
      target: "current",
      name: "L3 Dashboard",
      context: { default_project_id: projectId },
    });
  }
}

registry.category("fields").add("l4_dashboard", Dashboard);
