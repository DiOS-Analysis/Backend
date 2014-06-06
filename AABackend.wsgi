import sys
import os
sys.stdout = sys.stderr
appDir = os.path.dirname(__file__)
os.environ['AABACKEND_BASEDIR'] = appDir
os.environ['AABACKEND_SETTINGS'] = "%s/backend.cfg" % (appDir)
sys.path.insert(0, appDir)
from backend import app as application
