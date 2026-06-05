import sys
import os
from datetime import datetime, timezone

print("datetime.now():", datetime.now())
print("datetime.utcnow():", datetime.utcnow())
print("datetime.now(timezone.utc):", datetime.now(timezone.utc))
try:
    import time
    print("time.tzname:", time.tzname)
except Exception as e:
    print("Error getting tzname:", e)
