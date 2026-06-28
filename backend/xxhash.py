import hashlib

class MockXXHash:
    def __init__(self, data=b"", seed=0):
        self.data = data if isinstance(data, bytes) else str(data).encode("utf-8")
        
    def digest(self) -> bytes:
        return hashlib.sha256(self.data).digest()[:16]
        
    def hexdigest(self) -> str:
        return hashlib.sha256(self.data).hexdigest()[:32]

def xxh3_128(data=b"", seed=0) -> MockXXHash:
    return MockXXHash(data, seed)

def xxh3_128_hexdigest(data=b"", seed=0) -> str:
    data_bytes = data if isinstance(data, bytes) else str(data).encode("utf-8")
    return hashlib.sha256(data_bytes).hexdigest()[:32]

def xxh3_64_hexdigest(data=b"", seed=0) -> str:
    data_bytes = data if isinstance(data, bytes) else str(data).encode("utf-8")
    return hashlib.sha256(data_bytes).hexdigest()[:16]

def xxh64_hexdigest(data=b"", seed=0) -> str:
    data_bytes = data if isinstance(data, bytes) else str(data).encode("utf-8")
    return hashlib.sha256(data_bytes).hexdigest()[:16]

def xxh64(data=b"", seed=0) -> MockXXHash:
    return MockXXHash(data, seed)

def xxh32(data=b"", seed=0) -> MockXXHash:
    return MockXXHash(data, seed)
