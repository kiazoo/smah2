import os

def load_from_env():
    result = {}
    for k, v in os.environ.items():
        result[k] = v
    return result
