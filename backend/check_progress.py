import json
import sys

try:
    with open('sync_progress.json') as f:
        progress = json.load(f)
    
    completed = len(progress.get('completed', []))
    failed = len(progress.get('failed', []))
    total = 2560
    
    print(f"批量同步进度报告")
    print(f"=" * 50)
    print(f"总计: {total} 只基金")
    print(f"已完成: {completed} ({completed/total*100:.1f}%)")
    print(f"失败: {failed}")
    print(f"剩余: {total - completed - failed}")
    print(f"=" * 50)
    
    if completed > 0:
        print(f"\n最近完成的 5 只基金:")
        for code in progress['completed'][-5:]:
            print(f"  - {code}")
    
    if failed > 0:
        print(f"\n失败的基金数: {failed}")
        if failed <= 10:
            for item in progress['failed'][-5:]:
                print(f"  - {item.get('id', 'N/A')}: {item.get('error', 'N/A')[:50]}")
    
except FileNotFoundError:
    print("进度文件尚未创建")
except Exception as e:
    print(f"错误: {e}")
