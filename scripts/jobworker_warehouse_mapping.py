data = frappe.db.sql("""
    SELECT 
        s.name AS supplier_id,
        s.supplier_name,
        w_match.warehouse
    FROM `tabSupplier` s

    LEFT JOIN (
        SELECT 
            s_inner.name AS supplier_id,
            MIN(w.name) AS warehouse
        FROM `tabSupplier` s_inner
        JOIN `tabWarehouse` w
            ON LOWER(w.name) LIKE CONCAT(LOWER(s_inner.supplier_name), '%')
            OR LOWER(w.name) LIKE CONCAT(
                '%', LOWER(SUBSTRING_INDEX(s_inner.supplier_name, ' ', 1)), '%'
            )
        WHERE s_inner.supplier_group = 'Jobworker'
        GROUP BY s_inner.name
    ) w_match 
        ON w_match.supplier_id = s.name

    WHERE s.supplier_group = 'Jobworker'
    ORDER BY s.supplier_name
""", as_dict=True)

frappe.response["message"] = data