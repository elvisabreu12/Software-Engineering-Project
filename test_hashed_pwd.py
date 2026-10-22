from security import hash_password, verify_password
h = hash_password("hello")
print(verify_password("hello", h))   # True
print(verify_password("wrong", h))   # False