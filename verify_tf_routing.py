import sys
import json
import os

def verify():
    # 1. Check if ticker_config.json exists
    if not os.path.exists('ticker_config.json'):
        print("FAILED: ticker_config.json not found")
        sys.exit(1)
    
    # 2. Check live_engine.py for dynamic TF logic
    with open('live_engine.py', 'r') as f:
        live_content = f.read()
    
    live_checks = [
        "def load_ticker_config():",
        "CONFIG_FILE = \"ticker_config.json\"",
        "tf_str = f'{self.tf}m' if self.tf < 60 else f'{self.tf//60}h'",
        "engines = [LiveVelocityEngine(t, config.get(t, 5)) for t in config.keys()]"
    ]
    
    # 3. Check massive_backtest.py for dynamic TF logic
    with open('massive_backtest.py', 'r') as f:
        bt_content = f.read()
        
    bt_checks = [
        "def load_ticker_config():",
        "tf_val = tf_override if tf_override else config.get(ticker, 5)",
        "df_tf = df_1m.resample(tf_str).agg({",
        "df_1m['tf_group'] = df_1m.index.floor(tf_str)"
    ]
    
    print(f"{'Check':<50} | {'Status':<10}")
    print("-" * 65)
    
    all_passed = True
    for check in live_checks:
        status = "PASSED" if check in live_content else "FAILED"
        if status == "FAILED": all_passed = False
        print(f"Live Engine: {check[:40]:<37} | {status:<10}")
        
    for check in bt_checks:
        status = "PASSED" if check in bt_content else "FAILED"
        if status == "FAILED": all_passed = False
        print(f"Backtest: {check[:40]:<40} | {status:<10}")
        
    if all_passed:
        print("\nALL DYNAMIC ROUTING CHECKS PASSED")
    else:
        print("\nSOME CHECKS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    verify()
