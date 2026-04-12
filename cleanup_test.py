# -*- coding: utf-8 -*-
"""
清理测试文档脚本

自动删除测试过程中生成的临时文件
"""

import os
import glob

def cleanup_test_files():
    """清理测试文档"""
    test_files = [
        "test_output.log",
        "test_result.log",
        "*.pyc",
        "__pycache__",
        ".pytest_cache",
        "*.tmp"
    ]
    
    cleaned = []
    
    for pattern in test_files:
        if "*" in pattern:
            files = glob.glob(pattern)
            for file in files:
                try:
                    if os.path.isfile(file):
                        os.remove(file)
                        cleaned.append(file)
                    elif os.path.isdir(file):
                        import shutil
                        shutil.rmtree(file)
                        cleaned.append(file)
                except Exception as e:
                    print(f"删除失败 {file}: {e}")
        else:
            if os.path.exists(pattern):
                try:
                    if os.path.isfile(pattern):
                        os.remove(pattern)
                        cleaned.append(pattern)
                    elif os.path.isdir(pattern):
                        import shutil
                        shutil.rmtree(pattern)
                        cleaned.append(pattern)
                except Exception as e:
                    print(f"删除失败 {pattern}: {e}")
    
    if cleaned:
        print(f"\n✅ 已清理测试文档: {len(cleaned)} 个")
        for file in cleaned:
            print(f"  - {file}")
    else:
        print("\n✅ 没有需要清理的测试文档")

if __name__ == "__main__":
    cleanup_test_files()
