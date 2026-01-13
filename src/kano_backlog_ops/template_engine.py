"""
template_engine.py - Minimal zero-dependency template engine.

Supports:
- {{ variable }} replacement (nested access via dot notation)
- {{#each list}} ... {{/each}} looping
- {{#if (eq a b)}} conditional (basic) or just {{#if variable}}
"""

import re
from typing import Any, Dict, List, Match

class TemplateEngine:
    def __init__(self):
        pass

    def render(self, template: str, context: Dict[str, Any]) -> str:
        """Render template with context."""
        # Handle #each blocks first (nested not supported in this simple version for simplicity, 
        # unless we recurse, but let's do simple regex for linear blocks)
        
        # Regex for {{#each key}} ... {{/each}}
        # Non-greedy match for content
        pattern = re.compile(r"\{\{#each\s+([\w\.]+)\}\}(.*?)\{\{/each\}\}", re.DOTALL)
        
        def replace_each(match: Match) -> str:
            key = match.group(1)
            content_template = match.group(2)
            items = self._get_value(context, key)
            
            if not isinstance(items, list):
                return ""
            
            rendered_chunk = ""
            for item in items:
                # Create item context
                item_ctx = context.copy()
                if isinstance(item, dict):
                     item_ctx.update(item)
                # Also expose 'this' for simple lists
                item_ctx['this'] = item
                
                # Render the inner chunk with item context
                # Recurse for nested template vars
                rendered_chunk += self._render_vars(content_template, item_ctx)
                
            return rendered_chunk

        # Process loops
        # Support only one level of depth for this MVP safety
        processed = pattern.sub(replace_each, template)
        
        # Handle #if (basic: presence check only for now or eq stub)
        # {{#if (eq status "done")}} -> this is hard to regex strict.
        # Let's support simple {{#if variable}} or {{#if filter}} logic if possible.
        # My templates use {{#if (eq status "done")}}.
        # Let's implement a specific handler for that pattern.
        
        if_eq_pattern = re.compile(r"\{\{#if\s+\(eq\s+([\w\.]+)\s+\"([^\"]+)\"\)\}\}(.*?)\{\{/if\}\}", re.DOTALL)
        
        def replace_if_eq(match: Match) -> str:
            key = match.group(1)
            target_val = match.group(2)
            content = match.group(3)
            val = self._get_value(context, key)
            if str(val) == target_val:
                # Recurse render content
                return self._render_vars(content, context)
            return ""

        processed = if_eq_pattern.sub(replace_if_eq, processed)

        # Handle simple {{#if var}}
        if_pattern = re.compile(r"\{\{#if\s+([\w\.]+)\}\}(.*?)\{\{/if\}\}", re.DOTALL)
        def replace_if(match: Match) -> str:
            key = match.group(1)
            content = match.group(2)
            val = self._get_value(context, key)
            if val:
                return self._render_vars(content, context)
            return ""
            
        processed = if_pattern.sub(replace_if, processed)
        
        # Finally render remaining variables
        return self._render_vars(processed, context)

    def _render_vars(self, text: str, context: Dict[str, Any]) -> str:
        """Replace {{ var }} placeholders."""
        var_pattern = re.compile(r"\{\{\s*([\w\.\[\]]+)\s*\}\}")
        
        def replace_var(match: Match) -> str:
            key = match.group(1)
            if key == "this":
                val = context.get('this', '')
                return str(val)
                
            val = self._get_value(context, key)
            return str(val) if val is not None else ""
            
        return var_pattern.sub(replace_var, text)

    def _get_value(self, context: Dict[str, Any], path: str) -> Any:
        """Get value from context using dot notation."""
        parts = path.split('.')
        curr = context
        try:
            for part in parts:
                # Handle array access [0]
                if part.endswith(']') and '[' in part:
                    p_name = part.split('[')[0]
                    idx = int(part.split('[')[1].rstrip(']'))
                    if p_name:
                         curr = curr[p_name]
                    curr = curr[idx]
                else:
                    curr = curr.get(part)
                
                if curr is None:
                    return None
            return curr
        except Exception:
            return None
