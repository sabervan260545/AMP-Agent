# Hemolysis Knowledge Base Summary

**Built at**: 2025-12-13 15:44:48

## Dataset statistics

| Dataset            | Total | Hemolytic (+) | Non-hemolytic (-) |
|--------------------|-------|---------------|-------------------|
| cross_validation   | 1540  | 712           | 828               |
| independent_test   | 386   | 179           | 207               |

## Overall statistics

- **Total sequences**: 1,926
- **Hemolytic (+)**  : 891
- **Non-hemolytic (-)**: 1,035
- **Positive rate**  : 46.3%

## HC50 toxicity distribution

| Toxicity level | Count | Ratio  | HC50 range     |
|----------------|-------|--------|----------------|
| High           | 180   | 9.3%   | < 10 uM        |
| Medium         | 681   | 35.4%  | 10 - 100 uM    |
| Low            | 1065  | 55.3%  | >= 100 uM      |

## Use

This dataset is used to train the **hemolysis prediction model**, which
estimates the toxicity risk of candidate AMPs.

## Notes

- HC50: half-hemolytic concentration; lower values mean higher toxicity.
- `label = 1`: hemolytic   (HC50 < 100 uM)
- `label = 0`: non-hemolytic (HC50 >= 100 uM)
