
from typing import List, Union
from .index import BacklogIndex, BacklogItem

def resolve_ref(ref: str, index: BacklogIndex) -> List[BacklogItem]:
    # 1. Full UID
    if len(ref) == 36 and "-" in ref:
        item = index.get_by_uid(ref)
        if item:
            return [item]
            
    # 2. id@uidshort
    if "@" in ref:
        parts = ref.split("@", 1)
        if len(parts) == 2:
            did, short = parts
            candidates = index.get_by_id(did)
            matches = [c for c in candidates if c.uidshort.startswith(short)]
            return matches
        
    # 3. uidshort (8 chars hex)
    if len(ref) == 8 and all(c in "0123456789abcdefABCDEF" for c in ref):
        matches = index.get_by_uidshort(ref)
        if matches:
            return matches
            
    # 4. Display ID
    return index.get_by_id(ref)
