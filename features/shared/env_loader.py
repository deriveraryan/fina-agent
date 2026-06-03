import os

def load_env_file() -> None:
    """Loads environment variables from the root .env file if present.
    
    Looks for .env in the parent directory hierarchy of this file.
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    for _ in range(5):
        env_path = os.path.join(current_dir, ".env")
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        os.environ.setdefault(key, val)
            break
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
        current_dir = parent_dir
