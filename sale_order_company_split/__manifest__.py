{
    "name": "Sales Order Company Split",
    "version": "19.0.1.0.0",
    "category": "Sales/Sales",
    "summary": "Assign products to owning companies and split sales orders",
    "depends": ["sale_management", "product"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_views.xml",
        "views/sale_order_views.xml",
        "wizard/sale_order_split_views.xml",
    ],
    "installable": True,
    "application": False,
}
