def get_stock_in_hand():
    data = frappe.db.sql("""
        WITH po_qty_cte AS (
            SELECT
                soi.item_code,
                so_wh.branch,
                SUM(soi.qty) AS po_qty
            FROM `tabSales Order Item` AS soi
            JOIN `tabSales Order` AS so ON so.name = soi.parent
            JOIN `tabWarehouse` AS so_wh ON so_wh.name = soi.warehouse
            WHERE
                so.status != 'Closed'
                AND so.customer = "Encasa Homes Private Limited"
            GROUP BY soi.item_code, so_wh.branch
        ),
        fabric_required_cte AS (
            SELECT
                be.item_code,
                so_wh.branch,
                SUM(be.stock_qty * soi.qty) AS total_fabric_required
            FROM `tabBOM` AS bom
            JOIN `tabBOM Explosion Item` AS be ON be.parent = bom.name
            JOIN `tabSales Order Item` AS soi ON soi.item_code = bom.item
            JOIN `tabSales Order` AS so ON so.name = soi.parent
            JOIN `tabWarehouse` AS so_wh ON so_wh.name = soi.warehouse
            WHERE
                bom.is_active = 1
                AND bom.is_default = 1
                AND be.item_code LIKE '%FA-%'
                AND so.status != 'Closed'
                AND so.customer = "Encasa Homes Private Limited"
            GROUP BY be.item_code, so_wh.branch
        )
        SELECT
            b.item_code,
            i.description,
            w.branch,
            SUM(b.actual_qty) AS available_qty,
            -- Reserved for PO (cannot exceed available_qty)
            LEAST(COALESCE(p.po_qty, 0), SUM(b.actual_qty)) AS reserved_for_po,
            -- Reserved for Production (cannot exceed available_qty - reserved_for_po)
            LEAST(
                COALESCE(f.total_fabric_required, 0),
                GREATEST(SUM(b.actual_qty) - LEAST(COALESCE(p.po_qty, 0), SUM(b.actual_qty)), 0)
            ) AS reserved_for_production,
            -- Stock in Hand
            GREATEST(
                SUM(b.actual_qty)
                    - LEAST(COALESCE(p.po_qty, 0), SUM(b.actual_qty))
                    - LEAST(
                    COALESCE(f.total_fabric_required, 0),
                    GREATEST(SUM(b.actual_qty) - LEAST(COALESCE(p.po_qty, 0), SUM(b.actual_qty)), 0)
                ),
                0
            ) AS stock_in_hand
        FROM `tabBin` AS b
        JOIN `tabWarehouse` AS w ON w.name = b.warehouse
        JOIN `tabItem` AS i ON i.item_code = b.item_code
        LEFT JOIN po_qty_cte AS p ON p.item_code = b.item_code AND p.branch = w.branch
        LEFT JOIN fabric_required_cte AS f ON f.item_code = b.item_code AND f.branch = w.branch
        WHERE
            b.actual_qty > 0
            AND w.warehouse_type IN ("Finished Goods", "Raw Materials")
        GROUP BY b.item_code, i.description, w.branch, p.po_qty, f.total_fabric_required
        # HAVING stock_in_hand > 0
        ORDER BY b.item_code, w.branch;
    """, as_dict=1)

    return data


frappe.response["message"] = get_stock_in_hand()
