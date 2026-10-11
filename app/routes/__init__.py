"""HTTP routes.

Split by concern so that the boundary between "the page a person uses" and "the API the
page calls" is visible in the file layout. Every route that writes goes through
``repository`` and records an audit event; no route contains SQL.
"""
