#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
插件基础验证脚本
验证插件文件结构和基本语法
"""

import json
import os
import sys

def check_file_exists(filepath, description):
    """检查文件是否存在"""
    if os.path.exists(filepath):
        print(f"✅ {description}: {os.path.basename(filepath)}")
        return True
    else:
        print(f"❌ {description}: {os.path.basename(filepath)} 不存在")
        return False

def check_json_format(filepath, description):
    """检查JSON文件格式"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            json.load(f)
        print(f"✅ {description}: 格式正确")
        return True
    except Exception as e:
        print(f"❌ {description}: 格式错误 - {e}")
        return False

def check_python_syntax(filepath, description):
    """检查Python文件语法"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            code = f.read()
        compile(code, filepath, 'exec')
        print(f"✅ {description}: 语法正确")
        return True
    except SyntaxError as e:
        print(f"❌ {description}: 语法错误 - 第{e.lineno}行: {e.msg}")
        return False
    except Exception as e:
        print(f"❌ {description}: 检查失败 - {e}")
        return False

def check_plugin_structure():
    """检查插件文件结构"""
    print("=== 插件文件结构检查 ===")
    
    required_files = [
        ('main.py', '主程序文件'),
        ('metadata.yaml', '插件元数据'),
        ('_conf_schema.json', '配置模式文件'),
        ('README.md', '说明文档'),
        ('LICENSE', '许可证文件')
    ]
    
    all_exist = True
    for filename, description in required_files:
        if not check_file_exists(filename, description):
            all_exist = False
    
    return all_exist

def check_file_formats():
    """检查文件格式"""
    print("\n=== 文件格式检查 ===")
    
    format_checks = [
        ('main.py', 'Python主程序', check_python_syntax),
        ('_conf_schema.json', '配置模式JSON', check_json_format)
    ]
    
    all_valid = True
    for filename, description, check_func in format_checks:
        if os.path.exists(filename):
            if not check_func(filename, description):
                all_valid = False
        else:
            print(f"⚠️ {description}: 文件不存在，跳过检查")
    
    return all_valid

def check_config_schema():
    """检查配置模式内容"""
    print("\n=== 配置模式内容检查 ===")
    
    if not os.path.exists('_conf_schema.json'):
        print("❌ 配置模式文件不存在")
        return False
    
    try:
        with open('_conf_schema.json', 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        required_keys = [
            'source_group', 'target_group', 'auto_approve_timeout',
            'request_message_template', 'approve_message_template',
            'reject_message_template', 'command_permission_check'
        ]
        
        missing_keys = []
        for key in required_keys:
            if key not in schema:
                missing_keys.append(key)
        
        if missing_keys:
            print(f"❌ 缺少配置项: {', '.join(missing_keys)}")
            return False
        else:
            print(f"✅ 包含所有必需的配置项 ({len(required_keys)}个)")
            return True
            
    except Exception as e:
        print(f"❌ 检查配置模式失败: {e}")
        return False

def check_main_py_structure():
    """检查main.py的基本结构"""
    print("\n=== 主程序结构检查 ===")
    
    if not os.path.exists('main.py'):
        print("❌ main.py文件不存在")
        return False
    
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        required_elements = [
            ('@register', '插件注册装饰器'),
            ('class EntryReviewPlugin', '插件主类'),
            ('def __init__', '初始化方法'),
            ('async def initialize', '异步初始化方法'),
            ('@filter.command', '命令过滤器'),
            ('async def handle_event', '事件处理方法')
        ]
        
        missing_elements = []
        for element, description in required_elements:
            if element not in content:
                missing_elements.append(f"{description}({element})")
        
        if missing_elements:
            print(f"❌ 缺少关键结构: {', '.join(missing_elements)}")
            return False
        else:
            print(f"✅ 包含所有关键结构元素 ({len(required_elements)}个)")
            return True
            
    except Exception as e:
        print(f"❌ 检查主程序结构失败: {e}")
        return False

def main():
    """主验证函数"""
    print("开始插件基础验证...")
    print("=" * 50)
    
    # 检查当前目录
    current_dir = os.getcwd()
    print(f"当前目录: {current_dir}")
    
    # 运行各项检查
    checks = [
        ("文件结构", check_plugin_structure),
        ("文件格式", check_file_formats),
        ("配置模式", check_config_schema),
        ("程序结构", check_main_py_structure)
    ]
    
    results = []
    for check_name, check_func in checks:
        try:
            result = check_func()
            results.append((check_name, result))
        except Exception as e:
            print(f"❌ {check_name}检查失败: {e}")
            results.append((check_name, False))
    
    # 总结结果
    print("\n" + "=" * 50)
    print("验证结果总结:")
    
    passed = 0
    total = len(results)
    
    for check_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {check_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总体结果: {passed}/{total} 项检查通过")
    
    if passed == total:
        print("🎉 插件基础验证完全通过！")
        print("\n插件已准备就绪，可以部署到AstrBot环境中进行实际测试。")
    else:
        print("⚠️ 部分检查未通过，请根据上述提示进行修复。")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)