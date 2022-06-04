import json
from pathlib import Path


# class PayeeFormatter:
#     def __init__(self):
#         self._db_filepath = Path("bourso2ynab/payee_name_fix.json")
#         self._load_db()

#     def format(self, payee: str) -> str:
#         return self.db.get(payee, payee)

#     def add_formatting_rule(self, unformatted_payee: str, formatted_payee: str) -> str:
#         self.db[unformatted_payee] = formatted_payee

#     def __enter__(self):
#         return self

#     def __exit__(self, exc_type, exc_value, exc_traceback):
#         self._db_filepath.write_text(json.dumps(self.db, indent=4, sort_keys=True))

#     def _load_db(self):
#         # TODO: find a better way to handle resources
#         # TODO: even better: put this into an actual database.
#         self.db = json.loads(self._db_filepath.read_text())
