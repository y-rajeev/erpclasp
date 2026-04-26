# No imports allowed in Server Script

def execute(filters=None):
    txt = frappe.form_dict.get("txt", "")
    start = int(frappe.form_dict.get("start", 0))
    page_len = int(frappe.form_dict.get("page_len", 20))

    return frappe.db.sql("""
        SELECT DISTINCT po_no
        FROM `tabSales Order`
        WHERE docstatus = 1
          AND status != 'Closed'
          AND IFNULL(po_no, '') != ''
          AND po_no LIKE %(txt)s
        ORDER BY po_no
        LIMIT %(start)s, %(page_len)s
    """, {
        "txt": "%" + txt + "%",
        "start": start,
        "page_len": page_len
    })