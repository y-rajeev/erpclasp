def get_erp_stock():
    data = frappe.db.sql("""
        WITH required_for_po_cte AS (
            SELECT
                soi.item_code,
                so_wh.branch,
                SUM(soi.qty) AS required_for_po
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
                SUM(be.stock_qty * soi.qty) AS fabric_required_for_production
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
        ),
        base_stock AS (
            SELECT
                b.item_code,
                i.description,
                w.branch,
                CASE
                    WHEN i.is_purchase_item = 1 THEN 'Purchase'
                    WHEN i.is_sub_contracted_item = 1 THEN 'Subcontract'
                    WHEN i.include_item_in_manufacturing = 1 THEN 'Manufacture'
                END AS material_type,
                SUM(b.actual_qty) AS available_qty,
                COALESCE(r.required_for_po, 0) AS required_for_po,
                COALESCE(f.fabric_required_for_production, 0) AS raw_fabric_required_for_production
            FROM `tabBin` AS b
            JOIN `tabWarehouse` AS w ON w.name = b.warehouse
            JOIN `tabItem` AS i ON i.item_code = b.item_code
            LEFT JOIN required_for_po_cte AS r
                ON r.item_code = b.item_code AND r.branch = w.branch
            LEFT JOIN fabric_required_cte AS f
                ON f.item_code = b.item_code AND f.branch = w.branch
            WHERE
                w.warehouse_type IN ("Finished Goods", "Raw Materials")
            AND (
                i.is_purchase_item = 1
                OR i.is_sub_contracted_item = 1
                OR i.include_item_in_manufacturing = 1
            )
            GROUP BY
            b.item_code, i.description, w.branch,
            i.is_purchase_item, i.is_sub_contracted_item, i.include_item_in_manufacturing,
            r.required_for_po, f.fabric_required_for_production
        )
        SELECT
            item_code as sku,
            description,
            branch as production,
            material_type,
            available_qty,
            required_for_po AS required_for_prev_po,
            LEAST(required_for_po, available_qty) AS reserved_for_prev_po,
            raw_fabric_required_for_production AS fabric_required_for_production,
            LEAST(
                raw_fabric_required_for_production,
                available_qty - LEAST(required_for_po, available_qty)
            ) AS fabric_reserved_for_production,
            available_qty
                - LEAST(required_for_po, available_qty)
                - LEAST(raw_fabric_required_for_production, available_qty - LEAST(required_for_po, available_qty)) AS stock_in_hand
            # CASE
            #     WHEN material_type IN ('Purchase', 'Subcontract')
            #     THEN GREATEST(required_for_po + raw_fabric_required_for_production - available_qty, 0)
            #     ELSE 0
            # END AS reorder_qty
        FROM base_stock
        WHERE available_qty > 0
        ORDER BY item_code, branch
        """, as_dict=1)
    return data

frappe.response["output"] = get_erp_stock()
