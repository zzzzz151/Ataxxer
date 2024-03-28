# Ataxxer - run matches and SPRT between 2 Ataxx engines

### Requirements

`pip install ataxx`

### Example usage

```
python main.py ^
--engine1 first_engine.exe ^
--engine2 second_engine.exe ^
--tc 10+0.1 ^
--concurrency 16 ^
--openings openings_8ply.txt ^
--elo0 0 --elo1 5 --alpha 0.05 --beta 0.05 --cutechess_llr ^
--ratinginterval 25
```
