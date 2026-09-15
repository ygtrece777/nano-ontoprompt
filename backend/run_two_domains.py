"""
对 法律 和 HR 重新跑全流程（v2数据），输出最终结果。
用法: cd backend && python run_two_domains.py
"""
import sys, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '.')

# Patch run_full_flow_test to run only 法律 & HR
import run_full_flow_test as rff

rff.DOMAINS = [
    {"name": "HR本体-v2",   "domain": "其他",  "dir": "HR",
     "prompt_id": "779bd973-30ee-4ffd-9bfc-27e94f180fef"},
    {"name": "法律本体-v2", "domain": "法律",  "dir": "法律",
     "prompt_id": "c1ddd6d3-b648-4a64-98ce-64d293201d25"},
]

if __name__ == "__main__":
    rff.main()
