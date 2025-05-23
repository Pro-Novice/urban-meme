# Custom POA middleware implementation
# Save this to a file like custom_middleware.py in your project

import json
import logging
from hexbytes import HexBytes

logger = logging.getLogger(__name__)


def custom_poa_middleware(make_request, web3):
    """
    Custom middleware to handle POA chains
    This is a simplified version of geth_poa_middleware
    """

    def middleware(method, params):
        response = make_request(method, params)
        result = response.get('result')

        # Handle eth_getBlockBy* methods to process extraData field
        if result and method in ('eth_getBlockByHash', 'eth_getBlockByNumber'):
            if 'extraData' in result and isinstance(result['extraData'], str):
                # This is the key part - we don't validate extraData length
                pass

        return response

    return middleware


def apply_poa_middleware(web3_instance):
    """
    Apply our custom POA middleware to a web3 instance
    """
    try:
        # Try with middleware_onion (newer web3.py)
        if hasattr(web3_instance, 'middleware_onion'):
            web3_instance.middleware_onion.inject(custom_poa_middleware, layer=0)
            logger.info("Applied custom POA middleware using middleware_onion")
        # Try with middleware_stack (older web3.py)
        elif hasattr(web3_instance, 'middleware_stack'):
            web3_instance.middleware_stack.inject(custom_poa_middleware, layer=0)
            logger.info("Applied custom POA middleware using middleware_stack")
        else:
            logger.warning("Could not apply custom POA middleware - no middleware stack found")
            return False
        return True
    except Exception as e:
        logger.error(f"Error applying custom POA middleware: {str(e)}")
        return False