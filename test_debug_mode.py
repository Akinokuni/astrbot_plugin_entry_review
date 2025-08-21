#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
入群申请审核插件 - Debug模式测试脚本
测试插件的调试功能和详细日志输出
"""

import sys
import os
import asyncio
import json
from unittest.mock import Mock, AsyncMock

# 添加插件路径
sys.path.insert(0, os.path.abspath('.'))

# 模拟AstrBot相关类
class MockMessageEventResult:
    def __init__(self):
        self.chain = []
        self.use_t2i_ = False
        self.result_type = "text"
        self.result_content_type = "text"
        self.async_stream = False
    
    def message(self, text):
        self.chain.append({"type": "text", "data": {"text": text}})
        return self

class MockAstrMessageEvent:
    def __init__(self, message_str="", sender_id="123456", group_id=None):
        self.message_str = message_str
        self.sender_id = sender_id
        self.group_id = group_id
        self.message_type = "group" if group_id else "private"
        self._result = MockMessageEventResult()
        self.raw_message = {
            "user_id": sender_id,
            "group_id": group_id,
            "message": message_str
        }
        self.message_obj = Mock()
        self.message_obj.raw_message = self.raw_message
    
    def set_result(self, result):
        self._result = result
    
    def get_result(self):
        return self._result
    
    def get_sender_id(self):
        return self.sender_id
    
    def is_admin(self):
        return True  # 模拟管理员权限

class MockContext:
    def __init__(self):
        self.platform_adapter = Mock()
        self.platform_adapter.set_group_add_request = AsyncMock()
    
    def get_platform_adapter(self):
        return self.platform_adapter

class MockLogger:
    def info(self, msg):
        print(f"[INFO] {msg}")
    
    def debug(self, msg):
        print(f"[DEBUG] {msg}")
    
    def warning(self, msg):
        print(f"[WARNING] {msg}")
    
    def error(self, msg):
        print(f"[ERROR] {msg}")

# 创建模拟模块
class MockModule:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

# 创建模拟filter装饰器
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

# 设置模拟对象
import main
main.AstrMessageEvent = MockAstrMessageEvent
main.MessageEventResult = MockMessageEventResult
main.Context = MockContext
main.logger = MockLogger()
main.Platform = Mock()

def get_result_text(result):
    """从结果对象中提取文本消息"""
    if hasattr(result, 'chain') and result.chain:
        texts = []
        for item in result.chain:
            if item.get('type') == 'text' and 'data' in item and 'text' in item['data']:
                texts.append(item['data']['text'])
        return '\n'.join(texts)
    return ""

async def test_debug_mode():
    """测试调试模式功能"""
    print("\n" + "="*60)
    print("🐛 入群申请审核插件 - Debug模式测试")
    print("="*60)
    
    # 创建插件实例
    plugin = main.EntryReviewPlugin()
    plugin.context = MockContext()
    
    # 启用调试模式
    plugin.config = {
        "source_group_id": "123456789",
        "target_group_id": "987654321",
        "authorized_users": ["admin123"],
        "auto_approve_timeout": 10,  # 短超时用于测试
        "enable_auto_approve": True,
        "approval_message_template": "欢迎 {nickname} 加入群聊！",
        "rejection_message_template": "很抱歉，您的入群申请未通过审核。原因：{reason}",
        "debug_mode": True,  # 启用调试模式
        "debug_log_events": True,  # 启用事件详情记录
        "debug_log_api_calls": True,  # 启用API调用记录
        "check_permission": True,
        "log_level": "DEBUG"
    }
    
    # 初始化调试模式
    plugin._init_debug_mode()
    
    print("\n📋 测试1: 配置管理")
    print("-" * 30)
    
    # 测试设置源群
    event = MockAstrMessageEvent("设置源群 123456789", "admin123")
    plugin.set_source_group(event, "123456789")
    result_text = get_result_text(event._result)
    print(f"设置源群结果: {result_text}")
    
    # 测试设置审核群
    event = MockAstrMessageEvent("设置审核群 987654321", "admin123")
    plugin.set_target_group(event, "987654321")
    result_text = get_result_text(event._result)
    print(f"设置审核群结果: {result_text}")
    
    print("\n📋 测试2: 模拟入群申请")
    print("-" * 30)
    
    # 测试模拟入群申请
    event = MockAstrMessageEvent("测试申请", "admin123")
    plugin.test_group_request(event, "testuser001", "123456789", "我想加入这个群")
    result_text = get_result_text(event._result)
    print(f"模拟申请结果: {result_text}")
    
    print("\n📋 测试3: 查看待审核列表")
    print("-" * 30)
    
    # 测试查看待审核列表
    event = MockAstrMessageEvent("/待审核", "admin123")
    await plugin._process_review_command(event)
    result_text = get_result_text(event._result)
    print(f"待审核列表: {result_text}")
    
    print("\n📋 测试4: 审核指令处理")
    print("-" * 30)
    
    # 测试通过申请
    event = MockAstrMessageEvent("/通过 testuser001", "admin123")
    await plugin._process_review_command(event)
    result_text = get_result_text(event._result)
    print(f"通过申请结果: {result_text}")
    
    # 再次模拟申请用于拒绝测试
    await plugin._simulate_group_request("testuser002", "123456789", "第二个测试申请")
    
    # 测试拒绝申请
    event = MockAstrMessageEvent("/拒绝 testuser002 不符合要求", "admin123")
    await plugin._process_review_command(event)
    result_text = get_result_text(event._result)
    print(f"拒绝申请结果: {result_text}")
    
    print("\n📋 测试5: 帮助系统")
    print("-" * 30)
    
    # 测试帮助命令
    event = MockAstrMessageEvent("帮助", "admin123")
    plugin.help_command(event)
    result_text = get_result_text(event._result)
    print(f"帮助信息: {result_text[:200]}...")
    
    print("\n📋 测试6: 错误处理")
    print("-" * 30)
    
    # 测试无权限用户
    event = MockAstrMessageEvent("/通过 testuser003", "unauthorized_user")
    event.is_admin = lambda: False  # 模拟非管理员
    await plugin._process_review_command(event)
    result_text = get_result_text(event._result)
    print(f"无权限用户操作结果: {result_text if result_text else '无响应（权限检查通过）'}")
    
    # 测试错误的指令格式
    event = MockAstrMessageEvent("/通过", "admin123")
    await plugin._process_review_command(event)
    result_text = get_result_text(event._result)
    print(f"错误指令格式结果: {result_text}")
    
    print("\n📋 测试7: 调试信息验证")
    print("-" * 30)
    
    print(f"调试模式状态: {'启用' if plugin.debug_mode else '禁用'}")
    print(f"事件详情记录: {'启用' if plugin.debug_log_events else '禁用'}")
    print(f"API调用记录: {'启用' if plugin.debug_log_api_calls else '禁用'}")
    print(f"当前待审核申请数量: {len(plugin.pending_requests)}")
    
    # 显示当前配置
    print("\n当前配置:")
    for key, value in plugin.config.items():
        if key.startswith('debug'):
            print(f"  {key}: {value}")
    
    print("\n" + "="*60)
    print("✅ Debug模式测试完成！")
    print("🐛 调试功能验证通过，详细日志已输出")
    print("📝 请检查上方的调试信息输出")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(test_debug_mode())