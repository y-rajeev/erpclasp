def get_erp_purchase_inbound():
    data = frappe.db.sql("""
        SELECT
            po.name AS po_no,
            'Purchase Order' AS po_type,
            po.transaction_date AS po_date,
            po.supplier_name,
            w.branch as production,
            po.schedule_date,
            poi.item_code as sku,
            poi.qty AS ordered_qty,
            COALESCE(SUM(CASE WHEN pr.status NOT IN ('Cancelled', 'Draft') THEN pri.qty ELSE 0 END), 0) AS received_qty,
            CASE
                WHEN poi.qty - COALESCE(SUM(CASE WHEN pr.status NOT IN ('Cancelled', 'Draft') THEN pri.qty ELSE 0 END), 0) < 0 THEN 0
                ELSE poi.qty - COALESCE(SUM(CASE WHEN pr.status NOT IN ('Cancelled', 'Draft') THEN pri.qty ELSE 0 END), 0)
            END AS pending_qty,
            po.set_warehouse AS target_warehouse,
            po.owner AS purchase_dri
        FROM
            `tabPurchase Order` po
        LEFT JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
        LEFT JOIN `tabPurchase Receipt Item` pri ON pri.purchase_order = po.name 
            AND pri.item_code = poi.item_code
        LEFT JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
        LEFT JOIN `tabWarehouse` w ON po.set_warehouse = w.name
        WHERE
            po.is_subcontracted = 0
            AND po.status NOT IN ("Closed", "Completed", "Cancelled", "Draft")
            AND po.supplier_name NOT IN (
                "Palaniyappa Traders"
                )
            AND po.set_warehouse IN (
                "Finished Goods - Govandi - SLPL",
                "Finished Goods - KAR - SLPL",
                "Finished Goods - MUM - SLPL",
                "Raw Materials - Govandi - SLPL",
                "Raw Materials - KAR - SLPL",
                "Raw Materials - MUM - SLPL")
        GROUP BY
            po.name, po.transaction_date, po.supplier_name, w.branch,
            po.schedule_date, poi.item_code, poi.qty, po.set_warehouse

        UNION ALL

        SELECT
            po.name AS po_no,
            'Subcontracting Order' AS po_type,
            po.transaction_date AS po_date,
            po.supplier_name,
            w.branch as production,
            po.schedule_date,
            poi.fg_item as sku,
            poi.qty AS ordered_qty,
            COALESCE(SUM(CASE WHEN sr.status NOT IN ('Cancelled', 'Draft') THEN sor.qty ELSE 0 END), 0) AS received_qty,
            CASE
                WHEN poi.qty - COALESCE(SUM(CASE WHEN sr.status NOT IN ('Cancelled', 'Draft') THEN sor.qty ELSE 0 END), 0) < 0 THEN 0
                ELSE poi.qty - COALESCE(SUM(CASE WHEN sr.status NOT IN ('Cancelled', 'Draft') THEN sor.qty ELSE 0 END), 0)
            END AS pending_qty,
            po.set_warehouse AS target_warehouse,
            po.owner AS purchase_dri
        FROM
            `tabPurchase Order` po
        LEFT JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
        LEFT JOIN `tabSubcontracting Order` so ON so.purchase_order = po.name
        LEFT JOIN `tabSubcontracting Order Item` soi ON soi.parent = so.name
            AND soi.item_code = poi.item_code
        LEFT JOIN `tabSubcontracting Receipt Item` sor ON sor.subcontracting_order = so.name
            AND sor.item_code = poi.fg_item
        LEFT JOIN `tabSubcontracting Receipt` sr ON sr.name = sor.parent
        LEFT JOIN `tabWarehouse` w ON po.set_warehouse = w.name
        WHERE
            po.is_subcontracted = 1
            AND po.status NOT IN ("Closed", "Completed", "Cancelled", "Draft")
            AND po.set_warehouse IN (
                "Finished Goods - Govandi - SLPL",
                "Finished Goods - KAR - SLPL",
                "Finished Goods - MUM - SLPL",
                "Raw Materials - Govandi - SLPL",
                "Raw Materials - KAR - SLPL",
                "Raw Materials - MUM - SLPL")
        GROUP BY
            po.name, po.transaction_date, po.supplier_name, w.branch,
            po.schedule_date, poi.fg_item, poi.qty, po.set_warehouse

        ORDER BY
            po_no, po_date
        """, as_dict=1)
    return data

frappe.response["message"] = get_erp_purchase_inbound()
