def get_stock_ledger():
    data = frappe.db.sql("""
        SELECT 
            s.name AS id,
            s.posting_date,
            s.voucher_type,
            s.voucher_no,
            w.branch,
            s.item_code,
            s.actual_qty,
            s.qty_after_transaction,
            s.stock_uom,
            s.warehouse,
            w.warehouse_type,
            s.docstatus,
            /* Remarks logic:
                - For Stock Entry:
                    - If Material Issue -> use custom_against_order_no
                    - Else -> use se.remarks
                - For other voucher types -> use their remarks as before
            */
            CASE
                WHEN s.voucher_type = 'Stock Entry' THEN
                    CASE
                        WHEN se.stock_entry_type = 'Material Issue' THEN se.custom_against_order_no
                        ELSE se.remarks
                    END
                ELSE
                    COALESCE(pr.remarks, si.remarks, pinv.remarks)
            END AS remarks,
            s.is_cancelled,
            s.modified
            FROM `tabStock Ledger Entry` AS s
            LEFT JOIN `tabWarehouse` AS w
                ON s.warehouse = w.name
            LEFT JOIN `tabStock Entry` AS se
                ON s.voucher_type = 'Stock Entry' AND s.voucher_no = se.name
            LEFT JOIN `tabPurchase Receipt` AS pr
                ON s.voucher_type = 'Purchase Receipt' AND s.voucher_no = pr.name
            LEFT JOIN `tabSales Invoice` AS si
                ON s.voucher_type = 'Sales Invoice' AND s.voucher_no = si.name
            LEFT JOIN `tabPurchase Invoice` AS pinv
                ON s.voucher_type = 'Purchase Invoice' AND s.voucher_no = pinv.name;
        """, as_dict=1)
    return data

frappe.response["message"] = get_stock_ledger()
