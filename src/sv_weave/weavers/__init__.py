"""Built-in weavers."""
from .compare import CompareWeaver
from .copy import CopyWeaver
from .print import PrintWeaver
from .xcheck import XCheckWeaver

BUILTIN = [CopyWeaver, CompareWeaver, PrintWeaver, XCheckWeaver]
