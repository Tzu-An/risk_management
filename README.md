# Risk Management
Risk management on trading

## Setup
### Download and install Python
- [Link](https://www.python.org/downloads/)
- [Tutorial](https://www.codingspace.school/blog/2021-04-07)
### Install dependencies
```bash
pip install pandas
```
### Add your own trading record
- Create a new directory, add configuration file and trading record csv file like the ones in directory "test_data"
#### Files
##### Configs.json
- capital = 帳戶持有資金
- risk_taking_ratio (0 < x <= 1) = 可接受損失比率

##### trade_record.csv
- entry_year, entry_month, entry_day = 入場年月日
- close_year, close_month, close_day = 出場年月日
- earning = 交易所得
- cost = 手續費 + 稅
- invest = 投資額, 保證金等等

## How to use
```bash
python risk_manager.py -s 2023/01/01 -e 2023/12/31 --dir your_dir

# 或是只顯示無法推算個人資金的數值

python risk_manager.py -s 2023/01/01 -e 2023/12/31 --dir your_dir --keep-privacy
```


