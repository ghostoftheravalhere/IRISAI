import os
import sys
import logging


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(fmt)
        logger.addHandler(stream_handler)
        logger.setLevel(logging.DEBUG)

        try:
            local_appdata = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            log_dir = os.path.join(local_appdata, "IRIS AI", "logs")
            os.makedirs(log_dir, exist_ok=True)

            # Master backend log
            backend_file = os.path.join(log_dir, "backend.log")
            fh_backend = logging.FileHandler(backend_file, encoding="utf-8")
            fh_backend.setFormatter(fmt)
            logger.addHandler(fh_backend)

            # Specialized domain loggers
            lower_name = name.lower()
            if any(k in lower_name for k in ("voice", "recognizer", "pipeline", "speech")):
                fh_voice = logging.FileHandler(os.path.join(log_dir, "voice.log"), encoding="utf-8")
                fh_voice.setFormatter(fmt)
                logger.addHandler(fh_voice)

            if any(k in lower_name for k in ("app_resolver", "dispatcher", "action_engine", "controller")):
                fh_resolver = logging.FileHandler(os.path.join(log_dir, "resolver.log"), encoding="utf-8")
                fh_resolver.setFormatter(fmt)
                logger.addHandler(fh_resolver)

            if any(k in lower_name for k in ("event", "bus", "api", "app")):
                fh_events = logging.FileHandler(os.path.join(log_dir, "events.log"), encoding="utf-8")
                fh_events.setFormatter(fmt)
                logger.addHandler(fh_events)
        except Exception:
            pass

    return logger
