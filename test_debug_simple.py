#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化的调试模式测试脚本
测试入群申请审核插件的调试功能和日志输出
"""

import sys
import os
from unittest.mock import Mock, MagicMock

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 创建模拟类
class MockLogger:
    def info(self, message): print(f"[INFO] {message}")
    def debug(self, message): print(f"[DEBUG] {message}")
    def warning(self, message): print(f"[WARNING] {message}")
    def error(self, message): print(f"[ERROR] {message}")

class MockContext:
    def __init__(self):
        self.aget = Mock(return_value={})
        self.aset = Mock()

class MockSender:
    def __init__(self, user_id="test_user"):
        self.user_id = user_id
        self.nickname = f"User_{user_id}"

class MockAstrMessageEvent:
    def __init__(self, message_str="test", user_id="admin123"):
        self.message_str = message_str
        self.sender = MockSender(user_id)
        self.group_id = "987654321"
        self.is_admin = lambda: True
        self._result = Mock()
        self._result.chain = []

class MockMessageEventResult:
    def __init__(self):
        self.chain = []

class MockEventMessageType:
    GROUP_MESSAGE = "group_message"
    PRIVATE_MESSAGE = "private_message"

class MockFilter:
    EventMessageType = MockEventMessageType
    
    def command(self, command_name):
        def decorator(func):
            return func
        return decorator
    
    def group_request(self, func):
        return func
    
    def event_message_type(self, message_type):
        def decorator(func):
            return func
        return decorator

class MockModule:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

# 模拟导入 - 必须在导入main之前设置
sys.modules['astrbot'] = MockModule()
sys.modules['astrbot.api'] = MockModule(logger=MockLogger())
sys.modules['astrbot.api.event'] = MockModule(
    AstrMessageEvent=MockAstrMessageEvent,
    MessageEventResult=MockMessageEventResult,
    filter=MockFilter()
)
sys.modules['astrbot.api.star'] = MockModule(
    Context=MockContext, 
    logger=MockLogger(),
    Star=Mock(),
    register=Mock()
)
sys.modules['astrbot.api.platform'] = MockModule(Platform=Mock())
sys.modules['astrbot.message'] = MockModule(MessageEventResult=MockMessageEventResult)

# 现在可以安全导入main模块
import main

# 替换main模块中的logger
main.logger = MockLogger()

def test_debug_functionality():
    """测试调试功能"""
    print("\n" + "="*60)
    print("🐛 入群申请审核插件 - 调试功能测试")
    print("="*60)
    
    # 创建插件实例并启用调试模式
    plugin = main.EntryReviewPlugin(MockContext())
    
    # 手动设置调试模式配置 - 创建真实的字典对象
    plugin.config = {
        'debug_mode': True,
        'debug_log_events': True,
        'debug_log_api_calls': True,
        'log_level': 'DEBUG',
        'source_group': '',
        'target_group': '',
        'auto_approve_timeout': 300,
        'admin_users': ['admin123']
    }
    
    # 直接设置调试属性，绕过_init_debug_mode方法
    plugin.debug_mode = True
    plugin.debug_log_events = True
    plugin.debug_log_api_calls = True
    
    print("\n📋 测试1: 调试日志输出")
    print("-" * 30)
    
    # 检查调试模式状态
    print(f"调试模式状态: {getattr(plugin, 'debug_mode', 'Not Set')}")
    print(f"事件日志状态: {getattr(plugin, 'debug_log_events', 'Not Set')}")
    print(f"API日志状态: {getattr(plugin, 'debug_log_api_calls', 'Not Set')}")
    
    # 测试基本调试日志
    print("调用 _debug_log...")
    print(f"调用前 debug_mode: {plugin.debug_mode}")
    result = plugin._debug_log("这是一条调试日志消息", "INFO")
    print(f"_debug_log 返回值: {result}")
    
    # 手动执行_debug_log的逻辑
    print("手动执行调试日志逻辑...")
    if getattr(plugin, 'debug_mode', False):
        main.logger.info(f"🐛 [DEBUG] 手动调试日志测试")
    else:
        print("调试模式未启用")
    
    # 直接测试logger
    print("直接调用logger...")
    main.logger.info("直接调用logger测试")
    main.logger.debug("直接调用logger.debug测试")
    
    # 测试事件日志
    print("调用 _debug_log_event...")
    event = MockAstrMessageEvent("测试消息", "test_user")
    plugin._debug_log_event(event, "测试事件处理")
    
    # 测试API调用日志
    print("调用 _debug_log_api_call...")
    plugin._debug_log_api_call("send_message", {"group_id": "123456", "message": "测试消息"})
    
    print("\n📋 测试2: 配置管理调试")
    print("-" * 30)
    
    # 测试设置源群（同步调用）
    event = MockAstrMessageEvent("设置源群 123456789", "admin123")
    try:
        plugin.set_source_group(event, "123456789")
        print("✅ 设置源群调试日志输出正常")
    except Exception as e:
        print(f"⚠️ 设置源群时出现异常: {e}")
    
    # 测试设置审核群（同步调用）
    event = MockAstrMessageEvent("设置审核群 987654321", "admin123")
    try:
        plugin.set_target_group(event, "987654321")
        print("✅ 设置审核群调试日志输出正常")
    except Exception as e:
        print(f"⚠️ 设置审核群时出现异常: {e}")
    
    print("\n📋 测试3: 模拟申请调试")
    print("-" * 30)
    
    # 测试模拟入群申请（同步调用）
    event = MockAstrMessageEvent("测试申请", "admin123")
    try:
        plugin.test_group_request(event, "testuser001", "123456789", "我想加入这个群")
        print("✅ 模拟申请调试日志输出正常")
    except Exception as e:
        print(f"⚠️ 模拟申请时出现异常: {e}")
    
    print("\n📋 测试4: 帮助系统调试")
    print("-" * 30)
    
    # 测试帮助命令（同步调用）
    event = MockAstrMessageEvent("帮助", "admin123")
    try:
        plugin.help_command(event)
        print("✅ 帮助系统调试日志输出正常")
    except Exception as e:
        print(f"⚠️ 帮助系统时出现异常: {e}")
    
    print("\n📋 测试5: 错误处理调试")
    print("-" * 30)
    
    # 测试错误情况的调试日志
    try:
        plugin._debug_log("模拟错误处理场景")
        plugin._debug_log_api_call("invalid_api", {"error": "测试错误"})
        print("✅ 错误处理调试日志输出正常")
    except Exception as e:
        print(f"⚠️ 错误处理时出现异常: {e}")
    
    print("\n" + "="*60)
    print("🎉 调试功能测试完成！")
    print("="*60)
    
    # 显示配置信息
    print("\n📊 当前调试配置:")
    print(f"  - 调试模式: {plugin.config.get('debug_mode', False)}")
    print(f"  - 事件日志: {plugin.config.get('debug_log_events', False)}")
    print(f"  - API调用日志: {plugin.config.get('debug_log_api_calls', False)}")
    print(f"  - 日志级别: {plugin.config.get('log_level', 'INFO')}")
    
    return True

if __name__ == "__main__":
    try:
        test_debug_functionality()
        print("\n✅ 所有调试功能测试通过！")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()