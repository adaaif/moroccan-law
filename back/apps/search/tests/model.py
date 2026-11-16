"""The meaning model's third-party pieces as the project meets them (B7 of the search plan): `tokenizers.Tokenizer` gives
a text's ids (the start token first, then one id a word), truncated as the real one is once `enable_truncation` is set
(the ids cut to that length, the rest in `overflowing`, each piece opened by the start token again);
`onnxruntime.InferenceSession` runs the model, a vector of 1024 a text (bge-m3's size), its words' meanings counted.
The project's own Encoder, pieces, the model server, the passages and the ranking run on them for real (the fixtures
`model` and `served` are in conftest.py)."""
from types import SimpleNamespace as NS

import numpy as np

DIM = 1024
# Words that mean the same: every other word is a meaning of its own.
MEANINGS = {'الكراء': 1, 'المكتري': 1, 'المكري': 1, 'السكنى': 1, 'loyer': 1, 'الإفراغ': 2, 'إخلاء': 2, 'expulsion': 2,
            'الأجير': 3, 'الشغل': 3, 'العمل': 3, 'اللغة': 4, 'العربية': 4, 'اللغات': 4}


def meaning(word: str) -> int:
    word = word.strip('.,:؛،«»()')
    return MEANINGS.get(word) or 10 + sum(map(ord, word)) % (DIM - 10)


class Tokenizer:
    files: list[str] = []          # the files it was read from
    read: list[str] = []           # every text encoded, in order

    def __init__(self):
        self.most = None

    @classmethod
    def from_file(cls, path):
        cls.files.append(path)
        return cls()

    def enable_truncation(self, size):
        self.most = size

    def encode(self, text):
        Tokenizer.read.append(text)
        ids = [0] + [meaning(w) for w in text.split()]
        if not self.most or len(ids) <= self.most:
            return NS(ids=ids, overflowing=[])
        rest, step = ids[self.most:], self.most - 1
        return NS(ids=ids[:self.most], overflowing=[NS(ids=[0, *rest[k:k + step]], overflowing=[])
                                                    for k in range(0, len(rest), step)])

    def encode_batch(self, texts):
        return [self.encode(t) for t in texts]


class Session:
    output = 'sentence_embedding'  # 'last_hidden_state': a vector a token, the start token's the text's
    made: list[tuple] = []          # (model file, threads, providers) of each session

    def __init__(self, path, options, providers):
        Session.made.append((path, options.intra_op_num_threads, providers))

    def get_outputs(self):
        return [NS(name=self.output)]

    def run(self, names, feeds):
        ids, mask = feeds['input_ids'], feeds['attention_mask']
        out = np.zeros((len(ids), DIM), dtype=np.float32)
        for row, (line, seen) in enumerate(zip(ids, mask)):
            for i in line[seen == 1]:
                out[row, i] += 0.5 if i == 0 else 1       # the start token on every text: a little alike, as real ones
        if self.output == 'last_hidden_state':
            hidden = np.full((len(ids), ids.shape[1], DIM), 7.0, dtype=np.float32)
            hidden[:, 0] = out
            return [hidden]
        return [out]


def vector(text: str) -> list[float]:
    """What the model gives a text alone, as the project's Encoder reads it."""
    from apps.search.services.meaning import Encoder
    return Encoder().encode([text])[0].tolist()


def stored(passage) -> np.ndarray:
    """A passage's vector as the database gives it back (a half-precision vector on PostgreSQL, a list elsewhere)."""
    v = passage.vector
    return np.array(v.to_list() if hasattr(v, 'to_list') else v, dtype=np.float32)
