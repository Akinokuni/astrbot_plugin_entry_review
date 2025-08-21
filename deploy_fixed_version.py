#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
部署修复版入群申请审核插件
解决 NapCatQQ issue #1076: 处理入群申请时无法获取有效flag的问题
"""

import os
import shutil
import json
from datetime import datetime

def backup_original_files():
    """备份原始文件"""
    print("📦 备份原始文件...")
    
    backup_dir = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    os.makedirs(backup_dir, exist_ok=True)
    
    files_to_backup = ['main.py', 'entry_review_config.json']
    
    for file in files_to_backup:
        if os.path.exists(file):
            shutil.copy2(file, os.path.join(backup_dir, file))
            print(f"  ✅ 已备份: {file} -> {backup_dir}/{file}")
        else:
            print(f"  ⚠️  文件不存在: {file}")
    
    return backup_dir

def deploy_fixed_version():
    """部署修复版本"""
    print("🚀 部署修复版插件...")
    
    # 检查修复版文件是否存在
    if not os.path.exists('main_v2_fixed.py'):
        print("❌ 错误: main_v2_fixed.py 文件不存在")
        return False
    
    # 复制修复版文件
    shutil.copy2('main_v2_fixed.py', 'main.py')
    print("  ✅ 已部署: main_v2_fixed.py -> main.py")
    
    return True

def create_default_config():
    """创建默认配置文件"""
    print("⚙️  创建配置文件...")
    
    config_file = 'entry_review_config.json'
    
    if os.path.exists(config_file):
        print(f"  ℹ️  配置文件已存在: {config_file}")
        return
    
    default_config = {
        "target_groups": [],
        "review_group": 0,
        "auto_approve_time": 300,
        "debug_mode": True,
        "admin_users": [],
        "polling_interval": 30,
        "max_retry_count": 3,
        "use_system_msg_polling": True
    }
    
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, ensure_ascii=False, indent=2)
    
    print(f"  ✅ 已创建默认配置: {config_file}")
    print("  ⚠️  请编辑配置文件设置群号和管理员")

def run_tests():
    """运行测试"""
    print("🧪 运行功能测试...")
    
    if not os.path.exists('test_v2_fixed.py'):
        print("  ⚠️  测试文件不存在: test_v2_fixed.py")
        return
    
    try:
        import subprocess
        result = subprocess.run(['python', 'test_v2_fixed.py'], 
                              capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            print("  ✅ 所有测试通过")
            # 显示测试结果摘要
            output_lines = result.stdout.split('\n')
            for line in output_lines:
                if '✅ 通过' in line or '❌ 失败' in line:
                    print(f"    {line}")
                elif '🎉 所有测试通过' in line:
                    print(f"    {line}")
        else:
            print("  ❌ 测试失败")
            print(f"    错误: {result.stderr}")
    
    except Exception as e:
        print(f"  ❌ 运行测试时出错: {e}")

def show_configuration_guide():
    """显示配置指南"""
    print("\n📋 配置指南")
    print("=" * 50)
    
    print("\n1. 编辑 entry_review_config.json 文件:")
    print("   - target_groups: 需要审核的群号列表")
    print("   - review_group: 审核群号")
    print("   - admin_users: 管理员用户ID列表")
    
    print("\n2. 配置示例:")
    example_config = {
        "target_groups": [123456789, 987654321],
        "review_group": 111111111,
        "admin_users": [888888888, 777777777]
    }
    print(json.dumps(example_config, ensure_ascii=False, indent=2))
    
    print("\n3. 可用指令 (在审核群中使用):")
    print("   - /approve <申请ID>     # 通过申请")
    print("   - /reject <申请ID> [原因] # 拒绝申请")
    print("   - /info <申请ID>       # 查看申请详情")
    print("   - /list                # 查看待处理申请")
    print("   - /help                # 显示帮助")

def show_troubleshooting():
    """显示故障排除指南"""
    print("\n🔧 故障排除")
    print("=" * 50)
    
    print("\n如果遇到 'flag无效' 错误:")
    print("1. 检查调试日志，查看尝试了哪些flag格式")
    print("2. 确认机器人有足够权限执行相关API")
    print("3. 尝试调整轮询间隔 (polling_interval)")
    print("4. 检查 NapCatQQ 版本是否支持相关API")
    
    print("\n如果插件无响应:")
    print("1. 检查配置文件中的群号是否正确")
    print("2. 确认管理员用户ID是否正确")
    print("3. 启用调试模式查看详细日志")
    print("4. 检查事件监听是否正常工作")

def main():
    """主函数"""
    print("🔧 入群申请审核插件 - 修复版部署工具")
    print("解决 NapCatQQ issue #1076: flag无效问题")
    print("=" * 60)
    
    try:
        # 1. 备份原始文件
        backup_dir = backup_original_files()
        
        # 2. 部署修复版本
        if not deploy_fixed_version():
            return
        
        # 3. 创建配置文件
        create_default_config()
        
        # 4. 运行测试
        run_tests()
        
        # 5. 显示配置指南
        show_configuration_guide()
        
        # 6. 显示故障排除指南
        show_troubleshooting()
        
        print("\n" + "=" * 60)
        print("🎉 部署完成！")
        print(f"📦 原始文件已备份到: {backup_dir}")
        print("📝 请根据配置指南设置群号和管理员")
        print("🚀 重启机器人以应用更改")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ 部署过程中出现错误: {e}")
        print("请检查文件权限和路径是否正确")

if __name__ == "__main__":
    main()