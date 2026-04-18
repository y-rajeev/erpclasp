WITH receipts AS (

    -- Purchase Receipt
    SELECT
        'Purchase' AS receipt_type,
        pr.name AS name,
        pr.supplier_name AS supplier_name,
        pr.supplier_delivery_note AS supplier_delivery_note,
        pr.custom_lot_no AS custom_lot_no,
        pr.posting_date AS posting_date,
        pri.item_code AS item_code,
        pri.warehouse AS warehouse,
        sle.qty_after_transaction AS qty_after_transaction,
        pri.received_qty AS received_qty,
        (pri.received_qty - IFNULL(pri.rejected_qty, 0)) AS accepted_qty,
        IFNULL(pri.rejected_qty, 0) AS rejected_qty
    FROM `tabPurchase Receipt` pr
    INNER JOIN `tabPurchase Receipt Item` pri
        ON pri.parent = pr.name
    LEFT JOIN `tabPurchase Order` po
        ON po.name = pri.purchase_order
    LEFT JOIN `tabStock Ledger Entry` sle
        ON sle.voucher_type = 'Purchase Receipt'
        AND sle.voucher_no = pr.name
        AND sle.voucher_detail_no = pri.name
        AND sle.is_cancelled = 0
    WHERE pr.docstatus = 1
        AND IFNULL(po.is_subcontracted, 0) = 0

    UNION ALL

    -- Subcontracting Receipt
    SELECT
        'Subcontracting' AS receipt_type,
        scr.name AS name,
        scr.supplier_name AS supplier_name,
        scr.supplier_delivery_note AS supplier_delivery_note,
        scr.custom_lot_no AS custom_lot_no,
        scr.posting_date AS posting_date,
        scri.item_code AS item_code,
        scri.warehouse AS warehouse,
        sle.qty_after_transaction AS qty_after_transaction,
        scri.received_qty AS received_qty,
        (scri.received_qty - IFNULL(scri.rejected_qty, 0)) AS accepted_qty,
        IFNULL(scri.rejected_qty, 0) AS rejected_qty
    FROM `tabSubcontracting Receipt` scr
    INNER JOIN `tabSubcontracting Receipt Item` scri
        ON scri.parent = scr.name
    LEFT JOIN `tabStock Ledger Entry` sle
        ON sle.voucher_type = 'Subcontracting Receipt'
        AND sle.voucher_no = scr.name
        AND sle.voucher_detail_no = scri.name
        AND sle.is_cancelled = 0
    WHERE scr.docstatus = 1

)

SELECT
    receipt_type,
    name,
    supplier_name,
    supplier_delivery_note,
    custom_lot_no,
    posting_date,
    item_code,
    received_qty,
    accepted_qty,
    rejected_qty,
    warehouse,
    qty_after_transaction
FROM receipts
ORDER BY posting_date DESC, name DESC, item_code ASC
