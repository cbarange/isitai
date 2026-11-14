## Accuracy (fixed subsamples; threshold = 1 % false positives on `test`)

| Run | AUROC test | ood | fr | fiction | attack | TPR test | ood TPR/FPR | fr TPR/FPR | fiction TPR/FPR | attack TPR/FPR | thr@1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| bino.smollm2-135m+smollm2-135m-instruct.onnx-fp32 | 0.828 | 0.947 | 0.814 | 0.697 | 0.789 | 70 | 86 / 6 | 47 / 9 | 31 / 1 | 60 / 12 | -0.8802 |
| bino.smollm2-135m+smollm2-135m-instruct.onnx-int8-matmul | 0.822 | 0.953 | 0.804 | - | - | 67 | 82 / 4 | 24 / 4 | - | - | -0.8194 |
| bino.smollm2-135m+smollm2-135m-instruct.onnx-int8 | 0.821 | 0.955 | 0.803 | 0.670 | 0.793 | 67 | 82 / 2 | 20 / 4 | 14 / 0 | 55 / 10 | -0.8115 |
| fdgpt.neo125.onnx-fp32 | 0.800 | 0.938 | 0.818 | 0.646 | 0.750 | 60 | 75 / 1 | 22 / 2 | 28 / 3 | 42 / 2 | 2.2146 |
| fdgpt.neo125.onnx-int8 | 0.800 | 0.920 | 0.795 | 0.625 | 0.720 | 60 | 70 / 2 | 15 / 0 | 2 / 0 | 55 / 20 | -0.4381 |
| fdgpt.smollm2-135m.onnx-fp32 | 0.793 | 0.908 | 0.767 | 0.631 | 0.732 | 61 | 74 / 4 | 29 / 8 | 40 / 7 | 48 / 16 | 1.8485 |
| fdgpt.smollm2-135m.onnx-int8-matmul | 0.790 | 0.913 | 0.730 | - | - | 59 | 77 / 5 | 14 / 2 | - | - | 2.0686 |
| fdgpt.smollm2-135m.onnx-int8 | 0.790 | 0.911 | 0.743 | 0.613 | 0.723 | 58 | 74 / 5 | 10 / 0 | 41 / 14 | 46 / 14 | 2.0848 |

## Parity with the benchmark's PyTorch fp32 scores (same ids)

| Run | reference | n | max abs diff | mean abs diff |
|---|---|---|---|---|
| bino.smollm2-135m+smollm2-135m-instruct.onnx-fp32 | binoculars_small.smollm2-135m (torch fp32) | 1800 | 4.79e-05 | 2.90e-05 |
| bino.smollm2-135m+smollm2-135m-instruct.onnx-int8 | binoculars_small.smollm2-135m (torch fp32) | 1800 | 2.15e-01 | 4.99e-02 |
| fdgpt.neo125.onnx-fp32 | fast_detectgpt.neo125 (torch fp32) | 1800 | 1.11e-03 | 6.15e-04 |
| fdgpt.neo125.onnx-int8 | fast_detectgpt.neo125 (torch fp32) | 1800 | 6.65e+00 | 3.12e+00 |

## Quantised versus ONNX fp32 of the same detector (benchmark texts of the splits both runs scored: 1,800, or 1,200 for int8-matmul)

| Run | Spearman | max abs diff | mean abs diff | score sd (fp32) | at the fp32 threshold: test TPR/FPR | fr TPR/FPR | ood TPR/FPR |
|---|---|---|---|---|---|---|---|
| bino.smollm2-135m+smollm2-135m-instruct.onnx-int8-matmul | 0.9702 | 0.260 | 0.044 | 0.149 | 76 / 10 | 64 / 18 | 94 / 15 |
| bino.smollm2-135m+smollm2-135m-instruct.onnx-int8 | 0.9683 | 0.215 | 0.050 | 0.140 | 76 / 16 | 64 / 18 | 94 / 16 |
| fdgpt.neo125.onnx-int8 | 0.8545 | 6.651 | 3.116 | 2.471 | 24 / 0 | 0 / 0 | 24 / 0 |
| fdgpt.smollm2-135m.onnx-int8-matmul | 0.9322 | 2.671 | 0.513 | 2.294 | 62 / 3 | 16 / 4 | 82 / 7 |
| fdgpt.smollm2-135m.onnx-int8 | 0.9255 | 2.606 | 0.550 | 2.267 | 62 / 4 | 14 / 1 | 79 / 6 |

## Wikipedia humans (corpus/text, 117 texts): flagged at the run's own thr@1, per language

| Run | all | ar | de | en | es | fr | it | ja | nl | pl | pt | ru | zh | ai-snowman |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| bino.smollm2-135m+smollm2-135m-instruct.onnx-fp32 | 1/117 | 0/10 | 0/10 | 0/10 | 0/10 | 1/10 | 0/10 | 0/9 | 0/10 | 0/10 | 0/9 | 0/10 | 0/9 | missed |
| bino.smollm2-135m+smollm2-135m-instruct.onnx-int8 | 0/117 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/9 | 0/10 | 0/10 | 0/9 | 0/10 | 0/9 | missed |
| fdgpt.neo125.onnx-fp32 | 2/117 | 0/10 | 0/10 | 0/10 | 0/10 | 1/10 | 0/10 | 0/9 | 0/10 | 0/10 | 1/9 | 0/10 | 0/9 | flagged |
| fdgpt.neo125.onnx-int8 | 0/117 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/9 | 0/10 | 0/10 | 0/9 | 0/10 | 0/9 | missed |
| fdgpt.smollm2-135m.onnx-fp32 | 9/117 | 1/10 | 0/10 | 0/10 | 1/10 | 4/10 | 0/10 | 0/9 | 2/10 | 0/10 | 1/9 | 0/10 | 0/9 | flagged |
| fdgpt.smollm2-135m.onnx-int8 | 0/117 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/10 | 0/9 | 0/10 | 0/10 | 0/9 | 0/10 | 0/9 | missed |

## Golden set (bench/golden, v1.0): human class flagged at the run's own thr@1, Wilson 95 %

| Run | fr humans flagged (n=75, 9 documents) | en humans flagged (n=75, 27 documents) | fr AI flagged (n=50) | en AI flagged (n=50) | AUROC fr | AUROC en |
|---|---|---|---|---|---|---|
| bino.smollm2-135m+smollm2-135m-instruct.onnx-fp32 | 0/75 = 0 % [0, 5] | 0/75 = 0 % [0, 5] | 0/50 = 0 % [0, 7] | 0/50 = 0 % [0, 7] | 0.804 | 0.357 |
| bino.smollm2-135m+smollm2-135m-instruct.onnx-int8 | 0/75 = 0 % [0, 5] | 0/75 = 0 % [0, 5] | 0/50 = 0 % [0, 7] | 0/50 = 0 % [0, 7] | 0.561 | 0.202 |
| fdgpt.neo125.onnx-fp32 | 0/75 = 0 % [0, 5] | 0/75 = 0 % [0, 5] | 1/50 = 2 % [0, 10] | 0/50 = 0 % [0, 7] | 0.846 | 0.730 |
| fdgpt.neo125.onnx-int8 | 0/75 = 0 % [0, 5] | 0/75 = 0 % [0, 5] | 0/50 = 0 % [0, 7] | 0/50 = 0 % [0, 7] | 0.822 | 0.882 |
| fdgpt.smollm2-135m.onnx-fp32 | 0/75 = 0 % [0, 5] | 0/75 = 0 % [0, 5] | 1/50 = 2 % [0, 10] | 0/50 = 0 % [0, 7] | 0.825 | 0.542 |
| fdgpt.smollm2-135m.onnx-int8 | 0/75 = 0 % [0, 5] | 0/75 = 0 % [0, 5] | 0/50 = 0 % [0, 7] | 0/50 = 0 % [0, 7] | 0.538 | 0.289 |

## Per-language threshold sketch: French threshold = 1 % false positives on the human texts of `test_fr` (n=200)

| Run | thr en (test) | thr fr (test_fr) | test_fr TPR at thr fr | Wikipedia fr humans flagged | golden fr humans flagged | golden fr AI flagged |
|---|---|---|---|---|---|---|
| bino.smollm2-135m+smollm2-135m-instruct.onnx-fp32 | -0.8802 | -0.8303 | 20 | 0/10 | 0/75 [0, 5] | 0/50 |
| bino.smollm2-135m+smollm2-135m-instruct.onnx-int8 | -0.8115 | -0.7876 | 10 | 0/10 | 0/75 [0, 5] | 0/50 |
| fdgpt.neo125.onnx-fp32 | 2.2146 | 2.4502 | 18 | 1/10 | 0/75 [0, 5] | 0/50 |
| fdgpt.neo125.onnx-int8 | -0.4381 | -1.5048 | 28 | 1/10 | 0/75 [0, 5] | 1/50 |
| fdgpt.smollm2-135m.onnx-fp32 | 1.8485 | 2.7455 | 16 | 1/10 | 0/75 [0, 5] | 0/50 |
| fdgpt.smollm2-135m.onnx-int8 | 2.0848 | 1.8066 | 14 | 1/10 | 0/75 [0, 5] | 0/50 |

## Python timing and memory (4 threads; machine shared, indicative)

| Run | median ms/text on test | peak RSS MB | load s |
|---|---|---|---|
| bino.smollm2-135m+smollm2-135m-instruct.onnx-fp32 | 804 | 4973 | 1.5 |
| bino.smollm2-135m+smollm2-135m-instruct.onnx-int8-matmul | 423 | 4029 | 0.6 |
| bino.smollm2-135m+smollm2-135m-instruct.onnx-int8 | 493 | 4391 | 0.6 |
| fdgpt.neo125.onnx-fp32 | 196 | 3864 | 0.3 |
| fdgpt.neo125.onnx-int8 | 198 | 3307 | 0.2 |
| fdgpt.smollm2-135m.onnx-fp32 | 431 | 3328 | 1.4 |
| fdgpt.smollm2-135m.onnx-int8-matmul | 229 | 3052 | 0.3 |
| fdgpt.smollm2-135m.onnx-int8 | 395 | 3070 | 0.4 |
