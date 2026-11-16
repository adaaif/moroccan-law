"""The Message Batches API as these tests meet it: the `anthropic` client replaced by one that answers each request at
once, in the API's own shapes (a batch with an id, its status, its results by custom_id, a message with its model,
usage, stop reason and text blocks). Nothing of the project is replaced: the budget, the ledger, the requests and the
reading of the answers all run."""
import json
from types import SimpleNamespace as NS


class Batches:
    def __init__(self, answer):
        self.answer, self.sent = answer, {}
        self.refusals = []          # the API's answers to the next creates: None (taken) or (status, message)

    def create(self, requests):
        if self.refusals and (refused := self.refusals.pop(0)):
            raise refusal(*refused)
        bid = f'msgbatch_{len(self.sent) + 1:02d}'
        self.sent[bid] = list(requests)
        return NS(id=bid, processing_status='in_progress')

    def retrieve(self, bid):
        return NS(id=bid, processing_status='ended')

    def results(self, bid):
        for r in self.sent[bid]:
            said = self.answer(r['custom_id'], r['params'])
            if said is None:                                    # the API could not answer this one
                yield NS(custom_id=r['custom_id'], result=NS(type='errored'))
                continue
            stop = 'end_turn'
            if isinstance(said, tuple):                         # (text, stop reason): an answer cut short
                said, stop = said
            text = said if isinstance(said, str) else json.dumps(said, ensure_ascii=False)
            message = NS(model=r['params']['model'], stop_reason=stop, usage=NS(input_tokens=2000, output_tokens=400),
                         content=[NS(type='thinking', thinking='…'), NS(type='text', text=text)])
            yield NS(custom_id=r['custom_id'], result=NS(type='succeeded', message=message))

    def requests(self) -> list[dict]:
        return [r for group in self.sent.values() for r in group]


def refusal(status: int, message: str):
    """The error the SDK raises when the API refuses a request, as it builds it."""
    import anthropic
    import httpx2

    response = httpx2.Response(status, request=httpx2.Request('POST', 'https://api.anthropic.com/v1/messages/batches'))
    return anthropic.APIStatusError(message, response=response, body=None) if status != 400 else \
        anthropic.BadRequestError(message, response=response, body=None)


class Claude:
    def __init__(self, answer):
        self.messages = NS(batches=Batches(answer), create=self.create)
        self.answer = answer

    def create(self, **params):
        """One message at once (no batch): answered as a batch's request with the custom id «message»."""
        said = self.answer('message', params)
        return NS(model=params['model'], stop_reason='end_turn', usage=NS(input_tokens=2000, output_tokens=400),
                  content=[NS(type='text', text=json.dumps(said, ensure_ascii=False))])

    def with_options(self, **kw):
        return self


def install(monkeypatch, settings, tmp_path, answer) -> Batches:
    """The client every paid step builds answers with `answer(custom_id, params)`: a dict (the JSON the schema asked
    for), a string, `(text, stop_reason)`, or None (errored). The ledger and the budget's holds live under tmp_path;
    the permission to spend is this test's alone; the poll's sleep does not wait."""
    import anthropic

    from apps.sources.services.ocr import batches, guard

    settings.CORPUS_DIR = tmp_path
    settings.ANTHROPIC_API_KEY = 'sk-ant-test'
    client = Claude(answer)
    monkeypatch.setattr(anthropic, 'Anthropic', lambda **kw: client)
    monkeypatch.setattr(guard, '_SPENDING', False)
    monkeypatch.setattr(batches.time, 'sleep', lambda seconds: None)
    return client.messages.batches
