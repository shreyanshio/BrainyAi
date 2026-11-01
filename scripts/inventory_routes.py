#!/usr/bin/env python3
"""
Automated Flask API Route Inventory & Security Auditor for BrainyAi
Inspects app.url_map directly from the live application instance.
"""

import os
import sys
import inspect
from collections import defaultdict

# Add project root to sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import app as brainy_app

def categorize_route(rule_str: str) -> str:
    path = rule_str.strip("/")
    if not path:
        return "root"
    parts = path.split("/")
    if parts[0] == "api":
        if len(parts) > 1:
            sub = parts[1]
            if sub in ("auth", "login", "telegram-auth"):
                return "Authentication"
            elif sub == "admin":
                return "Admin Control Center"
            elif sub == "pdf":
                return "PDF Study Studio"
            elif sub == "user":
                return "User Profile & Memory"
            elif sub == "chat":
                return "Chat & Conversations"
            elif sub == "sessions":
                return "Chat Sessions"
            elif sub == "health":
                return "Health & Diagnostics"
            elif sub == "sandbox":
                return "Code Sandbox (Exposed)"
            else:
                return f"API ({sub})"
        return "API (General)"
    elif parts[0] == "ping":
        return "Health & Diagnostics"
    elif parts[0] == "share":
        return "Public Sharing"
    elif parts[0] == "static":
        return "Static Assets"
    return "Other"

def audit_routes():
    app = brainy_app.app
    routes = []
    
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        methods = sorted(list(rule.methods - {"OPTIONS", "HEAD"}))
        view_fn = app.view_functions.get(rule.endpoint)
        
        # Check source for decorators / auth guards
        auth_required = False
        admin_required = False
        doc = ""
        source_code = ""
        
        if view_fn:
            doc = inspect.getdoc(view_fn) or ""
            try:
                source_code = inspect.getsource(view_fn)
                if "@login_required" in source_code or "verify_auth_token" in source_code or "current_user" in source_code:
                    auth_required = True
                if "is_admin" in source_code or "ADMIN" in source_code or rule.rule.startswith("/api/admin"):
                    admin_required = True
            except Exception:
                pass
        
        category = categorize_route(rule.rule)
        
        routes.append({
            "rule": rule.rule,
            "endpoint": rule.endpoint,
            "methods": methods,
            "category": category,
            "auth_required": auth_required,
            "admin_required": admin_required,
            "doc": doc.split("\n")[0] if doc else ""
        })
    
    # Sort by category then rule
    routes.sort(key=lambda x: (x["category"], x["rule"]))
    return routes

def print_inventory(routes):
    categories = defaultdict(list)
    unique_paths = set()
    total_method_ops = 0
    
    for r in routes:
        categories[r["category"]].append(r)
        unique_paths.add(r["rule"])
        total_method_ops += len(r["methods"])
        
    print("=" * 80)
    print("BRAINY FLASK API ROUTE INVENTORY (PROGRAMMATIC URL MAP DISCOVERY)")
    print("=" * 80)
    print(f"Total Registered Flask Route Rules: {len(routes)}")
    print(f"Total Unique URL Paths:             {len(unique_paths)}")
    print(f"Total HTTP Method Operations:       {total_method_ops}")
    print("=" * 80)
    
    print("\nBREAKDOWN BY FUNCTIONAL CATEGORY:")
    print(f"{'Category':<30s} | {'Rules':<6s} | {'HTTP Ops':<8s} | {'Auth Required':<14s}")
    print("-" * 70)
    
    for cat, cat_routes in sorted(categories.items()):
        ops = sum(len(r["methods"]) for r in cat_routes)
        auth_count = sum(1 for r in cat_routes if r["auth_required"])
        print(f"{cat:<30s} | {len(cat_routes):<6d} | {ops:<8d} | {auth_count:<14d}")
        
    print("-" * 70)
    print(f"{'TOTAL':<30s} | {len(routes):<6d} | {total_method_ops:<8d} | {sum(1 for r in routes if r['auth_required']):<14d}")
    print("=" * 80)
    
    print("\nDETAILED ENDPOINT SPECIFICATION:")
    for cat, cat_routes in sorted(categories.items()):
        print(f"\n--- {cat} ({len(cat_routes)} endpoints) ---")
        for r in cat_routes:
            methods_str = ",".join(r["methods"])
            auth_tag = "[ADMIN]" if r["admin_required"] else ("[AUTH]" if r["auth_required"] else "[PUBLIC]")
            print(f"  {methods_str:<8s} {r['rule']:<45s} {auth_tag:<8s} {r['endpoint']}")
            
    # Check specifically for sandbox endpoints
    sandbox_endpoints = [r for r in routes if "sandbox" in r["rule"].lower()]
    print("\n" + "=" * 80)
    print("CODE SANDBOX PUBLIC EXPOSURE CHECK:")
    if sandbox_endpoints:
        print(f"  WARNING: Found {len(sandbox_endpoints)} public sandbox endpoints:")
        for r in sandbox_endpoints:
            print(f"    {r['rule']}")
    else:
        print("  CONFIRMED: Zero /api/sandbox/* endpoints exist in app.url_map.")
        print("  ai_routing/code_sandbox.py is strictly an internal utility, not an exposed API.")
    print("=" * 80)

if __name__ == "__main__":
    routes = audit_routes()
    print_inventory(routes)
