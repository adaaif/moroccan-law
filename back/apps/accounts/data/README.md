# Email-check data

Read by `apps/accounts/services/addresses.py` (sign-up and a new address refuse a throwaway inbox).
Built on 2 Oct 2026 from the two public lists below, and brought into this project on 3 Nov 2026.

| File | What | Edited by |
|---|---|---|
| `disposable_domains.txt` | throwaway-inbox domains, merged from the two lists below | generated (this repository has no command to rebuild it yet) |
| `disposable_extra.txt` | our own additions (a domain the lists missed, the RFC 2606 example domains) | hand |
| `disposable_allow.txt` | never treated as throwaway, whatever the lists say | hand |

A sub-domain of a listed domain is caught too (`x.yopmail.com`).

## Sources and licenses

- **disposable-email-domains** — https://github.com/disposable-email-domains/disposable-email-domains —
  CC0 1.0 Universal (public domain dedication).
- **fakefilter** — https://github.com/7c/fakefilter — BSD 3-Clause License, reproduced below.

```
BSD 3-Clause License

Copyright (c) 2022, 7c
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```
