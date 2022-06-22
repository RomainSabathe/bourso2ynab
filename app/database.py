import os

from pysondb import PysonDB
from dotenv import load_dotenv

load_dotenv()

db = PysonDB(os.environ["DB_FILEPATH"])