import logging
from functools import wraps

# Configure logging (you can customize this)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def trace_execution(func):
    """Decorator to log function calls, arguments, and return values."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            logger.info(f"Calling function: {func.__name__} with args: {args}, kwargs: {kwargs}")
            result = func(*args, **kwargs)
            logger.info(f"Function: {func.__name__} returned: {result}")
            return result
        except Exception as e:
            logger.error(f"Error in function: {func.__name__}: {e}", exc_info=True)
    return wrapper
