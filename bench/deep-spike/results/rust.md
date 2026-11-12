| Runtime | detector | precision | threads | n | token ids equal | max abs diff vs Python ORT | mean abs diff | median ms/text | of which model forward | p90 ms | median tokens | peak RSS MB |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ort-dyn | bino | fp32 | 1 | 120 | 120/120 | 2.34e-14 | 1.22e-15 | 498 | 370 | 598 | 444 | 2629 |
| ort-dyn | bino | fp32 | 4 | 120 | 120/120 | 2.34e-14 | 1.22e-15 | 440 | 311 | 540 | 444 | 2418 |
| ort-dyn | bino | int8 | 4 | 120 | 120/120 | 1.38e-14 | 9.50e-16 | 468 | 334 | 550 | 444 | 1892 |
| ort-dyn | fdgpt-neo125 | fp16 | 4 | 120 | 120/120 | 5.56e-13 | 1.31e-13 | 393 | 312 | 467 | 447 | 1134 |
| ort-dyn | fdgpt-neo125 | fp32 | 1 | 120 | 120/120 | 9.35e-14 | 2.42e-14 | 235 | 154 | 271 | 447 | 1501 |
| ort-dyn | fdgpt-neo125 | fp32 | 4 | 120 | 120/120 | 9.35e-14 | 2.42e-14 | 188 | 110 | 221 | 447 | 1513 |
| ort-dyn | fdgpt-neo125 | int8 | 4 | 120 | 120/120 | 6.86e-14 | 2.15e-14 | 194 | 112 | 232 | 447 | 1134 |
| ort-dyn | fdgpt-smollm2-135m | fp32 | 1 | 120 | 120/120 | 8.19e-14 | 2.37e-14 | 267 | 182 | 326 | 444 | 1496 |
| ort-dyn | fdgpt-smollm2-135m | fp32 | 4 | 120 | 120/120 | 8.19e-14 | 2.37e-14 | 229 | 150 | 271 | 444 | 1383 |
| ort-dyn | fdgpt-smollm2-135m | int8 | 4 | 120 | 120/120 | 1.14e-13 | 2.58e-14 | 246 | 163 | 289 | 444 | 1074 |
| rten | bino | fp32 | 4 | 120 | 120/120 | 1.35e-06 | 1.97e-07 | 870 | 734 | 1001 | 444 | 2393 |
| rten | bino | int8 | 4 | 120 | 120/120 | 2.01e-01 | 4.64e-02 | 516 | 385 | 587 | 444 | 1678 |
| rten | fdgpt-neo125 | fp32 | 1 | 120 | 120/120 | 3.64e-05 | 9.35e-06 | 1110 | 1023 | 1290 | 447 | 1566 |
| rten | fdgpt-neo125 | fp32 | 4 | 120 | 120/120 | 3.64e-05 | 9.35e-06 | 390 | 307 | 455 | 447 | 1486 |
| rten | fdgpt-neo125 | int8 | 4 | 120 | 120/120 | 5.39e+00 | 1.46e+00 | 263 | 169 | 300 | 447 | 1177 |
| rten | fdgpt-smollm2-135m | fp32 | 4 | 120 | 120/120 | 1.94e-05 | 4.61e-06 | 438 | 350 | 514 | 444 | 1462 |
| rten | fdgpt-smollm2-135m | int8 | 4 | 120 | 120/120 | 3.27e+00 | 1.02e+00 | 272 | 185 | 314 | 444 | 1068 |

| int8, same texts | n | max abs diff | mean abs diff |
|---|---|---|---|
| bino: rten vs ort (Rust) | 120 | 2.01e-01 | 4.64e-02 |
| fdgpt-smollm2-135m: rten vs ort (Rust) | 120 | 3.27e+00 | 1.02e+00 |
| fdgpt-neo125: rten vs ort (Rust) | 120 | 5.39e+00 | 1.46e+00 |
