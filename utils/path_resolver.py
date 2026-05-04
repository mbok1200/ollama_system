from pathlib import Path                                                                   
import sys      

def get_project_root():
    """Автоматично знаходить кореневу папку проекту"""
    # Шукаємо маркери root (setup.py, pyproject.toml, .git тощо)
    current = Path(__file__).parent.parent
    while current != current.parent:
        # Перевіряємо наявність маркерів
        if any((current / marker).exists()
               for marker in ['setup.py', 'pyproject.toml', '.git', '.env']):
            return current
        current = current.parent
    # Якщо не знайшли, повертаємо папку на 2 рівні вище
    return Path(__file__).parent.parent.parent
# Додаємо root один раз при імпорті
PROJECT_ROOT = get_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))