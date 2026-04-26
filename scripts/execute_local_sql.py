query = frappe.form_dict.get("query")

if not query:
    frappe.response["message"] = []
else:
    # -------------------------------
    # Clean query (remove comments)
    # -------------------------------
    lines = []
    for line in query.splitlines():
        line = line.strip()
        if line and not line.startswith("--"):
            lines.append(line)

    cleaned_query = " ".join(lines).lower()

    # -------------------------------
    # Safety checks
    # -------------------------------
    if not (
        cleaned_query.startswith("select")
        or cleaned_query.startswith("with")
    ):
        frappe.throw("Only SELECT queries are allowed")

    # Optional: block dangerous keywords
    if any(word in cleaned_query for word in ["delete", "update", "insert", "drop"]):
        frappe.throw("Dangerous query blocked")

    try:
        result = frappe.db.sql(query, as_dict=True)
        frappe.response["message"] = result

    except Exception:
        frappe.log_error(frappe.get_traceback(), "SQL Execution Error")
        frappe.throw("Failed to execute query")