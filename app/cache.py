import hashlib
import time

class ResponseCache:
     
    def  __init__(self,ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._cache: dict[str,dict] = {}
        self._hits = 0
        self._misses = 0
    def _make_key(self,query : str) -> str:
        """Create a cache  key from the normalized query

        Args:
            query (str): _description_

        Returns:
            str: _description_
        """
        normalized = query.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()
    def get(self,query : str) -> str | None:
        """get cached response if it exists and hasn't expired

        Args:
            query (str): _description_

        Returns:
            str | None: return None on cache miss
        """
        key = self._make_key(query)
        if key in self._cache:
            entry = self._cache[key]
            if time.time() - entry['timestamp'] < self.ttl:
                self._hits += 1
                return entry['response']
            else:
                del self._cache[key]
        self._misses += 1
        return None
    def set(self, query: str, response:str) -> None:
        """Save miss queries 

        Args:
            query (str): _description_
            response (str): _description_
        """
        key = self._make_key(query)
        
        self._cache[key] = {
            "response": response,
            "timestamp": time.time(),
            "query": query
        }
    @property
    def stats(self) -> dict:
        """cache performance statistics.

        Returns:
            dict: 
        """
        total = self._hits + self._misses
        hit_rate = self._hits/ total if total > 0 else 0.0
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1%}",
            "cached_entries": len(self._cache)
        }  