# Spike S0 results

Trajectories: 10 · valid questions: 199 · total tokens: 38,057,831

## Recall by arm (% score; identifier = exact match, others = blind judge, partial = 0.5)

| arm | overall | identifier | decision | dead_end | state |
|---|---|---|---|---|---|
| raw | 96.5 | 96.0 | 98.0 | 98.0 | 94.0 |
| summary | 60.1 | 70.0 | 74.0 | 32.7 | 63.0 |
| board_flash | 97.5 | 96.0 | 99.0 | 95.9 | 99.0 |
| board_pro | 95.2 | 96.0 | 95.0 | 94.9 | 95.0 |

## Per trajectory (overall %)

| trajectory | repo | raw | summary | board_flash | board_pro |
|---|---|---|---|---|---|
| chatcmpl-180 | falconry/falcon | 90.0 | 22.5 | 87.5 | 80.0 |
| chatcmpl-289 | geopandas/geopandas | 95.0 | 70.0 | 100.0 | 97.5 |
| chatcmpl-40e | tobymao/sqlglot | 100.0 | 55.0 | 100.0 | 100.0 |
| chatcmpl-76a | MycroftAI/lingua-franca | 97.4 | 52.6 | 100.0 | 97.4 |
| chatcmpl-795 | catalystneuro/neuroconv | 100.0 | 85.0 | 100.0 | 100.0 |
| chatcmpl-797 | pydap/pydap | 95.0 | 87.5 | 95.0 | 97.5 |
| chatcmpl-976 | facelessuser/pymdown-extensions | 100.0 | 52.5 | 100.0 | 100.0 |
| chatcmpl-c7a | nilearn/nilearn | 100.0 | 52.5 | 100.0 | 100.0 |
| chatcmpl-e2d | idaholab/MontePy | 87.5 | 62.5 | 92.5 | 85.0 |
| chatcmpl-f6c | pandas-dev/pandas | 100.0 | 60.0 | 100.0 | 95.0 |

## Mechanical checks

| trajectory | raw tok (compressed part) | summary tok | board_flash tok | board_pro tok | verbatim miss flash | verbatim miss pro | prefix ok |
|---|---|---|---|---|---|---|---|
| chatcmpl-180 | 31283 | 1426 | 27990 | 14027 | 14/787 | 15/349 | True |
| chatcmpl-289 | 30677 | 2142 | 24741 | 17653 | 14/590 | 10/480 | True |
| chatcmpl-40e | 30547 | 1833 | 37583 | 21808 | 88/1189 | 10/917 | True |
| chatcmpl-76a | 40423 | 2996 | 42377 | 24536 | 42/1119 | 8/654 | True |
| chatcmpl-795 | 31043 | 1842 | 30267 | 19387 | 7/608 | 22/512 | True |
| chatcmpl-797 | 20402 | 1401 | 16748 | 10521 | 15/489 | 3/444 | True |
| chatcmpl-976 | 41228 | 1886 | 38715 | 23967 | 17/957 | 14/661 | True |
| chatcmpl-c7a | 41040 | 1866 | 40080 | 27107 | 21/951 | 50/721 | True |
| chatcmpl-e2d | 41504 | 2271 | 34979 | 26645 | 7/668 | 12/714 | True |
| chatcmpl-f6c | 52697 | 2455 | 49145 | 33479 | 26/1367 | 31/912 | True |

board_flash: scribe turns that failed after retry (left empty): 19
board_flash: verbatim hallucination rate 2.9% (251/8725); examples: `'Response.stream must be a generator or implement an __aiter__ method. Error raised while iterating over Response.stream: '`; `kwargs.pop`; `/workspace/tobymao__sqlglot__18.6/tests/test_generator.py`; `/workspace/MycroftAI__lingua-franca__0.1/lingua_franca/lang/format_common.py`; `PYTHONPATH=src`; `IndexError: list index out of range`; `.tabbed-block`; `self._cache(image.resample_img, func_memory_level=2)`; `...[8231 chars clipped]...`; `meson 1.2.1`

board_pro: scribe turns that failed after retry (left empty): 0
board_pro: verbatim hallucination rate 2.7% (175/6364); examples: `Response.stream must be a generator or implement an '__aiter__' method. Error raised while iterating over 'Response.stream': `; `ValueError(
                    "CRS is not set. Cannot re-project to WGS84 (EPSG:4326)."
                )`; `"delta.dataSkippingNumIndexedCols"`; `extract_numbers('this is a one twenty one  test') == [1.0, 21.0]`; `[tool.ruff.lint.per-file-ignores]`; `./src/pydap/model.py`; `START = re.compile(
        r'(?:^|\n)={3}(\+|\+!|!\+|!)? +"(.*?)" *(?:\n|$)'
    )`; `760:	        region_ids = {"background": self.background_label}`; `syntax_node.SyntaxNode(
            "m

## Scribe prompt-cache stats (tokens)

- deepseek-v4.1-flash: input 1330473, cache read 18659968, cache write 0, output 715913 · read share 93.3%
- deepseek-v4-pro: input 1229252, cache read 11570176, cache write 0, output 828396 · read share 90.4%

## Tokens by step (Ark agent plan is flat-rate)

- answer:board_flash: 499,150
- answer:board_pro: 351,723
- answer:raw: 522,299
- answer:summary: 208,834
- handoff: 650,349
- judge: 134,274
- questions: 515,461
- scribe:flash: 20,706,354
- scribe:pro: 13,627,824
- summary: 841,563
