from uuid import UUID
from json import JSONEncoder
import random
import logging

logger = logging.getLogger(__name__)

class UUIDEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return str(obj)
        return JSONEncoder.default(self, obj)