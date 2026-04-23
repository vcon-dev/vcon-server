import importlib
import inspect
import time
import types
from typing import Optional

from lib.logging_utils import init_logger
from config import get_config


_imported_modules: dict[str, types.ModuleType] = {}


logger = init_logger(__name__)


def _validate_storage_module(module: types.ModuleType, module_name: str) -> None:
    """Enforce the storage-backend contract.

    Every backend module must expose:
        - ``default_options``: a dict (may be empty)
        - ``save(vcon_uuid, opts)``: a callable accepting at least 2 positional args

    Optionally:
        - ``get(vcon_uuid, opts)``, ``delete(vcon_uuid, opts)``: callables if present

    Raises:
        TypeError: if the module does not satisfy the contract. Surfacing this
            at import time (inside ``Storage.__init__``) keeps silent chain
            failures from masquerading as "storage skipped" in logs.
    """
    if not hasattr(module, "default_options"):
        raise TypeError(
            f"storage backend {module_name!r} is missing required `default_options`"
        )
    if not isinstance(module.default_options, dict):
        raise TypeError(
            f"storage backend {module_name!r}: default_options must be a dict, "
            f"got {type(module.default_options).__name__}"
        )

    save = getattr(module, "save", None)
    if not callable(save):
        raise TypeError(
            f"storage backend {module_name!r}: `save` is missing or not callable"
        )
    params = list(inspect.signature(save).parameters.values())
    positional = [
        p for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY)
    ]
    if len(positional) < 2:
        raise TypeError(
            f"storage backend {module_name!r}: save() must accept at least 2 "
            f"positional args (vcon_uuid, opts); got signature {inspect.signature(save)}"
        )

    for optional in ("get", "delete"):
        attr = getattr(module, optional, None)
        if attr is not None and not callable(attr):
            raise TypeError(
                f"storage backend {module_name!r}: `{optional}` exists but is not callable"
            )


def log_metrics(func):
    """Decorator to log the time taken to run the storage module"""

    def wrapper(self, vcon_id):
        started = time.time()
        logger.info(
            "Running storage %s module %s %s for vCon: %s",
            self.storage_name,
            self.module_name,
            func.__name__,
            vcon_id,
        )
        result = func(self, vcon_id)
        storage_processing_time = round(time.time() - started, 3)
        logger.info(
            "Finished storage %s module %s %s for vCon: %s in %s seconds.",
            self.storage_name,
            self.module_name,
            func.__name__,
            vcon_id,
            storage_processing_time,
            extra={"storage_processing_time": storage_processing_time},
        )
        return result

    return wrapper


class Storage:
    options: dict = None
    module: types.ModuleType = None
    module_name: str = None
    storage_name: str = None

    def __init__(self, storage_name: str) -> None:
        self.storage_name = storage_name
        config = get_config()
        storage = config["storages"][self.storage_name]
        self.module_name = storage["module"]

        if self.module_name not in _imported_modules:
            module = importlib.import_module(self.module_name)
            _validate_storage_module(module, self.module_name)
            _imported_modules[self.module_name] = module
        self.module = _imported_modules[self.module_name]
        self.options = storage.get("options", self.module.default_options)

    @log_metrics
    def save(self, vcon_id) -> None:
        self.module.save(vcon_id, self.options)

    @log_metrics
    def get(self, vcon_id) -> Optional[dict]:
        if hasattr(self.module, "get"):
            return self.module.get(vcon_id, self.options)
        return None

    @log_metrics
    def delete(self, vcon_id) -> bool:
        if hasattr(self.module, "delete"):
            return self.module.delete(vcon_id, self.options)
        return False
