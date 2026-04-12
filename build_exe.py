# -*- coding: utf-8 -*-
"""
打包脚本

使用PyInstaller将JusticePlutus打包成EXE文件
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def clean_build():
    """清理构建目录"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"已清理: {dir_name}")
    
    # 清理.spec文件生成的临时文件
    for file in Path('.').glob('*.spec'):
        if file.name != 'justiceplutus.spec':
            file.unlink()
            print(f"已清理: {file}")


def install_pyinstaller():
    """安装PyInstaller"""
    print("检查PyInstaller是否已安装...")
    try:
        import PyInstaller
        print("PyInstaller已安装")
    except ImportError:
        print("正在安装PyInstaller...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
        print("PyInstaller安装完成")


def build_exe():
    """构建EXE文件"""
    print("\n开始构建EXE文件...")
    print("=" * 60)
    
    # 使用spec文件构建
    cmd = [
        sys.executable,
        '-m',
        'PyInstaller',
        'justiceplutus.spec',
        '--clean',
        '--noconfirm'
    ]
    
    try:
        subprocess.check_call(cmd)
        print("\n" + "=" * 60)
        print("✅ 构建成功！")
        print(f"EXE文件位置: {os.path.abspath('dist/JusticePlutus.exe')}")
        print("=" * 60)
    except subprocess.CalledProcessError as e:
        print("\n" + "=" * 60)
        print(f"❌ 构建失败: {e}")
        print("=" * 60)
        sys.exit(1)


def main():
    """主函数"""
    print("=" * 60)
    print("JusticePlutus 打包工具")
    print("=" * 60)
    
    # 步骤1: 清理
    print("\n步骤1: 清理构建目录")
    clean_build()
    
    # 步骤2: 安装PyInstaller
    print("\n步骤2: 安装PyInstaller")
    install_pyinstaller()
    
    # 步骤3: 构建
    print("\n步骤3: 构建EXE文件")
    build_exe()
    
    print("\n打包完成！")


if __name__ == "__main__":
    main()
