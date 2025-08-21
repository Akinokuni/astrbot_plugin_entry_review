#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试修复版入群申请审核插件 v2
专门测试针对 NapCatQQ issue #1076 的修复方案
"""

import asyncio
import json
from datetime import datetime
from main_v2_fixed import EntryReviewPlugin

class MockPlatformAdapter:
    """模拟平台适配器"""
    
    def __init__(self):
        self.sent_messages = []
        self.api_calls = []
        self.system_messages = [
            {
                'type': 1,
                'sub_type': 1,
                'group_id': 123456789,
                'user_id': 987654321,
                'comment': '我想加入这个群',
                'invitor_uin': 'invalid_flag_123',  # 模拟无效的flag
                'seq': 12345,
                'time': int(datetime.now().timestamp())
            }
        ]
        self.flag_success_map = {
            'invalid_flag_123': False,  # 模拟无效flag
            '987654321': True,          # 用户ID作为flag成功
            '123456789_987654321': False, # 组合格式失败
            '12345': False              # seq失败
        }
    
    async def send_group_msg(self, group_id, message):
        """模拟发送群消息"""
        self.sent_messages.append({
            'group_id': group_id,
            'message': message,
            'time': datetime.now().isoformat()
        })
        print(f"[MOCK] 发送消息到群 {group_id}: {message[:50]}...")
        return {'status': 'ok'}
    
    async def get_group_system_msg(self):
        """模拟获取群系统消息"""
        self.api_calls.append({
            'api': 'get_group_system_msg',
            'time': datetime.now().isoformat()
        })
        return {
            'status': 'ok',
            'data': self.system_messages
        }
    
    async def set_group_add_request(self, flag, approve, reason=""):
        """模拟处理入群申请"""
        self.api_calls.append({
            'api': 'set_group_add_request',
            'params': {'flag': flag, 'approve': approve, 'reason': reason},
            'time': datetime.now().isoformat()
        })
        
        # 模拟flag有效性检查
        is_valid = self.flag_success_map.get(flag, False)
        
        if is_valid:
            print(f"[MOCK] 成功处理申请 - flag: {flag}, approve: {approve}")
            return {'status': 'ok', 'data': {'result': 'success'}}
        else:
            print(f"[MOCK] 处理申请失败 - 无效flag: {flag}")
            raise Exception(f"Invalid flag: {flag}")

async def test_flag_handling():
    """测试flag处理功能"""
    print("\n=== 测试flag处理功能 ===")
    
    # 创建插件实例
    plugin = EntryReviewPlugin(None)
    plugin.config = {
        'target_groups': [123456789],
        'review_group': 111111111,
        'debug_mode': True,
        'admin_users': [888888888],
        'use_system_msg_polling': False,  # 禁用轮询以便测试
        'max_retry_count': 3
    }
    
    # 创建模拟适配器
    adapter = MockPlatformAdapter()
    plugin.platform_adapter = adapter
    
    # 测试数据 - 模拟从系统消息获取的申请
    request_data = {
        'group_id': 123456789,
        'user_id': 987654321,
        'comment': '我想加入这个群',
        'flag': 'invalid_flag_123',  # 无效的原始flag
        'invitor_uin': 'invalid_flag_123',
        'seq': 12345,
        'time': datetime.now().isoformat()
    }
    
    print(f"\n测试数据: {json.dumps(request_data, ensure_ascii=False, indent=2)}")
    
    # 测试通过申请（应该尝试多种flag格式）
    print("\n--- 测试通过申请 ---")
    success = await plugin._approve_request_v2(request_data)
    print(f"通过申请结果: {success}")
    
    # 检查API调用记录
    print("\nAPI调用记录:")
    for call in adapter.api_calls:
        print(f"  {call}")
    
    # 检查发送的消息
    print("\n发送的消息:")
    for msg in adapter.sent_messages:
        print(f"  群{msg['group_id']}: {msg['message'][:100]}...")
    
    return success

async def test_system_message_processing():
    """测试系统消息处理"""
    print("\n=== 测试系统消息处理 ===")
    
    # 创建插件实例
    plugin = EntryReviewPlugin(None)
    plugin.config = {
        'target_groups': [123456789],
        'review_group': 111111111,
        'debug_mode': True,
        'admin_users': [888888888],
        'use_system_msg_polling': False,
        'auto_approve_time': 0  # 禁用自动通过
    }
    
    # 创建模拟适配器
    adapter = MockPlatformAdapter()
    plugin.platform_adapter = adapter
    
    # 模拟系统消息
    system_msg = {
        'type': 1,
        'sub_type': 1,
        'group_id': 123456789,
        'user_id': 987654321,
        'comment': '我想加入这个群',
        'invitor_uin': 'invalid_flag_123',
        'seq': 12345
    }
    
    print(f"\n处理系统消息: {json.dumps(system_msg, ensure_ascii=False, indent=2)}")
    
    # 处理系统消息
    await plugin._process_system_message_request(system_msg)
    
    # 检查待处理申请
    print(f"\n待处理申请数量: {len(plugin.pending_requests)}")
    for request_id, request_info in plugin.pending_requests.items():
        print(f"  {request_id}: {request_info}")
    
    # 检查发送的消息
    print("\n发送的审核消息:")
    for msg in adapter.sent_messages:
        print(f"  {msg['message']}")
    
    return len(plugin.pending_requests) > 0

async def test_command_handling():
    """测试指令处理"""
    print("\n=== 测试指令处理 ===")
    
    # 创建插件实例
    plugin = EntryReviewPlugin(None)
    plugin.config = {
        'target_groups': [123456789],
        'review_group': 111111111,
        'debug_mode': True,
        'admin_users': [888888888]
    }
    
    # 创建模拟适配器
    adapter = MockPlatformAdapter()
    plugin.platform_adapter = adapter
    
    # 添加一个待处理申请
    request_id = "test_request_123"
    plugin.pending_requests[request_id] = {
        'group_id': 123456789,
        'user_id': 987654321,
        'comment': '测试申请',
        'flag': 'invalid_flag_123',
        'invitor_uin': 'invalid_flag_123',
        'seq': 12345,
        'user_id': 987654321  # 这个会作为有效flag
    }
    
    print(f"\n添加测试申请: {request_id}")
    
    # 模拟审核群消息事件
    approve_event = {
        'raw_message': {
            'message_type': 'group',
            'group_id': 111111111,  # 审核群
            'user_id': 888888888,   # 管理员
            'message': f'/approve {request_id}'
        }
    }
    
    print(f"\n处理通过指令: /approve {request_id}")
    await plugin.handle_group_message_events(approve_event)
    
    # 检查申请是否被处理
    print(f"\n申请处理后，待处理申请数量: {len(plugin.pending_requests)}")
    
    # 检查API调用
    print("\nAPI调用记录:")
    for call in adapter.api_calls:
        if call['api'] == 'set_group_add_request':
            print(f"  {call}")
    
    return len(plugin.pending_requests) == 0

async def test_multiple_flag_formats():
    """测试多种flag格式"""
    print("\n=== 测试多种flag格式 ===")
    
    # 创建插件实例
    plugin = EntryReviewPlugin(None)
    plugin.config = {'debug_mode': True}
    
    # 创建模拟适配器
    adapter = MockPlatformAdapter()
    plugin.platform_adapter = adapter
    
    # 测试数据
    request_data = {
        'group_id': 123456789,
        'user_id': 987654321,
        'flag': 'invalid_flag_123',
        'invitor_uin': 'invalid_flag_123',
        'seq': 12345
    }
    
    print(f"\n测试数据: {json.dumps(request_data, ensure_ascii=False)}")
    print("\n尝试多种flag格式...")
    
    # 调用多flag格式处理
    success = await plugin._try_multiple_flag_formats(request_data, True, "测试通过")
    
    print(f"\n多flag格式处理结果: {success}")
    
    # 显示尝试的所有API调用
    print("\n尝试的API调用:")
    for call in adapter.api_calls:
        if call['api'] == 'set_group_add_request':
            params = call['params']
            flag = params['flag']
            is_valid = adapter.flag_success_map.get(flag, False)
            print(f"  flag: {flag} -> {'成功' if is_valid else '失败'}")
    
    return success

async def main():
    """主测试函数"""
    print("开始测试修复版入群申请审核插件 v2")
    print("专门针对 NapCatQQ issue #1076: 处理入群申请时无法获取有效flag")
    print("=" * 60)
    
    test_results = []
    
    # 测试1: flag处理功能
    try:
        result1 = await test_flag_handling()
        test_results.append(("flag处理功能", result1))
    except Exception as e:
        print(f"测试1失败: {e}")
        test_results.append(("flag处理功能", False))
    
    # 测试2: 系统消息处理
    try:
        result2 = await test_system_message_processing()
        test_results.append(("系统消息处理", result2))
    except Exception as e:
        print(f"测试2失败: {e}")
        test_results.append(("系统消息处理", False))
    
    # 测试3: 指令处理
    try:
        result3 = await test_command_handling()
        test_results.append(("指令处理", result3))
    except Exception as e:
        print(f"测试3失败: {e}")
        test_results.append(("指令处理", False))
    
    # 测试4: 多种flag格式
    try:
        result4 = await test_multiple_flag_formats()
        test_results.append(("多种flag格式", result4))
    except Exception as e:
        print(f"测试4失败: {e}")
        test_results.append(("多种flag格式", False))
    
    # 输出测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print("=" * 60)
    
    all_passed = True
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！修复版插件功能正常")
        print("\n主要修复内容:")
        print("1. ✅ 实现多种flag格式尝试机制")
        print("2. ✅ 增加系统消息轮询功能")
        print("3. ✅ 改进错误处理和重试机制")
        print("4. ✅ 增强调试功能和日志记录")
        print("\n这个版本应该能够解决 NapCatQQ issue #1076 中描述的flag无效问题")
    else:
        print("❌ 部分测试失败，需要进一步调试")
    
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())