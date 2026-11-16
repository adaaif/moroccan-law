"""A refusal the clients translate (`errors.<field>.<code>`): the server sends no sentences. `extra` carries data the
sentence needs (a suggested address, the minutes to wait), never words."""


class Refused(Exception):
    def __init__(self, field: str, code: str, status: int = 400, **extra):
        super().__init__(f'{field}.{code}')
        self.field, self.code, self.status, self.extra = field, code, status, extra
