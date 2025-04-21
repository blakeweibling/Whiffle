# hook-numpy.py
from PyInstaller.utils.hooks import collect_submodules

# Collect all submodules of numpy.core to ensure they are included
hiddenimports = collect_submodules('numpy.core')