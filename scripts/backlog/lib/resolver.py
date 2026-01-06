
from typing import List, Union, Optional
from .index import BacklogIndex, BacklogItem

def resolve_ref(ref: str, index: BacklogIndex, product: Optional[str] = None) -> List[BacklogItem]:
    """Resolve a reference to backlog items, optionally filtering by product.
    
    Args:
        ref: Reference string (UID, id@uidshort, uidshort, or display ID)
        index: BacklogIndex instance
        product: Optional product name to filter results
        
    Returns:
        List of matching BacklogItems
    """
    # 1. Full UID
    if len(ref) == 36 and "-" in ref:
        item = index.get_by_uid(ref)
        if item:
            # Filter by product if specified
            if product and item.product != product:
                return []
            return [item]
            
    # 2. id@uidshort
    if "@" in ref:
        parts = ref.split("@", 1)
        if len(parts) == 2:
            did, short = parts
            candidates = index.get_by_id(did, product=product)
            matches = [c for c in candidates if c.uidshort.startswith(short)]
            return matches
        
    # 3. uidshort (8 chars hex)
    if len(ref) == 8 and all(c in "0123456789abcdefABCDEF" for c in ref):
        matches = index.get_by_uidshort(ref)
        if product and matches:
            matches = [m for m in matches if m.product == product]
        if matches:
            return matches
            
    # 4. Display ID
    return index.get_by_id(ref, product=product)
