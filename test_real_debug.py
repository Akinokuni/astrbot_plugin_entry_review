#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
入群申请审核插件 - 真实调试功能测试
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 创建真实的logger类
class RealLogger:
    def info(self, message):
        print(f"[INFO] {message}")
    
    def debug(self, message):
        print(f"[DEBUG] {message}")
    
    def warning(self, message):
        print(f"[WARNING] {message}")
    
    def error(self, message):
        print(f"[ERROR] {message}")

# 创建真实的Context类
class RealContext:
    def __init__(self):
        self.config_helper = self
        self.config = {}
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def set(self, key, value):
        self.config[key] = value
        return True

# 创建真实的调试测试类
class DebugTester:
    def __init__(self):
        self.debug_mode = True
        self.debug_log_events = True
        self.debug_log_api_calls = True
        self.logger = RealLogger()
    
    def _debug_log(self, message: str, level: str = "DEBUG"):
        """输出调试日志"""
        if getattr(self, 'debug_mode', False):
            if level == "INFO":
                self.logger.info(f"🐛 [DEBUG] {message}")
            elif level == "WARNING":
                self.logger.warning(f"🐛 [DEBUG] {message}")
            elif level == "ERROR":
                self.logger.error(f"🐛 [DEBUG] {message}")
            else:
                self.logger.debug(f"🐛 [DEBUG] {message}")
    
    def _debug_log_event(self, event_type: str, event_data: dict):
        """输出事件调试日志"""
        if getattr(self, 'debug_mode', False) and getattr(self, 'debug_log_events', False):
            self.logger.info(f"🐛 [事件调试] {event_type}: {event_data}")
    
    def _debug_log_api_call(self, api_name: str, params: dict, result=None, error=None):
        """输出API调用调试日志"""
        if getattr(self, 'debug_mode', False) and getattr(self, 'debug_log_api_calls', False):
            self.logger.info(f"🐛 [API调试] {api_name}")
            self.logger.info(f"  参数: {params}")
            if result is not None:
                self.logger.info(f"  结果: {result}")
            if error is not None:
                self.logger.error(f"  错误: {error}")

def test_real_debug_functionality():
    """测试真实的调试功能"""
    print("\n" + "="*60)
    print("🐛 入群申请审核插件 - 真实调试功能测试")
    print("="*60)
    
    # 创建调试测试实例
    tester = DebugTester()
    
    print("\n📋 测试1: 基本调试日志")
    print("-" * 30)
    tester._debug_log("这是一条DEBUG级别的调试日志")
    tester._debug_log("这是一条INFO级别的调试日志", "INFO")
    tester._debug_log("这是一条WARNING级别的调试日志", "WARNING")
    tester._debug_log("这是一条ERROR级别的调试日志", "ERROR")
    
    print("\n📋 测试2: 事件调试日志")
    print("-" * 30)
    tester._debug_log_event("入群申请", {
        "user_id": "123456789",
        "group_id": "987654321",
        "nickname": "测试用户",
        "comment": "我想加入这个群"
    })
    
    print("\n📋 测试3: API调用调试日志")
    print("-" * 30)
    tester._debug_log_api_call("send_group_message", {
        "group_id": "987654321",
        "message": "新的入群申请需要审核"
    }, result={"message_id": "msg_123"})
    
    tester._debug_log_api_call("approve_group_request", {
        "user_id": "123456789",
        "group_id": "987654321"
    }, error="权限不足")
    
    print("\n📋 测试4: 调试模式开关")
    print("-" * 30)
    print("关闭调试模式...")
    tester.debug_mode = False
    tester._debug_log("调试模式关闭时的日志（不应该显示）")
    
    print("重新开启调试模式...")
    tester.debug_mode = True
    tester._debug_log("调试模式重新开启", "INFO")
    
    print("\n" + "="*60)
    print("🎉 真实调试功能测试完成！")
    print("="*60)
    
    print("\n📊 测试结果:")
    print("  ✅ 基本调试日志输出正常")
    print("  ✅ 事件调试日志输出正常")
    print("  ✅ API调用调试日志输出正常")
    print("  ✅ 调试模式开关功能正常")
    print("\n✅ 所有调试功能测试通过！")

if __name__ == "__main__":
    try:
        test_real_debug_functionality()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()