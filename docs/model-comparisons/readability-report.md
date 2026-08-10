# Case Study Readability Report

Comparable measurements for LESSON.md, index.md, and INSTRUCTIONS.md from every completed case study.

Markdown presentation syntax is removed before one deterministic English syllable heuristic is applied to every source. Scores are estimates, not editorial judgments.

## Bundle summary

| Model | Words | Sentences | Avg words/sentence | Flesch ease | FK grade | Fog | Coleman-Liau | ARI | SMOG | Lexical diversity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| deepseek/deepseek-v3.2 | 3552 | 331 | 10.73 | 72.09 | 5.87 | 8.93 | 8.16 | 5.34 | 9.50 | 0.19 |
| deepseek/deepseek-v4-flash | 4736 | 470 | 10.08 | 76.03 | 5.16 | 8.17 | 7.31 | 4.47 | 8.96 | 0.17 |
| deepseek/deepseek-v4-pro | 5458 | 371 | 14.71 | 68.13 | 7.41 | 10.39 | 8.55 | 7.04 | 10.48 | 0.18 |
| google/gemini-3.5-flash-lite | 3351 | 208 | 16.11 | 60.31 | 8.85 | 11.57 | 10.41 | 9.09 | 11.33 | 0.21 |
| google/gemini-3.6-flash | 3681 | 239 | 15.40 | 51.10 | 9.96 | 13.08 | 12.33 | 10.34 | 12.46 | 0.29 |
| google/gemma-3-12b-it | 1995 | 136 | 14.67 | 48.19 | 10.18 | 13.71 | 12.60 | 10.27 | 12.82 | 0.27 |
| google/gemma-4-26b-a4b-it | 2559 | 187 | 13.68 | 63.28 | 7.83 | 11.18 | 9.62 | 7.51 | 11.11 | 0.26 |
| google/gemma-4-31b-it | 2475 | 170 | 14.56 | 64.18 | 7.92 | 10.98 | 9.02 | 7.36 | 10.95 | 0.28 |
| gemma-4-e4b-it | 2366 | 152 | 15.57 | 57.99 | 9.04 | 12.16 | 9.78 | 8.37 | 11.81 | 0.26 |
| openai/gpt-4.1 | 2687 | 260 | 10.33 | 70.66 | 5.97 | 9.06 | 8.89 | 5.81 | 9.57 | 0.22 |
| openai/gpt-5.4 | 6852 | 757 | 9.05 | 79.18 | 4.46 | 7.13 | 6.99 | 3.97 | 8.22 | 0.17 |
| openai/gpt-5.5 | 8510 | 1004 | 8.48 | 80.78 | 4.10 | 6.78 | 6.34 | 3.34 | 7.97 | 0.15 |
| openai/gpt-5.6-luna | 6319 | 590 | 10.71 | 65.15 | 6.83 | 9.66 | 9.17 | 6.14 | 9.99 | 0.17 |
| openai/gpt-5.6-sol | 2978 | 311 | 9.58 | 73.85 | 5.34 | 8.03 | 8.32 | 5.15 | 8.86 | 0.24 |
| openai/gpt-5.6-terra | 3152 | 360 | 8.76 | 74.91 | 4.99 | 7.56 | 7.92 | 4.66 | 8.52 | 0.23 |

## Per-document measurements

| Model | Document | Words | Sentences | Paragraphs | Avg words/sentence | Flesch ease | FK grade | Fog |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| deepseek/deepseek-v3.2 | LESSON.md | 1315 | 131 | 22 | 10.04 | 76.15 | 5.13 | 8.15 |
| deepseek/deepseek-v3.2 | index.md | 1305 | 131 | 23 | 9.96 | 76.40 | 5.08 | 8.09 |
| deepseek/deepseek-v3.2 | INSTRUCTIONS.md | 932 | 69 | 9 | 13.51 | 59.60 | 8.30 | 11.50 |
| deepseek/deepseek-v4-flash | LESSON.md | 1422 | 156 | 30 | 9.12 | 76.69 | 4.83 | 8.01 |
| deepseek/deepseek-v4-flash | index.md | 2012 | 234 | 44 | 8.60 | 78.65 | 4.43 | 7.57 |
| deepseek/deepseek-v4-flash | INSTRUCTIONS.md | 1302 | 80 | 32 | 16.27 | 68.35 | 7.77 | 10.41 |
| deepseek/deepseek-v4-pro | LESSON.md | 1408 | 108 | 14 | 13.04 | 70.91 | 6.61 | 9.79 |
| deepseek/deepseek-v4-pro | index.md | 1407 | 108 | 14 | 13.03 | 70.89 | 6.61 | 9.79 |
| deepseek/deepseek-v4-pro | INSTRUCTIONS.md | 2643 | 155 | 35 | 17.05 | 64.63 | 8.48 | 11.26 |
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
| openai/gpt-5.6-sol | LESSON.md | 933 | 108 | 9 | 8.64 | 79.83 | 4.27 | 7.10 |
| openai/gpt-5.6-sol | index.md | 997 | 116 | 7 | 8.59 | 73.38 | 5.16 | 8.09 |
| openai/gpt-5.6-sol | INSTRUCTIONS.md | 1048 | 87 | 3 | 12.05 | 68.27 | 6.73 | 9.09 |
| openai/gpt-5.6-terra | LESSON.md | 887 | 102 | 9 | 8.70 | 77.83 | 4.56 | 7.31 |
| openai/gpt-5.6-terra | index.md | 1044 | 135 | 7 | 7.73 | 80.76 | 3.92 | 6.69 |
| openai/gpt-5.6-terra | INSTRUCTIONS.md | 1221 | 123 | 11 | 9.93 | 67.54 | 6.31 | 8.59 |

## Metric notes

- Flesch reading ease: higher is generally easier to read.
- FK grade, Fog, Coleman-Liau, ARI, and SMOG: estimated U.S. grade level; lower is generally easier to read.
- Lexical diversity: unique words divided by total words after normalization.
- Long sentence: 20 or more words. Long word: seven or more letters.
