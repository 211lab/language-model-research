# Case Study Readability Report

Comparable measurements for LESSON.md, index.md, and INSTRUCTIONS.md from every completed case study.

Markdown presentation syntax is removed before one deterministic English syllable heuristic is applied to every source. Scores are estimates, not editorial judgments.

## Bundle summary

| Model | Words | Sentences | Avg words/sentence | Flesch ease | FK grade | Fog | Coleman-Liau | ARI | SMOG | Lexical diversity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| anthropic/claude-opus-5 | 6585 | 587 | 11.22 | 77.99 | 5.17 | 8.14 | 6.69 | 4.31 | 8.91 | 0.17 |
| anthropic/claude-sonnet-5 | 3126 | 249 | 12.55 | 73.15 | 6.18 | 8.80 | 8.00 | 5.80 | 9.35 | 0.23 |
| cydonia-24b-v4.3 | 4673 | 341 | 13.70 | 60.39 | 8.24 | 11.40 | 10.21 | 7.98 | 11.26 | 0.18 |
| deepseek/deepseek-v3.2 | 3552 | 331 | 10.73 | 72.09 | 5.87 | 8.93 | 8.16 | 5.34 | 9.50 | 0.19 |
| deepseek/deepseek-v4-flash | 4736 | 470 | 10.08 | 76.03 | 5.16 | 8.17 | 7.31 | 4.47 | 8.96 | 0.17 |
| deepseek/deepseek-v4-pro | 5458 | 371 | 14.71 | 68.13 | 7.41 | 10.39 | 8.55 | 7.04 | 10.48 | 0.18 |
| dolphin-mistral-24b-venice | 1781 | 116 | 15.35 | 57.06 | 9.11 | 12.77 | 11.42 | 9.60 | 12.24 | 0.29 |
| gemma-4-12b-obliterated | 2084 | 111 | 18.77 | 49.31 | 11.05 | 14.92 | 11.85 | 11.37 | 13.78 | 0.22 |
| gemma-4-e4b-it | 2266 | 163 | 13.90 | 64.33 | 7.74 | 11.12 | 9.33 | 7.36 | 11.07 | 0.27 |
| google/gemini-3.5-flash-lite | 3351 | 208 | 16.11 | 60.31 | 8.85 | 11.57 | 10.41 | 9.09 | 11.33 | 0.21 |
| google/gemini-3.6-flash | 3681 | 239 | 15.40 | 51.10 | 9.96 | 13.08 | 12.33 | 10.34 | 12.46 | 0.29 |
| google/gemma-3-12b-it | 1995 | 136 | 14.67 | 48.19 | 10.18 | 13.71 | 12.60 | 10.27 | 12.82 | 0.27 |
| google/gemma-4-26b-a4b-it | 2559 | 187 | 13.68 | 63.28 | 7.83 | 11.18 | 9.62 | 7.51 | 11.11 | 0.26 |
| google/gemma-4-31b-it | 2475 | 170 | 14.56 | 64.18 | 7.92 | 10.98 | 9.02 | 7.36 | 10.95 | 0.28 |
| gemma-4-e4b-it | 2366 | 152 | 15.57 | 57.99 | 9.04 | 12.16 | 9.78 | 8.37 | 11.81 | 0.26 |
| nvidia/nemotron-3-ultra-550b-a55b | 4110 | 458 | 8.97 | 67.35 | 6.09 | 8.76 | 9.03 | 5.59 | 9.28 | 0.23 |
| openai/gpt-4.1 | 2687 | 260 | 10.33 | 70.66 | 5.97 | 9.06 | 8.89 | 5.81 | 9.57 | 0.22 |
| openai/gpt-5.4 | 6852 | 757 | 9.05 | 79.18 | 4.46 | 7.13 | 6.99 | 3.97 | 8.22 | 0.17 |
| openai/gpt-5.5 | 8510 | 1004 | 8.48 | 80.78 | 4.10 | 6.78 | 6.34 | 3.34 | 7.97 | 0.15 |
| openai/gpt-5.6-luna | 6319 | 590 | 10.71 | 65.15 | 6.83 | 9.66 | 9.17 | 6.14 | 9.99 | 0.17 |
| openai/gpt-5.6-sol | 7255 | 705 | 10.29 | 65.79 | 6.64 | 9.59 | 9.15 | 6.01 | 9.91 | 0.17 |
| openai/gpt-5.6-terra | 6451 | 596 | 10.82 | 69.27 | 6.29 | 9.15 | 8.40 | 5.56 | 9.65 | 0.18 |
| qwen/qwen3.7-plus | 2582 | 212 | 12.18 | 72.19 | 6.22 | 9.04 | 8.29 | 5.90 | 9.56 | 0.23 |
| qwen/qwen3.8-max | 6786 | 802 | 8.46 | 80.17 | 4.18 | 6.87 | 6.69 | 3.62 | 8.04 | 0.14 |
| qwen3.6-27b-heretic-neo-code | 3323 | 370 | 8.98 | 72.28 | 5.41 | 8.46 | 8.17 | 4.90 | 9.10 | 0.19 |
| qwen3.6-35b-hauhaucs-aggressive | 3518 | 395 | 8.91 | 77.58 | 4.65 | 7.53 | 6.79 | 3.78 | 8.50 | 0.19 |
| stepfun/step-3.7-flash | 5932 | 308 | 19.26 | 68.39 | 8.51 | 11.39 | 7.72 | 8.27 | 10.74 | 0.14 |
| tencent/hy3 | 2396 | 263 | 9.11 | 80.04 | 4.36 | 6.80 | 6.70 | 3.75 | 7.97 | 0.28 |
| unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-27b-ud-q4-k-xl | 3914 | 466 | 8.40 | 78.67 | 4.37 | 7.59 | 6.34 | 3.33 | 8.51 | 0.19 |
| unsloth-qwen3-6-35b-a3b-mtp-gguf-qwen3-6-35b-a3b-ud-q4-k-s | 4611 | 577 | 7.99 | 83.15 | 3.65 | 6.55 | 5.90 | 2.92 | 7.81 | 0.14 |
| unsloth-qwen3-8-27b-gguf-qwen3-8-27b-ud-q4-k-xl | 4734 | 639 | 7.41 | 88.86 | 2.71 | 5.45 | 4.24 | 1.52 | 7.00 | 0.15 |
| x-ai/grok-4.3 | 1456 | 94 | 15.49 | 66.25 | 7.87 | 10.18 | 9.07 | 7.77 | 10.22 | 0.32 |
| x-ai/grok-4.5 | 4923 | 396 | 12.43 | 76.14 | 5.73 | 8.30 | 7.49 | 5.35 | 8.93 | 0.18 |

## Per-document measurements

| Model | Document | Words | Sentences | Paragraphs | Avg words/sentence | Flesch ease | FK grade | Fog |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| anthropic/claude-opus-5 | LESSON.md | 2234 | 212 | 39 | 10.54 | 79.09 | 4.85 | 7.83 |
| anthropic/claude-opus-5 | index.md | 2049 | 205 | 52 | 10.00 | 80.30 | 4.54 | 7.63 |
| anthropic/claude-opus-5 | INSTRUCTIONS.md | 2302 | 170 | 52 | 13.54 | 74.28 | 6.26 | 9.12 |
| anthropic/claude-sonnet-5 | LESSON.md | 1087 | 97 | 23 | 11.21 | 76.54 | 5.37 | 8.20 |
| anthropic/claude-sonnet-5 | index.md | 1056 | 92 | 24 | 11.48 | 73.73 | 5.83 | 8.49 |
| anthropic/claude-sonnet-5 | INSTRUCTIONS.md | 983 | 60 | 9 | 16.38 | 67.57 | 7.91 | 10.26 |
| cydonia-24b-v4.3 | LESSON.md | 1563 | 134 | 41 | 11.66 | 60.98 | 7.65 | 10.65 |
| cydonia-24b-v4.3 | index.md | 1579 | 121 | 30 | 13.05 | 62.22 | 7.82 | 10.94 |
| cydonia-24b-v4.3 | INSTRUCTIONS.md | 1531 | 88 | 37 | 17.40 | 56.94 | 9.64 | 12.99 |
| deepseek/deepseek-v3.2 | LESSON.md | 1315 | 131 | 22 | 10.04 | 76.15 | 5.13 | 8.15 |
| deepseek/deepseek-v3.2 | index.md | 1305 | 131 | 23 | 9.96 | 76.40 | 5.08 | 8.09 |
| deepseek/deepseek-v3.2 | INSTRUCTIONS.md | 932 | 69 | 9 | 13.51 | 59.60 | 8.30 | 11.50 |
| deepseek/deepseek-v4-flash | LESSON.md | 1422 | 156 | 30 | 9.12 | 76.69 | 4.83 | 8.01 |
| deepseek/deepseek-v4-flash | index.md | 2012 | 234 | 44 | 8.60 | 78.65 | 4.43 | 7.57 |
| deepseek/deepseek-v4-flash | INSTRUCTIONS.md | 1302 | 80 | 32 | 16.27 | 68.35 | 7.77 | 10.41 |
| deepseek/deepseek-v4-pro | LESSON.md | 1408 | 108 | 14 | 13.04 | 70.91 | 6.61 | 9.79 |
| deepseek/deepseek-v4-pro | index.md | 1407 | 108 | 14 | 13.03 | 70.89 | 6.61 | 9.79 |
| deepseek/deepseek-v4-pro | INSTRUCTIONS.md | 2643 | 155 | 35 | 17.05 | 64.63 | 8.48 | 11.26 |
| dolphin-mistral-24b-venice | LESSON.md | 436 | 28 | 7 | 15.57 | 57.92 | 9.05 | 13.20 |
| dolphin-mistral-24b-venice | index.md | 530 | 33 | 8 | 16.06 | 68.90 | 7.64 | 11.18 |
| dolphin-mistral-24b-venice | INSTRUCTIONS.md | 815 | 55 | 11 | 14.82 | 48.86 | 10.13 | 13.58 |
| gemma-4-12b-obliterated | LESSON.md | 604 | 34 | 8 | 17.76 | 49.86 | 10.72 | 14.39 |
| gemma-4-12b-obliterated | index.md | 837 | 46 | 14 | 18.20 | 50.30 | 10.76 | 14.88 |
| gemma-4-12b-obliterated | INSTRUCTIONS.md | 643 | 32 | 3 | 20.09 | 47.90 | 11.57 | 15.32 |
| gemma-4-e4b-it | LESSON.md | 685 | 48 | 13 | 14.27 | 63.66 | 7.93 | 11.08 |
| gemma-4-e4b-it | index.md | 782 | 57 | 18 | 13.72 | 67.42 | 7.26 | 10.55 |
| gemma-4-e4b-it | INSTRUCTIONS.md | 799 | 59 | 9 | 13.54 | 62.11 | 7.96 | 11.62 |
| google/gemini-3.5-flash-lite | LESSON.md | 1341 | 85 | 24 | 15.78 | 62.75 | 8.43 | 11.02 |
| google/gemini-3.5-flash-lite | index.md | 1289 | 82 | 29 | 15.72 | 62.31 | 8.47 | 11.04 |
| google/gemini-3.5-flash-lite | INSTRUCTIONS.md | 721 | 41 | 15 | 17.59 | 52.05 | 10.37 | 13.58 |
| google/gemini-3.6-flash | LESSON.md | 1074 | 70 | 17 | 15.34 | 63.34 | 8.24 | 11.02 |
| google/gemini-3.6-flash | index.md | 1475 | 103 | 17 | 14.32 | 49.37 | 9.93 | 13.35 |
| google/gemini-3.6-flash | INSTRUCTIONS.md | 1132 | 66 | 9 | 17.15 | 41.45 | 11.74 | 14.81 |
| google/gemma-3-12b-it | LESSON.md | 533 | 34 | 7 | 15.68 | 48.39 | 10.40 | 13.70 |
| google/gemma-3-12b-it | index.md | 651 | 41 | 8 | 15.88 | 47.90 | 10.52 | 14.09 |
| google/gemma-3-12b-it | INSTRUCTIONS.md | 811 | 61 | 8 | 13.30 | 48.03 | 9.86 | 13.51 |
| google/gemma-4-26b-a4b-it | LESSON.md | 838 | 56 | 18 | 14.96 | 58.79 | 8.78 | 12.24 |
| google/gemma-4-26b-a4b-it | index.md | 931 | 70 | 18 | 13.30 | 67.12 | 7.20 | 10.39 |
| google/gemma-4-26b-a4b-it | INSTRUCTIONS.md | 790 | 61 | 5 | 12.95 | 63.36 | 7.64 | 11.05 |
| google/gemma-4-31b-it | LESSON.md | 833 | 62 | 17 | 13.44 | 66.25 | 7.36 | 10.22 |
| google/gemma-4-31b-it | index.md | 989 | 64 | 17 | 15.45 | 64.72 | 8.07 | 10.99 |
| google/gemma-4-31b-it | INSTRUCTIONS.md | 653 | 44 | 4 | 14.84 | 60.53 | 8.50 | 12.00 |
| gemma-4-e4b-it | LESSON.md | 714 | 46 | 7 | 15.52 | 56.36 | 9.25 | 12.32 |
| gemma-4-e4b-it | index.md | 897 | 63 | 16 | 14.24 | 61.85 | 8.17 | 11.36 |
| gemma-4-e4b-it | INSTRUCTIONS.md | 755 | 43 | 8 | 17.56 | 54.55 | 10.01 | 13.12 |
| nvidia/nemotron-3-ultra-550b-a55b | LESSON.md | 1070 | 127 | 19 | 8.43 | 68.22 | 5.84 | 8.68 |
| nvidia/nemotron-3-ultra-550b-a55b | index.md | 927 | 125 | 21 | 7.42 | 68.35 | 5.57 | 8.32 |
| nvidia/nemotron-3-ultra-550b-a55b | INSTRUCTIONS.md | 2113 | 206 | 64 | 10.26 | 66.14 | 6.58 | 9.12 |
| openai/gpt-4.1 | LESSON.md | 758 | 85 | 20 | 8.92 | 74.01 | 5.15 | 8.26 |
| openai/gpt-4.1 | index.md | 1092 | 109 | 22 | 10.02 | 75.11 | 5.27 | 8.51 |
| openai/gpt-4.1 | INSTRUCTIONS.md | 837 | 66 | 27 | 12.68 | 61.15 | 7.88 | 10.76 |
| openai/gpt-5.4 | LESSON.md | 1853 | 212 | 49 | 8.74 | 83.73 | 3.75 | 6.45 |
| openai/gpt-5.4 | index.md | 3240 | 414 | 103 | 7.83 | 82.28 | 3.73 | 6.49 |
| openai/gpt-5.4 | INSTRUCTIONS.md | 1759 | 131 | 52 | 13.43 | 66.86 | 7.27 | 9.76 |
| openai/gpt-5.5 | LESSON.md | 1727 | 207 | 50 | 8.34 | 86.14 | 3.32 | 5.88 |
| openai/gpt-5.5 | index.md | 4362 | 557 | 179 | 7.83 | 82.38 | 3.71 | 6.35 |
| openai/gpt-5.5 | INSTRUCTIONS.md | 2421 | 240 | 45 | 10.09 | 73.70 | 5.49 | 8.33 |
| openai/gpt-5.6-luna | LESSON.md | 1412 | 138 | 36 | 10.23 | 72.67 | 5.67 | 8.29 |
| openai/gpt-5.6-luna | index.md | 2215 | 235 | 69 | 9.43 | 70.85 | 5.72 | 8.56 |
| openai/gpt-5.6-luna | INSTRUCTIONS.md | 2692 | 217 | 54 | 12.41 | 56.12 | 8.51 | 11.46 |
| openai/gpt-5.6-sol | LESSON.md | 1895 | 201 | 54 | 9.43 | 71.68 | 5.60 | 8.46 |
| openai/gpt-5.6-sol | index.md | 2148 | 219 | 66 | 9.81 | 72.58 | 5.57 | 8.24 |
| openai/gpt-5.6-sol | INSTRUCTIONS.md | 3212 | 285 | 57 | 11.27 | 57.62 | 8.02 | 11.21 |
| openai/gpt-5.6-terra | LESSON.md | 1439 | 151 | 41 | 9.53 | 73.17 | 5.42 | 8.09 |
| openai/gpt-5.6-terra | index.md | 2853 | 303 | 108 | 9.42 | 74.81 | 5.16 | 8.13 |
| openai/gpt-5.6-terra | INSTRUCTIONS.md | 2159 | 142 | 45 | 15.20 | 57.66 | 8.99 | 11.86 |
| qwen/qwen3.7-plus | LESSON.md | 725 | 67 | 10 | 10.82 | 77.30 | 5.17 | 8.25 |
| qwen/qwen3.7-plus | index.md | 812 | 86 | 17 | 9.44 | 75.87 | 5.02 | 7.91 |
| qwen/qwen3.7-plus | INSTRUCTIONS.md | 1045 | 59 | 10 | 17.71 | 63.29 | 8.83 | 11.45 |
| qwen/qwen3.8-max | LESSON.md | 2413 | 305 | 53 | 7.91 | 81.98 | 3.79 | 6.48 |
| qwen/qwen3.8-max | index.md | 2326 | 285 | 40 | 8.16 | 81.54 | 3.91 | 6.69 |
| qwen/qwen3.8-max | INSTRUCTIONS.md | 2047 | 212 | 39 | 9.66 | 76.27 | 5.02 | 7.63 |
| qwen3.6-27b-heretic-neo-code | LESSON.md | 1050 | 123 | 37 | 8.54 | 72.88 | 5.21 | 8.33 |
| qwen3.6-27b-heretic-neo-code | index.md | 1322 | 156 | 58 | 8.47 | 73.70 | 5.08 | 8.29 |
| qwen3.6-27b-heretic-neo-code | INSTRUCTIONS.md | 951 | 91 | 39 | 10.45 | 69.37 | 6.18 | 8.93 |
| qwen3.6-35b-hauhaucs-aggressive | LESSON.md | 709 | 90 | 22 | 7.88 | 78.92 | 4.21 | 7.16 |
| qwen3.6-35b-hauhaucs-aggressive | index.md | 1653 | 196 | 46 | 8.43 | 80.51 | 4.12 | 7.05 |
| qwen3.6-35b-hauhaucs-aggressive | INSTRUCTIONS.md | 1156 | 109 | 17 | 10.61 | 72.17 | 5.83 | 8.60 |
| stepfun/step-3.7-flash | LESSON.md | 1696 | 96 | 1 | 17.67 | 70.88 | 7.76 | 10.72 |
| stepfun/step-3.7-flash | index.md | 2536 | 155 | 8 | 16.36 | 71.83 | 7.30 | 10.38 |
| stepfun/step-3.7-flash | INSTRUCTIONS.md | 1700 | 57 | 6 | 29.82 | 56.03 | 12.85 | 15.44 |
| tencent/hy3 | LESSON.md | 827 | 100 | 14 | 8.27 | 85.71 | 3.36 | 5.77 |
| tencent/hy3 | index.md | 678 | 93 | 17 | 7.29 | 82.27 | 3.60 | 6.04 |
| tencent/hy3 | INSTRUCTIONS.md | 891 | 70 | 8 | 12.73 | 71.62 | 6.43 | 8.91 |
| unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-27b-ud-q4-k-xl | LESSON.md | 1325 | 155 | 30 | 8.55 | 80.10 | 4.21 | 7.49 |
| unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-27b-ud-q4-k-xl | index.md | 1453 | 188 | 32 | 7.73 | 81.20 | 3.85 | 6.95 |
| unsloth-qwen3-6-27b-mtp-gguf-qwen3-6-27b-ud-q4-k-xl | INSTRUCTIONS.md | 1136 | 123 | 31 | 9.24 | 73.61 | 5.29 | 8.59 |
| unsloth-qwen3-6-35b-a3b-mtp-gguf-qwen3-6-35b-a3b-ud-q4-k-s | LESSON.md | 1350 | 178 | 39 | 7.58 | 85.33 | 3.24 | 6.26 |
| unsloth-qwen3-6-35b-a3b-mtp-gguf-qwen3-6-35b-a3b-ud-q4-k-s | index.md | 1664 | 197 | 42 | 8.45 | 81.28 | 4.02 | 6.79 |
| unsloth-qwen3-6-35b-a3b-mtp-gguf-qwen3-6-35b-a3b-ud-q4-k-s | INSTRUCTIONS.md | 1597 | 203 | 41 | 7.87 | 83.26 | 3.60 | 6.55 |
| unsloth-qwen3-8-27b-gguf-qwen3-8-27b-ud-q4-k-xl | LESSON.md | 1604 | 237 | 39 | 6.77 | 92.90 | 1.98 | 4.50 |
| unsloth-qwen3-8-27b-gguf-qwen3-8-27b-ud-q4-k-xl | index.md | 1690 | 236 | 24 | 7.16 | 91.14 | 2.33 | 5.18 |
| unsloth-qwen3-8-27b-gguf-qwen3-8-27b-ud-q4-k-xl | INSTRUCTIONS.md | 1440 | 168 | 19 | 8.57 | 81.52 | 4.02 | 6.87 |
| x-ai/grok-4.3 | LESSON.md | 369 | 28 | 7 | 13.18 | 72.18 | 6.47 | 8.52 |
| x-ai/grok-4.3 | index.md | 485 | 33 | 8 | 14.70 | 66.33 | 7.66 | 10.17 |
| x-ai/grok-4.3 | INSTRUCTIONS.md | 602 | 33 | 9 | 18.24 | 61.84 | 9.17 | 11.48 |
| x-ai/grok-4.5 | LESSON.md | 1331 | 136 | 23 | 9.79 | 82.30 | 4.21 | 6.77 |
| x-ai/grok-4.5 | index.md | 1660 | 166 | 29 | 10.00 | 79.21 | 4.69 | 7.35 |
| x-ai/grok-4.5 | INSTRUCTIONS.md | 1932 | 94 | 49 | 20.55 | 64.99 | 9.30 | 11.84 |

## Metric notes

- Flesch reading ease: higher is generally easier to read.
- FK grade, Fog, Coleman-Liau, ARI, and SMOG: estimated U.S. grade level; lower is generally easier to read.
- Lexical diversity: unique words divided by total words after normalization.
- Long sentence: 20 or more words. Long word: seven or more letters.
