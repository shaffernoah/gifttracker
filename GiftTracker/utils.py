def format_currency(value):
    if value is None:
        return "$0.00"
    return f"${value:,.2f}"
